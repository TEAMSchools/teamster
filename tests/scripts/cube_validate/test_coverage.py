"""Coverage: one status per must-cover measure, in the spec's order."""

from dataclasses import replace

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import cells, config, coverage, report, rows

from .test_cells import _checks as base_checks

TWB = """<workbook>
<worksheets>
<worksheet name='Mapped'><table><view><datasource-dependencies datasource='ds'>
<column caption='Attendance Metric' name='[c1]' />
<column caption='Truancy' name='[c2]' />
<column caption='Odd' name='[c3]' />
</datasource-dependencies></view></table></worksheet>
<worksheet name='Roster'><table><view><datasource-dependencies datasource='ds'>
<column caption='Odd' name='[c3]' />
<column caption='Names Only' name='[c4]' />
</datasource-dependencies></view></table></worksheet>
<worksheet name='New Sheet'><table><view><datasource-dependencies datasource='ds'>
<column caption='Fresh' name='[c5]' />
</datasource-dependencies></view></table></worksheet>
<worksheet name='Other Source'><table><view><datasource-dependencies datasource='ds2'>
<column caption='Split' name='[c7]' />
</datasource-dependencies></view></table></worksheet>
<worksheet name='Elsewhere'><table><view><datasource-dependencies datasource='ds'>
<column caption='Far Away' name='[c6]' />
</datasource-dependencies></view></table></worksheet>
</worksheets>
<dashboards><dashboard name='Overview'>
<zones><zone name='Mapped' /><zone name='Roster' /><zone name='New Sheet' />
<zone name='Other Source' /></zones>
</dashboard></dashboards>
</workbook>"""


def _entry(column, name=None, cube=("m", "v"), param=None, rows_=()):
    return config.MustCover(name or column, "link", cube, column, param, rows_)


def _checks(*entries):
    return replace(
        base_checks(),
        cuts=(
            config.Cut("default"),
            config.Cut("trunc", params={"Metric": "Truancy"}),
        ),
        sheets={"Mapped": base_checks().sheets["ADA"]},
        excluded_sheets={
            "Roster": "Names: a student name column",
            "Other Source": "separate run",
        },
        must_cover=tuple(entries),
    )


def _cell(measure, verdict, cut="default", reason=""):
    return cells.Cell(cut, "Mapped", {}, measure, "1", 1.0, verdict, reason=reason)


def _rr(differing=None):
    return rows.RowsResult(
        totals={"tableau": 0, "cube": 0, "joined": 0},
        buckets=[],
        differing_columns=differing or {},
        invariants={},
    )


def _line(entry, cs=(), differing=None, twb=TWB):
    got = coverage.lines(_checks(entry), list(cs), _rr(differing), twb)
    assert len(got) == 1 and got[0]["source"] == "link"
    return got[0]


def test_statuses_are_in_the_specs_order():
    assert coverage.STATUSES == (
        "gaps open",
        "covered",
        "in the data, not in Cube",
        "not judged",
        "not mapped yet",
        "only on sheets with names",
        "not on these dashboards",
    )


def test_covered_needs_a_judged_cell_where_all_pass_or_are_decided():
    cs = [_cell("M", cells.PASS), _cell("M", cells.FIX_CUBE, reason="rule")]
    got = _line(_entry("M"), cs + [_cell("M", cells.NO_ROWS)])
    assert got["status"] == "covered"
    assert got["detail"] == "<10 judged cells"


def test_gaps_open_on_a_row_gap_formula_gap_or_coincidental_match():
    for v in (cells.ROW_GAP, cells.FORMULA_GAP, cells.COINCIDENTAL):
        got = _line(_entry("M"), [_cell("M", cells.PASS), _cell("M", v)])
        assert got["status"] == "gaps open", v
    assert got["detail"] == "<10 judged, <10 gaps"


def test_mixed_verdicts_across_sheets_take_gaps_open():
    cs = [
        _cell("M", cells.PASS),
        replace(_cell("M", cells.FORMULA_GAP), sheet="Other"),
        replace(_cell("M", cells.FIX_DASHBOARD), sheet="Third"),
    ]
    assert _line(_entry("M"), cs)["status"] == "gaps open"


