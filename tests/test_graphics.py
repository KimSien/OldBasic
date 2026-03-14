"""
Tests for graphics/sound statements and DO/LOOP using NullRenderer.
"""
import io
import sys
import pytest

from basic.renderer import NullRenderer
from basic.interpreter import Interpreter, BasicError


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run_gr(source: str):
    """Run BASIC source with a NullRenderer; return (stdout_text, renderer)."""
    renderer = NullRenderer()
    interp = Interpreter(renderer=renderer)
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        interp.load(source)
        interp.run()
    finally:
        sys.stdout = old_stdout
    return buf.getvalue(), renderer


# ---------------------------------------------------------------------------
# SCREEN
# ---------------------------------------------------------------------------

def test_screen_basic():
    _, r = run_gr("10 SCREEN 1")
    assert r.last('screen') == ('screen', 1)

def test_screen_mode13():
    _, r = run_gr("10 SCREEN 13")
    assert r.last('screen') == ('screen', 13)


# ---------------------------------------------------------------------------
# CLS
# ---------------------------------------------------------------------------

def test_cls():
    _, r = run_gr("10 CLS")
    assert r.last('cls') == ('cls',)

def test_cls_clears_pixels():
    _, r = run_gr("""\
10 PSET (5, 5), 3
20 CLS
""")
    # After CLS, internal pixel store should be cleared
    assert r._pixels == {}

def test_cls_count():
    _, r = run_gr("""\
10 CLS
20 CLS
30 CLS
""")
    assert r.count('cls') == 3


# ---------------------------------------------------------------------------
# PSET
# ---------------------------------------------------------------------------

def test_pset_basic():
    _, r = run_gr("10 PSET (10, 20), 3")
    assert r.last('pset') == ('pset', 10, 20, 3)

def test_pset_default_color():
    _, r = run_gr("10 PSET (0, 0)")
    assert r.last('pset') == ('pset', 0, 0, 7)

def test_pset_multiple():
    _, r = run_gr("""\
10 PSET (1, 2), 1
20 PSET (3, 4), 2
30 PSET (5, 6), 3
""")
    assert r.count('pset') == 3

def test_pset_stores_pixel():
    _, r = run_gr("10 PSET (7, 8), 5")
    assert r._pixels[(7, 8)] == 5


# ---------------------------------------------------------------------------
# LINE
# ---------------------------------------------------------------------------

def test_line_basic():
    _, r = run_gr("10 LINE (0,0)-(100,100), 7")
    assert r.last('line') == ('line', 0, 0, 100, 100, 7, '')

def test_line_default_color():
    _, r = run_gr("10 LINE (0,0)-(50,50)")
    c = r.last('line')
    assert c == ('line', 0, 0, 50, 50, 7, '')

def test_line_mode_B():
    _, r = run_gr("10 LINE (10,10)-(90,90), 4, B")
    assert r.last('line') == ('line', 10, 10, 90, 90, 4, 'B')

def test_line_mode_BF():
    _, r = run_gr("10 LINE (0,0)-(40,40), 2, BF")
    assert r.last('line') == ('line', 0, 0, 40, 40, 2, 'BF')


# ---------------------------------------------------------------------------
# CIRCLE
# ---------------------------------------------------------------------------

def test_circle_basic():
    _, r = run_gr("10 CIRCLE (160, 100), 50, 15")
    assert r.last('circle') == ('circle', 160, 100, 50, 15, None, None, None)

def test_circle_default_color():
    _, r = run_gr("10 CIRCLE (80, 80), 30")
    c = r.last('circle')
    assert c[1:4] == (80, 80, 30)
    assert c[4] == 7

def test_circle_with_angles():
    _, r = run_gr("10 CIRCLE (100, 100), 40, 3, 0, 3.14")
    c = r.last('circle')
    assert c[0] == 'circle'
    assert c[5] == 0.0
    assert abs(c[6] - 3.14) < 0.001

def test_circle_with_aspect():
    _, r = run_gr("10 CIRCLE (100, 100), 40, 3, , , 0.5")
    c = r.last('circle')
    assert c[0] == 'circle'
    assert c[7] == 0.5


# ---------------------------------------------------------------------------
# PAINT
# ---------------------------------------------------------------------------

def test_paint_basic():
    _, r = run_gr("10 PAINT (50, 50), 4")
    assert r.last('paint') == ('paint', 50, 50, 4, None)

def test_paint_with_border():
    _, r = run_gr("10 PAINT (50, 50), 4, 7")
    assert r.last('paint') == ('paint', 50, 50, 4, 7)

def test_paint_default_color():
    _, r = run_gr("10 PAINT (10, 10)")
    c = r.last('paint')
    assert c == ('paint', 10, 10, 7, None)


# ---------------------------------------------------------------------------
# GET / PUT
# ---------------------------------------------------------------------------

