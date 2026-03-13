"""
Tests for the BASIC interpreter — statements, operators, and built-in functions.
"""

import math
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from basic.interpreter import BasicError, Interpreter


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run(source: str) -> str:
    """Load and run a BASIC program, returning captured stdout."""
    interp = Interpreter()
    interp.load(source)
    buf = StringIO()
    with patch("sys.stdout", buf):
        interp.run()
    return buf.getvalue()


# ===========================================================================
# Statements
# ===========================================================================

class TestPrint:
    def test_string(self):
        assert run('10 PRINT "hello"') == "hello\n"

    def test_number(self):
        assert run("10 PRINT 42") == "42\n"

    def test_expression(self):
        assert run("10 PRINT 3 + 4") == "7\n"

    def test_semicolon_suppresses_newline(self):
        assert run('10 PRINT "A";\n20 PRINT "B"') == "AB\n"

    def test_multiple_items_semicolon(self):
        assert run('10 PRINT "X"; "Y"') == "XY\n"

    def test_empty_print(self):
        assert run("10 PRINT") == "\n"


class TestLet:
    def test_numeric_assignment(self):
        assert run("10 LET X = 7\n20 PRINT X") == "7\n"

    def test_string_assignment(self):
        assert run('10 LET A$ = "hi"\n20 PRINT A$') == "hi\n"

    def test_expression_assignment(self):
        assert run("10 LET Y = 3 * 4\n20 PRINT Y") == "12\n"


class TestIfThenElse:
    def test_then_branch_taken(self):
        assert run("10 IF 1 = 1 THEN PRINT \"yes\"") == "yes\n"

    def test_then_branch_skipped(self):
        assert run("10 IF 1 = 2 THEN PRINT \"yes\"") == ""

    def test_else_branch_taken(self):
        assert run('10 IF 1 = 2 THEN PRINT "yes" ELSE PRINT "no"') == "no\n"

    def test_else_branch_skipped(self):
        assert run('10 IF 1 = 1 THEN PRINT "yes" ELSE PRINT "no"') == "yes\n"


class TestGoto:
    def test_jump_forward(self):
        assert run("10 GOTO 30\n20 PRINT \"skip\"\n30 PRINT \"ok\"") == "ok\n"


class TestGosubReturn:
    def test_basic_gosub(self):
        src = (
            "10 GOSUB 100\n"
            "20 PRINT \"back\"\n"
            "30 END\n"
            "100 PRINT \"sub\"\n"
            "110 RETURN\n"
        )
        assert run(src) == "sub\nback\n"


class TestForNext:
    def test_simple_loop(self):
        src = "10 FOR I = 1 TO 3\n20 PRINT I\n30 NEXT I"
        assert run(src) == "1\n2\n3\n"

    def test_step_positive(self):
        src = "10 FOR I = 0 TO 6 STEP 2\n20 PRINT I\n30 NEXT I"
        assert run(src) == "0\n2\n4\n6\n"

    def test_step_negative(self):
        src = "10 FOR I = 3 TO 1 STEP -1\n20 PRINT I\n30 NEXT I"
        assert run(src) == "3\n2\n1\n"

    def test_skip_when_start_exceeds_end(self):
        src = "10 FOR I = 5 TO 1\n20 PRINT I\n30 NEXT I\n40 PRINT \"done\""
        assert run(src) == "done\n"


class TestDim:
    def test_array_store_and_retrieve(self):
        src = (
            "10 DIM A(5)\n"
            "20 LET A(1) = 99\n"
            "30 PRINT A(1)\n"
        )
        assert run(src) == "99\n"


class TestDataReadRestore:
    def test_read_values(self):
        src = (
            "10 DATA 1, 2, 3\n"
            "20 READ A\n"
            "30 READ B\n"
            "40 PRINT A + B\n"
        )
        assert run(src) == "3\n"

    def test_restore_resets_pointer(self):
        src = (
            "10 DATA 7\n"
            "20 READ X\n"
            "30 RESTORE\n"
            "40 READ Y\n"
            "50 PRINT X + Y\n"
        )
        assert run(src) == "14\n"