def test_a_selector_entry_reads_only_the_cells_of_its_value():
    e = _entry("M", param=("Metric", "Truancy"))
    cs = [_cell("M", cells.ROW_GAP), _cell("M", cells.PASS, cut="trunc")]
    assert _line(e, cs)["status"] == "covered"
    assert _line(_entry("M"), cs)["status"] == "gaps open"


def test_in_the_data_not_in_cube_says_rows_agree():
    got = _line(_entry("M", cube=None, rows_=("a",)))
    assert got["status"] == "in the data, not in Cube"
    assert got["detail"] == "rows agree"


def test_rows_differing_still_reads_not_in_cube_with_the_count():
    got = _line(
        _entry("M", cube=None, rows_=("a", "b")), differing={"a": 12, "b": 3, "z": 9}
    )
    assert got["status"] == "in the data, not in Cube"
    assert got["detail"] == "15 rows differ"


def test_not_judged_names_the_most_common_tool_limit():
    cs = [
        _cell("M", cells.UNPROVEN, reason="no join"),
        _cell("M", cells.UNPROVEN, reason="no join"),
        _cell("M", cells.NO_ROWS),
    ]
    got = _line(_entry("M"), cs)
    assert got["status"] == "not judged" and got["detail"] == "no join"
    assert _line(_entry("M"), [_cell("M", cells.NO_ROWS)])["detail"] == (cells.NO_ROWS)


def test_not_judged_when_a_mapped_sheet_shows_it_but_no_cell_was_built():
    got = _line(_entry("Truancy"))
    assert got["status"] == "not judged"
    assert got["detail"] == "mapped, but no cell was built: no cut covers it"
    got = _line(_entry("Truancy", param=("Metric", "Tardy")))
    assert got["detail"] == (
        "mapped, but no cell was built: no cut sets Metric = Tardy"
    )


def test_not_mapped_yet_when_a_sheet_shows_it_and_nothing_maps_it():
    got = _line(_entry("Fresh"))
    assert got["status"] == "not mapped yet" and got["detail"] == "New Sheet"


def test_a_prefixed_header_finds_its_caption():
    got = _line(_entry("Avg. Fresh"))
    assert got["status"] == "not mapped yet"


def test_only_on_sheets_with_names_lists_their_reasons():
    got = _line(_entry("Names Only"))
    assert got["status"] == "only on sheets with names"
    assert got["detail"] == "Roster: Names: a student name column"


def test_an_excluded_sheet_without_a_names_reason_reads_not_mapped_yet():
    got = _line(_entry("Split"))
    assert got["status"] == "not mapped yet" and got["detail"] == "Other Source"


def test_not_on_these_dashboards_when_no_dashboard_sheet_shows_it():
    assert _line(_entry("Far Away"))["status"] == "not on these dashboards"
    assert _line(_entry("Nothing"))["status"] == "not on these dashboards"


def test_a_mapped_and_a_named_sheet_with_cells_is_judged_on_the_mapped_one():
    assert _line(_entry("Odd"), [_cell("Odd", cells.PASS)])["status"] == "covered"


def test_a_sheets_student_count_column_reads_not_judged():
    got = _line(_entry("Students"))
    assert got["status"] == "not judged"
    assert "student count" in got["detail"]


def test_report_puts_coverage_right_after_the_trust_verdict():
    checks = _checks(_entry("M"))
    lines = [{"name": "M", "status": "covered", "detail": "x", "source": "link"}]
    text = report.render(
        checks,
        {},
        _rr(),
        [],
        {},
        "",
        {},
        coverage=lines,
    )
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    assert heads[:3] == ["## Trust verdict", "## Coverage", "## Invariants"]
    assert "| M | covered | x | link |" in text
    bare = report.render(base_checks(), {}, _rr(), [], {}, "", {})
    assert "## Coverage" not in bare
