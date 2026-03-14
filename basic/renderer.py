"""
Renderer abstraction for BASIC graphics and sound.

Backends:
  Renderer      — base no-op class
  NullRenderer  — records all calls for testing
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time


class Renderer:
    """Base renderer — all methods are no-ops."""
    def screen(self, mode: int) -> None: pass
    def cls(self) -> None: pass
    def pset(self, x: int, y: int, color: int) -> None: pass
    def line(self, x1: int, y1: int, x2: int, y2: int, color: int, mode: str = '') -> None: pass
    def circle(self, x: int, y: int, r: int, color: int, start=None, end=None, aspect=None) -> None: pass
    def paint(self, x: int, y: int, color: int, border=None) -> None: pass
    def point(self, x: int, y: int) -> int: return 0
    def get_region(self, x1: int, y1: int, x2: int, y2: int) -> list: return []
    def put_region(self, x: int, y: int, data: list, mode: str = 'PSET') -> None: pass
    def color(self, fg: int, bg: int = None) -> None: pass
    def palette(self, attr: int, color_val: int) -> None: pass
    def beep(self) -> None: pass
    def sound(self, freq: float, duration: float) -> None: pass
    def play(self, music: str) -> None: pass
    def sleep(self, seconds: float) -> None: time.sleep(seconds)


class NullRenderer(Renderer):
    """Records all calls without producing output. Used for testing."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._pixels: dict[tuple, int] = {}

    def screen(self, mode: int) -> None:
        self.calls.append(('screen', mode))

    def cls(self) -> None:
        self.calls.append(('cls',))
        self._pixels.clear()

    def pset(self, x: int, y: int, color: int) -> None:
        self.calls.append(('pset', x, y, color))
        self._pixels[(x, y)] = color

    def line(self, x1: int, y1: int, x2: int, y2: int, color: int, mode: str = '') -> None:
        self.calls.append(('line', x1, y1, x2, y2, color, mode))

    def circle(self, x: int, y: int, r: int, color: int, start=None, end=None, aspect=None) -> None:
        self.calls.append(('circle', x, y, r, color, start, end, aspect))

    def paint(self, x: int, y: int, color: int, border=None) -> None:
        self.calls.append(('paint', x, y, color, border))

    def point(self, x: int, y: int) -> int:
        self.calls.append(('point', x, y))
        return self._pixels.get((x, y), 0)

    def get_region(self, x1: int, y1: int, x2: int, y2: int) -> list:
        self.calls.append(('get_region', x1, y1, x2, y2))
        w = x2 - x1 + 1
        h = y2 - y1 + 1
        return [self._pixels.get((x1 + dx, y1 + dy), 0)
                for dy in range(h) for dx in range(w)]

    def put_region(self, x: int, y: int, data: list, mode: str = 'PSET') -> None:
        self.calls.append(('put_region', x, y, mode))

    def color(self, fg: int, bg: int = None) -> None:
        self.calls.append(('color', fg, bg))

    def palette(self, attr: int, color_val: int) -> None:
        self.calls.append(('palette', attr, color_val))

    def beep(self) -> None:
        self.calls.append(('beep',))

    def sound(self, freq: float, duration: float) -> None:
        self.calls.append(('sound', freq, duration))

    def play(self, music: str) -> None:
        self.calls.append(('play', music))

    def sleep(self, seconds: float) -> None:
        self.calls.append(('sleep', seconds))

    def last(self, name: str):
        for call in reversed(self.calls):
            if call[0] == name:
                return call
        return None

    def count(self, name: str) -> int:
        return sum(1 for c in self.calls if c[0] == name)
