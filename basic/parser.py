"""
BASIC Parser - converts token streams into AST nodes.

Grammar (simplified):

program       := line*
line          := NUMBER statement_list
statement_list:= statement (COLON statement)*
statement     := rem_stmt | print_stmt | let_stmt | input_stmt
               | if_stmt | goto_stmt | gosub_stmt | return_stmt
               | for_stmt | next_stmt | end_stmt | stop_stmt
               | dim_stmt | data_stmt | read_stmt | restore_stmt
               | assign_stmt
expression    := or_expr
or_expr       := and_expr (OR and_expr)*
and_expr      := not_expr (AND not_expr)*
not_expr      := NOT not_expr | compare_expr
compare_expr  := add_expr ((= | <> | < | > | <= | >=) add_expr)*
add_expr      := mul_expr ((+ | -) mul_expr)*
mul_expr      := pow_expr ((* | / | MOD) pow_expr)*
pow_expr      := unary (^ unary)*
unary         := - unary | atom
atom          := NUMBER | STRING | IDENT | IDENT(args) | IDENT$(args) | ( expr )
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .lexer import Lexer, Token, TT, LexerError


# ---------------------------------------------------------------------------
# AST node definitions
# ---------------------------------------------------------------------------

@dataclass
class NumberNode:
    value: float | int

@dataclass
class StringNode:
    value: str

@dataclass
class VarNode:
    name: str          # e.g. "A", "NAME$"

@dataclass
class ArrayAccessNode:
    name: str
    index: Any         # expression node

@dataclass
class FuncCallNode:
    name: str          # uppercase, e.g. "INT", "LEFT$"
    args: list

@dataclass
class BinOpNode:
    op: TT
    left: Any
    right: Any

@dataclass
class UnaryOpNode:
    op: TT
    operand: Any

# Statements

@dataclass
class RemStmt:
    comment: str

@dataclass
class PrintStmt:
    items: list          # list of (expr | separator_string)
    # separators are encoded inline: "," ";" are kept as TT.COMMA / TT.SEMICOLON
    # We store items as list of ('expr', node) | ('sep', TT.COMMA|TT.SEMICOLON)

@dataclass
class LetStmt:
    target: Any          # VarNode or ArrayAccessNode
    value: Any

@dataclass
class InputStmt:
    prompt: Optional[str]
    var: Any             # VarNode or ArrayAccessNode

@dataclass
class IfStmt:
    condition: Any
    then_stmt: Any       # single statement
    else_stmt: Any = None

@dataclass
class GotoStmt:
    lineno: int

@dataclass
class GosubStmt:
    lineno: int

@dataclass
class ReturnStmt:
    pass

@dataclass
class ForStmt:
    var: str
    start: Any
    end: Any
    step: Any = None     # None means 1

@dataclass
class NextStmt:
    var: Optional[str] = None

@dataclass
class EndStmt:
    pass

@dataclass
class StopStmt:
    pass

@dataclass
class DimStmt:
    name: str
    size: Any            # expression

@dataclass
class DataStmt:
    values: list         # list of literals (numbers/strings)

@dataclass
class ReadStmt:
    vars: list           # list of VarNode / ArrayAccessNode

@dataclass
class RestoreStmt:
    pass

@dataclass
class WhileStmt:
    condition: Any

@dataclass
class WendStmt:
    pass

@dataclass
class RandomizeStmt:
    seed: Any = None    # None = use system time

@dataclass
class OnGotoStmt:
    expr: Any
    targets: list       # list of int line numbers

@dataclass
class OnGosubStmt:
    expr: Any
    targets: list       # list of int line numbers

@dataclass
class DefFnStmt:
    name: str           # e.g. "FNSQR"
    param: str          # parameter variable name
    body: Any           # expression node

@dataclass
class ScreenStmt:
    mode: Any

@dataclass
class ClsStmt:
    pass

@dataclass
class PsetStmt:
    x: Any
    y: Any
    color: Any = None

@dataclass
class LineStmt:
    x1: Any
    y1: Any
    x2: Any
    y2: Any
    color: Any = None
    mode: str = ''

@dataclass
class CircleStmt:
    x: Any
    y: Any
    r: Any
    color: Any = None
    start: Any = None
    end: Any = None
    aspect: Any = None

@dataclass
class PaintStmt:
    x: Any
    y: Any
    color: Any = None
    border: Any = None

@dataclass
class GetStmt:
    x1: Any
    y1: Any
    x2: Any
    y2: Any
    array_name: str = ''

@dataclass
class PutStmt:
    x: Any
    y: Any
    array_name: str = ''
    mode: str = 'PSET'

@dataclass
class ColorStmt:
    fg: Any = None
    bg: Any = None

@dataclass
class PaletteStmt:
    attr: Any
    color_val: Any

@dataclass
class BeepStmt:
    pass

@dataclass
class SoundStmt:
    freq: Any
    duration: Any

@dataclass
class PlayStmt:
    music: Any

@dataclass
class SleepStmt:
    duration: Any

@dataclass
class DoStmt:
    condition_type: str = None   # 'WHILE', 'UNTIL', or None
    condition: Any = None

@dataclass
class LoopStmt:
    condition_type: str = None   # 'WHILE', 'UNTIL', or None
    condition: Any = None

@dataclass
class Line:
    lineno: int
    stmts: list
    source: str = ''   # original source text (body only, without line number)


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self):
        self._lexer = Lexer()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def parse_program(self, source: str) -> list[Line]:
        """Parse a full BASIC program, returning a list of Line objects."""
        lines: list[Line] = []
        for raw_line in source.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            line = self._parse_line(raw_line)
            if line is not None:
                lines.append(line)
        lines.sort(key=lambda l: l.lineno)
        return lines

    def parse_line(self, raw_line: str) -> Optional[Line]:
        """Parse a single line (used by REPL)."""
        return self._parse_line(raw_line.strip())

    # ------------------------------------------------------------------
    # Internal: line parsing
    # ------------------------------------------------------------------

    def _parse_line(self, raw: str) -> Optional[Line]:
        if not raw:
            return None
        # Extract leading line number
        m = _LINENO_RE.match(raw)
        if not m:
            # No line number – treat as direct statement at lineno 0
            lineno = 0
            body = raw
        else:
            lineno = int(m.group(1))
            body = raw[m.end():].strip()

        try:
            tokens = self._lexer.tokenize(body, lineno)
        except LexerError as e:
            raise ParseError(str(e)) from e

        self._tokens = tokens
        self._pos    = 0
        self._lineno = lineno

        stmts = self._parse_statement_list()
        return Line(lineno, stmts, source=body)

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _cur(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return Token(TT.EOF)

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.type != TT.EOF:
            self._pos += 1
        return tok

    def _expect(self, tt: TT) -> Token:
        tok = self._cur()
        if tok.type != tt:
            raise ParseError(
                f'Line {self._lineno}: expected {tt}, got {tok}'
            )
        return self._advance()

    def _match(self, *types: TT) -> bool:
        return self._cur().type in types

    # ------------------------------------------------------------------
    # Statement list  (colon-separated)
    # ------------------------------------------------------------------

    def _parse_statement_list(self) -> list:
        stmts = []
        stmt = self._parse_statement()
        if stmt is not None:
            stmts.append(stmt)
        while self._match(TT.COLON):
            self._advance()
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _parse_statement(self) -> Any:
        tt = self._cur().type

        if tt == TT.REM:
            return self._parse_rem()
        elif tt == TT.PRINT:
            return self._parse_print()
        elif tt == TT.LET:
            return self._parse_let()
        elif tt == TT.INPUT:
            return self._parse_input()
        elif tt == TT.IF:
            return self._parse_if()
        elif tt == TT.GOTO:
            return self._parse_goto()
        elif tt == TT.GOSUB:
            return self._parse_gosub()
        elif tt == TT.RETURN:
            self._advance(); return ReturnStmt()
        elif tt == TT.FOR:
            return self._parse_for()
        elif tt == TT.NEXT:
            return self._parse_next()
        elif tt == TT.END:
            self._advance(); return EndStmt()
        elif tt == TT.STOP:
            self._advance(); return StopStmt()
        elif tt == TT.DIM:
            return self._parse_dim()
        elif tt == TT.DATA:
            return self._parse_data()
        elif tt == TT.READ:
            return self._parse_read()
        elif tt == TT.RESTORE:
            self._advance(); return RestoreStmt()
        elif tt == TT.WHILE:
            return self._parse_while()
        elif tt == TT.WEND:
            self._advance(); return WendStmt()
        elif tt == TT.RANDOMIZE:
            return self._parse_randomize()
        elif tt == TT.ON:
            return self._parse_on()
        elif tt == TT.DEF:
            return self._parse_def_fn()
        elif tt == TT.SCREEN:
            return self._parse_screen()
        elif tt == TT.CLS:
            self._advance(); return ClsStmt()
        elif tt == TT.PSET:
            return self._parse_pset()
        elif tt == TT.LINE:
            return self._parse_line_stmt()
        elif tt == TT.CIRCLE:
            return self._parse_circle()
        elif tt == TT.PAINT:
            return self._parse_paint()
        elif tt == TT.GET:
            return self._parse_get()
        elif tt == TT.PUT:
            return self._parse_put()
        elif tt == TT.COLOR:
            return self._parse_color()
        elif tt == TT.PALETTE:
            return self._parse_palette()
        elif tt == TT.BEEP:
            self._advance(); return BeepStmt()
        elif tt == TT.SOUND:
            return self._parse_sound()
        elif tt == TT.PLAY:
            return self._parse_play()
        elif tt == TT.SLEEP:
            return self._parse_sleep()
        elif tt == TT.DO:
            return self._parse_do()
        elif tt == TT.LOOP:
            return self._parse_loop()
        elif tt == TT.IDENT:
            # Could be assignment  VAR = expr  or  VAR(idx) = expr
            return self._parse_assign()
        elif tt == TT.EOF:
            return None
        else:
            raise ParseError(
                f'Line {self._lineno}: unexpected token {self._cur()}'
            )

    def _parse_rem(self):
        self._advance()               # consume REM
        comment = ''
        if self._cur().type == TT.STRING:
            comment = self._advance().value
        return RemStmt(comment)

    def _parse_print(self):
        self._advance()  # consume PRINT
        items = []
        # PRINT with no args is valid
        while not self._match(TT.EOF, TT.COLON, TT.ELSE):
            if self._match(TT.COMMA):
                items.append(('sep', TT.COMMA))
                self._advance()
            elif self._match(TT.SEMICOLON):
                items.append(('sep', TT.SEMICOLON))
                self._advance()
            else:
                expr = self._parse_expression()
                items.append(('expr', expr))
        return PrintStmt(items)

    def _parse_let(self):
        self._advance()  # consume LET
        return self._parse_assign()

    def _parse_assign(self):
        name = self._expect(TT.IDENT).value
        # Array assignment?
        if self._match(TT.LPAREN):
            self._advance()
            idx = self._parse_expression()
            self._expect(TT.RPAREN)
            target = ArrayAccessNode(name, idx)
        else:
            target = VarNode(name)
        self._expect(TT.EQ)
        value = self._parse_expression()
        return LetStmt(target, value)

    def _parse_input(self):
        self._advance()  # consume INPUT
        prompt = None
        if self._match(TT.STRING):
            prompt = self._advance().value
            if self._match(TT.SEMICOLON):
                self._advance()
            elif self._match(TT.COMMA):
                self._advance()
        # variable
        var = self._parse_lvalue()
        return InputStmt(prompt, var)

    def _parse_lvalue(self):
        name = self._expect(TT.IDENT).value
        if self._match(TT.LPAREN):
            self._advance()
            idx = self._parse_expression()
            self._expect(TT.RPAREN)
            return ArrayAccessNode(name, idx)
        return VarNode(name)

    def _parse_if(self):
        self._advance()  # consume IF
        condition = self._parse_expression()
        self._expect(TT.THEN)
        # THEN may be followed by a line number (shorthand GOTO)
        if self._match(TT.NUMBER):
            lineno = int(self._advance().value)
            then_stmt = GotoStmt(lineno)
        else:
            then_stmt = self._parse_statement()
        else_stmt = None
        if self._match(TT.ELSE):
            self._advance()
            if self._match(TT.NUMBER):
                lineno = int(self._advance().value)
                else_stmt = GotoStmt(lineno)
            else:
                else_stmt = self._parse_statement()
        return IfStmt(condition, then_stmt, else_stmt)

    def _parse_goto(self):
        self._advance()  # consume GOTO
        lineno = int(self._expect(TT.NUMBER).value)
        return GotoStmt(lineno)

    def _parse_gosub(self):
        self._advance()  # consume GOSUB
        lineno = int(self._expect(TT.NUMBER).value)
        return GosubStmt(lineno)

    def _parse_for(self):
        self._advance()  # consume FOR
        var = self._expect(TT.IDENT).value
        self._expect(TT.EQ)
        start = self._parse_expression()
        self._expect(TT.TO)
        end = self._parse_expression()
        step = None
        if self._match(TT.STEP):
            self._advance()
            step = self._parse_expression()
        return ForStmt(var, start, end, step)

    def _parse_next(self):
        self._advance()  # consume NEXT
        var = None
        if self._match(TT.IDENT):
            var = self._advance().value
        return NextStmt(var)

    def _parse_dim(self):
        self._advance()  # consume DIM
        name = self._expect(TT.IDENT).value
        self._expect(TT.LPAREN)
        size = self._parse_expression()
        self._expect(TT.RPAREN)
        return DimStmt(name, size)

    def _parse_data(self):
        self._advance()  # consume DATA
        values = []
        while not self._match(TT.EOF, TT.COLON):
            if self._match(TT.NUMBER):
                values.append(self._advance().value)
            elif self._match(TT.STRING):
                values.append(self._advance().value)
            elif self._match(TT.MINUS):
                self._advance()
                v = self._expect(TT.NUMBER).value
                values.append(-v)
            else:
                raise ParseError(
                    f'Line {self._lineno}: invalid DATA value {self._cur()}'
                )
            if self._match(TT.COMMA):
                self._advance()
        return DataStmt(values)

    def _parse_read(self):
        self._advance()  # consume READ
        vars_ = [self._parse_lvalue()]
        while self._match(TT.COMMA):
            self._advance()
            vars_.append(self._parse_lvalue())
        return ReadStmt(vars_)

    def _parse_while(self):
        self._advance()  # consume WHILE
        condition = self._parse_expression()
        return WhileStmt(condition)

    def _parse_randomize(self):
        self._advance()  # consume RANDOMIZE
        # Optional seed expression
        if self._match(TT.EOF, TT.COLON):
            return RandomizeStmt(None)
        seed = self._parse_expression()
        return RandomizeStmt(seed)

    def _parse_on(self):
        self._advance()  # consume ON
        expr = self._parse_expression()
        if self._match(TT.GOTO):
            self._advance()
            targets = [int(self._expect(TT.NUMBER).value)]
            while self._match(TT.COMMA):
                self._advance()
                targets.append(int(self._expect(TT.NUMBER).value))
            return OnGotoStmt(expr, targets)
        elif self._match(TT.GOSUB):
            self._advance()
            targets = [int(self._expect(TT.NUMBER).value)]
            while self._match(TT.COMMA):
                self._advance()
                targets.append(int(self._expect(TT.NUMBER).value))
            return OnGosubStmt(expr, targets)
        else:
            raise ParseError(
                f'Line {self._lineno}: expected GOTO or GOSUB after ON expr'
            )

    def _parse_def_fn(self):
        self._advance()  # consume DEF
        fn_name = self._expect(TT.IDENT).value
        if not fn_name.startswith('FN'):
            raise ParseError(
                f'Line {self._lineno}: DEF must be followed by FN<name>'
            )
        self._expect(TT.LPAREN)
        param = self._expect(TT.IDENT).value
        self._expect(TT.RPAREN)
        self._expect(TT.EQ)
        body = self._parse_expression()
        return DefFnStmt(fn_name, param, body)

    def _parse_coord_pair(self):
        """Parse (expr, expr) and return (x_node, y_node)."""
        self._expect(TT.LPAREN)
        x = self._parse_expression()
        self._expect(TT.COMMA)
        y = self._parse_expression()
        self._expect(TT.RPAREN)
        return x, y

    def _parse_screen(self):
        self._advance()  # consume SCREEN
        mode = self._parse_expression()
        return ScreenStmt(mode)

    def _parse_pset(self):
        self._advance()  # consume PSET
        x, y = self._parse_coord_pair()
        color = None
        if self._match(TT.COMMA):
            self._advance()
            color = self._parse_expression()
        return PsetStmt(x, y, color)

    def _parse_line_stmt(self):
        self._advance()  # consume LINE
        x1, y1 = self._parse_coord_pair()
        self._expect(TT.MINUS)
        x2, y2 = self._parse_coord_pair()
        color = None
        mode = ''
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.COMMA, TT.EOF, TT.COLON):
                color = self._parse_expression()
            if self._match(TT.COMMA):
                self._advance()
                if self._match(TT.IDENT):
                    mode = self._advance().value  # B, BF, N
        return LineStmt(x1, y1, x2, y2, color, mode)

    def _parse_circle(self):
        self._advance()  # consume CIRCLE
        x, y = self._parse_coord_pair()
        self._expect(TT.COMMA)
        r = self._parse_expression()
        color = start = end = aspect = None
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.COMMA, TT.EOF, TT.COLON):
                color = self._parse_expression()
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.COMMA, TT.EOF, TT.COLON):
                start = self._parse_expression()
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.COMMA, TT.EOF, TT.COLON):
                end = self._parse_expression()
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.EOF, TT.COLON):
                aspect = self._parse_expression()
        return CircleStmt(x, y, r, color, start, end, aspect)

    def _parse_paint(self):
        self._advance()  # consume PAINT
        x, y = self._parse_coord_pair()
        color = border = None
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.COMMA, TT.EOF, TT.COLON):
                color = self._parse_expression()
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.EOF, TT.COLON):
                border = self._parse_expression()
        return PaintStmt(x, y, color, border)

    def _parse_get(self):
        self._advance()  # consume GET
        x1, y1 = self._parse_coord_pair()
        self._expect(TT.MINUS)
        x2, y2 = self._parse_coord_pair()
        self._expect(TT.COMMA)
        name = self._expect(TT.IDENT).value
        return GetStmt(x1, y1, x2, y2, name)

    def _parse_put(self):
        self._advance()  # consume PUT
        x, y = self._parse_coord_pair()
        self._expect(TT.COMMA)
        name = self._expect(TT.IDENT).value
        mode = 'PSET'
        if self._match(TT.COMMA):
            self._advance()
            if self._match(TT.IDENT):
                mode = self._advance().value
        return PutStmt(x, y, name, mode)

    def _parse_color(self):
        self._advance()  # consume COLOR
        fg = bg = None
        if not self._match(TT.COMMA, TT.EOF, TT.COLON):
            fg = self._parse_expression()
        if self._match(TT.COMMA):
            self._advance()
            if not self._match(TT.EOF, TT.COLON):
                bg = self._parse_expression()
        return ColorStmt(fg, bg)

    def _parse_palette(self):
        self._advance()  # consume PALETTE
        attr = self._parse_expression()
        self._expect(TT.COMMA)
        color_val = self._parse_expression()
        return PaletteStmt(attr, color_val)

    def _parse_sound(self):
        self._advance()  # consume SOUND
        freq = self._parse_expression()
        self._expect(TT.COMMA)
        duration = self._parse_expression()
        return SoundStmt(freq, duration)

    def _parse_play(self):
        self._advance()  # consume PLAY
        music = self._parse_expression()
        return PlayStmt(music)

    def _parse_sleep(self):
        self._advance()  # consume SLEEP
        duration = self._parse_expression()
        return SleepStmt(duration)

    def _parse_do(self):
        self._advance()  # consume DO
        condition_type = None
        condition = None
        if self._match(TT.WHILE):
            self._advance()
            condition_type = 'WHILE'
            condition = self._parse_expression()
        elif self._match(TT.UNTIL):
            self._advance()
            condition_type = 'UNTIL'
            condition = self._parse_expression()
        return DoStmt(condition_type, condition)

    def _parse_loop(self):
        self._advance()  # consume LOOP
        condition_type = None
        condition = None
        if self._match(TT.WHILE):
            self._advance()
            condition_type = 'WHILE'
            condition = self._parse_expression()
        elif self._match(TT.UNTIL):
            self._advance()
            condition_type = 'UNTIL'
            condition = self._parse_expression()
        return LoopStmt(condition_type, condition)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _parse_expression(self):
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while self._match(TT.OR):
            op = self._advance().type
            right = self._parse_and()
            left = BinOpNode(op, left, right)
        return left

    def _parse_and(self):
        left = self._parse_not()
        while self._match(TT.AND):
            op = self._advance().type
            right = self._parse_not()
            left = BinOpNode(op, left, right)
        return left

    def _parse_not(self):
        if self._match(TT.NOT):
            op = self._advance().type
            operand = self._parse_not()
            return UnaryOpNode(op, operand)
        return self._parse_compare()

    def _parse_compare(self):
        left = self._parse_add()
        while self._match(TT.EQ, TT.NEQ, TT.LT, TT.GT, TT.LTE, TT.GTE):
            op = self._advance().type
            right = self._parse_add()
            left = BinOpNode(op, left, right)
        return left

    def _parse_add(self):
        left = self._parse_mul()
        while self._match(TT.PLUS, TT.MINUS):
            op = self._advance().type
            right = self._parse_mul()
            left = BinOpNode(op, left, right)
        return left

    def _parse_mul(self):
        left = self._parse_pow()
        while self._match(TT.STAR, TT.SLASH, TT.MOD):
            op = self._advance().type
            right = self._parse_pow()
            left = BinOpNode(op, left, right)
        return left

    def _parse_pow(self):
        base = self._parse_unary()
        if self._match(TT.CARET):
            self._advance()
            exp = self._parse_unary()
            return BinOpNode(TT.CARET, base, exp)
        return base

    def _parse_unary(self):
        if self._match(TT.MINUS):
            op = self._advance().type
            operand = self._parse_unary()
            return UnaryOpNode(op, operand)
        if self._match(TT.PLUS):
            self._advance()
            return self._parse_unary()
        return self._parse_atom()

    def _parse_atom(self):
        tok = self._cur()

        if tok.type == TT.NUMBER:
            self._advance()
            return NumberNode(tok.value)

        if tok.type == TT.STRING:
            self._advance()
            return StringNode(tok.value)

        if tok.type == TT.IDENT:
            name = tok.value
            self._advance()
            # Function call or array access?
            if self._match(TT.LPAREN):
                self._advance()
                args = []
                if not self._match(TT.RPAREN):
                    args.append(self._parse_expression())
                    while self._match(TT.COMMA):
                        self._advance()
                        args.append(self._parse_expression())
                self._expect(TT.RPAREN)
                # Determine whether it's a built-in, user-defined, or array
                if name in _BUILTIN_FUNCS or name.startswith('FN'):
                    return FuncCallNode(name, args)
                else:
                    # Array access (single index)
                    if len(args) != 1:
                        raise ParseError(
                            f'Line {self._lineno}: array {name} requires 1 index'
                        )
                    return ArrayAccessNode(name, args[0])
            if name in _BARE_BUILTIN_FUNCS:
                return FuncCallNode(name, [])
            return VarNode(name)

        if tok.type == TT.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TT.RPAREN)
            return expr

        raise ParseError(
            f'Line {self._lineno}: unexpected token in expression: {tok}'
        )


# Set of known built-in function names (uppercase)
_BUILTIN_FUNCS = {
    # Original
    'INT', 'ABS', 'SQR', 'RND', 'LEN',
    'LEFT$', 'RIGHT$', 'MID$',
    'STR$', 'VAL', 'CHR$', 'ASC',
    'TAB',
    'SGN', 'FIX', 'LOG', 'EXP', 'SIN', 'COS', 'TAN', 'ATN',
    # New string functions
    'INSTR', 'SPACE$', 'STRING$', 'UCASE$', 'LCASE$',
    'LTRIM$', 'RTRIM$', 'HEX$', 'OCT$',
    # New numeric functions
    'CINT', 'CLNG', 'CSNG', 'CDBL',
    # New I/O functions
    'INKEY$', 'INPUT$', 'SPC', 'POS', 'CSRLIN',
    # New system functions
    'TIMER', 'DATE$', 'TIME$',
    # Graphics
    'POINT',
}

# BASIC dialect compatibility: some zero-arg built-ins are commonly used
# without trailing parentheses, e.g. `INKEY$` in game loops.
_BARE_BUILTIN_FUNCS = {
    'INKEY$',
}

import re
_LINENO_RE = re.compile(r'^(\d+)\s*')
