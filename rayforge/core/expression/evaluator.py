import ast
import logging
import math
import operator
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Allowed functions and constants in expressions
MATH_CONTEXT = {
    k: v for k, v in math.__dict__.items() if not k.startswith("__")
}

# AST node types explicitly permitted in user expressions.
#
# The whitelist keeps out constructs that could escape the sandbox
# (imports, comprehensions, lambdas, comprehensions, generators,
#  assignment expressions, async nodes, etc.) while still allowing
# rich expression syntax including attribute access and slicing.
_ALLOWED_EXPR_NODES = frozenset(
    {
        ast.Expression,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.Not,
        ast.IfExp,
        ast.Call,
        ast.Tuple,
        ast.List,
        ast.Attribute,
        ast.Subscript,
        ast.Slice,
        ast.Index,  # py<3.9 only
    }
)

# Names of builtins that must never be reachable from a sandboxed
# expression, even if the user shadows them in the namespace. This
# is a defence-in-depth check on top of the AST whitelist.
_FORBIDDEN_BUILTIN_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
    }
)

_BINARY_OPS: Dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: Dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_CMP_OPS: Dict[type, Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _check_ast(node: ast.AST, allowed: frozenset) -> None:
    for child in ast.walk(node):
        if type(child) not in allowed:
            raise ValueError(
                f"Forbidden AST node: {type(child).__name__}"
            )


def _eval_node(node: ast.AST, namespace: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, namespace)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        try:
            return namespace[node.id]
        except KeyError:
            raise ValueError(f"Unknown name: '{node.id}'")
    if isinstance(node, ast.BinOp):
        op_fn = _BINARY_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(
                f"Unsupported operator: {type(node.op).__name__}"
            )
        return op_fn(
            _eval_node(node.left, namespace),
            _eval_node(node.right, namespace),
        )
    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARY_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(
                f"Unsupported unary: {type(node.op).__name__}"
            )
        return op_fn(_eval_node(node.operand, namespace))
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, namespace) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
        result = False
        for v in values:
            result = result or v
        return result
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, namespace)
        for op, comp in zip(node.ops, node.comparators):
            op_fn = _CMP_OPS.get(type(op))
            if op_fn is None:
                raise ValueError(
                    f"Unsupported comparison: {type(op).__name__}"
                )
            right = _eval_node(comp, namespace)
            if not op_fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, namespace)
        if test:
            return _eval_node(node.body, namespace)
        return _eval_node(node.orelse, namespace)
    if isinstance(node, ast.Call):
        func = _eval_node(node.func, namespace)
        # Reject calls to dangerous builtins even if the user
        # attempted to inject them via the namespace.
        func_name = getattr(func, "__name__", None)
        if func_name in _FORBIDDEN_BUILTIN_NAMES:
            raise ValueError(
                f"Function '{func_name}' is not allowed"
            )
        # Allow calling:
        #   * math functions from MATH_CONTEXT
        #   * callables the user injected via the namespace
        #     (e.g. lambdas, helper functions)
        #   * methods bound to objects in the namespace
        #     (e.g. ``d.isoformat()``)
        # The AST whitelist already blocks access to
        # ``__class__`` and other dunder attrs, so reaching
        # dangerous callables that way is not possible.
        if not callable(func):
            raise ValueError(
                f"Object is not callable: {type(func).__name__}"
            )
        if node.keywords:
            raise ValueError(
                "Keyword arguments are not allowed"
            )
        args = [_eval_node(a, namespace) for a in node.args]
        return func(*args)
    if isinstance(node, ast.Attribute):
        # Reject dunder / private attribute access as a safety
        # measure. Public attribute access on namespace values
        # is permitted (e.g. ``d.year``, ``d.isoformat``).
        if node.attr.startswith("_"):
            raise ValueError(
                f"Attribute access to '{node.attr}' is not allowed"
            )
        value = _eval_node(node.value, namespace)
        return getattr(value, node.attr)
    if isinstance(node, ast.Subscript):
        container = _eval_node(node.value, namespace)
        # ``ast.Index`` wraps the slice on Python < 3.9; unwrap it
        # for compatibility. Newer versions produce the slice
        # directly.
        slice_node = node.slice
        if hasattr(ast, "Index") and isinstance(slice_node, ast.Index):
            slice_node = slice_node.value  # type: ignore[attr-defined]
        key = _eval_node(slice_node, namespace)
        return container[key]
    if isinstance(node, ast.Slice):
        lower = (
            _eval_node(node.lower, namespace)
            if node.lower is not None
            else None
        )
        upper = (
            _eval_node(node.upper, namespace)
            if node.upper is not None
            else None
        )
        step = (
            _eval_node(node.step, namespace)
            if node.step is not None
            else None
        )
        return slice(lower, upper, step)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(e, namespace) for e in node.elts]
    raise ValueError(f"Unsupported node: {type(node).__name__}")


def _ast_evaluate(expr: str, namespace: Dict[str, Any]) -> Any:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}") from e
    _check_ast(tree, _ALLOWED_EXPR_NODES)
    return _eval_node(tree, namespace)


def safe_evaluate(expression: str, context: Dict[str, Any]) -> float:
    """
    Evaluates a mathematical expression string using a specific context
    (variable names) and standard math functions.

    Uses an AST whitelist instead of ``eval()`` so unsafe constructs
    (imports, comprehensions, lambdas, dunder access, etc.) are
    rejected before execution. Public attribute access on objects
    in the namespace is permitted (e.g. ``d.year``, ``d.isoformat()``)
    so that sketcher text templates can use ``{date.today().isoformat()}``
    style expressions. Dunder / private attribute access is blocked.

    Args:
        expression: The string to evaluate (e.g., "width / 2 + 5").
        context: A dictionary of variable names to values.

    Returns:
        float: The calculated value.

    Raises:
        ValueError: If evaluation fails or syntax is invalid.
    """
    if not expression:
        return 0.0

    expr = expression.strip()
    namespace = MATH_CONTEXT.copy()
    namespace.update(context)

    try:
        result = _ast_evaluate(expr, namespace)
        return float(result)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(
            "Failed to evaluate expression '%s': %s", expression, e
        )
        raise ValueError(f"Invalid expression: {e}") from e
