import dataclasses
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, pipeline, read_sheet, tableau

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.builder import Member

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.find_field import Candidate

FIXTURES = Path(__file__).parent / "fixtures"
TWB = (FIXTURES / "preflight.twb").read_text()
# Read only, never committed; the real-workbook test skips without it.
DDI_TWB = Path("/workspaces/teamster/.claude/scratch/ddi-twb/ddi_suite.twb")


def _member(name, kind="dimension"):
    return Member(f"v.{name}", "v", kind, name, "", "", "", "", view=True)


MEMBERS = [_member(n) for n in ("abbreviation", "grade_level", "academic_year")]


def _comparison(**changes):
    base = Comparison(
        id="grid",
        measure="pct",
        workbook="wb-1",
        sheet="Grid",
        sheet_field="Avg. Is Mastery Int",
        dims=[ColumnPair("school", "abbreviation")],
        filters={
            "Academic Year": ColumnPair("academic_year", "academic_year"),
            "School": ColumnPair("school", "abbreviation"),
            "Subject Area": ColumnPair("subject_area", "academic_subject"),
        },
    )
    return dataclasses.replace(base, **changes)


RESHAPE = {
    "drop": ["Week Start Monday", "Grade/Subject"],
    "add": {"rows": ["Grade Level"]},
}


def _check(comparison=None, members=MEMBERS):
    lines, before = read_sheet.check("v", TWB, "Grid", comparison, members)
    return "\n".join(lines), before


def test_shelf_fields_name_their_member_or_the_reshape_they_need():
    text, before = _check(_comparison())

    assert "- School (columns): v.abbreviation" in text
    assert (
        "- Grade/Subject (rows): no Cube member — reshape with shelves: drop/add, "
        "or add a Cube member"
    ) in text
    assert (
        "Week Start Monday: no Cube member on the columns; reshape with shelves: "
        "drop/add, or add a Cube member"
    ) in before
    # A measure on an encoding is a value, not a shelf field.
    assert "Is Mastery Int (text)" not in text


