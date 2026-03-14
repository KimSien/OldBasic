"""
CanvasRenderer — Pyodide/browser implementation of the Renderer interface.

Requires Pyodide environment (import js). Use this file by loading it into
Pyodide's virtual filesystem from web/index.html.
"""
import math
import sys
sys.path.insert(0, '/home/pyodide')

from basic.renderer import Renderer

try:
    import js
    _HAS_JS = True
except ImportError:
    _HAS_JS = False


# 16-color EGA/CGA palette (BASIC color indices 0-15)
_EGA = [
    '#000000', '#0000AA', '#00AA00', '#00AAAA',
    '#AA0000', '#AA00AA', '#AA5500', '#AAAAAA',
    '#555555', '#5555FF', '#55FF55', '#55FFFF',
    '#FF5555', '#FF55FF', '#FFFF55', '#FFFFFF',
]


class CanvasRenderer(Renderer):
    """Renders BASIC graphics to an HTML5 Canvas via Pyodide."""

    def __init__(self, canvas_id: str = 'canvas', output_id: str = 'output'):
        if not _HAS_JS:
            raise RuntimeError('CanvasRenderer requires Pyodide (js module not available)')
        self._canvas = js.document.getElementById(canvas_id)
        self._ctx    = self._canvas.getContext('2d')
        self._out    = js.document.getElementById(output_id)
        self._w      = int(self._canvas.width)
        self._h      = int(self._canvas.height)
        self._palette = list(_EGA)
        self._fg = 7
        self._bg = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _css(self, color: int) -> str:
        if isinstance(color, int) and 0 <= color < len(self._palette):
            return self._palette[color]
        return '#FFFFFF'

    def _print(self, text: str):
        if self._out:
            self._out.textContent += text

    # ------------------------------------------------------------------
    # Screen / CLS
    # ------------------------------------------------------------------

    def screen(self, mode: int) -> None:
        # Resize canvas for common screen modes
        sizes = {1: (320, 200), 7: (320, 200), 9: (640, 350),
                 12: (640, 480), 13: (320, 200)}
        if mode in sizes:
            w, h = sizes[mode]
            self._canvas.width  = w
            self._canvas.height = h
            self._w, self._h = w, h

    def cls(self) -> None:
        self._ctx.fillStyle = self._css(self._bg)
        self._ctx.fillRect(0, 0, self._w, self._h)

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def pset(self, x: int, y: int, color: int) -> None:
        self._ctx.fillStyle = self._css(color)
        self._ctx.fillRect(x, y, 1, 1)

    def line(self, x1: int, y1: int, x2: int, y2: int, color: int, mode: str = '') -> None:
        self._ctx.strokeStyle = self._css(color)
        self._ctx.fillStyle   = self._css(color)
        if mode in ('', 'N'):
            self._ctx.beginPath()
            self._ctx.moveTo(x1 + 0.5, y1 + 0.5)
            self._ctx.lineTo(x2 + 0.5, y2 + 0.5)
            self._ctx.stroke()
        elif mode == 'B':
            self._ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
        elif mode == 'BF':
            self._ctx.fillRect(x1, y1, x2 - x1, y2 - y1)

    def circle(self, x: int, y: int, r: int, color: int,
               start=None, end=None, aspect=None) -> None:
        self._ctx.strokeStyle = self._css(color)
        s = float(start) if start is not None else 0.0
        e = float(end)   if end   is not None else 2 * math.pi
        self._ctx.beginPath()
        if aspect is not None and aspect != 1.0:
            self._ctx.save()
            self._ctx.translate(x, y)
            self._ctx.scale(1.0, float(aspect))
            self._ctx.arc(0, 0, r, s, e)
            self._ctx.restore()
        else:
            self._ctx.arc(x, y, r, s, e)
        self._ctx.stroke()

    def paint(self, x: int, y: int, color: int, border=None) -> None:
        # Simplified flood-fill: set a single pixel (full flood-fill needs
        # ImageData manipulation which is complex in Pyodide)
        self._ctx.fillStyle = self._css(color)
        self._ctx.fillRect(x, y, 1, 1)

    def point(self, x: int, y: int) -> int:
        data = self._ctx.getImageData(x, y, 1, 1).data
        r_val = int(data[0])
        g_val = int(data[1])
        b_val = int(data[2])
        css = f'#{r_val:02X}{g_val:02X}{b_val:02X}'
        try:
            return self._palette.index(css)
        except ValueError:
            return -1

    def get_region(self, x1: int, y1: int, x2: int, y2: int) -> list:
        w = x2 - x1 + 1
        h = y2 - y1 + 1
        img  = self._ctx.getImageData(x1, y1, w, h)
        data = img.data
        pixels = []
        for i in range(0, len(data), 4):
            pixels.append((int(data[i]) << 16) | (int(data[i+1]) << 8) | int(data[i+2]))
        return pixels

    def put_region(self, x: int, y: int, data: list, mode: str = 'PSET') -> None:
        # Simplified: draw each pixel using PSET (XOR/AND modes not yet supported)
        if not data:
            return
        w = int(len(data) ** 0.5) or 1
        for i, px in enumerate(data):
            dx = i % w
            dy = i // w
            r_val = (px >> 16) & 0xFF
            g_val = (px >>  8) & 0xFF
            b_val =  px        & 0xFF
            self._ctx.fillStyle = f'rgb({r_val},{g_val},{b_val})'
            self._ctx.fillRect(x + dx, y + dy, 1, 1)

    # ------------------------------------------------------------------
    # Color / Palette
    # ------------------------------------------------------------------

    def color(self, fg: int, bg: int = None) -> None:
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg

    def palette(self, attr: int, color_val: int) -> None:
        if 0 <= attr < len(self._palette):
            r_val = (color_val >> 16) & 0xFF
            g_val = (color_val >>  8) & 0xFF
            b_val =  color_val        & 0xFF
            self._palette[attr] = f'#{r_val:02X}{g_val:02X}{b_val:02X}'

    # ------------------------------------------------------------------
    # Sound
    # ------------------------------------------------------------------

    def beep(self) -> None:
        self._tone(800, 100)

    def sound(self, freq: float, duration: float) -> None:
        # BASIC SOUND duration is in 18.2 Hz ticks
        ms = int(duration * 1000 / 18.2)
        self._tone(freq, ms)

    def _tone(self, freq: float, ms: int) -> None:
        try:
            audio_ctx = js.eval('new (window.AudioContext || window.webkitAudioContext)()')
            osc = audio_ctx.createOscillator()
            osc.frequency.value = freq
            osc.connect(audio_ctx.destination)
            osc.start()
            js.setTimeout(js.Function.new('o', 'o.stop()'), ms, osc)
        except Exception:
            pass  # Audio not available

    def play(self, music: str) -> None:
        # Minimal MML: notes A-G, O<n> octave, T<n> tempo, L<n> length
        # Full MML parsing is omitted; play just beeps once per note letter
        for ch in music.upper():
            if ch in 'ABCDEFG':
                self.beep()

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def sleep(self, seconds: float) -> None:
        # Blocking sleep in Pyodide blocks the JS event loop.
        # In browser use TIMER()-based busy-wait instead.
        import time
        time.sleep(seconds)
