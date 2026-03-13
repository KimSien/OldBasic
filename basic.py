#!/usr/bin/env python3
"""
basic.py - CLI entry point for the BASIC interpreter.

Usage
-----
    python basic.py program.bas     # run a file
    python basic.py                 # start interactive REPL
"""

import sys
import os

# Ensure the project root is on the path so `import basic` works whether
# this script is run directly or from another directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from basic.interpreter import Interpreter, BasicError


# ---------------------------------------------------------------------------
# File runner
# ---------------------------------------------------------------------------

def run_file(path: str) -> int:
    """Load and run a BASIC program file. Returns exit code."""
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            source = fh.read()
    except FileNotFoundError:
        print(f'basic: file not found: {path}', file=sys.stderr)
        return 1
    except OSError as e:
        print(f'basic: cannot read {path}: {e}', file=sys.stderr)
        return 1

    interp = Interpreter(interactive=False)
    try:
        interp.load(source)
        interp.run()
        return 0
    except BasicError as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrupted', file=sys.stderr)
        return 130


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

_REPL_HELP = """\
BASIC Interpreter REPL
----------------------
Type BASIC statements with a line number to add them to the program:
  10 PRINT "hello"
  20 END

Special REPL commands (no line number):
  RUN      - execute the current program
  LIST     - list the current program
  NEW      - clear the program and all variables
  QUIT     - exit the REPL
  HELP     - show this message

Or type BASIC statements without a line number for immediate execution:
  PRINT 2 + 2
"""


def run_repl() -> int:
    """Interactive REPL. Returns exit code."""
    print('BASIC Interpreter  (type HELP for commands, QUIT to exit)')
    interp = Interpreter(interactive=True)

    while True:
        try:
            raw = input('READY\n> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        upper = raw.upper()

        if upper == 'QUIT' or upper == 'EXIT' or upper == 'BYE':
            break

        if upper == 'HELP':
            print(_REPL_HELP)
            continue

        if upper == 'RUN':
            try:
                interp.run()
            except BasicError as e:
                print(e)
            continue

        if upper == 'LIST':
            interp.list_program()
            continue

        if upper == 'NEW':
            interp = Interpreter(interactive=True)
            print('OK')
            continue

        # Otherwise parse/execute the line
        try:
            interp.run_line(raw)
        except BasicError as e:
            print(e)
        except KeyboardInterrupt:
            print('\nBreak')

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]

    if not args:
        return run_repl()

    if args[0] in ('-h', '--help'):
        print('Usage: python basic.py [program.bas]')
        print('       python basic.py          # start interactive REPL')
        return 0

    if len(args) == 1:
        return run_file(args[0])

    print(f'basic: too many arguments', file=sys.stderr)
    print('Usage: python basic.py [program.bas]', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
