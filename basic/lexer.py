"""
BASIC Lexer - tokenizes BASIC source lines into token streams.
"""

import re
from enum import Enum, auto


class TT(Enum):
    """Token types."""
    # Literals
    NUMBER    = auto()
    STRING    = auto()
    IDENT     = auto()   # plain identifier  (A, SCORE, NAME$)

    # Keywords
    REM       = auto()
    PRINT     = auto()
    LET       = auto()
    INPUT     = auto()
    IF        = auto()
    THEN      = auto()
    ELSE      = auto()
    GOTO      = auto()
    GOSUB     = auto()
    RETURN    = auto()
    FOR       = auto()
    TO        = auto()
    STEP      = auto()
    NEXT      = auto()
    END       = auto()
    STOP      = auto()
    DIM       = auto()
    DATA      = auto()
    READ      = auto()
    RESTORE   = auto()
    AND       = auto()
    OR        = auto()
    NOT       = auto()
    MOD       = auto()
    WHILE     = auto()
    WEND      = auto()
    RANDOMIZE = auto()
    ON        = auto()
    DEF       = auto()
    SCREEN    = auto()
    CLS       = auto()
    PSET      = auto()
    LINE      = auto()
    CIRCLE    = auto()
    PAINT     = auto()
    GET       = auto()
    PUT       = auto()
    COLOR     = auto()
    PALETTE   = auto()
    BEEP      = auto()
    SOUND     = auto()
    PLAY      = auto()
    SLEEP     = auto()
    DO        = auto()
    LOOP      = auto()
    UNTIL     = auto()

    # Operators / punctuation
    PLUS      = auto()
    MINUS     = auto()
    STAR      = auto()
    SLASH     = auto()
    CARET     = auto()
    EQ        = auto()
    NEQ       = auto()
    LT        = auto()
    GT        = auto()
    LTE       = auto()
    GTE       = auto()
    LPAREN    = auto()
    RPAREN    = auto()
    COMMA     = auto()
    SEMICOLON = auto()
    COLON     = auto()

    EOF       = auto()


_KEYWORDS = {
    'REM':     TT.REM,
    'PRINT':   TT.PRINT,
    'LET':     TT.LET,
    'INPUT':   TT.INPUT,
    'IF':      TT.IF,
    'THEN':    TT.THEN,
    'ELSE':    TT.ELSE,
    'GOTO':    TT.GOTO,
    'GOSUB':   TT.GOSUB,
    'RETURN':  TT.RETURN,
    'FOR':     TT.FOR,
    'TO':      TT.TO,
    'STEP':    TT.STEP,
    'NEXT':    TT.NEXT,
    'END':     TT.END,
    'STOP':    TT.STOP,
    'DIM':     TT.DIM,
    'DATA':    TT.DATA,
    'READ':    TT.READ,
    'RESTORE': TT.RESTORE,
    'AND':       TT.AND,
    'OR':        TT.OR,
    'NOT':       TT.NOT,
    'MOD':       TT.MOD,
    'WHILE':     TT.WHILE,
    'WEND':      TT.WEND,
    'RANDOMIZE': TT.RANDOMIZE,
    'ON':        TT.ON,
    'DEF':       TT.DEF,
    'SCREEN':    TT.SCREEN,
    'CLS':       TT.CLS,
    'PSET':      TT.PSET,
    'LINE':      TT.LINE,
    'CIRCLE':    TT.CIRCLE,
    'PAINT':     TT.PAINT,
    'GET':       TT.GET,
    'PUT':       TT.PUT,
    'COLOR':     TT.COLOR,
    'PALETTE':   TT.PALETTE,
    'BEEP':      TT.BEEP,
    'SOUND':     TT.SOUND,
    'PLAY':      TT.PLAY,
    'SLEEP':     TT.SLEEP,
    'DO':        TT.DO,
    'LOOP':      TT.LOOP,
    'UNTIL':     TT.UNTIL,
}


class Token:
    __slots__ = ('type', 'value')

    def __init__(self, type_: TT, value=None):
        self.type  = type_
        self.value = value

    def __repr__(self):
        return f'Token({self.type}, {self.value!r})'


class LexerError(Exception):
    pass


