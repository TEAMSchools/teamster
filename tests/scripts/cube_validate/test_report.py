"""Report rendering: small cells, trust verdict, held findings."""

import datetime as dt

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, config, report, rows


def test_small_hides_counts_under_ten():
    assert (
        report.small(0) == "0"
        and report.small(7) == "<10"
        and report.small(1204) == "1,204"
    )


def test_trust_reads_invariants_then_hand_checks():
    ok = {"a": True}
    assert report.trust({"a": False}, {}).startswith("Not trusted: invariant broken: a")
    assert report.trust(ok, {}).startswith("Pending: no hand checks")
    assert report.trust(ok, {"C1": "pending", "C2": "agree"}).startswith(
        "Pending: 1 of 2"
    )
    assert report.trust(ok, {"C1": "disagree"}).startswith("Not trusted: 1 hand check")
    assert report.trust(ok, {"C1": "agree"}).startswith("Trusted for this run")


def test_render_holds_findings_and_suppresses_small_cells():
    rr = rows.RowsResult(
        totals={"tableau": 12, "cube": 13, "joined": 13},
        buckets=[
            {
                "region": "Newark",
                "month": dt.date(2026, 10, 1),
                "base": "cube_only",
                "cause": "unexplained",
                "rows": 3,
                "students": 1,
            }
        ],
        differing_columns={},
        invariants={"dashboard rows balance": True},
    )
    cs = [
        cells.Cell(
            "default",
            "ADA",
            {"School": "Rise"},
            "ADA",
            "94.2%",
            0.95,
            cells.FORMULA_GAP,
        )
    ]
    checks = config.Checks.__new__(config.Checks)
    object.__setattr__(checks, "dashboard", "attendance_dashboard")
    object.__setattr__(checks, "excluded_sheets", {"Comm Log": "no Cube counterpart"})
    object.__setattr__(
        checks,
        "sheets",
        {
            "ADA": config.SheetMap(
                "ADA",
                "v",
                {},
                {"ADA": config.MeasureMap("ADA", "avg_daily_attendance")},
            )
        },
    )
    text = report.render(
        checks,
        {"period": "2026-07-01:2026-10-15"},
        rr,
        cs,
        {},
        {"ADA": "SUM([x])"},
        {cells.answer_key("default", "ADA"): {"sql": "SELECT 1"}},
    )
    assert "Findings (held until the tool is trusted)" in text
    assert "<10" in text and "| 3 |" not in text
    assert "SUM([x])" in text and "SELECT 1" in text
    assert "Comm Log" in text
