"""
basic - A BASIC language interpreter written in Python.

Package structure
-----------------
basic.lexer       - Tokeniser (Lexer class, Token, TT enum)
basic.parser      - AST parser (Parser class, AST node dataclasses)
basic.interpreter - Tree-walk interpreter (Interpreter class)
"""

from .lexer       import Lexer, Token, TT, LexerError
from .parser      import Parser, ParseError
from .interpreter import Interpreter, BasicError

__all__ = [
    'Lexer', 'Token', 'TT', 'LexerError',
    'Parser', 'ParseError',
    'Interpreter', 'BasicError',
]

__version__ = '1.0.0'
