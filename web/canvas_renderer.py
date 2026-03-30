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
        self._batch: list = []      # B-2: pending draw commands
        self._css_cache: dict = {}  # E-1: color → CSS string cache

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _css(self, color: int) -> str:
        # E-1: cache color → CSS lookups to avoid repeated isinstance + range checks
        try:
            return self._css_cache[color]
        except KeyError:
            css = self._palette[color] if isinstance(color, int) and 0 <= color < len(self._palette) else '#FFFFFF'
            self._css_cache[color] = css
            return css

    def _print(self, text: str):
        if self._out:
            self._out.textContent += text

    # ------------------------------------------------------------------
    # Screen / CLS
    # ------------------------------------------------------------------

    def screen(self, mode: int) -> None:
        self.flush()  # flush pending draws before canvas resize
        # Resize canvas for common screen modes
        sizes = {1: (320, 200), 7: (320, 200), 9: (640, 350),
                 12: (640, 480), 13: (320, 200)}
        if mode in sizes:
            w, h = sizes[mode]
            self._canvas.width  = w
            self._canvas.height = h
            self._w, self._h = w, h

    def cls(self) -> None:
        # B-2: queue clear command instead of executing immediately
        self._batch.append(('cls', self._css(self._bg), self._w, self._h))

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def pset(self, x: int, y: int, color: int) -> None:
        # B-2: queue draw command
        self._batch.append(('pset', self._css(color), x, y))

    def line(self, x1: int, y1: int, x2: int, y2: int, color: int, mode: str = '') -> None:
        # B-2: queue draw command; E-3: single CSS call per line invocation
        c = self._css(color)
        if mode in ('', 'N'):
            self._batch.append(('line', c, x1, y1, x2, y2))
        elif mode == 'B':
            self._batch.append(('rect', c, x1, y1, x2 - x1, y2 - y1))
        elif mode == 'BF':
            self._batch.append(('fillrect', c, x1, y1, x2 - x1, y2 - y1))

    def circle(self, x: int, y: int, r: int, color: int,
               start=None, end=None, aspect=None) -> None:
        # B-2: queue draw command
        c = self._css(color)
        s = float(start) if start is not None else 0.0
        e = float(end)   if end   is not None else 2 * math.pi
        if aspect is not None and aspect != 1.0:
            self._batch.append(('circle_scaled', c, x, y, r, s, e, float(aspect)))
        else:
            self._batch.append(('circle', c, x, y, r, s, e))

    def flush(self) -> None:
        """B-3: flush queued draw commands to the JS canvas in a single call."""
        if self._batch:
            js.window.basicBatchDraw(to_js(self._batch))
            self._batch.clear()

    def paint(self, x: int, y: int, color: int, border=None) -> None:
        """C-1: Flood-fill via JS (avoids Python↔JS buffer round-trips)."""
        self.flush()  # must render pending draws before reading canvas pixels
        w, h = self._w, self._h
        if x < 0 or x >= w or y < 0 or y >= h:
            return

        fc = self._css(color)
        fr, fg_v, fb = int(fc[1:3], 16), int(fc[3:5], 16), int(fc[5:7], 16)

        if border is not None:
            bc = self._css(border)
            brr, brg, brb = int(bc[1:3], 16), int(bc[3:5], 16), int(bc[5:7], 16)
            js.window.basicFloodFill(x, y, fr, fg_v, fb, brr, brg, brb, True)
        else:
            js.window.basicFloodFill(x, y, fr, fg_v, fb, 0, 0, 0, False)

    def point(self, x: int, y: int) -> int:
        self.flush()  # render pending draws before sampling pixel
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
        self.flush()  # render pending draws before capturing region
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
        self.flush()  # ensure pending draws land before blitting sprite
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
            self._css_cache.clear()  # E-1: invalidate cache on palette change

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
        try:
            queue = js.window.basicKeyQueue
            if queue.length:
                return str(queue.shift())
            held = js.window.basicKeyBuf
            return str(held or '')
        except Exception:
            return ''

    def sleep(self, seconds: float) -> None:
        # Async sleep is handled by the interpreter's _run_loop_async via
        # asyncio.sleep; this method is only called from the sync run() path
        # (CLI/tests) and falls back to a blocking sleep there.
        import time
        time.sleep(seconds)
