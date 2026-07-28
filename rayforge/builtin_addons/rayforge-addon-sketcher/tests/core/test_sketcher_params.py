import math

import pytest
from sketcher.core.params import ParameterContext


@pytest.fixture
def params():
    return ParameterContext()


def test_set_get_simple(params):
    params.set("width", 100)
    assert params.get("width") == 100.0


def test_expression_evaluation(params):
    params.set("a", 10)
    params.set("b", 20)
    params.set("c", "a + b")
    assert params.get("c") == 30.0


def test_math_functions(params):
    params.set("x", "sqrt(16)")
    params.set("y", "pi")
    assert params.get("x") == 4.0
    assert params.get("y") == pytest.approx(math.pi)


def test_dependency_resolution_order(params):
    # 'b' depends on 'a', but 'b' is defined first (conceptually)
    # The solver iterates, so order of set() shouldn't strictly matter
    # if evaluate() is called after.
    params.set("b", "a * 2")
    params.set("a", 10)
    assert params.get("b") == 20.0


def test_chained_dependencies(params):
    params.set("val1", 10)
    params.set("val2", "val1 + 5")  # 15
    params.set("val3", "val2 * 2")  # 30
    assert params.get("val3") == 30.0


def test_dirty_flag_logic(params):
    params.set("x", 10)
    assert params.get("x") == 10.0
    # Modifying a dependency should mark dirty and re-eval
    params.set("x", 20)
    params.set("y", "x + 5")
    assert params.get("y") == 25.0


def test_missing_dependency_safe_fail(params):
    # Should not crash, returns 0.0 or stays unresolved
    params.set("z", "non_existent + 5")
    assert params.get("z") == 0.0


def test_evaluate_arbitrary_string(params):
    params.set("w", 50)
    result = params.evaluate("w / 2")
    assert result == 25.0


def test_circular_dependency_protection(params):
    """
    Test that circular dependencies don't cause infinite recursion/hanging.
    """
    params.set("a", "b")
    params.set("b", "a")

    # This should evaluate without crashing (likely returning 0.0 or failing
    # resolution). The current implementation limits passes to len(exprs),
    # so it is safe.
    assert params.get("a") == 0.0
    assert params.get("b") == 0.0


def test_parameter_syntax_error(params):
    """Test graceful handling of bad math strings."""
    params.set("bad", "sqrt(")  # Incomplete syntax
    assert params.get("bad") == 0.0


def test_parameter_overwrite(params):
    """Test overwriting a parameter updates dependents."""
    params.set("base", 10)
    params.set("res", "base * 2")
    assert params.get("res") == 20.0

    params.set("base", 5)
    assert params.get("res") == 10.0


def test_parameter_context_serialization_round_trip(params):
    """Tests to_dict and from_dict for ParameterContext."""
    params.set("width", 100)
    params.set("height", "width / 2")
    params.set("depth", "sqrt(width)")

    data = params.to_dict()
    assert data == {
        "expressions": {
            "width": "100",
            "height": "width / 2",
            "depth": "sqrt(width)",
        }
    }

    new_params = ParameterContext.from_dict(data)

    # Check that expressions were loaded and evaluate correctly
    assert new_params.get("width") == 100.0
    assert new_params.get("height") == 50.0
    assert new_params.get("depth") == 10.0


def test_get_all_values(params):
    """Test getting a dictionary of all evaluated parameters."""
    params.set("a", 10)
    params.set("b", "a * 2")
    params.set("c", "sqrt(a + 6)")  # sqrt(16) = 4

    expected = {"a": 10.0, "b": 20.0, "c": 4.0}
    result = params.get_all_values()
    assert result == expected

    # Ensure it's a copy and not a reference to the internal cache
    result["a"] = 999
    assert params.get("a") == 10.0