def test_shelf_fields_after_a_reshape():
    comparison = _comparison(
        shelves=RESHAPE,
        dims=[
            ColumnPair("school", "abbreviation"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )

    text, before = _check(comparison)

    assert "- Grade/Subject (rows): no Cube member; dropped by shelves" in text
    assert "- Grade Level (rows, added by shelves): v.grade_level" in text
    assert not [b for b in before if "Cube member" in b or "dims" in b]


def test_a_member_cube_has_but_dims_leaves_out_blocks():
    text, before = _check(_comparison(), MEMBERS + [_member("week_start_monday")])

    assert "- Week Start Monday (columns): v.week_start_monday, not under dims" in text
    assert (
        "Week Start Monday: on the columns; map it under dims to v.week_start_monday"
        in before
    )


def test_table_calcs_list_their_ordering_and_the_reshape_removing_them():
    facts = read_sheet.read_sheet(TWB, "Grid")
    assert [c.label for c in facts.table_calcs] == [
        "Difference in Avg. Is Mastery Int (along Week Start Monday)",
        "Difference in Avg. Is Mastery Int (along Rows)",
    ]

    comparison = _comparison(
        shelves=RESHAPE,
        dims=[
            ColumnPair("school", "abbreviation"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )
    text, _ = _check(comparison)

    assert (
        "- removed by shelves.drop: Difference in Avg. Is Mastery Int (along Week "
        "Start Monday)"
    ) in text
    assert "- recomputes along the new rows: Difference in Avg. Is Mastery Int" in text


def test_filters_name_their_kind_and_who_shares_them():
    by = {f.caption: f for f in read_sheet.read_sheet(TWB, "Grid").filters}

    assert by["Discipline"].kinds == ("code group",)
    assert by["Discipline"].source == "subject_area"
    assert by["Discipline"].shared_with == ("Other",)
    future = by["Exclude Future Assessments"]
    assert future.kinds == ("context", "relative date")
    assert future.formula.startswith(
        "[Administered At] <= [Current Week (Sunday)]; Current Week (Sunday) = "
        "DATE(DATEADD('day', 8 - DATEPART('weekday', TODAY()), TODAY()))"
    )
    assert by["Metric Switch"].kinds == ("parameter-driven",)
    assert by["Academic Year"].kinds == ("regular",) and by["Academic Year"].restricting
    assert not by["School"].restricting


def test_sheet_lines_flag_relative_dates_code_groups_and_shared_filters():
    facts = read_sheet.read_sheet(TWB, "Grid")

    text = "\n".join(read_sheet._sheet_lines("w.twb", "Grid", facts))

    assert (
        "- Discipline: code group; restricting; clear with shelves.clear_filters, "
        "or default the comparison to its members; shared through filter-group 94 "
        "with 1 other sheets (Other)"
    ) in text
    assert (
        "needs dashboard_filters with days_from_week_end or a sheet query filter"
        in text
    )
    assert "- School: regular; keeps all\n" in text
    # Discipline is off the allowlist; Academic Year is on it.
    assert "ELA" not in text and "shows 2026" in text


def test_restricting_filters_block_until_the_comparison_handles_them():
    _, before = _check(_comparison())

    assert (
        "Discipline: code group; clear with shelves.clear_filters, or default the "
        "comparison to its members"
    ) in before
    assert (
        "Exclude Future Assessments: relative date; needs dashboard_filters with "
        "days_from_week_end or a sheet query filter"
    ) in before
    assert not [b for b in before if b.startswith("Academic Year")]

    handled = _comparison(
        shelves={"clear_filters": ["Discipline"]},
        dashboard_filters=[
            {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
        ],
    )
    text, before = _check(handled)

    assert "- Discipline: cleared by shelves.clear_filters" in text
    assert "- Exclude Future Assessments: dashboard_filters days_from_week_end" in text
    assert not [b for b in before if b.startswith(("Discipline", "Exclude"))]

    defaulted = _comparison(defaults={"Subject Area": ["Text Study"]})
    assert "- Discipline: defaults narrow subject_area" in _check(defaulted)[0]


def test_parameters_say_whether_the_comparison_sets_them():
    facts = read_sheet.read_sheet(TWB, "Grid")
    assert facts.parameters == [read_sheet.Parameter("Parameter 1", "Metric")]

    text, before = _check(_comparison())
    assert "Parameter Metric: not set" in text
    assert any(b.startswith("Metric Switch: driven by a parameter") for b in before)
    text, before = _check(_comparison(parameters={"Metric": "Mastery"}))
    assert "Parameter Metric: set under parameters:" in text
    # The comparison sets the parameter the switch reads: nothing to decide.
    assert "- Metric Switch: its parameter is set under parameters:" in text
    assert not [b for b in before if b.startswith("Metric Switch")]


def test_no_parameter_value_prints():
    sheet = "\n".join(
        read_sheet._sheet_lines("w.twb", "Grid", read_sheet.read_sheet(TWB, "Grid"))
    )
    text, _ = _check(_comparison(parameters={"Metric": "Mastery"}))
    lines = text.splitlines()

    assert "    - Metric (Parameter 1)" in sheet.splitlines()
    assert "    Parameter Metric: set under parameters:" in lines
    # The parameter's current value is a member value: it never prints.
    assert not [line for line in sheet.splitlines() + lines if "now" in line]


def test_measure_found_or_not():
    text, before = _check(_comparison())
    assert "Measure: sheet_field 'Avg. Is Mastery Int' is on the sheet" in text
    assert not [b for b in before if b.startswith("sheet_field")]

    text, before = _check(_comparison(sheet_field="Nope"))
    assert before[-1] == (
        "sheet_field 'Nope': not on the sheet; it shows Difference in Avg. Is "
        "Mastery Int, AVG(Is Mastery Int)"
    )


def test_report_ends_each_comparison_with_before_prove():
    cfg = type("Cfg", (), {"view": "v", "comparisons": [_comparison()]})()

    text = read_sheet.report(cfg, lambda wb: ("w.twb", TWB), MEMBERS)

    assert text.startswith(f"Grid (w.twb); {tableau.NOT_CHECKED}\n")
    assert "\n  grid:\n" in text
    assert "\n    Before rebuild-sheet:\n      - Grade/Subject: no Cube member" in text
    assert read_sheet.report(cfg, lambda wb: ("w.twb", TWB), MEMBERS, ["Nope"]) == (
        "Nope: not in w.twb"
    )


def test_preflight_names_a_comparison_whose_cells_cannot_be_covered():
    rows = RowSpec(
        grain=[ColumnPair("student", "student_number")],
        values=[ColumnPair("ok", "ok")],
    )

    def report(comparison):
        cfg = type("Cfg", (), {"view": "v", "comparisons": [comparison]})()
        return read_sheet.report(cfg, lambda wb: ("w.twb", TWB), MEMBERS)

    text = report(_comparison())
    assert "\n    Cells cannot be covered: the comparison has no rows" in text
    on_grain = _comparison(rows=rows, dims=[ColumnPair("student", "student_number")])
    assert "    Cells cannot be covered: its dims student_number are part of the " in (
        report(on_grain)
    )
    assert "Cells cannot be covered" not in report(_comparison(rows=rows))


VIEW = """\
view: v
fact: kipptaf_marts.fct_f
comparisons:
  - id: grid
    measure: pct
    confirmed: true
    workbook: wb-1
    sheet: Grid
    dashboard_view: kipptaf_tableau.rpt_d
    sheet_query: avg(is_mastery_int)
    sheet_field: Avg. Is Mastery Int
    decimals: 2
    dims:
      - { dashboard: school, cube: abbreviation }
    filters:
      School: { dashboard: school, cube: abbreviation }
    defaults: {}
    cuts: [{}]
    rebuild_check: null
"""


def _files(tmp_path, members=True):
    view, twb = tmp_path / "v.yml", tmp_path / "w.twb"
    view.write_text(VIEW)
    twb.write_text(TWB)
    if members:
        _save_members()
    return view, twb


def _save_members():
    saved = cli.cache_root() / "members.json"
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps({"members": [dataclasses.asdict(m) for m in MEMBERS]}))


def test_preflight_command_reads_a_local_workbook(tmp_path, capsys, monkeypatch):
    def no_tableau():
        raise AssertionError("preflight --twb signs in to no Tableau")

    monkeypatch.setattr(cli, "tableau_session", no_tableau)
    view, twb = _files(tmp_path)

    assert cli.main(["read-sheet", str(view), "--twb", str(twb)]) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"Grid (w.twb); {tableau.NOT_CHECKED}\n")
    assert "Before rebuild-sheet:" in out
    assert (
        cli.main(["read-sheet", str(view), "--twb", str(twb), "--sheet", "Other"]) == 0
    )
    assert "Other (w.twb)" in capsys.readouterr().out


def test_preflight_command_refuses_without_members_or_a_workbook(tmp_path, capsys):
    view, twb = _files(tmp_path, members=False)

    assert cli.main(["read-sheet", str(view), "--twb", str(twb)]) == 1
    assert "members.json: missing; run `members` first" in capsys.readouterr().err

    _save_members()
    assert cli.main(["read-sheet", str(view), "--twb", str(tmp_path / "none")]) == 1


def test_preflight_command_never_signs_in_to_tableau(tmp_path, capsys, monkeypatch):
    def no_tableau():
        raise AssertionError("preflight signs in to no Tableau")

    monkeypatch.setattr(cli, "tableau_session", no_tableau)
    view, _ = _files(tmp_path)

    assert cli.main(["read-sheet", str(view)]) == 1
    assert "pass --twb <path>" in capsys.readouterr().err


@pytest.mark.skipif(not DDI_TWB.is_file(), reason="the DDI workbook is not on disk")
def test_preflight_reads_the_dki_grid_offline():
    sheet = "DKI - Assessment Mastery Grid"
    comparison = _comparison(
        sheet=sheet,
        dims=[
            ColumnPair("school", "abbreviation"),
            ColumnPair("module_code", "module_code"),
        ],
    )
    xml = DDI_TWB.read_text(encoding="utf-8")
    members = [_member(n) for n in ("abbreviation", "module_code", "grade_level")]

    lines, before = read_sheet.check("v", xml, sheet, comparison, members)
    facts = read_sheet.read_sheet(xml, sheet)
    sheet_text = "\n".join(read_sheet._sheet_lines("ddi_suite.twb", sheet, facts))

    for field in ("Grade/Subject", "Week Start Monday"):
        assert any(b.startswith(f"{field}: no Cube member") for b in before), field
    assert [c.label for c in facts.table_calcs] == [
        "Difference in Avg. Is Mastery Int (along Week Start Monday, Module Code)",
        "Difference in Avg. Is Mastery Int (along Rows)",
    ]
    by = {f.caption: f for f in facts.filters}
    assert by["Exclude Future Assessments"].kinds == ("context", "relative date")
    assert "TODAY()" in by["Exclude Future Assessments"].formula
    assert by["Discipline"].kinds == ("code group",)
    assert by["Discipline"].group == "94" and by["Discipline"].shared_with
    assert "Discipline: code group; restricting" in sheet_text


# A relative-date filter as Tableau writes one: no groupfilter, no min or max.
_RELATIVE = (
    "<filter class='relative-date' column='[federated.0pf].[none:week_start_monday:ok]' "
    "first-period='-1' include-future='true' include-null='false' last-period='0' "
    "period-type='week' />\n          "
)
_ANCHOR = "<filter class='categorical' column='[federated.0pf].[none:school:nk]'"


def _with_relative():
    assert TWB.count(_ANCHOR) == 1
    return TWB.replace(_ANCHOR, _RELATIVE + _ANCHOR)


def test_a_relative_date_filter_restricts_and_blocks():
    xml = _with_relative()
    by = {f.caption: f for f in read_sheet.read_sheet(xml, "Grid").filters}

    assert by["Week Start Monday"].kinds == ("relative date",)
    assert by["Week Start Monday"].restricting
    _, before = read_sheet.check("v", xml, "Grid", _comparison(), MEMBERS)
    assert any(b.startswith("Week Start Monday: relative date") for b in before)


def test_a_week_end_dashboard_filter_handles_only_the_column_it_names():
    xml = _with_relative()
    comparison = _comparison(
        dashboard_filters=[
            {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
        ]
    )

    lines, before = read_sheet.check("v", xml, "Grid", comparison, MEMBERS)

    # Exclude Future Assessments reads administered_at; the week filter does not.
    assert "- Exclude Future Assessments: dashboard_filters days_from_week_end" in (
        "\n".join(lines)
    )
    assert any(b.startswith("Week Start Monday: relative date") for b in before)


def test_a_probe_handles_only_the_relative_dates_whose_column_it_names():
    probe = (
        "SELECT {dims}, AVG(is_mastery_int) AS value FROM ({rows}) WHERE {where} "
        "AND administered_at <= CURRENT_DATE('America/New_York') GROUP BY {dims}"
    )
    xml = _with_relative()

    lines, before = read_sheet.check(
        "v", xml, "Grid", _comparison(sheet_query_sql=probe), MEMBERS
    )

    assert "- Exclude Future Assessments: in sheet_query_sql" in "\n".join(lines)
    assert not [b for b in before if b.startswith("Exclude Future")]
    assert any(b.startswith("Week Start Monday: relative date") for b in before)


def test_a_probe_with_a_fixed_date_does_not_clear_a_relative_date():
    probe = (
        "SELECT {dims}, AVG(is_mastery_int) AS value FROM ({rows}) WHERE {where} "
        "AND administered_at >= '2025-07-01' GROUP BY {dims}"
    )

    _, before = _check(_comparison(sheet_query_sql=probe))

    # The column is named, but no rolling date bounds it.
    assert any(
        b.startswith("Exclude Future Assessments: relative date") for b in before
    )


def test_a_sheet_field_the_reshape_recomputes_blocks():
    comparison = _comparison(
        shelves=RESHAPE,
        sheet_field="Difference in Avg. Is Mastery Int",
        dims=[
            ColumnPair("school", "abbreviation"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )

    _, before = _check(comparison)

    assert (
        "sheet_field 'Difference in Avg. Is Mastery Int': recomputes along the new "
        "rows on the reshaped copy, a number the dashboard never shows"
    ) in before


def test_a_rows_grain_field_on_the_shelves_is_mapped():
    comparison = _comparison(
        rows=RowSpec(
            grain=[ColumnPair("week_start_monday", "assessment_week")],
            values=[ColumnPair("is_mastery_int", "is_mastery")],
        )
    )

    text, before = _check(comparison)

    assert "- Week Start Monday (columns): v.assessment_week (rows:)" in text
    assert not [b for b in before if b.startswith("Week Start Monday")]


def test_export_name_reads_a_countd_caption():
    assert (
        read_sheet._export_name("Distinct count of Student Number") == "student number"
    )


def test_measure_line_finds_a_countd_sheet_field():
    facts = read_sheet.Sheet(
        [], [], [], [], {"COUNTD(Student Number)": {"student number"}}
    )
    out = read_sheet._Checklist([], [])
    read_sheet._measure_line(
        out, _comparison(sheet_field="Distinct count of Student Number"), facts
    )
    assert out.before == []


def test_read_sheet_points_a_non_null_filter_at_dashboard_filters_set():
    non_null = (
        "<filter class='quantitative' column='[federated.0pf].[none:score:qk]' "
        "included-values='non-null'/>\n          "
    )
    xml = TWB.replace(_ANCHOR, non_null + _ANCHOR)
    _, before = read_sheet.check("v", xml, "Grid", _comparison(), MEMBERS)
    assert any("non-null values only" in b and "operator: set" in b for b in before)


def _non_null_calc(columns):
    return read_sheet.SheetFilter(
        caption="Is Mastery Int - Custom", name="Calculation_1",
        kinds=("parameter-driven",), restricting=True, formula="", group="",
        shared_with=(), source="", columns=("Calculation_1", *columns),
        parameters=("Mastery Level",), null_mode="non-null",
    )  # fmt: skip


@pytest.mark.parametrize(
    "columns, entries, handled",
    [
        (("is_mastery_int", "is_mastery"), [{"dashboard": "is_mastery_int",
                                             "operator": "set"}], True),
        (("is_mastery",), [{"dashboard": "is_mastery_int", "operator": "set"}],
         False),
        (("is_mastery_int",), [{"dashboard": "is_mastery_int",
                                "values": ["1"]}], False),
        (("is_mastery_int",), [], False),
    ],
    ids=["set on a column it reads", "set on another column", "not set", "none"],
)  # fmt: skip
def test_a_non_null_calc_filter_is_handled_by_a_set_entry_on_a_column_it_reads(
    columns, entries, handled
):
    facts = read_sheet.Sheet([], [], [_non_null_calc(columns)], [], {})
    out = read_sheet._Checklist([], [])

    read_sheet._filter_lines(out, _comparison(dashboard_filters=entries), facts)

    if handled:
        assert out.before == []
        assert (
            "    - Is Mastery Int - Custom: dashboard_filters operator: set on "
            "is_mastery_int"
        ) in out.lines
    else:
        (blocking,) = out.before
        assert "non-null values only" in blocking and "operator: set" in blocking


def test_read_sheet_refuses_a_text_sheet_field():
    facts = read_sheet.Sheet(
        [], [], [], [], {"Status": {"status"}}, text_values=frozenset({"status"})
    )
    assert (
        read_sheet.text_measure(facts, "Status")
        == f"sheet_field 'Status': {tableau.TEXT_MEASURE}"
    )


def test_text_measure_refuses_a_text_field_whose_caption_starts_with_count():
    facts = read_sheet.Sheet(
        [], [], [], [], {"Count Type": {"count type"}},
        text_values=frozenset({"count type"}),
    )  # fmt: skip
    assert (
        read_sheet.text_measure(facts, "Count Type")
        == f"sheet_field 'Count Type': {tableau.TEXT_MEASURE}"
    )
    status = read_sheet.Sheet(
        [], [], [], [], {"ATTR(Status)": {"status"}},
        text_values=frozenset({"status"}),
    )  # fmt: skip
    for counted in ("COUNTD(Status)", "CNT(Status)", "Distinct count of Status",
                    "Count of Status"):  # fmt: skip
        assert read_sheet.text_measure(status, counted) is None, counted


STATUS_TWB = (
    "<workbook><worksheets><worksheet name='S'><table><view>"
    "<datasource-dependencies datasource='f'>"
    "<column caption='Status' datatype='string' name='[status]' role='dimension' />"
    "</datasource-dependencies></view>"
    "<rows>{rows}</rows>"
    "</table></worksheet></worksheets></workbook>"
)


def test_text_measure_without_sheet_field_counts_a_count_as_a_number():
    both = read_sheet.read_sheet(
        STATUS_TWB.format(rows="([f].[attr:status:nk] + [f].[ctd:status:qk])"), "S"
    )
    assert set(both.values) == {"Status", "COUNTD(Status)"}
    assert read_sheet.text_measure(both, None) is None

    attr = read_sheet.read_sheet(STATUS_TWB.format(rows="[f].[attr:status:nk]"), "S")
    assert read_sheet.text_measure(attr, None) == (
        f"the sheet's measure: {tableau.TEXT_MEASURE}"
    )


def test_sheet_lines_say_an_allowlisted_null_mode_once():
    non_null = (
        "<filter class='quantitative' column='[federated.0pf].[none:grade_level:qk]' "
        "included-values='non-null'/>\n          "
    )
    facts = read_sheet.read_sheet(TWB.replace(_ANCHOR, non_null + _ANCHOR), "Grid")
    (grade,) = [f for f in facts.filters if f.name == "grade_level"]
    assert grade.shown == "non-null values only"

    text = "\n".join(read_sheet._sheet_lines("w.twb", "Grid", facts))

    assert "- Grade Level: regular; non-null values only\n" in text
    assert "shows non-null" not in text


def test_read_sheet_does_not_point_a_null_filter_at_the_not_null_operator():
    null_only = (
        "<filter class='quantitative' column='[federated.0pf].[none:score:qk]' "
        "included-values='null'/>\n          "
    )
    xml = TWB.replace(_ANCHOR, null_only + _ANCHOR)
    _, before = read_sheet.check("v", xml, "Grid", _comparison(), MEMBERS)
    line = next(b for b in before if "null values only" in b)
    assert "operator" not in line


UNPUBLISHED = TWB.replace(
    "<window class='worksheet' name='Grid'>",
    "<window class='worksheet' hidden='true' name='Grid'>",
)
NOT_PUBLISHED_ITEM = (
    "sheet: not on a published dashboard; set unpublished: true to compare it anyway"
)


def test_read_sheet_says_published_is_not_checked_offline():
    assert UNPUBLISHED != TWB
    cfg = type("Cfg", (), {"view": "v", "comparisons": [_comparison()]})()
    # A hidden window or a visible one: the .twb cannot say which sheets the
    # server publishes, so neither is guessed.
    for xml in (TWB, UNPUBLISHED):
        _, before = read_sheet.check("v", xml, "Grid", _comparison(), MEMBERS)
        assert NOT_PUBLISHED_ITEM not in before

        text = read_sheet.report(cfg, lambda wb, xml=xml: ("w.twb", xml), MEMBERS)
        assert text.startswith(f"Grid (w.twb); {tableau.NOT_CHECKED}\n")
        assert "not on a published dashboard" not in text


def test_print_sheets_parses_each_workbook_once(monkeypatch, capsys):
    found = [
        Candidate("wb-1", "w.twb", ["Grid", "Other"], "a", "SUM([x])", 1.0),
        Candidate("wb-1", "w.twb", ["Other"], "b", "SUM([y])", 0.5),
    ]
    parses = []
    real = ET.fromstring
    monkeypatch.setattr(ET, "fromstring", lambda text: parses.append(1) or real(text))

    pipeline._print_sheets(found, {"wb-1": TWB})

    out = capsys.readouterr().out
    assert "  Grid (w.twb): " in out and "  Other (w.twb): " in out
    assert len(parses) == 1


def test_read_sheet_lets_an_opted_in_unpublished_sheet_through():
    comparison = _comparison(unpublished=True)

    _, before = read_sheet.check("v", UNPUBLISHED, "Grid", comparison, MEMBERS)

    assert NOT_PUBLISHED_ITEM not in before
    cfg = type("Cfg", (), {"view": "v", "comparisons": [comparison]})()
    text = read_sheet.report(cfg, lambda wb: ("w.twb", UNPUBLISHED), MEMBERS)
    assert text.startswith(f"Grid (w.twb); {tableau.NOT_CHECKED}\n")


def test_read_sheet_shows_an_allowlisted_filter_s_values():
    facts = read_sheet.read_sheet(TWB, "Grid")
    by = {f.caption: f for f in facts.filters}
    assert by["Academic Year"].shown == "2026"
    assert by["School"].shown == ""
    text = "\n".join(read_sheet._sheet_lines("v", "Grid", facts))
    assert "Academic Year: regular; restricting; shows 2026" in text


def test_read_sheet_keeps_a_filter_off_the_allowlist_hidden():
    facts = read_sheet.read_sheet(TWB, "Grid")
    by = {f.caption: f for f in facts.filters}
    assert by["Discipline"].shown == ""
    assert "ELA" not in "\n".join(read_sheet._sheet_lines("v", "Grid", facts))


def test_a_countd_sheet_field_is_not_text_beside_an_attr_of_the_same_field():
    twb = (
        "<workbook><worksheets><worksheet name='S'><table><view>"
        "<datasource-dependencies datasource='f'>"
        "<column datatype='string' name='[status]' role='dimension' />"
        "</datasource-dependencies></view>"
        "<rows>([f].[attr:status:nk] + [f].[ctd:status:qk])</rows>"
        "<cols/></table></worksheet></worksheets></workbook>"
    )
    facts = read_sheet.read_sheet(twb, "S")
    assert read_sheet.text_measure(facts, "COUNTD(status)") is None
    assert read_sheet.text_measure(facts, "Distinct count of status") is None
    assert read_sheet.text_measure(facts, "ATTR(status)") is not None
    assert read_sheet.text_measure(facts, "status") is not None
