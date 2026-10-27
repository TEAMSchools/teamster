import math

import pytest
from cube_validation.checks import (
    CheckResult,
    anchor_finding,
    anchor_query,
    identity_finding,
    identity_queries,
    strongest_check,
    verdict,
)
from cube_validation.config import Anchor, Identity

ANCHOR = Anchor(
    measure="ada",
    value=0.95,
    source="State report",
    as_of="2025-06-30",
    date_range=["2024-09-01", "2025-06-30"],
    filters={"region": "Newark", "grade": [5, 6]},
)


def test_anchor_query_shape():
    q = anchor_query(ANCHOR, "attendance", "attendance_date")
    assert q["measures"] == ["attendance.ada"]
    assert q["timeDimensions"] == [
        {
            "dimension": "attendance.attendance_date",
            "dateRange": ["2024-09-01", "2025-06-30"],
        }
    ]
    region = {"member": "attendance.region", "operator": "equals", "values": ["Newark"]}
    grade = {"member": "attendance.grade", "operator": "equals", "values": ["5", "6"]}
    assert region in q["filters"]
    assert grade in q["filters"]


def test_anchor_difference_is_always_triaged():
    same = anchor_finding(ANCHOR, 0.95)
    off = anchor_finding(ANCHOR, 0.90)
    for f in (same, off):
        assert f.kind == "anchor"
        assert f.passed is False
        assert "State report" in f.detail
        assert "2025-06-30" in f.detail
    assert (off.left, off.right) == (0.95, 0.90)
    assert "0.05" in off.detail


IDENT = Identity(name="split", left="total", right="a + b")


def test_identity_queries():
    left, right = identity_queries(
        IDENT, {"region": ["Newark", "Camden"], "year": 2025}, "v"
    )
    assert left["measures"] == ["v.total"]
    assert sorted(right["measures"]) == ["v.a", "v.b"]
    for q in (left, right):
        region = {
            "member": "v.region",
            "operator": "equals",
            "values": ["Newark", "Camden"],
        }
        year = {"member": "v.year", "operator": "equals", "values": ["2025"]}
        assert region in q["filters"]
        assert year in q["filters"]


def test_identity_queries_with_view():
    left, _ = identity_queries(IDENT, {"year": 2025}, view="v")
    assert left["measures"] == ["v.total"]
    assert left["filters"][0]["member"] == "v.year"


def test_identity_queries_reject_expression_without_measures():
    with pytest.raises(ValueError):
        identity_queries(Identity(name="x", left="t", right="1+2"), {}, "v")


def test_identity_non_finite_fails():
    i = Identity(name="x", left="t", right="a")
    inf = float("inf")
    f = identity_finding(i, inf, {"a": inf})
    assert not f.passed
    assert "finite" in f.detail
    assert not identity_finding(i, 1.0, {"a": float("nan")}).passed


def test_identity_zero_left_is_kept_when_right_missing():
    i = Identity(name="x", left="t", right="a")
    f = identity_finding(i, 0.0, {"a": None})  # type: ignore[dict-item]
    assert f.left == 0.0


def test_identity_passes_at_9_decimals():
    assert identity_finding(IDENT, 3.0, {"a": 1.0, "b": 2.0 + 1e-11}).passed
    assert not identity_finding(IDENT, 3.0, {"a": 1.0, "b": 2.001}).passed


def test_identity_evaluator_ops():
    i = Identity(name="x", left="t", right="-(a - b) * 2 / 4")
    assert identity_finding(i, 0.5, {"a": 1.0, "b": 2.0}).passed


@pytest.mark.parametrize(
    "expr",
    ["open('x')", "a ** 2", "a.real", "f(a)", "a if b else a", "'s'", "[a]"],
)
def test_identity_rejects_unsafe(expr):
    ident = Identity(name="x", left="t", right=expr)
    with pytest.raises(ValueError):
        identity_finding(ident, 1.0, {"a": 1.0, "b": 1.0})


def test_identity_division_by_zero_and_none_fail_with_detail():
    i = Identity(name="x", left="t", right="a / b")
    zero = identity_finding(i, 1.0, {"a": 1.0, "b": 0.0})
    assert not zero.passed
    assert "zero" in zero.detail.lower()
    assert math.isnan(zero.right)
    none = identity_finding(i, 1.0, {"a": 1.0, "b": None})  # type: ignore[dict-item]
    assert not none.passed
    assert "b" in none.detail


def test_strongest_check_order():
    d = CheckResult("dashboard", True)
    a = CheckResult("anchor", True)
    i = CheckResult("identity", True)
    assert strongest_check("m", [i, a, d]) == "matches a dashboard"
    assert strongest_check("m", [i, a]) == "anchored to a source"
    assert strongest_check("m", [i]) == "consistent only"
    assert strongest_check("m", []) == "none"
    assert (
        strongest_check("m", [CheckResult("dashboard", False)]) == "matches a dashboard"
    )


def test_consistent_only_is_not_validated():
    assert verdict([CheckResult("identity", True)]) == "not validated"
    assert verdict([]) == "not validated"
    assert verdict([CheckResult("anchor", True)]) == "judge the anchor"
    assert (
        verdict([CheckResult("dashboard", True), CheckResult("anchor", False)])
        == "validated"
    )
    assert (
        verdict([CheckResult("dashboard", True), CheckResult("dashboard", False)])
        == "differs"
    )
