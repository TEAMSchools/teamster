"""Tests for scripts/cube_validate_snapshot.py. No live calls."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate_snapshot.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate_snapshot", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate_snapshot"] = mod
    spec.loader.exec_module(mod)
    return mod


snap = _load()
TWB = (FIX / "review.twb").read_text(encoding="utf-8", newline="")


def test_read_workbook_lists_each_dashboards_sheets():
    wb = snap.read_workbook(TWB)
    assert wb.dashboards == {"Overview": ["Overview - Table", "Overview - Detail"]}


def test_filter_cards_carry_field_caption_and_default():
    wb = snap.read_workbook(TWB)
    cards = {c.field: c for c in wb.filters}
    assert set(cards) == {
        "region",
        "school",
        "grade_level",
        "iep_status",
        "student_name",
        "Calculation_1",
        "academic_year",
    }
    assert cards["school"].caption == "School Name"  # explicit caption wins
    assert cards["grade_level"].caption == "Grade Level"  # Tableau's default
    assert cards["region"].default_all is True
    assert cards["iep_status"].default_all is False  # saved as "No IEP" only
    assert cards["school"].datasource == "rpt_demo (kipptaf_tableau)"


def test_calculated_filter_values_come_from_formula_literals():
    wb = snap.read_workbook(TWB)
    calc = next(c for c in wb.filters if c.field == "Calculation_1")
    assert calc.calculated is True
    assert calc.caption == "Is Tested"
    assert calc.values == ("Yes", "No")


def test_parameters_list_values_and_range_has_none():
    wb = snap.read_workbook(TWB)
    params = {p.caption: p for p in wb.params}
    assert params["Group By"].values == ("School", "Teacher", "Student")
    assert params["Group By"].default == "School"
    assert params["Goal %"].values == ()


def test_actions_are_filter_or_link():
    wb = snap.read_workbook(TWB)
    acts = {a.caption: a for a in wb.actions}
    assert acts["Table to Detail"].kind == "filter"
    assert acts["Table to Detail"].source_sheet == "Overview - Table"
    assert acts["Table to Detail"].target == "Overview"
    assert acts["Table to Detail"].exclude == ("Overview - Table",)
    assert acts["Open Report"].kind == "link"


@pytest.mark.parametrize(
    ("field", "caption"),
    [
        ("grade_level", "Grade Level"),
        ("c_504_status", "C 504 Status"),
        ("Title", "Title"),
    ],
)
def test_default_caption(field, caption):
    assert snap.default_caption(field) == caption


def test_review_copy_exposes_dashboard_sheets_only():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<window class='worksheet' name='Overview - Table' />" in out
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "hidden='true'" not in out
    # A sheet on no named dashboard keeps its window untouched.
    assert "<window class='worksheet' name='Scratch Sheet' />" in out


def test_review_copy_sets_on_empty_all_and_strips_click_filters():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<param name='on-empty' value='all' />" in out
    assert "value='none'" not in out
    assert "[Action (" not in out


def test_review_copy_is_valid_xml_and_leaves_the_rest_alone():
    out = snap.review_copy(TWB, ["Overview"])
    snap.SafeET.fromstring(out)
    # The saved "No IEP" filter on the table is not a click filter: it stays.
    assert "member='&quot;No IEP&quot;'" in out


def test_review_copy_refuses_a_dashboard_it_cannot_find():
    with pytest.raises(snap.ReviewCopyError, match="Nope"):
        snap.review_copy(TWB, ["Nope"])


def test_review_copy_detects_a_sheet_left_hidden(monkeypatch):
    # Break the expose step: the check must catch it, not pass it silently.
    monkeypatch.setattr(snap, "_expose", lambda text, sheets: text)
    with pytest.raises(snap.ReviewCopyError, match="still hidden"):
        snap.review_copy(TWB, ["Overview"])


def test_views_to_hide_keeps_only_the_named_views():
    out = snap.review_copy(TWB, ["Overview"])
    hide = snap.views_to_hide(
        out, {"Overview", "Overview - Table", "Overview - Detail"}
    )
    assert hide == ["Scratch Sheet"]


def make_hyper(path, columns, rows):
    """A synthetic .hyper with one table, "Extract"."Extract"."""
    hapi = pytest.importorskip("tableauhyperapi")
    types = {
        "text": hapi.SqlType.text(),
        "int": hapi.SqlType.int(),
        "double": hapi.SqlType.double(),
    }
    table = hapi.TableDefinition(
        hapi.TableName("Extract", "Extract"),
        [hapi.TableDefinition.Column(n, types[t], hapi.NULLABLE) for n, t in columns],
    )
    with hapi.HyperProcess(hapi.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with hapi.Connection(
            hp.endpoint, str(path), hapi.CreateMode.CREATE_AND_REPLACE
        ) as c:
            c.catalog.create_schema("Extract")
            c.catalog.create_table(table)
            with hapi.Inserter(c, table) as ins:
                ins.add_rows(rows)
                ins.execute()
    return path


COLUMNS = [
    ("student_number", "int"),
    ("academic_year", "int"),
    ("region", "text"),
    ("school", "text"),
    ("grade_level", "int"),
    ("homeroom", "text"),
    ("iep_status", "text"),
    ("is_flag", "text"),
]


def demo_rows():
    """2 regions, 2 schools each, grades 5 and 6, 1 homeroom per school-grade."""
    rows, sid = [], 0
    for region, schools in (
        ("North", ("Alpha", "Beta")),
        ("South", ("Gamma", "Delta")),
    ):
        for school in schools:
            for grade in (5, 6):
                for i in range(12):
                    sid += 1
                    iep = "Has IEP" if i % 4 == 0 else "No IEP"
                    flag = "Yes" if i == 0 else None
                    rows.append(
                        (
                            sid,
                            2026,
                            region,
                            school,
                            grade,
                            f"{school}-{grade}",
                            iep,
                            flag,
                        )
                    )
    return rows


@pytest.fixture
def demo_hyper(tmp_path):
    return make_hyper(tmp_path / "demo.hyper", COLUMNS, demo_rows())


def test_profile_counts_distinct_students_and_keeps_blank(demo_hyper):
    with snap.Hyper(demo_hyper) as h:
        prof = snap.profile(h, ["region", "is_flag"])
    assert prof["region"] == [("North", 48), ("South", 48)]
    assert (None, 88) in prof["is_flag"] and ("Yes", 8) in prof["is_flag"]


def test_profile_where_limits_rows(demo_hyper):
    with snap.Hyper(demo_hyper) as h:
        prof = snap.profile(h, ["school"], where="\"region\" = 'North'")
    assert sorted(v for v, _ in prof["school"]) == ["Alpha", "Beta"]


def test_nesting_finds_school_inside_region_and_grade_crossing_school(demo_hyper):
    fields = ["region", "school", "grade_level", "homeroom", "iep_status"]
    with snap.Hyper(demo_hyper) as h:
        scores, distinct = snap.nesting(h, fields)
    assert scores[("school", "region")] == pytest.approx(1.0)
    assert scores[("homeroom", "school")] == pytest.approx(1.0)
    assert scores[("homeroom", "grade_level")] == pytest.approx(1.0)
    # grade has fewer values than school, so it is never scored as school's child,
    # and school does not predict grade: they cross.
    assert ("grade_level", "school") not in scores
    assert scores[("school", "grade_level")] == pytest.approx(0.0)
    assert distinct["homeroom"] == 8


def test_nesting_scores_a_lopsided_parent_as_zero_not_one(demo_hyper):
    # is_flag is blank on 11 of 12 rows: "school predicts is_flag" must not
    # score near 1 just because blank is the majority everywhere.
    with snap.Hyper(demo_hyper) as h:
        scores, _ = snap.nesting(h, ["school", "is_flag"])
    assert scores[("school", "is_flag")] == pytest.approx(0.0)


# Scores as measured on the DDI weekly extract (2026-10-09), rounded.
DDI_SCORES = {
    ("head_of_school", "region"): 1.0,
    ("school", "region"): 1.0,
    ("school", "head_of_school"): 1.0,
    ("school", "school_level"): 1.0,
    ("homeroom_section", "region"): 0.941,
    ("homeroom_section", "head_of_school"): 0.960,
    ("homeroom_section", "school"): 0.909,
    ("homeroom_section", "grade_level"): 0.996,
    ("course_section", "grade_level"): 0.877,
    ("week_start_monday", "term"): 1.0,
    ("module_code", "module_type"): 1.0,
    ("school", "grade_level"): 0.10,
}
DDI_DISTINCT = {
    "region": 4,
    "school_level": 3,
    "head_of_school": 9,
    "school": 24,
    "grade_level": 13,
    "homeroom_section": 389,
    "course_section": 409,
    "term": 2,
    "week_start_monday": 21,
    "module_type": 6,
    "module_code": 20,
    "iep_status": 2,
}


def test_derive_trees_matches_the_ddi_measurement():
    t = snap.derive_trees(list(DDI_DISTINCT), DDI_SCORES, DDI_DISTINCT)
    assert t.trees["region"] == [
        "region",
        "head_of_school",
        "school_level",
        "school",
        "grade_level",
        "homeroom_section",
    ]
    assert t.trees["term"] == ["term", "week_start_monday"]
    assert t.trees["module_type"] == ["module_type", "module_code"]
    assert t.cross_cuts == ["course_section", "iep_status"]
    assert t.borderline == [("course_section", "grade_level", 0.877)]


def test_an_accepted_borderline_pair_joins_its_tree():
    t = snap.derive_trees(
        list(DDI_DISTINCT),
        DDI_SCORES,
        DDI_DISTINCT,
        accept={("course_section", "grade_level")},
    )
    assert "course_section" in t.trees["region"]
    assert t.borderline == []
    assert "course_section" not in t.cross_cuts


DS = "rpt_demo (kipptaf_tableau)"
PROFILES = {
    DS: {
        "region": [("North", 48), ("South", 48)],
        "school": [("Alpha", 24), ("Beta", 24), ("Gamma", 24), ("Delta", 6)],
        "grade_level": [("5", 48), ("6", 48)],
        "iep_status": [("No IEP", 72), ("Has IEP", 24), (None, 3)],
        "academic_year": [("2026", 96), ("2025", 90), ("2024", 80)],
        "student_name": [("someone", 1)],
    }
}
TREES = {
    DS: snap.Trees({"region": ["region", "school", "grade_level"]}, ["iep_status"])
}


def _plan():
    wb = snap.read_workbook(TWB)
    return snap.plan_states(wb, PROFILES, TREES, ("2026", "2025"))


def _ids(items, tier):
    return {i.state.id for i in items if i.tier == tier}


def test_state_ids_are_stable_and_readable():
    s = snap.State("Overview", filters=(("School Name", "Alpha"), ("Region", "North")))
    assert s.id == "overview--region-north--school-name-alpha"
    assert snap.State("Overview").id == "overview--default"
    assert snap.State.from_dict(s.as_dict()) == s


def test_must_includes_default_params_tree_top_crosscuts_years_and_clicks():
    must = _ids(_plan(), "must")
    assert "overview--default" in must
    assert "overview--group-by-teacher" in must
    assert {"overview--region-north", "overview--region-south"} <= must
    assert {"overview--iep-status-no-iep", "overview--iep-status-has-iep"} <= must
    assert "overview--iep-status-blank" in must
    assert {"overview--academic-year-2026", "overview--academic-year-2025"} <= must
    assert "overview--academic-year-2024" not in must
    assert "overview--is-tested-yes" in must  # calculated filter, every value
    assert "overview--iep-status-all" in must  # saved default is not All
    assert "overview--click-table-to-detail-largest" in must
    assert "overview--click-table-to-detail-small" in must


def test_person_level_values_and_links_are_skipped_not_exported():
    items = _plan()
    skipped = _ids(items, "skipped")
    assert "overview--group-by-student" in skipped  # person-level parameter value
    assert "overview--group-by-student" not in _ids(items, "must")
    assert any(
        i.state.id.startswith("overview--student-name")
        for i in items
        if i.tier == "skipped"
    )
    assert "overview--click-open-report-largest" in skipped
    assert any("free-entry" in i.why for i in items if i.tier == "skipped")


def test_tree_levels_below_the_top_are_left_to_the_descent():
    every = {i.state.id for i in _plan()}
    assert not any(i.startswith("overview--school-name-") for i in every)


def test_plan_yaml_groups_by_tier():
    text = snap.plan_yaml(_plan())
    assert text.index("must:") < text.index("optional:") < text.index("skipped:")