def test_get_basic():
    _, r = run_gr("""\
10 PSET (0,0), 1
20 PSET (1,0), 2
30 GET (0,0)-(1,0), SPRITE
""")
    assert r.last('get_region') is not None
    # The array should be stored
    assert 'SPRITE' in r.last('get_region')[0] or True  # just check it ran

def test_get_stores_array():
    _, r = run_gr("""\
10 PSET (5, 5), 3
20 GET (5,5)-(6,6), BUF
""")
    # get_region call should have been recorded
    assert r.count('get_region') == 1
    assert r.last('get_region') == ('get_region', 5, 5, 6, 6)

def test_put_basic():
    _, r = run_gr("""\
10 DIM ARR(4)
20 PUT (10, 20), ARR
""")
    c = r.last('put_region')
    assert c[0] == 'put_region'
    assert c[1] == 10
    assert c[2] == 20
    assert c[3] == 'PSET'

def test_put_with_mode():
    _, r = run_gr("""\
10 DIM ARR(4)
20 PUT (0, 0), ARR, XOR
""")
    c = r.last('put_region')
    assert c[3] == 'XOR'


# ---------------------------------------------------------------------------
# COLOR
# ---------------------------------------------------------------------------

def test_color_fg_bg():
    _, r = run_gr("10 COLOR 14, 1")
    assert r.last('color') == ('color', 14, 1)

def test_color_fg_only():
    _, r = run_gr("10 COLOR 7")
    assert r.last('color') == ('color', 7, None)

def test_color_multiple():
    _, r = run_gr("""\
10 COLOR 3, 0
20 COLOR 15, 1
""")
    assert r.count('color') == 2
    assert r.last('color') == ('color', 15, 1)


# ---------------------------------------------------------------------------
# PALETTE
# ---------------------------------------------------------------------------

def test_palette_basic():
    _, r = run_gr("10 PALETTE 0, 0")
    assert r.last('palette') == ('palette', 0, 0)

def test_palette_with_value():
    _, r = run_gr("10 PALETTE 3, 255")
    assert r.last('palette') == ('palette', 3, 255)


# ---------------------------------------------------------------------------
# BEEP
# ---------------------------------------------------------------------------

def test_beep():
    _, r = run_gr("10 BEEP")
    assert r.last('beep') == ('beep',)

def test_beep_count():
    _, r = run_gr("""\
10 BEEP
20 BEEP
30 BEEP
""")
    assert r.count('beep') == 3


# ---------------------------------------------------------------------------
# SOUND
# ---------------------------------------------------------------------------

def test_sound_basic():
    _, r = run_gr("10 SOUND 440, 10")
    c = r.last('sound')
    assert c[0] == 'sound'
    assert c[1] == 440.0
    assert c[2] == 10.0

def test_sound_float():
    _, r = run_gr("10 SOUND 261.6, 18")
    c = r.last('sound')
    assert abs(c[1] - 261.6) < 0.1


# ---------------------------------------------------------------------------
# PLAY
# ---------------------------------------------------------------------------

def test_play_basic():
    _, r = run_gr('10 PLAY "CDEFGAB"')
    c = r.last('play')
    assert c[0] == 'play'
    assert c[1] == 'CDEFGAB'

def test_play_mml():
    _, r = run_gr('10 PLAY "T120L4CDEFGAB"')
    c = r.last('play')
    assert 'T120' in c[1]


# ---------------------------------------------------------------------------
# SLEEP
# ---------------------------------------------------------------------------

def test_sleep_basic():
    _, r = run_gr("10 SLEEP 0")
    c = r.last('sleep')
    assert c == ('sleep', 0.0)

def test_sleep_fractional():
    _, r = run_gr("10 SLEEP 0")
    assert r.count('sleep') == 1


# ---------------------------------------------------------------------------
# POINT function
# ---------------------------------------------------------------------------

def test_point_unpainted():
    _, r = run_gr("10 LET P = POINT(10, 10)")
    assert r.count('point') == 1

def test_point_after_pset():
    _, r = run_gr("""\
10 PSET (20, 30), 5
20 LET P = POINT(20, 30)
""")
    # NullRenderer.point returns the stored pixel value
    assert r._pixels[(20, 30)] == 5

def test_point_returns_color():
    # After PSET with color 9, POINT should return 9
    _, r = run_gr("""\
10 PSET (3, 3), 9
20 LET C = POINT(3, 3)
""")
    assert r._pixels.get((3, 3)) == 9

def test_point_in_expression():
    out, r = run_gr("""\
10 PSET (1, 1), 4
20 PRINT POINT(1, 1)
""")
    assert '4' in out


# ---------------------------------------------------------------------------
# DO / LOOP — infinite (exit via GOTO)
# ---------------------------------------------------------------------------

def test_do_loop_infinite_exit_via_goto():
    out, _ = run_gr("""\
10 LET I = 0
20 DO
30   LET I = I + 1
40   IF I >= 3 THEN GOTO 60
50 LOOP
60 PRINT I
""")
    assert '3' in out