def test_get_with_default(params):
    """Test the default value functionality of get()."""
    params.set("exists", 42)
    # The default for `get` in the method signature is 0.0
    assert params.get("does_not_exist") == 0.0
    # Test providing a custom default value
    assert params.get("does_not_exist_either", default=-1.0) == -1.0
    # Test that existing keys don't use the provided default
    assert params.get("exists", default=99.0) == 42.0


# ---------------------------------------------------------------------------
# Security regression tests
#
# ParameterContext historically used ``eval()`` with ``{"__builtins__": None}``
# as the "sandbox". That sandbox is bypassable via attribute access on
# objects in the namespace (e.g. ``().__class__.__mro__[1].__subclasses__()``).
# The class now uses the AST-whitelisted ``safe_evaluate`` from
# ``rayforge.core.expression``, which rejects dunder / private attribute
# access. These tests pin that property.
# ---------------------------------------------------------------------------


class TestParameterContextSandboxHardening:
    """
    Regression tests ensuring that the AST-hardened
    ``safe_evaluate`` blocks sandbox-escape attempts via
    ``__class__``/``__mro__``/``__subclasses__`` etc.
    """

    def test_dunder_attribute_blocked(self, params):
        # The classic Python sandbox escape — should be blocked.
        params.set("evil", "().__class__")
        assert params.get("evil") == 0.0

    def test_dunder_mro_blocked(self, params):
        params.set("evil", "().__class__.__mro__")
        assert params.get("evil") == 0.0

    def test_dunder_subclasses_blocked(self, params):
        # A more complete attack vector
        params.set("evil", "().__class__.__base__.__subclasses__()")
        assert params.get("evil") == 0.0

    def test_builtins_blocked(self, params):
        # ``__builtins__`` is not accessible via attribute (would
        # normally allow reaching ``eval``/``__import__``)
        params.set("evil", "(1).__class__.__init__.__globals__")
        assert params.get("evil") == 0.0

    def test_arbitrary_eval_blocked(self, params):
        params.set("evil", "eval('1+1')")
        assert params.get("evil") == 0.0

    def test_arbitrary_exec_blocked(self, params):
        params.set("evil", "exec('print(1)')")
        assert params.get("evil") == 0.0

    def test_import_blocked(self, params):
        params.set("evil", "__import__('os')")
        assert params.get("evil") == 0.0

    def test_lambda_blocked(self, params):
        params.set("evil", "(lambda: 1)()")
        assert params.get("evil") == 0.0

    def test_comprehension_blocked(self, params):
        params.set("evil", "[x for x in range(10)]")
        assert params.get("evil") == 0.0

    def test_attribute_access_on_string_blocked(self, params):
        # Even if a string slips into the cache (e.g. as a default
        # value from a sketch file), attribute access is blocked.
        params.set("name", "hello")
        params.set("evil", "name.upper()")
        assert params.get("evil") == 0.0

    def test_attribute_access_on_int_blocked(self, params):
        params.set("n", 42)
        params.set("evil", "n.bit_length()")
        assert params.get("evil") == 0.0

    def test_arbitrary_evaluate_blocked(self, params):
        # ``evaluate()`` uses the same hardening
        assert params.evaluate("().__class__") == 0.0
        assert params.evaluate("__import__('os')") == 0.0

    def test_arbitrary_evaluate_attribute_blocked(self, params):
        params.set("name", "hello")
        assert params.evaluate("name.upper()") == 0.0

    def test_legitimate_math_still_works(self, params):
        # Sanity check: the hardening didn't break normal usage.
        params.set("a", 10)
        params.set("b", 20)
        params.set("c", "a + b * 2")  # 10 + 40 = 50
        assert params.get("c") == 50.0

    def test_legitimate_math_function_still_works(self, params):
        params.set("x", "sqrt(144)")
        assert params.get("x") == 12.0

    def test_legitimate_ternary_still_works(self, params):
        params.set("flag", 1)
        params.set("result", "1 if flag > 0 else -1")
        assert params.get("result") == 1.0
