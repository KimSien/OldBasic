"""
CanvasRenderer — Pyodide/browser implementation of the Renderer interface.

Requires Pyodide environment (import js). Use this file by loading it into
Pyodide's virtual filesystem from web/index.html.
"""
import math
import sys
sys.path.insert(0, '/home/pyodide')

# Module-level key buffer.  JS keydown/keyup handlers call _set_key() directly
# as a Python callback registered on window._pySetKey.  This avoids all
# Pyodide JsProxy round-trip issues when reading window.basicKeyBuf from Python.
_KEY_BUF: list[str] = ['']

def _set_key(k: str) -> None:
    """Called synchronously by the JS keydown/keyup handler."""
    _KEY_BUF[0] = str(k) if k else ''

from basic.renderer import Renderer

try:
    import js
    from pyodide.ffi import to_js
    _HAS_JS = True
except ImportError:
    _HAS_JS = False
    def to_js(x): return x


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
        """Flood-fill from (x, y) with color, stopping at border color."""
        w, h = self._w, self._h
        if x < 0 or x >= w or y < 0 or y >= h:
            return

        # Parse fill color
        fc = self._css(color)
        fr, fg_v, fb = int(fc[1:3], 16), int(fc[3:5], 16), int(fc[5:7], 16)

        # Read full canvas into a Python bytearray
        img = self._ctx.getImageData(0, 0, w, h)
        buf = bytearray(img.data.to_py())

        # Seed pixel color
        i0 = (y * w + x) * 4
        sr, sg, sb = buf[i0], buf[i0 + 1], buf[i0 + 2]

        if (sr, sg, sb) == (fr, fg_v, fb):
            return  # already the target color

        if border is not None:
            bc = self._css(border)
            brr, brg, brb = int(bc[1:3], 16), int(bc[3:5], 16), int(bc[5:7], 16)
            def _passable(r, g, b):
                return (r, g, b) != (brr, brg, brb)
        else:
            def _passable(r, g, b):
                return (r, g, b) == (sr, sg, sb)

        # BFS scanline-based flood fill
        visited = bytearray(w * h)
        stack = [x + y * w]
        while stack:
            p = stack.pop()
            if visited[p]:
                continue
            py_y, px = divmod(p, w)
            i4 = p * 4
            if not _passable(buf[i4], buf[i4 + 1], buf[i4 + 2]):
                continue
            visited[p] = 1
            buf[i4], buf[i4 + 1], buf[i4 + 2], buf[i4 + 3] = fr, fg_v, fb, 255
            if px > 0:     stack.append(p - 1)
            if px < w - 1: stack.append(p + 1)
            if py_y > 0:   stack.append(p - w)
            if py_y < h-1: stack.append(p + w)

        img.data.set(to_js(bytes(buf)))
        self._ctx.putImageData(img, 0, 0)

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
        """Blit sprite data to canvas. Supports PSET, PRESET, XOR, AND, OR."""
        if not data:
            return
        n = len(data)
        sw = int(n ** 0.5) or 1   # sprite width (assumes square; works for GET regions)
        sh = (n + sw - 1) // sw   # sprite height

        # Clamp to canvas bounds
        dx_off = max(0, -x)
        dy_off = max(0, -y)
        draw_w = min(sw - dx_off, self._w - max(0, x))
        draw_h = min(sh - dy_off, self._h - max(0, y))
        if draw_w <= 0 or draw_h <= 0:
            return

        cx = max(0, x)
        cy = max(0, y)

        if mode == 'PSET':
            # Build an ImageData directly from sprite pixels (fast path)
            raw = bytearray(draw_w * draw_h * 4)
            for row in range(draw_h):
                for col in range(draw_w):
                    px = data[(row + dy_off) * sw + (col + dx_off)]
                    i4 = (row * draw_w + col) * 4
                    raw[i4]     = (px >> 16) & 0xFF
                    raw[i4 + 1] = (px >>  8) & 0xFF
                    raw[i4 + 2] =  px        & 0xFF
                    raw[i4 + 3] = 255
            new_img = js.ImageData.new(
                js.Uint8ClampedArray.new(to_js(bytes(raw))), draw_w, draw_h)
            self._ctx.putImageData(new_img, cx, cy)

        elif mode == 'PRESET':
            # Invert each sprite pixel
            raw = bytearray(draw_w * draw_h * 4)
            for row in range(draw_h):
                for col in range(draw_w):
                    px = data[(row + dy_off) * sw + (col + dx_off)]
                    i4 = (row * draw_w + col) * 4
                    raw[i4]     = 0xFF ^ ((px >> 16) & 0xFF)
                    raw[i4 + 1] = 0xFF ^ ((px >>  8) & 0xFF)
                    raw[i4 + 2] = 0xFF ^ ( px        & 0xFF)
                    raw[i4 + 3] = 255
            new_img = js.ImageData.new(
                js.Uint8ClampedArray.new(to_js(bytes(raw))), draw_w, draw_h)
            self._ctx.putImageData(new_img, cx, cy)

        else:  # XOR, AND, OR — read-modify-write existing canvas pixels
            img = self._ctx.getImageData(cx, cy, draw_w, draw_h)
            buf = bytearray(img.data.to_py())
            for row in range(draw_h):
                for col in range(draw_w):
                    px = data[(row + dy_off) * sw + (col + dx_off)]
                    sr = (px >> 16) & 0xFF
                    sg = (px >>  8) & 0xFF
                    sb =  px        & 0xFF
                    i4 = (row * draw_w + col) * 4
                    if mode == 'XOR':
                        buf[i4]     ^= sr
                        buf[i4 + 1] ^= sg
                        buf[i4 + 2] ^= sb
                    elif mode == 'AND':
                        buf[i4]     &= sr
                        buf[i4 + 1] &= sg
                        buf[i4 + 2] &= sb
                    elif mode == 'OR':
                        buf[i4]     |= sr
                        buf[i4 + 1] |= sg
                        buf[i4 + 2] |= sb
                    buf[i4 + 3] = 255
            img.data.set(to_js(bytes(buf)))
            self._ctx.putImageData(img, cx, cy)

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
        """Play MML string via Web Audio API.

        Supported commands:
          A-G [#/+/-] [n]  — note (optional sharp/flat, optional length override)
          O<n>             — set octave (1-8, default 4)
          L<n>             — set default note length (1/2/4/8/16/32, default 4)
          T<n>             — set tempo BPM (default 120)
          P<n> / R<n>      — rest
          < / >            — octave down / up
          .                — dotted note (×1.5 duration)
          N<n>             — play MIDI note number directly
        """
        _SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

        def _read_int(s, pos):
            j = pos
            while j < len(s) and s[j].isdigit():
                j += 1
            return (int(s[pos:j]), j) if j > pos else (None, pos)

        def _midi_freq(midi):
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))

        try:
            audio_ctx = js.eval(
                'new (window.AudioContext || window.webkitAudioContext)()')
            t = float(audio_ctx.currentTime) + 0.05
        except Exception:
            return

        octave = 4
        length = 4
        tempo  = 120
        s = music.upper()
        i = 0

        while i < len(s):
            c = s[i]
            i += 1

            if c == 'O':
                n, i = _read_int(s, i)
                if n is not None:
                    octave = max(1, min(8, n))

            elif c == 'L':
                n, i = _read_int(s, i)
                if n is not None and n > 0:
                    length = n

            elif c == 'T':
                n, i = _read_int(s, i)
                if n is not None:
                    tempo = max(1, min(255, n))

            elif c == '<':
                octave = max(1, octave - 1)

            elif c == '>':
                octave = min(8, octave + 1)

            elif c in _SEMITONES:
                semi = _SEMITONES[c]
                # sharp / flat
                if i < len(s) and s[i] in '#+':
                    semi += 1; i += 1
                elif i < len(s) and s[i] == '-':
                    semi -= 1; i += 1
                # explicit length
                n, new_i = _read_int(s, i)
                note_len = n if (n is not None and n > 0) else length
                if n is not None:
                    i = new_i
                # dotted
                dotted = i < len(s) and s[i] == '.'
                if dotted:
                    i += 1
                midi = 12 * (octave + 1) + semi
                freq = _midi_freq(midi)
                dur  = (60.0 / tempo) * (4.0 / note_len) * (1.5 if dotted else 1.0)
                try:
                    osc  = audio_ctx.createOscillator()
                    gain = audio_ctx.createGain()
                    osc.type = 'square'
                    osc.frequency.value = freq
                    gain.gain.value = 0.25
                    osc.connect(gain)
                    gain.connect(audio_ctx.destination)
                    osc.start(t)
                    osc.stop(t + dur * 0.9)
                    t += dur
                except Exception:
                    pass

            elif c in ('P', 'R'):
                n, new_i = _read_int(s, i)
                rest_len = n if (n is not None and n > 0) else length
                if n is not None:
                    i = new_i
                t += (60.0 / tempo) * (4.0 / rest_len)

            elif c == 'N':
                n, i = _read_int(s, i)
                if n is not None:
                    dur = (60.0 / tempo) * (4.0 / length)
                    try:
                        osc  = audio_ctx.createOscillator()
                        gain = audio_ctx.createGain()
                        osc.type = 'square'
                        osc.frequency.value = _midi_freq(n)
                        gain.gain.value = 0.25
                        osc.connect(gain)
                        gain.connect(audio_ctx.destination)
                        osc.start(t)
                        osc.stop(t + dur * 0.9)
                        t += dur
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def inkey(self) -> str:
        return _KEY_BUF[0]

    def sleep(self, seconds: float) -> None:
        # Async sleep is handled by the interpreter's _run_loop_async via
        # asyncio.sleep; this method is only called from the sync run() path
        # (CLI/tests) and falls back to a blocking sleep there.
        import time
        time.sleep(seconds)
