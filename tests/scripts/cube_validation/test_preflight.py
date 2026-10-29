import dataclasses
import json
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, preflight

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.builder import Member

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison

FIXTURES = Path(__file__).parent / "fixtures"
TWB = (FIXTURES / "preflight.twb").read_text()
# Read only, never committed; the real-workbook test skips without it.
DDI_TWB = Path("/workspaces/teamster/.claude/scratch/ddi-twb/ddi_suite.twb")


@pytest.fixture(autouse=True)
def _cache_in_tmp(monkeypatch, tmp_path):
    """Keep every test off the analyst's own cache."""
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")


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
    lines, before = preflight.check("v", TWB, "Grid", comparison, members)
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
    facts = preflight.read_sheet(TWB, "Grid")
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
    by = {f.caption: f for f in preflight.read_sheet(TWB, "Grid").filters}

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
    facts = preflight.read_sheet(TWB, "Grid")

    text = "\n".join(preflight._sheet_lines("w.twb", "Grid", facts))

    assert (
        "- Discipline: code group; restricting; clear with shelves.clear_filters, "
        "or default the comparison to its members; shared through filter-group 94 "
        "with 1 other sheets (Other)"
    ) in text
    assert "needs dashboard_filters with days_from_week_end or a probe filter" in text
    assert "- School: regular; keeps all\n" in text
    # A filter's chosen values never print.
    assert "ELA" not in text and "2026" not in text


def test_restricting_filters_block_until_the_comparison_handles_them():
    _, before = _check(_comparison())

    assert (
        "Discipline: code group; clear with shelves.clear_filters, or default the "
        "comparison to its members"
    ) in before
    assert (
        "Exclude Future Assessments: relative date; needs dashboard_filters with "
        "days_from_week_end or a probe filter"
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
    facts = preflight.read_sheet(TWB, "Grid")
    assert facts.parameters == [preflight.Parameter("Parameter 1", "Metric", "Mastery")]

    assert "Parameter Metric: not set (now Mastery)" in _check(_comparison())[0]
    text, before = _check(_comparison(parameters={"Metric": "Mastery"}))
    assert "Parameter Metric: set under parameters: (now Mastery)" in text
    # The switch it drives still needs a call.
    assert any(b.startswith("Metric Switch: driven by a parameter") for b in before)


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

    text = preflight.report(cfg, lambda wb: ("w.twb", TWB), MEMBERS)

    assert text.startswith("Grid (w.twb)\n")
    assert "\n  grid:\n" in text
    assert "\n    Before prove:\n      - Grade/Subject: no Cube member" in text
    assert preflight.report(cfg, lambda wb: ("w.twb", TWB), MEMBERS, ["Nope"]) == (
        "Nope: not in w.twb"
    )


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
    probe: avg(is_mastery_int)
    sheet_field: Avg. Is Mastery Int
    decimals: 2
    dims:
      - { dashboard: school, cube: abbreviation }
    filters:
      School: { dashboard: school, cube: abbreviation }
    defaults: {}
    cuts: [{}]
    proof: null
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

    assert cli.main(["preflight", str(view), "--twb", str(twb)]) == 0

    out = capsys.readouterr().out
    assert out.startswith("Grid (w.twb)\n") and "Before prove:" in out
    assert (
        cli.main(["preflight", str(view), "--twb", str(twb), "--sheet", "Other"]) == 0
    )
    assert "Other (w.twb)" in capsys.readouterr().out


def test_preflight_command_refuses_without_members_or_a_workbook(tmp_path, capsys):
    view, twb = _files(tmp_path, members=False)

    assert cli.main(["preflight", str(view), "--twb", str(twb)]) == 1
    assert "members.json: missing; run `members` first" in capsys.readouterr().err

    _save_members()
    assert cli.main(["preflight", str(view), "--twb", str(tmp_path / "none")]) == 1
    assert cli.main(["preflight", str(view), "--sheet", "Other"]) == 1
    assert "no comparison names the sheet Other; pass --twb" in capsys.readouterr().err


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

    lines, before = preflight.check("v", xml, sheet, comparison, members)
    facts = preflight.read_sheet(xml, sheet)
    sheet_text = "\n".join(preflight._sheet_lines("ddi_suite.twb", sheet, facts))

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
