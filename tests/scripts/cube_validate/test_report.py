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
    ok = {"a": True, "capture completeness": True}
    assert report.trust({"a": False}, {}, 0).startswith(
        "Not trusted: invariant broken: a"
    )
    assert report.trust(ok, {}, 5).startswith("Pending: no hand checks")
    assert report.trust(ok, {"C1": "pending", "C2": "agree"}, 5).startswith(
        "Pending: 1 of 2"
    )
    assert report.trust(ok, {"C1": "disagree"}, 5).startswith(
        "Not trusted: 1 hand check"
    )
    assert report.trust(ok, {"C1": "agree"}, 5).startswith("Trusted for this run")
    assert report.trust({"a": True}, {"C1": "agree"}, 5).startswith(
        "Pending: capture completeness"
    )


def test_trust_disagreement_wins_over_pending():
    ok = {"a": True, "capture completeness": True}
    assert report.trust(ok, {"C1": "pending", "C2": "disagree"}, 5).startswith(
        "Not trusted: 1 hand check"
    )


def test_trust_counts_unknown_status_as_open():
    ok = {"a": True, "capture completeness": True}
    assert report.trust(ok, {"C1": "Agree"}, 5).startswith("Pending: 1 of 1")


def _gap_row(tableau: str, cube: float) -> str:
    rr = rows.RowsResult(
        totals={"tableau": 0, "cube": 0, "joined": 0},
        buckets=[],
        differing_columns={},
        invariants={},
    )
    cs = [
        cells.Cell(
            "default", "ADA", {"School": "Rise"}, "ADA", tableau, cube, cells.ROW_GAP
        )
    ]
    checks = config.Checks.__new__(config.Checks)
    object.__setattr__(checks, "dashboard", "attendance_dashboard")
    object.__setattr__(checks, "excluded_sheets", {})
    object.__setattr__(checks, "sheets", {})
    text = report.render(checks, {}, rr, cs, {}, "", {})
    return next(line for line in text.splitlines() if line.startswith("| default |"))


def test_gap_table_masks_small_counts_only():
    assert _gap_row("3", 4.0).endswith("| row gap | <10 | <10 |")
    assert _gap_row("94.2%", 0.95).endswith("| row gap | 94.2% | 0.95 |")


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
        "<workbook><column name='[C]' caption='ADA'><calculation class='tableau' "
        "formula='SUM([x])' /></column></workbook>",
        {cells.answer_key("default", "ADA"): {"sql": "SELECT 1"}},
    )
    assert "Findings (held until the tool is trusted)" in text
    assert "<10" in text and "| 3 |" not in text
    assert "SUM([x])" in text and "SELECT 1" in text
    assert "Comm Log" in text


def _render(cs, sheets, decisions=None):
    rr = rows.RowsResult(
        totals={"tableau": 0, "cube": 0, "joined": 0},
        buckets=[],
        differing_columns={},
        invariants={},
    )
    checks = config.Checks.__new__(config.Checks)
    object.__setattr__(checks, "dashboard", "attendance_dashboard")
    object.__setattr__(checks, "excluded_sheets", {})
    object.__setattr__(checks, "sheets", sheets)
    return report.render(checks, {}, rr, cs, {}, "", {}, decisions)


def test_row_gap_lists_its_buckets_once_per_mark_with_small_counts():
    buckets = [("match", None, 25, 12), ("dashboard_only", "unexplained", 3, 2)]
    cs = [
        cells.Cell(
            "default",
            "ADA",
            {"School": "Rise"},
            m,
            "94.2%",
            0.95,
            cells.ROW_GAP,
            buckets=buckets,
        )  # fmt: skip
        for m in ("ADA", "Tardy")
    ]
    text = _render(cs, {})
    assert "| Cut | Sheet | Marks | Base | Cause | Rows | Students |" in text
    assert text.count("| default | ADA | School=Rise | dashboard_only |") == 1
    assert (
        "| default | ADA | School=Rise | dashboard_only | unexplained | <10 | <10 |"
        in text
    )
    assert "| default | ADA | School=Rise | match | None | 25 | 12 |" in text