class Lexer:
    """
    Tokenise a single logical BASIC line (everything after the line number).
    Line numbers are stripped by the caller before passing text here.
    """

    def tokenize(self, text: str, lineno: int = 0) -> list[Token]:
        self._text   = text
        self._pos    = 0
        self._lineno = lineno
        tokens: list[Token] = []

        while self._pos < len(self._text):
            self._skip_spaces()
            if self._pos >= len(self._text):
                break

            ch = self._text[self._pos]

            # --- String literal ---
            if ch == '"':
                tokens.append(self._read_string())

            # --- Number literal ---
            elif ch.isdigit() or (ch == '.' and self._peek_digit()):
                tokens.append(self._read_number())

            # --- Identifier / keyword ---
            elif ch.isalpha() or ch == '_':
                tok = self._read_ident()
                # REM eats the rest of the line
                if tok.type == TT.REM:
                    tokens.append(tok)
                    rest = self._text[self._pos:].strip()
                    tokens.append(Token(TT.STRING, rest))
                    self._pos = len(self._text)
                else:
                    tokens.append(tok)

            # --- Two-char operators first ---
            elif ch == '<':
                if self._text[self._pos:self._pos+2] == '<>':
                    tokens.append(Token(TT.NEQ)); self._pos += 2
                elif self._text[self._pos:self._pos+2] == '<=':
                    tokens.append(Token(TT.LTE)); self._pos += 2
                else:
                    tokens.append(Token(TT.LT)); self._pos += 1
            elif ch == '>':
                if self._text[self._pos:self._pos+2] == '>=':
                    tokens.append(Token(TT.GTE)); self._pos += 2
                else:
                    tokens.append(Token(TT.GT)); self._pos += 1
            elif ch == '=':
                tokens.append(Token(TT.EQ)); self._pos += 1

            # --- Single-char operators ---
            elif ch == '+':  tokens.append(Token(TT.PLUS));      self._pos += 1
            elif ch == '-':  tokens.append(Token(TT.MINUS));     self._pos += 1
            elif ch == '*':  tokens.append(Token(TT.STAR));      self._pos += 1
            elif ch == '/':  tokens.append(Token(TT.SLASH));     self._pos += 1
            elif ch == '^':  tokens.append(Token(TT.CARET));     self._pos += 1
            elif ch == '(':  tokens.append(Token(TT.LPAREN));    self._pos += 1
            elif ch == ')':  tokens.append(Token(TT.RPAREN));    self._pos += 1
            elif ch == ',':  tokens.append(Token(TT.COMMA));     self._pos += 1
            elif ch == ';':  tokens.append(Token(TT.SEMICOLON)); self._pos += 1
            elif ch == ':':  tokens.append(Token(TT.COLON));     self._pos += 1

            else:
                raise LexerError(
                    f'Line {lineno}: unexpected character {ch!r}'
                )

        tokens.append(Token(TT.EOF))
        return tokens

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _skip_spaces(self):
        while self._pos < len(self._text) and self._text[self._pos] in ' \t':
            self._pos += 1

    def _peek_digit(self) -> bool:
        nxt = self._pos + 1
        return nxt < len(self._text) and self._text[nxt].isdigit()

    def _read_string(self) -> Token:
        self._pos += 1  # skip opening "
        start = self._pos
        while self._pos < len(self._text) and self._text[self._pos] != '"':
            self._pos += 1
        value = self._text[start:self._pos]
        if self._pos < len(self._text):
            self._pos += 1  # skip closing "
        return Token(TT.STRING, value)

    def _read_number(self) -> Token:
        start = self._pos
        has_dot = False
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch.isdigit():
                self._pos += 1
            elif ch == '.' and not has_dot:
                has_dot = True
                self._pos += 1
            elif ch in ('E', 'e') and self._pos > start:
                self._pos += 1
                if self._pos < len(self._text) and self._text[self._pos] in '+-':
                    self._pos += 1
            else:
                break
        raw = self._text[start:self._pos]
        value = float(raw) if ('.' in raw or 'e' in raw.lower()) else int(raw)
        return Token(TT.NUMBER, value)

    def _read_ident(self) -> Token:
        start = self._pos
        while self._pos < len(self._text) and (
            self._text[self._pos].isalnum() or
            self._text[self._pos] in ('_', '$')
        ):
            self._pos += 1
        raw = self._text[start:self._pos].upper()
        # Check for keyword (string variables like A$ must not be keywords)
        if raw in _KEYWORDS and not raw.endswith('$'):
            return Token(_KEYWORDS[raw])
        return Token(TT.IDENT, raw)
