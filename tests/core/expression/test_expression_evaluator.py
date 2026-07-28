import math

import pytest

from rayforge.core.expression import evaluator


def test_evaluate_simple_arithmetic():
    """Tests basic math operations without context."""
    assert evaluator.safe_evaluate("10 + 5", {}) == 15.0
    assert evaluator.safe_evaluate("10 * (4 - 2)", {}) == 20.0


def test_evaluate_with_context_variables():
    """Tests evaluation using variables from the context."""
    context = {"width": 100.0, "height": 50}
    assert evaluator.safe_evaluate("width / 2", context) == 50.0
    assert evaluator.safe_evaluate("width + height", context) == 150.0


def test_evaluate_with_math_functions():
    """Tests that standard math functions are available."""
    assert evaluator.safe_evaluate("pi", {}) == pytest.approx(math.pi)
    assert evaluator.safe_evaluate("sin(pi / 2)", {}) == pytest.approx(1.0)
    assert evaluator.safe_evaluate("sqrt(16)", {}) == 4.0


def test_evaluate_empty_string():
    """An empty string should evaluate to 0.0."""
    assert evaluator.safe_evaluate("", {}) == 0.0


def test_evaluate_context_overrides_math():
    """Tests that context variables take precedence over built-in math."""
    context = {"pi": 3.0, "sin": 10}
    assert evaluator.safe_evaluate("pi", context) == 3.0
    assert evaluator.safe_evaluate("sin * 2", context) == 20.0


def test_evaluate_raises_value_error_on_failure():
    """Ensures that evaluation failures raise a `ValueError`."""
    # Syntax error
    with pytest.raises(ValueError, match="Invalid expression"):
        evaluator.safe_evaluate("10 + * 5", {})

    # Unknown variable
    with pytest.raises(ValueError, match="Invalid expression"):
        evaluator.safe_evaluate("width + 5", {})

    # Type error
    with pytest.raises(ValueError, match="Invalid expression"):
        evaluator.safe_evaluate("'a' + 5", {})


def test_evaluate_prevents_builtin_access():
    """
    Crucially, tests that `eval` is properly sandboxed and cannot access
    dangerous built-in functions.
    """
    with pytest.raises(ValueError, match="Invalid expression"):
        evaluator.safe_evaluate("__import__('os')", {})

    with pytest.raises(ValueError, match="Invalid expression"):
        evaluator.safe_evaluate("open('file.txt')", {})