class TestRem:
    def test_comment_ignored(self):
        src = "10 REM this is a comment\n20 PRINT \"ok\""
        assert run(src) == "ok\n"


class TestEnd:
    def test_end_stops_execution(self):
        src = "10 PRINT \"a\"\n20 END\n30 PRINT \"b\""
        assert run(src) == "a\n"


class TestStop:
    def test_stop_halts_execution(self):
        src = "10 PRINT \"a\"\n20 STOP\n30 PRINT \"b\""
        assert run(src) == "a\n"


# ===========================================================================
# Operators
# ===========================================================================

class TestArithmeticOperators:
    def test_add(self):
        assert run("10 PRINT 3 + 4") == "7\n"

    def test_subtract(self):
        assert run("10 PRINT 10 - 3") == "7\n"

    def test_multiply(self):
        assert run("10 PRINT 3 * 4") == "12\n"

    def test_divide(self):
        assert run("10 PRINT 10 / 2") == "5\n"

    def test_exponent(self):
        assert run("10 PRINT 2 ^ 8") == "256\n"

    def test_mod(self):
        assert run("10 PRINT 10 MOD 3") == "1\n"

    def test_unary_minus(self):
        assert run("10 PRINT -5") == "-5\n"

    def test_division_by_zero(self):
        with pytest.raises(BasicError):
            run("10 PRINT 1 / 0")


class TestComparisonOperators:
    def test_eq_true(self):
        assert run("10 PRINT (2 = 2)") == "-1\n"

    def test_eq_false(self):
        assert run("10 PRINT (2 = 3)") == "0\n"

    def test_neq(self):
        assert run("10 PRINT (2 <> 3)") == "-1\n"

    def test_lt(self):
        assert run("10 PRINT (1 < 2)") == "-1\n"

    def test_gt(self):
        assert run("10 PRINT (2 > 1)") == "-1\n"

    def test_lte(self):
        assert run("10 PRINT (2 <= 2)") == "-1\n"

    def test_gte(self):
        assert run("10 PRINT (3 >= 2)") == "-1\n"


class TestLogicalOperators:
    def test_and_true(self):
        assert run("10 PRINT (1 AND 1)") == "-1\n"

    def test_and_false(self):
        assert run("10 PRINT (1 AND 0)") == "0\n"

    def test_or_true(self):
        assert run("10 PRINT (0 OR 1)") == "-1\n"

    def test_or_false(self):
        assert run("10 PRINT (0 OR 0)") == "0\n"

    def test_not_true(self):
        assert run("10 PRINT NOT 0") == "-1\n"

    def test_not_false(self):
        assert run("10 PRINT NOT 1") == "0\n"


# ===========================================================================
# Built-in Functions
# ===========================================================================

class TestFuncInt:
    def test_floor_positive(self):
        assert run("10 PRINT INT(3.9)") == "3\n"

    def test_floor_negative(self):
        assert run("10 PRINT INT(-3.1)") == "-4\n"


class TestFuncAbs:
    def test_positive(self):
        assert run("10 PRINT ABS(5)") == "5\n"

    def test_negative(self):
        assert run("10 PRINT ABS(-5)") == "5\n"


class TestFuncSqr:
    def test_perfect_square(self):
        assert run("10 PRINT SQR(9)") == "3\n"

    def test_negative_raises(self):
        with pytest.raises(BasicError):
            run("10 PRINT SQR(-1)")


class TestFuncRnd:
    def test_returns_float_in_range(self):
        src = "10 LET R = RND(1)\n20 PRINT (R >= 0 AND R < 1)"
        assert run(src) == "-1\n"


