"""
BASIC Tree-walk Interpreter.

Execution model
---------------
* The program is stored as an ordered list of Line objects.
* A program counter (PC) indexes into that list.
* GOTO / GOSUB / NEXT alter the PC directly.
* Variables live in a flat dict.  String var names end in '$'.
* Arrays are stored as {name: list}.
* A GOSUB stack tracks return addresses.
* FOR loops push a LoopFrame onto a loop stack.
* DATA values are collected at load time; READ walks a pointer through them.
"""

from __future__ import annotations

import asyncio
import datetime
import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .parser import (
    Parser, ParseError,
    Line,
    NumberNode, StringNode, VarNode, ArrayAccessNode, FuncCallNode,
    BinOpNode, UnaryOpNode,
    RemStmt, PrintStmt, LetStmt, InputStmt, IfStmt,
    GotoStmt, GosubStmt, ReturnStmt,
    ForStmt, NextStmt,
    EndStmt, StopStmt,
    DimStmt, DataStmt, ReadStmt, RestoreStmt,
    WhileStmt, WendStmt, RandomizeStmt,
    OnGotoStmt, OnGosubStmt, DefFnStmt,
    ScreenStmt, ClsStmt, PsetStmt, LineStmt, CircleStmt, PaintStmt,
    GetStmt, PutStmt, ColorStmt, PaletteStmt, BeepStmt, SoundStmt,
    PlayStmt, SleepStmt, DoStmt, LoopStmt,
)
from .lexer import TT
from .renderer import Renderer


# ---------------------------------------------------------------------------
# Helpers / sentinel exceptions
# ---------------------------------------------------------------------------

class BasicError(Exception):
    """Runtime error with optional BASIC line number."""
    def __init__(self, msg: str, lineno: int = 0):
        self.lineno = lineno
        super().__init__(msg)

    def __str__(self):
        prefix = f'Error at line {self.lineno}: ' if self.lineno else 'Error: '
        return prefix + super().__str__()


class _EndSignal(Exception):
    """Raised by END / STOP to exit the run loop cleanly."""


class _GotoSignal(Exception):
    def __init__(self, lineno: int):
        self.lineno = lineno


class _GosubSignal(Exception):
    def __init__(self, lineno: int):
        self.lineno = lineno


class _ReturnSignal(Exception):
    pass


class _PcJumpSignal(Exception):
    """Used by DO/LOOP to jump to a specific PC index directly."""
    def __init__(self, pc: int):
        self.pc = pc


class _SleepSignal(Exception):
    """Raised by SLEEP so async loop can await instead of blocking."""
    def __init__(self, seconds: float):
        self.seconds = seconds


@dataclass
class _ForFrame:
    var:     str
    end:     float
    step:    float
    loop_pc: int   # PC of the FOR line (we jump back here on NEXT)


@dataclass
class _WhileFrame:
    condition: object   # AST node, re-evaluated on each WEND
    loop_pc:   int      # PC of the WHILE line


@dataclass
class _DoFrame:
    do_pc:              int    # PC of the DO line
    condition_type:     str    # 'WHILE', 'UNTIL', or None
    condition:          object # AST node or None


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

