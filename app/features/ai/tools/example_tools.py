"""Example tools for the conversational agent.

Two dependency-free tools so the template's agent works out of the box with
zero extra API keys or services: the current time, and a calculator. Replace
or extend these with tools specific to your project — the pattern (a
``@tool``-decorated function with a clear docstring, which LangChain uses
verbatim as the tool description the LLM sees) is what matters here, not
these two examples themselves.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import UTC, datetime

from langchain_core.tools import tool

# Only these operators are ever evaluated — no names, calls, attribute access,
# subscripts, or comprehensions can reach `_eval_node`, so this is safe to run
# on untrusted (LLM-generated) input, unlike a bare `eval()`.
_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.expr) -> float:
    """Recursively evaluate one node of a parsed arithmetic expression.

    Raises:
        ValueError: The node is not a numeric literal or an allow-listed
            operator — e.g. a name, call, or anything else `eval()` would
            otherwise happily execute.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@tool
def get_current_time() -> str:
    """Return the current date and time in UTC, as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression and return the numeric result.

    Supports ``+ - * / // % **``, parentheses, and unary +/-, e.g.
    ``"(2 + 3) * 4"``. Rejects anything that is not a numeric expression
    (names, function calls, attribute access, etc.).
    """
    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_node(parsed.body)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
        return f"Error: could not evaluate {expression!r} ({exc})"
    return str(int(result) if result.is_integer() else result)
