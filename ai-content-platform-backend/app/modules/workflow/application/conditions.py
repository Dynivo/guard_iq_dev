"""Pluggable condition evaluation."""

from __future__ import annotations

import ast
import operator
from typing import Any

from app.modules.workflow.domain.models import (
    ConditionType,
    NodeCondition,
    WorkflowContext,
)


_BIN_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class DefaultConditionEvaluator:
    """Supports always / success / failure / expression (safe subset)."""

    def matches(
        self,
        condition: NodeCondition,
        context: WorkflowContext,
        *,
        last_success: bool,
    ) -> bool:
        if condition.type == ConditionType.ALWAYS:
            return True
        if condition.type == ConditionType.SUCCESS:
            return last_success
        if condition.type == ConditionType.FAILURE:
            return not last_success
        if condition.type == ConditionType.EXPRESSION:
            if not condition.expression:
                return False
            return self._eval_expression(condition.expression, context)
        return False

    def _eval_expression(self, expression: str, context: WorkflowContext) -> bool:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            return False
        return bool(self._eval_node(tree.body, context))

    def _eval_node(self, node: ast.AST, context: WorkflowContext) -> Any:
        if isinstance(node, ast.Expression):
            return self._eval_node(node.body, context)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "data":
                return context.data
            if node.id in context.data:
                return context.data[node.id]
            raise ValueError(f"Unknown name: {node.id}")
        if isinstance(node, ast.Attribute):
            value = self._eval_node(node.value, context)
            if isinstance(value, dict):
                return value.get(node.attr)
            return getattr(value, node.attr)
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value, context)
            key = self._eval_node(node.slice, context)
            return value[key]
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            result = True
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                op_fn = _BIN_OPS.get(type(op))
                if op_fn is None:
                    raise ValueError("Unsupported comparison")
                right = self._eval_node(comparator, context)
                result = bool(op_fn(left, right))
                if not result:
                    return False
                left = right
            return result
        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, context) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand, context)
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")