class Interpreter:
    def __init__(self, interactive: bool = False, renderer=None):
        self._interactive = interactive
        self._renderer    = renderer if renderer is not None else Renderer()
        self._parser      = Parser()
        self._reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, source: str):
        """Parse and load a program from source text."""
        self._reset()
        try:
            lines = self._parser.parse_program(source)
        except ParseError as e:
            raise BasicError(str(e)) from e
        self._lines   = lines
        self._line_map = {l.lineno: i for i, l in enumerate(lines)}
        self._collect_data()

    def run(self):
        """Execute the loaded program from the first line."""
        if not self._lines:
            return
        self._pc = 0
        self._run_loop()

    async def run_async(self):
        """Execute asynchronously, yielding to the JS event loop each line.

        Use this from Pyodide/browser to allow canvas repaints between frames.
        """
        if not self._lines:
            return
        self._pc = 0
        await self._run_loop_async()

    async def _run_loop_async(self):
        step = 0
        while 0 <= self._pc < len(self._lines):
            line = self._lines[self._pc]
            try:
                self._exec_line(line)
                self._pc += 1
            except _GotoSignal as g:
                self._pc = self._resolve_lineno(g.lineno, line.lineno)
            except _GosubSignal as gs:
                self._gosub_stack.append(self._pc + 1)
                self._pc = self._resolve_lineno(gs.lineno, line.lineno)
            except _ReturnSignal:
                if not self._gosub_stack:
                    raise BasicError('RETURN without GOSUB', line.lineno)
                self._pc = self._gosub_stack.pop()
            except _PcJumpSignal as j:
                self._pc = j.pc
            except _SleepSignal as s:          # A-3: SLEEP (including SLEEP 0)
                self._pc += 1
                self._renderer.flush()          # B-3: flush draw batch before yield
                await asyncio.sleep(s.seconds)
                step = 0
                continue
            except _EndSignal:
                self._renderer.flush()
                return
            except BasicError:
                raise

            step += 1
            if step >= 500:                     # A-2: fallback yield every 500 lines
                self._renderer.flush()
                await asyncio.sleep(0)
                step = 0
        self._renderer.flush()

    def run_line(self, raw: str):
        """Execute a single line (REPL mode). Line number 0 = immediate."""
        try:
            line = self._parser.parse_line(raw)
        except ParseError as e:
            print(f'Parse error: {e}')
            return
        if line is None:
            return
        if line.lineno == 0:
            # Immediate mode: execute all statements
            try:
                for stmt in line.stmts:
                    self._exec_stmt(stmt, lineno=0)
            except _EndSignal:
                pass
            except BasicError as e:
                print(e)
        else:
            # Numbered line: add/replace in program
            self._add_line(line)

    def list_program(self):
        """Print the stored program (REPL LIST command)."""
        for line in self._lines:
            print(self._decompile_line(line))

    # ------------------------------------------------------------------
    # Internal reset
    # ------------------------------------------------------------------

    def _reset(self):
        self._lines:       list[Line]        = []
        self._line_map:    dict[int, int]    = {}
        self._vars:        dict[str, Any]    = {}
        self._arrays:      dict[str, list]   = {}
        self._gosub_stack: list[int]         = []  # stack of return PCs
        self._for_stack:   list[_ForFrame]   = []
        self._while_stack: list[_WhileFrame] = []
        self._do_stack:    list[_DoFrame]    = []
        self._user_funcs:  dict[str, tuple]  = {}  # name -> (param, body_node)
        self._data:        list[Any]         = []
        self._data_ptr:    int               = 0
        self._pc:          int               = 0

    # ------------------------------------------------------------------
    # DATA collection
    # ------------------------------------------------------------------

    def _collect_data(self):
        self._data = []
        for line in self._lines:
            for stmt in line.stmts:
                if isinstance(stmt, DataStmt):
                    self._data.extend(stmt.values)
        self._data_ptr = 0

    # ------------------------------------------------------------------
    # Program manipulation (REPL)
    # ------------------------------------------------------------------

    def _add_line(self, line: Line):
        if line.lineno in self._line_map:
            idx = self._line_map[line.lineno]
            self._lines[idx] = line
        else:
            self._lines.append(line)
            self._lines.sort(key=lambda l: l.lineno)
        # Rebuild map
        self._line_map = {l.lineno: i for i, l in enumerate(self._lines)}
        self._collect_data()

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        while 0 <= self._pc < len(self._lines):
            line = self._lines[self._pc]
            try:
                self._exec_line(line)
                # Normal advance only if _exec_line didn't change PC
                self._pc += 1
            except _GotoSignal as g:
                self._pc = self._resolve_lineno(g.lineno, line.lineno)
            except _GosubSignal as gs:
                self._gosub_stack.append(self._pc + 1)
                self._pc = self._resolve_lineno(gs.lineno, line.lineno)
            except _ReturnSignal:
                if not self._gosub_stack:
                    raise BasicError('RETURN without GOSUB', line.lineno)
                self._pc = self._gosub_stack.pop()
            except _PcJumpSignal as j:
                self._pc = j.pc
            except _SleepSignal as s:
                self._renderer.sleep(s.seconds)
                self._pc += 1
            except _EndSignal:
                return
            except BasicError:
                raise

    def _exec_line(self, line: Line):
        for stmt in line.stmts:
            self._exec_stmt(stmt, lineno=line.lineno)

    def _exec_stmt(self, stmt: Any, lineno: int = 0):
        try:
            self._dispatch(stmt, lineno)
        except (_EndSignal, _GotoSignal, _GosubSignal, _ReturnSignal, _PcJumpSignal, _SleepSignal):
            raise
        except BasicError:
            raise
        except Exception as e:
            raise BasicError(str(e), lineno) from e

    def _dispatch(self, stmt: Any, lineno: int):
        if isinstance(stmt, RemStmt):
            return

        if isinstance(stmt, PrintStmt):
            self._exec_print(stmt, lineno)
            return

        if isinstance(stmt, LetStmt):
            value = self._eval(stmt.value, lineno)
            self._assign(stmt.target, value, lineno)
            return

        if isinstance(stmt, InputStmt):
            self._exec_input(stmt, lineno)
            return

        if isinstance(stmt, IfStmt):
            cond = self._eval(stmt.condition, lineno)
            if self._truthy(cond):
                self._exec_stmt(stmt.then_stmt, lineno)
            elif stmt.else_stmt is not None:
                self._exec_stmt(stmt.else_stmt, lineno)
            return

        if isinstance(stmt, GotoStmt):
            raise _GotoSignal(stmt.lineno)

        if isinstance(stmt, GosubStmt):
            raise _GosubSignal(stmt.lineno)

        if isinstance(stmt, ReturnStmt):
            raise _ReturnSignal()

        if isinstance(stmt, ForStmt):
            self._exec_for(stmt, lineno)
            return

        if isinstance(stmt, NextStmt):
            self._exec_next(stmt, lineno)
            return

        if isinstance(stmt, EndStmt):
            raise _EndSignal()

        if isinstance(stmt, StopStmt):
            if self._interactive:
                print('STOP')
            raise _EndSignal()

        if isinstance(stmt, DimStmt):
            size = int(self._eval(stmt.size, lineno))
            # BASIC arrays are 1-based; allocate size+1 elements
            self._arrays[stmt.name] = [0] * (size + 1)
            return

        if isinstance(stmt, DataStmt):
            return  # already collected

        if isinstance(stmt, ReadStmt):
            for var in stmt.vars:
                if self._data_ptr >= len(self._data):
                    raise BasicError('Out of DATA', lineno)
                value = self._data[self._data_ptr]
                self._data_ptr += 1
                self._assign(var, value, lineno)
            return

        if isinstance(stmt, RestoreStmt):
            self._data_ptr = 0
            return

        if isinstance(stmt, WhileStmt):
            self._exec_while(stmt, lineno)
            return

        if isinstance(stmt, WendStmt):
            self._exec_wend(lineno)
            return

        if isinstance(stmt, RandomizeStmt):
            if stmt.seed is None:
                random.seed(int(time.time()))
            else:
                seed_val = self._num(self._eval(stmt.seed, lineno), lineno)
                random.seed(int(seed_val))
            return

        if isinstance(stmt, OnGotoStmt):
            idx = int(self._num(self._eval(stmt.expr, lineno), lineno))
            if 1 <= idx <= len(stmt.targets):
                raise _GotoSignal(stmt.targets[idx - 1])
            return

        if isinstance(stmt, OnGosubStmt):
            idx = int(self._num(self._eval(stmt.expr, lineno), lineno))
            if 1 <= idx <= len(stmt.targets):
                raise _GosubSignal(stmt.targets[idx - 1])
            return

        if isinstance(stmt, DefFnStmt):
            self._user_funcs[stmt.name] = (stmt.param, stmt.body)
            return

        if isinstance(stmt, ScreenStmt):
            mode = int(self._num(self._eval(stmt.mode, lineno), lineno))
            self._renderer.screen(mode)
            return

        if isinstance(stmt, ClsStmt):
            self._renderer.cls()
            return

        if isinstance(stmt, PsetStmt):
            x = int(self._num(self._eval(stmt.x, lineno), lineno))
            y = int(self._num(self._eval(stmt.y, lineno), lineno))
            color = int(self._num(self._eval(stmt.color, lineno), lineno)) if stmt.color is not None else 7
            self._renderer.pset(x, y, color)
            return

        if isinstance(stmt, LineStmt):
            x1 = int(self._num(self._eval(stmt.x1, lineno), lineno))
            y1 = int(self._num(self._eval(stmt.y1, lineno), lineno))
            x2 = int(self._num(self._eval(stmt.x2, lineno), lineno))
            y2 = int(self._num(self._eval(stmt.y2, lineno), lineno))
            color = int(self._num(self._eval(stmt.color, lineno), lineno)) if stmt.color is not None else 7
            self._renderer.line(x1, y1, x2, y2, color, stmt.mode)
            return

        if isinstance(stmt, CircleStmt):
            x = int(self._num(self._eval(stmt.x, lineno), lineno))
            y = int(self._num(self._eval(stmt.y, lineno), lineno))
            r = int(self._num(self._eval(stmt.r, lineno), lineno))
            color = int(self._num(self._eval(stmt.color, lineno), lineno)) if stmt.color is not None else 7
            start  = float(self._num(self._eval(stmt.start,  lineno), lineno)) if stmt.start  is not None else None
            end    = float(self._num(self._eval(stmt.end,    lineno), lineno)) if stmt.end    is not None else None
            aspect = float(self._num(self._eval(stmt.aspect, lineno), lineno)) if stmt.aspect is not None else None
            self._renderer.circle(x, y, r, color, start, end, aspect)
            return

        if isinstance(stmt, PaintStmt):
            x = int(self._num(self._eval(stmt.x, lineno), lineno))
            y = int(self._num(self._eval(stmt.y, lineno), lineno))
            color  = int(self._num(self._eval(stmt.color,  lineno), lineno)) if stmt.color  is not None else 7
            border = int(self._num(self._eval(stmt.border, lineno), lineno)) if stmt.border is not None else None
            self._renderer.paint(x, y, color, border)
            return

        if isinstance(stmt, GetStmt):
            x1 = int(self._num(self._eval(stmt.x1, lineno), lineno))
            y1 = int(self._num(self._eval(stmt.y1, lineno), lineno))
            x2 = int(self._num(self._eval(stmt.x2, lineno), lineno))
            y2 = int(self._num(self._eval(stmt.y2, lineno), lineno))
            data = self._renderer.get_region(x1, y1, x2, y2)
            self._arrays[stmt.array_name] = data
            return

        if isinstance(stmt, PutStmt):
            x = int(self._num(self._eval(stmt.x, lineno), lineno))
            y = int(self._num(self._eval(stmt.y, lineno), lineno))
            data = self._get_array(stmt.array_name, lineno)
            self._renderer.put_region(x, y, data, stmt.mode)
            return

        if isinstance(stmt, ColorStmt):
            fg = int(self._num(self._eval(stmt.fg, lineno), lineno)) if stmt.fg is not None else None
            bg = int(self._num(self._eval(stmt.bg, lineno), lineno)) if stmt.bg is not None else None
            self._renderer.color(fg, bg)
            return

        if isinstance(stmt, PaletteStmt):
            attr      = int(self._num(self._eval(stmt.attr,      lineno), lineno))
            color_val = int(self._num(self._eval(stmt.color_val, lineno), lineno))
            self._renderer.palette(attr, color_val)
            return

        if isinstance(stmt, BeepStmt):
            self._renderer.beep()
            return

        if isinstance(stmt, SoundStmt):
            freq     = float(self._num(self._eval(stmt.freq,     lineno), lineno))
            duration = float(self._num(self._eval(stmt.duration, lineno), lineno))
            self._renderer.sound(freq, duration)
            return

        if isinstance(stmt, PlayStmt):
            music = str(self._eval(stmt.music, lineno))
            self._renderer.play(music)
            return

        if isinstance(stmt, SleepStmt):
            secs = float(self._num(self._eval(stmt.duration, lineno), lineno))
            raise _SleepSignal(secs)

        if isinstance(stmt, DoStmt):
            self._exec_do(stmt, lineno)
            return

        if isinstance(stmt, LoopStmt):
            self._exec_loop(stmt, lineno)
            return

        raise BasicError(f'Unknown statement type {type(stmt).__name__}', lineno)

    # ------------------------------------------------------------------
    # PRINT
    # ------------------------------------------------------------------

    def _exec_print(self, stmt: PrintStmt, lineno: int):
        output_parts = []
        suppress_newline = False

        items = stmt.items
        for i, item in enumerate(items):
            kind, val = item
            if kind == 'sep':
                if val == TT.SEMICOLON:
                    suppress_newline = True
                    # no space added
                elif val == TT.COMMA:
                    # advance to next 14-char tab stop
                    col = sum(len(p) for p in output_parts)
                    spaces = 14 - (col % 14)
                    output_parts.append(' ' * spaces)
                    suppress_newline = True
            else:
                suppress_newline = False
                value = self._eval(val, lineno)
                if isinstance(value, float):
                    # Avoid trailing .0 for whole numbers
                    if value == int(value) and not math.isinf(value):
                        output_parts.append(str(int(value)))
                    else:
                        output_parts.append(str(value))
                elif isinstance(value, int):
                    output_parts.append(str(value))
                else:
                    output_parts.append(str(value))

        text = ''.join(output_parts)
        if suppress_newline:
            print(text, end='', flush=True)
        else:
            print(text)

    # ------------------------------------------------------------------
    # INPUT
    # ------------------------------------------------------------------

    def _exec_input(self, stmt: InputStmt, lineno: int):
        prompt = stmt.prompt if stmt.prompt is not None else '? '
        if not prompt.endswith(' ') and not prompt.endswith('?'):
            prompt += ' '
        try:
            raw = input(prompt)
        except EOFError:
            raw = ''
        # Determine type from variable name
        name = stmt.var.name if isinstance(stmt.var, (VarNode, ArrayAccessNode)) else ''
        if name.endswith('$'):
            value = raw
        else:
            try:
                value = float(raw)
                if value == int(value):
                    value = int(value)
            except ValueError:
                print('?Redo from start')
                self._exec_input(stmt, lineno)
                return
        self._assign(stmt.var, value, lineno)

    # ------------------------------------------------------------------
    # FOR / NEXT
    # ------------------------------------------------------------------

    def _exec_for(self, stmt: ForStmt, lineno: int):
        start = self._num(self._eval(stmt.start, lineno), lineno)
        end   = self._num(self._eval(stmt.end,   lineno), lineno)
        step  = self._num(self._eval(stmt.step,  lineno), lineno) if stmt.step else 1

        if step == 0:
            raise BasicError('FOR step cannot be zero', lineno)

        self._vars[stmt.var] = start

        # Remove any existing frame for this var
        self._for_stack = [f for f in self._for_stack if f.var != stmt.var]

        frame = _ForFrame(
            var     = stmt.var,
            end     = end,
            step    = step,
            loop_pc = self._pc,   # will be used by NEXT
        )
        self._for_stack.append(frame)

        # Check if loop body should execute at all
        if (step > 0 and start > end) or (step < 0 and start < end):
            # Skip to matching NEXT
            self._skip_to_next(stmt.var, lineno)

    def _skip_to_next(self, var: str, lineno: int):
        """Advance PC past the matching NEXT statement."""
        depth = 0
        search_pc = self._pc + 1
        while search_pc < len(self._lines):
            for stmt in self._lines[search_pc].stmts:
                if isinstance(stmt, ForStmt):
                    depth += 1
                elif isinstance(stmt, NextStmt):
                    if depth == 0:
                        if stmt.var is None or stmt.var == var:
                            self._pc = search_pc
                            # Remove the frame since we're skipping
                            self._for_stack = [
                                f for f in self._for_stack if f.var != var
                            ]
                            return
                        else:
                            depth -= 1
                    else:
                        depth -= 1
            search_pc += 1
        raise BasicError(f'FOR without matching NEXT for {var}', lineno)

    def _exec_next(self, stmt: NextStmt, lineno: int):
        # Find the matching frame
        if not self._for_stack:
            raise BasicError('NEXT without FOR', lineno)

        if stmt.var:
            # Find frame with matching variable
            frame = None
            for f in reversed(self._for_stack):
                if f.var == stmt.var:
                    frame = f
                    break
            if frame is None:
                raise BasicError(f'NEXT {stmt.var} without FOR', lineno)
        else:
            frame = self._for_stack[-1]

        # Increment
        current = self._num(self._vars.get(frame.var, 0), lineno)
        current += frame.step
        self._vars[frame.var] = current

        # Check loop condition
        continue_loop = (
            (frame.step > 0 and current <= frame.end) or
            (frame.step < 0 and current >= frame.end)
        )
        if continue_loop:
            # Jump back to the line AFTER the FOR statement (loop body start)
            self._pc = frame.loop_pc  # _run_loop will do +1, landing on body
        else:
            # Loop finished: pop the frame
            self._for_stack = [f for f in self._for_stack if f is not frame]

    # ------------------------------------------------------------------
    # WHILE / WEND
    # ------------------------------------------------------------------

    def _exec_while(self, stmt: WhileStmt, lineno: int):
        cond = self._eval(stmt.condition, lineno)
        if self._truthy(cond):
            # Push a frame only on first entry (not on re-entry from WEND)
            if not self._while_stack or self._while_stack[-1].loop_pc != self._pc:
                self._while_stack.append(_WhileFrame(stmt.condition, self._pc))
        else:
            # Remove stale frame for this PC if present
            if self._while_stack and self._while_stack[-1].loop_pc == self._pc:
                self._while_stack.pop()
            self._skip_to_wend(lineno)

    def _exec_wend(self, lineno: int):
        if not self._while_stack:
            raise BasicError('WEND without WHILE', lineno)
        frame = self._while_stack[-1]
        cond = self._eval(frame.condition, lineno)
        if self._truthy(cond):
            # Jump back to body (loop_pc + 1); set to loop_pc so +1 lands there
            self._pc = frame.loop_pc
        else:
            self._while_stack.pop()
            # Fall through: run_loop does +1, advancing past WEND

    def _skip_to_wend(self, lineno: int):
        """Advance PC to the matching WEND, accounting for nesting."""
        depth = 0
        search_pc = self._pc + 1
        while search_pc < len(self._lines):
            for stmt in self._lines[search_pc].stmts:
                if isinstance(stmt, WhileStmt):
                    depth += 1
                elif isinstance(stmt, WendStmt):
                    if depth == 0:
                        self._pc = search_pc
                        return
                    depth -= 1
            search_pc += 1
        raise BasicError('WHILE without matching WEND', lineno)

    # ------------------------------------------------------------------
    # DO / LOOP
    # ------------------------------------------------------------------

    def _exec_do(self, stmt: DoStmt, lineno: int):
        if stmt.condition_type is not None:
            cond = self._eval(stmt.condition, lineno)
            passes = self._truthy(cond) if stmt.condition_type == 'WHILE' else not self._truthy(cond)
            if not passes:
                # Condition fails on entry — pop any stale frame and skip to LOOP
                if self._do_stack and self._do_stack[-1].do_pc == self._pc:
                    self._do_stack.pop()
                self._skip_to_loop(lineno)
                return
        # Push frame only on first entry
        if not self._do_stack or self._do_stack[-1].do_pc != self._pc:
            self._do_stack.append(_DoFrame(self._pc, stmt.condition_type, stmt.condition))

    def _exec_loop(self, stmt: LoopStmt, lineno: int):
        if not self._do_stack:
            raise BasicError('LOOP without DO', lineno)
        frame = self._do_stack[-1]

        if stmt.condition_type is not None:
            cond = self._eval(stmt.condition, lineno)
            cont = self._truthy(cond) if stmt.condition_type == 'WHILE' else not self._truthy(cond)
            if cont:
                raise _PcJumpSignal(frame.do_pc + 1)  # jump to body
            else:
                self._do_stack.pop()  # exit loop, fall through
        else:
            # No LOOP condition: jump back to DO (re-evaluates DO condition if any)
            if frame.condition_type is not None:
                raise _PcJumpSignal(frame.do_pc)  # re-execute DO line
            else:
                raise _PcJumpSignal(frame.do_pc + 1)  # jump straight to body (infinite)

    def _skip_to_loop(self, lineno: int):
        """Advance PC to the matching LOOP, accounting for nesting."""
        depth = 0
        search_pc = self._pc + 1
        while search_pc < len(self._lines):
            for stmt in self._lines[search_pc].stmts:
                if isinstance(stmt, DoStmt):
                    depth += 1
                elif isinstance(stmt, LoopStmt):
                    if depth == 0:
                        self._pc = search_pc
                        return
                    depth -= 1
            search_pc += 1
        raise BasicError('DO without matching LOOP', lineno)

    # ------------------------------------------------------------------
    # Variable access / assignment
    # ------------------------------------------------------------------

    def _assign(self, target: Any, value: Any, lineno: int):
        if isinstance(target, VarNode):
            name = target.name
            if name.endswith('$'):
                self._vars[name] = str(value)
            else:
                self._vars[name] = self._coerce_num(value, lineno)
        elif isinstance(target, ArrayAccessNode):
            idx = int(self._eval(target.index, lineno))
            arr = self._get_array(target.name, lineno)
            if idx < 0 or idx >= len(arr):
                raise BasicError(
                    f'Array index {idx} out of bounds for {target.name}', lineno
                )
            if target.name.endswith('$'):
                arr[idx] = str(value)
            else:
                arr[idx] = self._coerce_num(value, lineno)
        else:
            raise BasicError(f'Cannot assign to {target}', lineno)

    def _get_array(self, name: str, lineno: int) -> list:
        if name not in self._arrays:
            # Auto-dimension to 10 (BASIC default)
            self._arrays[name] = [0] * 11
        return self._arrays[name]

    def _get_var(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]
        # Default values
        if name.endswith('$'):
            return ''
        return 0

    # ------------------------------------------------------------------
    # Expression evaluator
    # ------------------------------------------------------------------

    def _eval(self, node: Any, lineno: int) -> Any:
        # D-1: O(1) dispatch table — avoids 7-level isinstance chain
        try:
            return self._EVAL_DISPATCH[type(node)](self, node, lineno)
        except KeyError:
            raise BasicError(f'Unknown node type {type(node).__name__}', lineno)

    def _eval_array_access(self, node: Any, lineno: int) -> Any:
        arr = self._get_array(node.name, lineno)
        idx = int(self._eval(node.index, lineno))
        if idx < 0 or idx >= len(arr):
            raise BasicError(
                f'Array index {idx} out of bounds for {node.name}', lineno
            )
        return arr[idx]

    def _eval_unary_op(self, node: Any, lineno: int) -> Any:
        operand = self._eval(node.operand, lineno)
        if node.op == TT.MINUS:
            return -self._num(operand, lineno)
        if node.op == TT.NOT:
            return 0 if self._truthy(operand) else -1
        raise BasicError(f'Unknown unary op {node.op}', lineno)

    def _eval_binop(self, node: BinOpNode, lineno: int) -> Any:
        op = node.op

        # Short-circuit logic
        if op == TT.AND:
            left = self._eval(node.left, lineno)
            if not self._truthy(left):
                return 0
            right = self._eval(node.right, lineno)
            return -1 if self._truthy(right) else 0

        if op == TT.OR:
            left = self._eval(node.left, lineno)
            if self._truthy(left):
                return -1
            right = self._eval(node.right, lineno)
            return -1 if self._truthy(right) else 0

        left  = self._eval(node.left,  lineno)
        right = self._eval(node.right, lineno)

        # String concatenation
        if op == TT.PLUS and (isinstance(left, str) or isinstance(right, str)):
            return str(left) + str(right)

        # Arithmetic ops
        if op == TT.PLUS:
            return self._num(left, lineno) + self._num(right, lineno)
        if op == TT.MINUS:
            return self._num(left, lineno) - self._num(right, lineno)
        if op == TT.STAR:
            return self._num(left, lineno) * self._num(right, lineno)
        if op == TT.SLASH:
            r = self._num(right, lineno)
            if r == 0:
                raise BasicError('Division by zero', lineno)
            result = self._num(left, lineno) / r
            # Return int if whole number
            if result == int(result):
                return int(result)
            return result
        if op == TT.CARET:
            return self._num(left, lineno) ** self._num(right, lineno)
        if op == TT.MOD:
            r = self._num(right, lineno)
            if r == 0:
                raise BasicError('MOD by zero', lineno)
            return int(self._num(left, lineno)) % int(r)

        # Comparisons – work on both numbers and strings
        if op == TT.EQ:
            return -1 if left == right else 0
        if op == TT.NEQ:
            return -1 if left != right else 0
        if op == TT.LT:
            return -1 if left < right else 0
        if op == TT.GT:
            return -1 if left > right else 0
        if op == TT.LTE:
            return -1 if left <= right else 0
        if op == TT.GTE:
            return -1 if left >= right else 0

        raise BasicError(f'Unknown binary op {op}', lineno)

    # ------------------------------------------------------------------
    # Built-in functions
    # ------------------------------------------------------------------

    def _call_func(self, name: str, args: list, lineno: int) -> Any:
        evaled = [self._eval(a, lineno) for a in args]

        def num(i=0):
            return self._num(evaled[i], lineno)

        def s(i=0):
            v = evaled[i]
            if not isinstance(v, str):
                raise BasicError(f'{name}: expected string argument', lineno)
            return v

        def require(n: int):
            if len(evaled) != n:
                raise BasicError(
                    f'{name} requires {n} argument(s), got {len(evaled)}', lineno
                )

        if name == 'INT':
            require(1); return int(math.floor(num()))

        if name == 'ABS':
            require(1); return abs(num())

        if name == 'SQR':
            require(1)
            v = num()
            if v < 0:
                raise BasicError('SQR of negative number', lineno)
            return math.sqrt(v)

        if name == 'RND':
            # RND(1) or RND(n) – returns 0 <= x < 1
            if len(evaled) == 0:
                return random.random()
            return random.random()

        if name == 'LEN':
            require(1); return len(s())

        if name == 'LEFT$':
            require(2); return s(0)[:int(num(1))]

        if name == 'RIGHT$':
            require(2)
            n = int(num(1))
            return s(0)[-n:] if n > 0 else ''

        if name == 'MID$':
            if len(evaled) not in (2, 3):
                raise BasicError('MID$ requires 2 or 3 arguments', lineno)
            src = s(0)
            start = int(num(1)) - 1  # BASIC is 1-based
            start = max(0, start)
            if len(evaled) == 3:
                length = int(num(2))
                return src[start:start + length]
            return src[start:]

        if name == 'STR$':
            require(1)
            v = num()
            if v == int(v):
                return str(int(v))
            return str(v)

        if name == 'VAL':
            require(1)
            raw = s().strip()
            try:
                v = float(raw)
                return int(v) if v == int(v) else v
            except ValueError:
                return 0

        if name == 'CHR$':
            require(1)
            return chr(int(num()))

        if name == 'ASC':
            require(1)
            sv = s()
            if not sv:
                raise BasicError('ASC of empty string', lineno)
            return ord(sv[0])

        if name == 'TAB':
            require(1)
            # Returns enough spaces to reach column n (1-based)
            # We approximate by just returning spaces
            n = max(0, int(num()) - 1)
            return '\t' + (' ' * n)   # crude approximation

        if name == 'SGN':
            require(1)
            v = num()
            return 1 if v > 0 else (-1 if v < 0 else 0)

        if name == 'FIX':
            require(1)
            v = num()
            return int(v)  # truncate toward zero

        if name == 'LOG':
            require(1)
            v = num()
            if v <= 0:
                raise BasicError('LOG of non-positive number', lineno)
            return math.log(v)

        if name == 'EXP':
            require(1); return math.exp(num())

        if name == 'SIN':
            require(1); return math.sin(num())

        if name == 'COS':
            require(1); return math.cos(num())

        if name == 'TAN':
            require(1); return math.tan(num())

        if name == 'ATN':
            require(1); return math.atan(num())

        # ------------------------------------------------------------------
        # New string functions
        # ------------------------------------------------------------------

        if name == 'INSTR':
            if len(evaled) == 2:
                haystack, needle = s(0), evaled[1]
                if not isinstance(needle, str):
                    raise BasicError('INSTR: second argument must be a string', lineno)
                pos = haystack.find(needle)
                return 0 if pos == -1 else pos + 1
            elif len(evaled) == 3:
                start = int(num(0)) - 1  # 1-based → 0-based
                haystack, needle = s(1), evaled[2]
                if not isinstance(needle, str):
                    raise BasicError('INSTR: third argument must be a string', lineno)
                pos = haystack.find(needle, max(0, start))
                return 0 if pos == -1 else pos + 1
            else:
                raise BasicError('INSTR requires 2 or 3 arguments', lineno)

        if name == 'SPACE$':
            require(1); return ' ' * max(0, int(num()))

        if name == 'STRING$':
            require(2)
            n = max(0, int(num(0)))
            c = evaled[1]
            if isinstance(c, str):
                ch = c[0] if c else ''
            else:
                ch = chr(int(c))
            return ch * n

        if name == 'UCASE$':
            require(1); return s().upper()

        if name == 'LCASE$':
            require(1); return s().lower()

        if name == 'LTRIM$':
            require(1); return s().lstrip()

        if name == 'RTRIM$':
            require(1); return s().rstrip()

        if name == 'HEX$':
            require(1); return hex(int(num()))[2:].upper()

        if name == 'OCT$':
            require(1); return oct(int(num()))[2:]

        # ------------------------------------------------------------------
        # New numeric / type-conversion functions
        # ------------------------------------------------------------------

        if name == 'CINT':
            require(1); return int(round(num()))

        if name == 'CLNG':
            require(1); return int(num())

        if name == 'CSNG':
            require(1); return float(num())

        if name == 'CDBL':
            require(1); return float(num())

        # ------------------------------------------------------------------
        # New I/O functions
        # ------------------------------------------------------------------

        if name == 'SPC':
            require(1); return ' ' * max(0, int(num()))

        if name == 'INKEY$':
            if len(evaled) != 0:
                raise BasicError('INKEY$ takes no arguments', lineno)
            if hasattr(self._renderer, 'inkey'):
                return self._renderer.inkey()
            try:
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    return sys.stdin.read(1)
            except Exception:
                pass
            return ''

        if name == 'INPUT$':
            require(1)
            n = max(0, int(num()))
            try:
                result = ''
                for _ in range(n):
                    ch = sys.stdin.read(1)
                    if not ch:
                        break
                    result += ch
                return result
            except EOFError:
                return ''

        if name == 'POS':
            # Cursor column position — not trackable in plain text mode
            return 0

        if name == 'CSRLIN':
            # Cursor row position — not trackable in plain text mode
            return 0

        # ------------------------------------------------------------------
        # New system / date-time functions
        # ------------------------------------------------------------------

        if name == 'TIMER':
            if len(evaled) != 0:
                raise BasicError('TIMER takes no arguments', lineno)
            now = datetime.datetime.now()
            return now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1_000_000

        if name == 'DATE$':
            if len(evaled) != 0:
                raise BasicError('DATE$ takes no arguments', lineno)
            now = datetime.datetime.now()
            return now.strftime('%m-%d-%Y')

        if name == 'TIME$':
            if len(evaled) != 0:
                raise BasicError('TIME$ takes no arguments', lineno)
            now = datetime.datetime.now()
            return now.strftime('%H:%M:%S')

        # ------------------------------------------------------------------
        # Graphics functions
        # ------------------------------------------------------------------

        if name == 'POINT':
            require(2)
            x = int(num(0))
            y = int(num(1))
            return self._renderer.point(x, y)

        # ------------------------------------------------------------------
        # User-defined functions  DEF FN...
        # ------------------------------------------------------------------

        if name in self._user_funcs:
            param_name, body = self._user_funcs[name]
            if len(evaled) != 1:
                raise BasicError(f'{name} requires 1 argument', lineno)
            old_val = self._vars.get(param_name)
            self._vars[param_name] = evaled[0]
            result = self._eval(body, lineno)
            if old_val is None:
                self._vars.pop(param_name, None)
            else:
                self._vars[param_name] = old_val
            return result

        raise BasicError(f'Unknown function: {name}', lineno)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _resolve_lineno(self, lineno: int, current: int) -> int:
        if lineno not in self._line_map:
            raise BasicError(f'Undefined line number {lineno}', current)
        return self._line_map[lineno]

    @staticmethod
    def _truthy(val: Any) -> bool:
        if isinstance(val, str):
            return val != ''
        return val != 0

    def _num(self, val: Any, lineno: int) -> float | int:
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            try:
                v = float(val)
                return int(v) if v == int(v) else v
            except ValueError:
                raise BasicError(f'Expected number, got string {val!r}', lineno)
        raise BasicError(f'Expected number, got {type(val).__name__}', lineno)

    def _coerce_num(self, value: Any, lineno: int) -> float | int:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                v = float(value)
                return int(v) if v == int(v) else v
            except ValueError:
                raise BasicError(
                    f'Cannot convert {value!r} to number', lineno
                )
        return value

    def _decompile_line(self, line: Line) -> str:
        """Return the original source text for the LIST command."""
        return f'{line.lineno} {line.source}'


# D-1/D-2: Dispatch table for _eval — O(1) type → handler lookup.
# NumberNode and VarNode (most frequent) are listed first for dict-insert order,
# but dict lookup is O(1) regardless of order.
Interpreter._EVAL_DISPATCH = {
    NumberNode:      lambda self, node, lineno: node.value,
    StringNode:      lambda self, node, lineno: node.value,
    VarNode:         lambda self, node, lineno: self._get_var(node.name),
    BinOpNode:       Interpreter._eval_binop,
    FuncCallNode:    lambda self, node, lineno: self._call_func(node.name, node.args, lineno),
    ArrayAccessNode: Interpreter._eval_array_access,
    UnaryOpNode:     Interpreter._eval_unary_op,
}