def test_formula_gap_section_shows_the_selected_calc():
    from cube_validate import workbook  # noqa: F401

    twb = (
        "<workbook><datasources><datasource name='Parameters'>"
        "<column name='[Parameter 2]' caption='Attendance Metric' /></datasource>"
        "<datasource name='d'>"
        "<column name='[Calculation_9]' caption='Is Chronic Absentee'>"
        "<calculation class='tableau' formula='IF [is_absent] THEN 1 END' /></column>"
        "<column name='[Calc_1]' caption='Attendance Metric'><calculation "
        "class='tableau' formula=\"IF [Parameters].[Parameter 2] = 'ADA' THEN "
        "[is_present] ELSEIF [Parameters].[Parameter 2] = 'Chronic Absenteeism' "
        'THEN [Calculation_9] END" /></column></datasource></datasources></workbook>'
    )
    cs = [
        cells.Cell(
            "chronic", "ADA", {}, "Avg. Attendance Metric", "9%", 0.1, cells.FORMULA_GAP
        )
    ]
    rr = rows.RowsResult(
        totals={"tableau": 0, "cube": 0, "joined": 0},
        buckets=[],
        differing_columns={},
        invariants={},
    )
    checks = config.Checks.__new__(config.Checks)
    object.__setattr__(checks, "dashboard", "d")
    object.__setattr__(checks, "excluded_sheets", {})
    object.__setattr__(checks, "sheets", {})
    object.__setattr__(
        checks,
        "cuts",
        (config.Cut("chronic", params={"Attendance Metric": "Chronic Absenteeism"}),),
    )
    text = report.render(checks, {}, rr, cs, {}, twb, {})
    assert "Is Chronic Absentee => IF [is_absent] THEN 1 END" in text


def test_formulas_not_tested_lists_mapped_measures_with_no_clean_cut():
    sheets = {
        "ADA": config.SheetMap(
            "ADA",
            "v",
            {},
            {
                "ADA": config.MeasureMap("ADA", "avg_daily_attendance"),
                "Tardy": config.MeasureMap("Tardy", "tardy_rate"),
                "Other": config.MeasureMap("Other", None),
            },
        )
    }
    cs = [
        cells.Cell("default", "ADA", {}, "ADA", "1", 1.0, cells.PASS),
        cells.Cell("default", "ADA", {}, "Tardy", "1", 1.0, cells.ROW_GAP),
        cells.Cell("default", "ADA", {}, "Tardy", "1", 1.0, cells.COINCIDENTAL),
    ]
    text = _render(cs, sheets)
    section = text.split("### Formulas not tested", 1)[1].split("##", 1)[0]
    assert "- ADA / Tardy" in section
    assert "ADA / ADA" not in section and "Other" not in section


def test_trust_is_pending_when_no_cell_was_compared():
    ok = {"a": True, "capture completeness": True}
    got = report.trust(ok, {"C1": "agree"}, 0)
    assert got.startswith("Pending: no cell was compared yet")
    # a broken invariant and a disagreement still win
    assert report.trust({"a": False}, {}, 0).startswith("Not trusted")
    assert report.trust(ok, {"C1": "disagree"}, 0).startswith("Not trusted")


def test_compared_counts_judged_verdicts_only():
    from types import SimpleNamespace as N

    cells = [N(verdict=v) for v in (report.PASS, report.ROW_GAP, "never in cube")]
    assert report.compared(cells) == 2


def test_decided_verdicts_count_as_compared_and_decisions_render():
    cs = [
        cells.Cell("default", "S", {}, "M", "1", 1.0, v)
        for v in (cells.FIX_DASHBOARD, cells.FIX_CUBE, cells.ACCEPTED)
    ]
    assert report.compared(cs) == 3
    assert cells.ORDER.index(cells.FIX_CUBE) == cells.ORDER.index(cells.FORMULA_GAP) + 2


def test_decisions_section_shows_only_with_a_decision_and_masks_counts():
    cs = [cells.Cell("default", "S", {}, "M", "1", 1.0, cells.FIX_CUBE)]
    d = {
        "decision": "M (cube)",
        "owner": "cube",
        "relabeled": 3,
        "still_formula_gap": 0,
        "resolved": 12,
        "probe_proven": True,
    }
    assert "### Decisions" not in _render(cs, {})
    text = _render(cs, {}, [d])
    assert "- M (cube): <10 relabeled, 0 still formula gap, 12 resolved" in text