class TestASTSecurityHardening:
    """
    Security regression tests for the AST-whitelist evaluator.

    Each test verifies that a known attack vector raises ``ValueError``
    instead of executing arbitrary code.  These tests MUST all raise
    (i.e. the attack must be BLOCKED).
    """

    def _blocked(self, expr: str, ctx: dict = None):
        """Assert that *expr* is blocked by the evaluator."""
        with pytest.raises(
            (ValueError, KeyError),
            match=".*",
        ):
            evaluator.safe_evaluate(expr, ctx or {})

    def test_attribute_access_blocked(self):
        self._blocked("a.__class__", {"a": 1})

    def test_dunder_mro_blocked(self):
        self._blocked("().__class__.__mro__")

    def test_import_via_builtin_blocked(self):
        self._blocked("__import__('os')")

    def test_open_function_blocked(self):
        self._blocked("open('/etc/passwd')")

    def test_getattr_blocked(self):
        self._blocked("getattr(a, '__class__')", {"a": 1})

    def test_lambda_blocked(self):
        self._blocked("(lambda: 1)()")

    def test_list_comprehension_blocked(self):
        self._blocked("[x for x in range(10)]")

    def test_generator_blocked(self):
        self._blocked("(x for x in range(10))")

    def test_dict_comprehension_blocked(self):
        self._blocked("{k: v for k, v in items}", {"items": []})

    def test_subscript_allowed(self):
        # Subscript is now allowed for legitimate slicing
        # (e.g. ``uuid4()[:8]`` in text templates). The
        # ``ast.Slice`` node + key allowlist mean we can only
        # read public container values, not write to them.
        # ``a[0]`` is a legitimate read.
        result = evaluator.safe_evaluate("a[0]", {"a": [1, 2, 3]})
        assert result == 1.0

    def test_subscript_dunder_blocked(self):
        # ``a.__class__`` must still be blocked because the
        # attribute name starts with ``_``.
        self._blocked("a.__class__", {"a": [1, 2, 3]})

    def test_attribute_public_allowed(self):
        # Public attribute access (e.g. ``d.year``) is allowed
        # for namespace values like ``datetime.date``.
        import datetime
        d = datetime.date(2026, 1, 1)
        result = evaluator.safe_evaluate("d.year", {"d": d})
        assert result == 2026.0

    def test_attribute_method_call_allowed(self):
        # Method calls on public attributes are allowed for
        # objects in the namespace (e.g. ``d.isoformat()``).
        # Note: ``safe_evaluate`` is for math expressions and
        # will raise ``ValueError`` if the result is not
        # numeric. The ``ExpressionMap`` (template use case)
        # does not coerce to float and works with any type.
        import datetime
        d = datetime.date(2026, 1, 1)
        # Numeric attribute via method call: ``str(d.year)`` is
        # the kind of mixed expression a template might use.
        result = evaluator._ast_evaluate("d.isoformat()", {"d": d})
        assert result == "2026-01-01"

    def test_augmented_assignment_blocked(self):
        self._blocked("x += 1")

    def test_walrus_operator_blocked(self):
        self._blocked("(y := 5)")

    def test_starred_blocked(self):
        self._blocked("*a", {"a": [1, 2]})

    def test_non_math_function_call_blocked(self):
        self._blocked("print('hello')")

    def test_exec_string_blocked(self):
        self._blocked("exec('import os')")

    def test_eval_string_blocked(self):
        self._blocked("eval('1+1')")


class TestASTLegitimateExpressions:
    """
    Regression tests ensuring that legitimate math expressions that
    were valid before the AST hardening continue to work correctly.
    """

    def test_basic_arithmetic(self):
        assert evaluator.safe_evaluate("1 + 2 * 3", {}) == 7.0

    def test_parentheses(self):
        assert evaluator.safe_evaluate("(1 + 2) * 3", {}) == 9.0

    def test_float_division(self):
        assert evaluator.safe_evaluate("10 / 4", {}) == 2.5

    def test_floor_division(self):
        assert evaluator.safe_evaluate("10 // 3", {}) == 3.0

    def test_modulo(self):
        assert evaluator.safe_evaluate("10 % 3", {}) == 1.0

    def test_power(self):
        assert evaluator.safe_evaluate("2 ** 8", {}) == 256.0

    def test_unary_minus(self):
        assert evaluator.safe_evaluate("-width", {"width": 5}) == -5.0

    def test_context_variable(self):
        assert evaluator.safe_evaluate(
            "width * height", {"width": 4, "height": 5}
        ) == 20.0

    def test_math_function_sqrt(self):
        assert evaluator.safe_evaluate("sqrt(25)", {}) == pytest.approx(5.0)

    def test_math_function_abs(self):
        assert evaluator.safe_evaluate("fabs(-3)", {}) == pytest.approx(3.0)

    def test_math_constant_pi(self):
        result = evaluator.safe_evaluate("pi", {})
        assert result == pytest.approx(math.pi)

    def test_ternary_if(self):
        assert evaluator.safe_evaluate(
            "1 if x > 0 else -1", {"x": 5}
        ) == 1.0

    def test_comparison(self):
        assert evaluator.safe_evaluate("x > 0", {"x": 5}) == 1.0

    def test_nested_math_calls(self):
        result = evaluator.safe_evaluate("sqrt(pow(3, 2) + pow(4, 2))", {})
        assert result == pytest.approx(5.0)