class TestFuncLen:
    def test_length(self):
        assert run('10 PRINT LEN("hello")') == "5\n"

    def test_empty_string(self):
        assert run('10 PRINT LEN("")') == "0\n"


class TestFuncLeftRight:
    def test_left(self):
        assert run('10 PRINT LEFT$("ABCDE", 3)') == "ABC\n"

    def test_left_zero(self):
        assert run('10 PRINT LEFT$("ABCDE", 0)') == "\n"

    def test_right(self):
        assert run('10 PRINT RIGHT$("ABCDE", 3)') == "CDE\n"

    def test_right_zero(self):
        assert run('10 PRINT RIGHT$("ABCDE", 0)') == "\n"


class TestFuncMid:
    def test_mid_two_args(self):
        assert run('10 PRINT MID$("ABCDE", 2)') == "BCDE\n"

    def test_mid_three_args(self):
        assert run('10 PRINT MID$("ABCDE", 2, 3)') == "BCD\n"

    def test_mid_one_based(self):
        assert run('10 PRINT MID$("HELLO", 1, 1)') == "H\n"


class TestFuncStr:
    def test_integer(self):
        assert run("10 PRINT STR$(42)") == "42\n"

    def test_float(self):
        assert run("10 PRINT STR$(3.14)") == "3.14\n"


class TestFuncVal:
    def test_integer_string(self):
        assert run('10 PRINT VAL("42")') == "42\n"

    def test_float_string(self):
        assert run('10 PRINT VAL("3.5")') == "3.5\n"

    def test_non_numeric_returns_zero(self):
        assert run('10 PRINT VAL("abc")') == "0\n"


class TestFuncChrAsc:
    def test_chr(self):
        assert run("10 PRINT CHR$(65)") == "A\n"

    def test_asc(self):
        assert run('10 PRINT ASC("A")') == "65\n"

    def test_asc_empty_raises(self):
        with pytest.raises(BasicError):
            run('10 PRINT ASC("")')


class TestFuncSgn:
    def test_positive(self):
        assert run("10 PRINT SGN(5)") == "1\n"

    def test_negative(self):
        assert run("10 PRINT SGN(-3)") == "-1\n"

    def test_zero(self):
        assert run("10 PRINT SGN(0)") == "0\n"


class TestFuncFix:
    def test_truncate_positive(self):
        assert run("10 PRINT FIX(3.9)") == "3\n"

    def test_truncate_negative(self):
        # FIX truncates toward zero (unlike INT which floors)
        assert run("10 PRINT FIX(-3.9)") == "-3\n"


class TestFuncLog:
    def test_log_e(self):
        result = run("10 PRINT LOG(1)")
        assert float(result.strip()) == pytest.approx(0.0)

    def test_log_negative_raises(self):
        with pytest.raises(BasicError):
            run("10 PRINT LOG(-1)")

    def test_log_zero_raises(self):
        with pytest.raises(BasicError):
            run("10 PRINT LOG(0)")


class TestFuncExp:
    def test_exp_zero(self):
        result = run("10 PRINT EXP(0)")
        assert float(result.strip()) == pytest.approx(1.0)

    def test_exp_one(self):
        result = run("10 PRINT EXP(1)")
        assert float(result.strip()) == pytest.approx(math.e)


class TestFuncTrig:
    def test_sin_zero(self):
        result = run("10 PRINT SIN(0)")
        assert float(result.strip()) == pytest.approx(0.0)

    def test_cos_zero(self):
        result = run("10 PRINT COS(0)")
        assert float(result.strip()) == pytest.approx(1.0)

    def test_tan_zero(self):
        result = run("10 PRINT TAN(0)")
        assert float(result.strip()) == pytest.approx(0.0)

    def test_atn_zero(self):
        result = run("10 PRINT ATN(0)")
        assert float(result.strip()) == pytest.approx(0.0)

    def test_atn_one(self):
        result = run("10 PRINT ATN(1)")
        assert float(result.strip()) == pytest.approx(math.pi / 4)
