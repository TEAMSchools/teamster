"""Anchors, identities, and the strongest check for a measure.

An anchor is a figure from a source outside the dashboards. An identity is an
equation between measures that must hold. Both are weaker than matching a
dashboard, so neither is ever reported as validated. The module only builds
Cube queries and judges numbers; it runs nothing.
"""

from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from typing import Any, Callable, Literal

from .config import Anchor, Identity

DECIMALS = 9

StrongestCheck = Literal[
    "matches a dashboard", "anchored to a source", "consistent only", "none"
]
Verdict = Literal["validated", "differs", "judge the anchor", "not validated"]


@dataclass(frozen=True)
class Finding:
    kind: Literal["anchor", "identity"]
    measure: str
    detail: str
    left: float
    right: float
    passed: bool


@dataclass(frozen=True)
class CheckResult:
    kind: Literal["dashboard", "anchor", "identity"]
    passed: bool


def _member(view: str, name: str) -> str:
    return f"{view}.{name}"


def _equals(member: str, value: Any) -> dict:
    values = value if isinstance(value, list) else [value]
    return {
        "member": member,
        "operator": "equals",
        "values": [str(v) for v in values],
    }


def anchor_query(anchor: Anchor, view: str, time_dimension: str) -> dict:
    """Build the Cube query that reads an anchor's measure.

    Anchors run on current data; the source figure is frozen at its date.

    Args:
        anchor: The anchor.
        view: The Cube view the measure lives in.
        time_dimension: The view's time dimension member short name.

    Returns:
        A Cube query with the anchor's date range and filters.
    """
    query: dict = {"measures": [_member(view, anchor.measure)]}
    if anchor.date_range:
        query["timeDimensions"] = [
            {
                "dimension": _member(view, time_dimension),
                "dateRange": [str(d) for d in anchor.date_range],
            }
        ]
    query["filters"] = [
        _equals(_member(view, name), value) for name, value in anchor.filters.items()
    ]
    return query


def anchor_finding(anchor: Anchor, cube_value: float) -> Finding:
    """Show an anchor next to Cube's figure.

    Always `passed=False`: the analyst judges every anchor, so there is no
    threshold.

    Args:
        anchor: The anchor.
        cube_value: What Cube returned for the anchor's query.

    Returns:
        A triage finding naming the source, its date, and the difference.
    """
    diff = cube_value - anchor.value
    detail = (
        f"{anchor.source} (as of {anchor.as_of}) says {anchor.value}; "
        f"Cube says {cube_value}; difference {diff:+g}"
    )
    return Finding("anchor", anchor.measure, detail, anchor.value, cube_value, False)


_BINARY: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _parse(expression: str) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"not an arithmetic expression: {expression!r}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(f"only numbers are allowed: {expression!r}")
        elif not isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Name,
                ast.Load,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.USub,
            ),
        ):
            raise ValueError(f"{type(node).__name__} is not allowed in {expression!r}")
    return tree


def _names(tree: ast.Expression) -> list[str]:
    seen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in seen:
            seen.append(node.id)
    return seen


def _eval(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, values)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        return -_eval(node.operand, values)
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](
            _eval(node.left, values), _eval(node.right, values)
        )
    raise ValueError(f"{type(node).__name__} is not allowed")


def identity_query(identity: Identity, cut: dict, view: str) -> dict:
    """Build the one Cube query that tests an identity on one cut.

    Both sides come from the same query, so a fact rebuild cannot fall between
    them and read as a failed identity.

    Args:
        identity: The identity; `right` is arithmetic over measures and numbers.
        cut: Member short names mapped to a value or list of values.
        view: The Cube view; every measure and member is qualified with it.

    Returns:
        A query whose measures are `left` then each measure `right` names.

    Raises:
        ValueError: `right` is not plain arithmetic over measure names and numbers, or
            names no measure.
    """
    names = _names(_parse(identity.right))
    if not names:
        raise ValueError(f"{identity.right!r} names no measure")
    filters = [_equals(_member(view, name), value) for name, value in cut.items()]
    measures = dict.fromkeys(_member(view, n) for n in [identity.left, *names])
    return {"measures": list(measures), "filters": filters}


def identity_finding(
    identity: Identity, left: float, right_values: dict[str, float]
) -> Finding:
    """Evaluate an identity's right side and compare it with the left.

    Args:
        identity: The identity.
        left: Cube's value for the `left` measure.
        right_values: Cube's value for each measure named in `right`.

    Returns:
        A finding that passes when both sides are equal at 9 decimals. A missing
        value or a division by zero fails with the reason in `detail`.

    Raises:
        ValueError: `right` is not plain arithmetic over measure names and numbers.
    """
    tree = _parse(identity.right)
    nan = float("nan")
    missing = [n for n in _names(tree) if right_values.get(n) is None]
    if missing or left is None:
        what = ", ".join(missing) if missing else identity.left
        detail = f"{identity.name}: no value for {what}"
        left_value = nan if left is None else left
        return Finding("identity", identity.name, detail, left_value, nan, False)
    try:
        right = float(_eval(tree, right_values))
    except ZeroDivisionError:
        detail = f"{identity.name}: division by zero in {identity.right}"
        return Finding("identity", identity.name, detail, left, nan, False)

    if not (math.isfinite(left) and math.isfinite(right)):
        detail = (
            f"{identity.name}: not a finite number "
            f"({identity.left} = {left}; {identity.right} = {right})"
        )
        return Finding("identity", identity.name, detail, left, right, False)

    passed = round(left, DECIMALS) == round(right, DECIMALS)
    detail = f"{identity.name}: {identity.left} = {left}; {identity.right} = {right}"
    return Finding("identity", identity.name, detail, left, right, passed)


def strongest_check(measure: str, results: list[CheckResult]) -> StrongestCheck:
    """Name the strongest kind of check a measure has, whether or not it passed.

    Args:
        measure: The measure (kept for the caller's report; results are already
            for this measure).
        results: The measure's check results.

    Returns:
        The label for dashboard, then anchor, then identity, else `none`.
    """
    kinds = {r.kind for r in results}
    if "dashboard" in kinds:
        return "matches a dashboard"
    if "anchor" in kinds:
        return "anchored to a source"
    if "identity" in kinds:
        return "consistent only"
    return "none"


def verdict(results: list[CheckResult]) -> Verdict:
    """Decide whether a measure counts as validated.

    Only a dashboard check validates. An anchor is left to the analyst, and an
    identity or nothing at all is never reported as validated.

    Args:
        results: The measure's check results.

    Returns:
        `validated`, `differs`, `judge the anchor`, or `not validated`.
    """
    strongest = strongest_check("", results)
    if strongest == "matches a dashboard":
        dashboards = [r for r in results if r.kind == "dashboard"]
        return "validated" if all(r.passed for r in dashboards) else "differs"
    if strongest == "anchored to a source":
        return "judge the anchor"
    return "not validated"