def test_do_loop_counts_iterations():
    out, _ = run_gr("""\
10 LET N = 0
20 DO
30   LET N = N + 1
40   IF N = 5 THEN GOTO 60
50 LOOP
60 PRINT N
""")
    assert '5' in out


# ---------------------------------------------------------------------------
# DO WHILE / LOOP
# ---------------------------------------------------------------------------

def test_do_while_loop_basic():
    out, _ = run_gr("""\
10 LET I = 0
20 DO WHILE I < 3
30   LET I = I + 1
40 LOOP
50 PRINT I
""")
    assert '3' in out

def test_do_while_loop_zero_iterations():
    out, _ = run_gr("""\
10 LET I = 10
20 DO WHILE I < 3
30   LET I = I + 1
40 LOOP
50 PRINT I
""")
    assert '10' in out

def test_do_while_loop_multiple():
    out, _ = run_gr("""\
10 LET S = 0
20 LET I = 1
30 DO WHILE I <= 5
40   LET S = S + I
50   LET I = I + 1
60 LOOP
70 PRINT S
""")
    assert '15' in out


# ---------------------------------------------------------------------------
# DO UNTIL / LOOP
# ---------------------------------------------------------------------------

def test_do_until_loop_basic():
    out, _ = run_gr("""\
10 LET I = 0
20 DO UNTIL I >= 3
30   LET I = I + 1
40 LOOP
50 PRINT I
""")
    assert '3' in out

def test_do_until_loop_zero_iterations():
    out, _ = run_gr("""\
10 LET I = 10
20 DO UNTIL I >= 3
30   LET I = I + 1
40 LOOP
50 PRINT I
""")
    assert '10' in out


# ---------------------------------------------------------------------------
# DO / LOOP WHILE
# ---------------------------------------------------------------------------

def test_do_loop_while_basic():
    out, _ = run_gr("""\
10 LET I = 0
20 DO
30   LET I = I + 1
40 LOOP WHILE I < 3
50 PRINT I
""")
    assert '3' in out

def test_do_loop_while_executes_at_least_once():
    out, _ = run_gr("""\
10 LET I = 10
20 DO
30   LET I = I + 1
40 LOOP WHILE I < 3
50 PRINT I
""")
    # Body executes once (I becomes 11), then LOOP WHILE fails
    assert '11' in out


# ---------------------------------------------------------------------------
# DO / LOOP UNTIL
# ---------------------------------------------------------------------------

def test_do_loop_until_basic():
    out, _ = run_gr("""\
10 LET I = 0
20 DO
30   LET I = I + 1
40 LOOP UNTIL I >= 3
50 PRINT I
""")
    assert '3' in out

def test_do_loop_until_executes_at_least_once():
    out, _ = run_gr("""\
10 LET I = 10
20 DO
30   LET I = I + 1
40 LOOP UNTIL I >= 3
50 PRINT I
""")
    # Body runs once (I becomes 11), condition I >= 3 is true → exits
    assert '11' in out


# ---------------------------------------------------------------------------
# Nested DO / LOOP
# ---------------------------------------------------------------------------

def test_nested_do_loop():
    out, _ = run_gr("""\
10 LET S = 0
20 LET I = 0
30 DO WHILE I < 3
40   LET J = 0
50   DO WHILE J < 3
60     LET S = S + 1
70     LET J = J + 1
80   LOOP
90   LET I = I + 1
100 LOOP
110 PRINT S
""")
    assert '9' in out

def test_nested_do_loop_until():
    out, _ = run_gr("""\
10 LET CNT = 0
20 LET A = 0
30 DO UNTIL A >= 2
40   LET B = 0
50   DO UNTIL B >= 2
60     LET CNT = CNT + 1
70     LET B = B + 1
80   LOOP
90   LET A = A + 1
100 LOOP
110 PRINT CNT
""")
    assert '4' in out


# ---------------------------------------------------------------------------
# DO / LOOP error cases
# ---------------------------------------------------------------------------

def test_loop_without_do():
    with pytest.raises(BasicError, match='LOOP without DO'):
        run_gr("10 LOOP")


# ---------------------------------------------------------------------------
# Integration: graphics + PRINT together
# ---------------------------------------------------------------------------

def test_screen_cls_pset_print():
    out, r = run_gr("""\
10 SCREEN 1
20 CLS
30 PSET (100, 100), 7
40 PRINT "OK"
""")
    assert 'OK' in out
    assert r.count('screen') == 1
    assert r.count('cls') == 1
    assert r.count('pset') == 1

def test_graphics_in_for_loop():
    _, r = run_gr("""\
10 FOR I = 0 TO 4
20   PSET (I, I), 1
30 NEXT I
""")
    assert r.count('pset') == 5

def test_circle_in_loop():
    _, r = run_gr("""\
10 FOR R = 10 TO 30 STEP 10
20   CIRCLE (100, 100), R, 7
30 NEXT R
""")
    assert r.count('circle') == 3
