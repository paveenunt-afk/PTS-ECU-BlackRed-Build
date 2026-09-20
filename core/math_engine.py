from __future__ import annotations

import ast
import operator


class MathExpressionError(ValueError):
    pass


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class SafeExpression:
    def __init__(self, expression: str | None):
        self.expression = (expression or "X").strip() or "X"
        try:
            self.tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as exc:
            raise MathExpressionError(f"Invalid expression: {self.expression}") from exc
        self._validate(self.tree)

    def _validate(self, node: ast.AST) -> None:
        if isinstance(node, ast.Expression):
            self._validate(node.body)
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return
        if isinstance(node, ast.Name) and node.id == "X":
            return
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            self._validate(node.left)
            self._validate(node.right)
            return
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            self._validate(node.operand)
            return
        raise MathExpressionError(f"Unsupported expression construct: {type(node).__name__}")

    def evaluate(self, X: float | int) -> float:
        return float(self._eval(self.tree.body, float(X)))

    def _eval(self, node: ast.AST, X: float) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return X
        if isinstance(node, ast.BinOp):
            fn = _BIN_OPS[type(node.op)]
            try:
                return float(fn(self._eval(node.left, X), self._eval(node.right, X)))
            except (ZeroDivisionError, OverflowError) as exc:
                raise MathExpressionError(str(exc)) from exc
        if isinstance(node, ast.UnaryOp):
            fn = _UNARY_OPS[type(node.op)]
            return float(fn(self._eval(node.operand, X)))
        raise MathExpressionError(f"Unsupported expression construct: {type(node).__name__}")


def apply_quick_formula(value: float, formula: str) -> float:
    text = formula.strip()
    if not text:
        raise MathExpressionError("Quick formula is empty")
    first = text[0]
    if first in "+-*/" and len(text) > 1:
        rhs = SafeExpression(text[1:]).evaluate(0)
        if first == "+":
            return float(value + rhs)
        if first == "-":
            return float(value - rhs)
        if first == "*":
            return float(value * rhs)
        if rhs == 0:
            raise MathExpressionError("Division by zero")
        return float(value / rhs)
    try:
        return float(text)
    except ValueError as exc:
        raise MathExpressionError(f"Invalid quick formula: {formula}") from exc
