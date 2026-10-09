"""Tests for scripts/cube_validate_snapshot.py. No live calls."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
    ("tier", "text"),
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
                    # Blank on exactly the rows is_flag is blank: correlated blanks.
                    tier = ("Tier 1" if grade == 5 else "Tier 2") if i == 0 else None
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
                            tier,
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


def test_a_single_value_flag_is_never_a_parent(demo_hyper):
    # is_flag is "Yes" or blank. Blank is not a value for nesting, so the flag has
    # one value and nothing can nest inside it: it stays a cross-cut.
    with snap.Hyper(demo_hyper) as h:
        scores, _ = snap.nesting(h, ["school", "is_flag"])
    assert ("school", "is_flag") not in scores


def test_fields_blank_on_the_same_rows_do_not_nest(demo_hyper):
    # tier is blank exactly where is_flag is. Counting blank as a value made tier
    # look "inside" is_flag (lambda 1.0) on the DDI assessment extract.
    with snap.Hyper(demo_hyper) as h:
        scores, _ = snap.nesting(h, ["is_flag", "tier"])
    assert ("tier", "is_flag") not in scores


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


def test_a_cross_cut_with_many_values_is_sampled_not_split():
    # On the DDI assessment extract, `team` (400+ homerooms) landed as a cross-cut
    # and planned 413 must states.
    wb = snap.read_workbook(TWB)
    profiles = {
        DS: {**PROFILES[DS], "school": [(f"S{i:02d}", 20 + i) for i in range(20)]}
    }
    trees = {DS: snap.Trees({"region": ["region"]}, ["iep_status", "school"])}
    items = snap.plan_states(wb, profiles, trees, ("2026", "2025"))
    school = [i for i in items if i.state.id.startswith("overview--school-name-")]
    assert [i.tier for i in school] == ["optional", "optional"]
    assert "too many values" in school[0].why
    assert {"overview--iep-status-no-iep", "overview--iep-status-has-iep"} <= _ids(
        items, "must"
    )


def test_best_parents_names_the_strongest_candidate_for_each_field():
    scores = {
        ("team", "school"): 0.7,
        ("team", "region"): 0.5,
        ("school", "region"): 1.0,
    }
    assert snap.best_parents(scores, ["team", "region"]) == {"team": ("school", 0.7)}


def test_plan_yaml_groups_by_tier():
    text = snap.plan_yaml(_plan())
    assert text.index("must:") < text.index("optional:") < text.index("skipped:")


def test_new_snapshot_dir_keeps_the_latest_two(tmp_path):
    t0 = dt.datetime(2026, 10, 9, 8, 0)
    dirs = [
        snap.new_snapshot_dir("DDI Suite", t0 + dt.timedelta(hours=h), tmp_path)
        for h in range(3)
    ]
    left = sorted(p.name for p in (tmp_path / "ddi-suite").iterdir())
    assert left == [dirs[1].name, dirs[2].name]
    assert snap.latest_snapshot("DDI Suite", tmp_path) == dirs[2]


def test_manifest_round_trips(tmp_path):
    m = snap.Manifest(
        workbook="DDI Suite",
        workbook_luid="w1",
        copy_luid="c1",
        opened_at="2026-10-09T08:00:00+00:00",
        live_updated_at="2026-10-09T05:00:00+00:00",
        extracts={
            DS: {
                "file": "federated_demo1.hyper",
                "refreshed": "2026-10-08T05:39:00+00:00",
            }
        },
        fields={"Region": {"field": "region", "datasource": DS}},
        states={},
    )
    snap.write_manifest(tmp_path / "manifest.json", m)
    assert snap.read_manifest(tmp_path / "manifest.json") == m


def test_csv_rows_counts_data_rows_and_survives_empty_exports():
    assert snap.csv_rows(b"\xef\xbb\xbfA,B\r\n1,2\r\n3,4\r\n") == 2
    assert snap.csv_rows(b"A,B\r\n") == 0
    assert snap.csv_rows(b"") == 0


def test_filter_ignored_when_every_sheet_is_unchanged():
    parent = {"S1": b"a\r\n1\r\n", "S2": b"b\r\n2\r\n"}
    assert snap.filter_ignored(parent, dict(parent), covers_all=False) is True
    assert (
        snap.filter_ignored(
            parent, {"S1": b"a\r\n9\r\n", "S2": parent["S2"]}, covers_all=False
        )
        is False
    )


def test_filter_unchanged_is_fine_when_the_value_covers_every_row():
    parent = {"S1": b"a\r\n1\r\n"}
    assert snap.filter_ignored(parent, dict(parent), covers_all=True) is False


def test_empty_exports_on_both_sides_are_not_read_as_ignored():
    # A state can legitimately empty a sheet the parent also left empty.
    parent = {"S1": b"a\r\n"}
    assert snap.filter_ignored(parent, {"S1": b"a\r\n"}, covers_all=False) is False


def test_parent_of_drops_the_last_filter():
    s = snap.State("Overview", filters=(("Region", "North"), ("School Name", "Alpha")))
    assert snap.parent_of(s) == snap.State("Overview", filters=(("Region", "North"),))
    assert snap.parent_of(
        snap.State("Overview", params=(("Group By", "Teacher"),))
    ) == snap.State("Overview")


class FakeWorkbooks:
    def __init__(self, items):
        self.items = {w.id: w for w in items}
        self.deleted, self.published = [], []

    def delete(self, luid):
        self.deleted.append(luid)
        self.items.pop(luid, None)

    def publish(self, item, path, mode):
        self.published.append(
            (item.name, item.project_id, list(item.hidden_views), mode)
        )
        new = SimpleNamespace(
            id="copy-1",
            name=item.name,
            project_id=item.project_id,
            project_name="TEMP-CB",
            created_at=None,
        )
        self.items[new.id] = new
        return new

    def get_by_id(self, luid):
        return SimpleNamespace(updated_at=dt.datetime(2026, 10, 9, 5, 0, tzinfo=dt.UTC))


def _session(monkeypatch, items):
    wbs = FakeWorkbooks(items)
    server = SimpleNamespace(workbooks=wbs)
    monkeypatch.setattr(
        snap, "_workbooks_in", lambda server, project: list(wbs.items.values())
    )
    now = lambda: dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.UTC)  # noqa: E731
    return snap.Session(server, snap.TEMP_CB, now=now), wbs


def test_session_refuses_a_production_project():
    with pytest.raises(snap.SessionError, match="non-production"):
        snap.Session(SimpleNamespace(), "some-production-project")


def test_sweep_deletes_only_old_review_copies(monkeypatch):
    old = SimpleNamespace(
        id="a",
        name="ZZ-REVIEW 2026-10-07 0800 DDI Suite",
        created_at=dt.datetime(2026, 10, 7, 8, tzinfo=dt.UTC),
        project_id=snap.TEMP_CB,
    )
    fresh = SimpleNamespace(
        id="b",
        name="ZZ-REVIEW 2026-10-09 1100 DDI Suite",
        created_at=dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC),
        project_id=snap.TEMP_CB,
    )
    mine = SimpleNamespace(
        id="c",
        name="My Draft",
        created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        project_id=snap.TEMP_CB,
    )
    # Review copies other work made (the tableau-workbook-xml skill uses the same
    # prefix), and this tool's copies of other workbooks, are never swept.
    other_work = SimpleNamespace(
        id="d",
        name="ZZ-REVIEW 2026-09-09 Survey Dashboard dept gate",
        created_at=dt.datetime(2026, 9, 9, tzinfo=dt.UTC),
        project_id=snap.TEMP_CB,
    )
    other_book = SimpleNamespace(
        id="e",
        name="ZZ-REVIEW 2026-10-07 0800 Attendance Dashboard",
        created_at=dt.datetime(2026, 10, 7, 8, tzinfo=dt.UTC),
        project_id=snap.TEMP_CB,
    )
    s, wbs = _session(monkeypatch, [old, fresh, mine, other_work, other_book])
    assert s.sweep("DDI Suite") == ["ZZ-REVIEW 2026-10-07 0800 DDI Suite"]
    assert wbs.deleted == ["a"]


def test_publish_requires_the_prefix_and_creates_new(monkeypatch, tmp_path):
    s, wbs = _session(monkeypatch, [])
    with pytest.raises(snap.SessionError, match="ZZ-REVIEW"):
        s.publish(tmp_path / "x.twbx", "DDI Suite", [])
    luid = s.publish(
        tmp_path / "x.twbx", "ZZ-REVIEW 2026-10-09 1200 DDI Suite", ["Scratch Sheet"]
    )
    assert luid == "copy-1"
    name, project, hidden, mode = wbs.published[0]
    assert (
        project == snap.TEMP_CB and hidden == ["Scratch Sheet"] and mode == "CreateNew"
    )


def test_close_confirms_the_copy_is_gone(monkeypatch):
    copy = SimpleNamespace(
        id="copy-1", name="ZZ-REVIEW x", created_at=None, project_id=snap.TEMP_CB
    )
    s, wbs = _session(monkeypatch, [copy])
    s.close("copy-1")
    assert wbs.deleted == ["copy-1"]


def test_close_raises_with_the_luid_when_the_copy_survives(monkeypatch):
    copy = SimpleNamespace(
        id="copy-1", name="ZZ-REVIEW x", created_at=None, project_id=snap.TEMP_CB
    )
    s, wbs = _session(monkeypatch, [copy])
    wbs.delete = lambda luid: None  # the server ignores the delete
    with pytest.raises(snap.SessionError, match="copy-1"):
        s.close("copy-1")


def test_check_refresh_stops_when_the_live_workbook_moved(monkeypatch):
    s, _ = _session(monkeypatch, [])
    s.check_refresh("w1", "2026-10-09T05:00:00+00:00")
    with pytest.raises(snap.RefreshedError):
        s.check_refresh("w1", "2026-10-08T05:00:00+00:00")


def test_vf_value_escapes_commas_and_expands_all_and_blank():
    assert snap.vf_value("KIPP, Newark", []) == "KIPP\\, Newark"
    assert snap.vf_value(snap.ALL, ["A", "B, C"]) == "A,B\\, C"
    assert snap.vf_value(snap.BLANK, []) == "Null"


def test_pick_click_row_takes_the_largest_or_smallest_mark():
    data = "Title,School,Score\r\nT1,All,50\r\nT1,Alpha,80\r\nT2,Beta,20\r\nT3,*,90\r\n".encode()
    assert snap.pick_click_row(data, "largest", ["Title", "School"]) == {
        "Title": "T1",
        "School": "Alpha",
    }
    assert snap.pick_click_row(data, "small", ["Title", "School"]) == {
        "Title": "T2",
        "School": "Beta",
    }


def test_retry_recovers_then_gives_up():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("401002")
        return "ok"

    assert snap.retry(flaky, sleep=lambda s: None) == "ok"
    with pytest.raises(RuntimeError):
        snap.retry(
            lambda: (_ for _ in ()).throw(RuntimeError("x")), sleep=lambda s: None
        )


def NEVER(state):  # noqa: N802 - a coverage check that never covers
    return False


class FakeSession:
    def __init__(self, exports):
        self.exports, self.calls = exports, []

    def export_view(self, sheet, filters, params=()):
        self.calls.append((sheet, tuple(filters), tuple(params)))
        return self.exports(sheet, {**dict(filters), **dict(params)})


def _manifest():
    return snap.Manifest(
        "Demo",
        "w1",
        "copy-1",
        "t",
        "t",
        {},
        {"Region": {"field": "region", "datasource": DS}},
        {},
    )


def test_export_state_writes_csvs_and_marks_ok(tmp_path):
    snapdir = tmp_path
    (snapdir / "csv").mkdir()
    wb = snap.read_workbook(TWB)

    def exports(sheet, f):
        return f"Region,N\r\n{f.get('Region', 'All')},1\r\n".encode()

    s, m = FakeSession(exports), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, snapdir, wb, default, {}, NEVER, {})
    north = snap.State("Overview", filters=(("Region", "North"),))
    entry = snap.export_state(s, m, snapdir, wb, north, {}, NEVER, {})
    assert entry["status"] == "ok"
    assert entry["sheets"]["Overview - Table"]["rows"] == 1
    assert (snapdir / "csv" / "overview-table" / f"{north.id}.csv").exists()


def test_export_state_flags_an_ignored_filter(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s, m = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n"), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, tmp_path, wb, default, {}, NEVER, {})
    north = snap.State("Overview", filters=(("Region", "North"),))
    assert (
        snap.export_state(s, m, tmp_path, wb, north, {}, NEVER, {})["status"]
        == "filter_ignored"
    )


def test_export_state_marks_a_failing_export(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)

    def boom(sheet, f):
        raise RuntimeError("429")

    entry = snap.export_state(
        FakeSession(boom), _manifest(), tmp_path, wb, snap.State("Overview"), {}, {}, {}
    )
    assert entry["status"] == "export_failed"


def test_click_state_exports_targets_with_the_clicked_marks_values(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)

    def exports(sheet, f):
        if sheet == "Overview - Table" and not f:
            return b"Title,Score\r\nT1,80\r\nT2,20\r\n"
        return b"Title,Score\r\nT1,80\r\n"

    s = FakeSession(exports)
    state = snap.State("Overview", click=("Table to Detail", "largest"))
    entry = snap.export_state(
        s, _manifest(), tmp_path, wb, state, {}, {}, {"Overview - Table": ["Title"]}
    )
    assert entry["click_filters"] == {"Title": "T1"}
    assert ("Overview - Detail", (("Title", "T1"),), ()) in s.calls
    assert list(entry["sheets"]) == ["Overview - Detail"]


def test_plan_command_writes_a_proposal_from_a_local_twbx(tmp_path, demo_hyper):
    twbx = tmp_path / "demo.twbx"
    with snap.zipfile.ZipFile(twbx, "w") as z:
        z.writestr("Demo.twb", TWB)
        z.write(demo_hyper, "Data/Extracts/federated_demo1.hyper")
    checks = tmp_path / "checks.yml"
    checks.write_text("workbook: Demo\nworkbook_luid: w1\ndashboards: [Overview]\n")
    out = tmp_path / "plan.yml"
    assert snap.main(["plan", str(checks), "--twbx", str(twbx), "--out", str(out)]) == 0
    text = out.read_text()
    assert "overview--default" in text and "trees:" in text


# ---------------------------------------------------------------- final review fixes
def test_saved_default_selections_are_read():
    cards = {c.field: c for c in snap.read_workbook(TWB).filters}
    assert cards["iep_status"].default_values == ("No IEP",)
    assert cards["region"].default_values == ()


def test_manifest_carries_saved_defaults(tmp_path):
    m = _manifest()
    m.defaults = {"Overview": {"IEP Status": ["No IEP"]}}
    snap.write_manifest(tmp_path / "manifest.json", m)
    assert snap.read_manifest(tmp_path / "manifest.json").defaults == m.defaults


def test_parameter_states_use_parameters_and_are_checked(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s, m = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n"), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, tmp_path, wb, default, {}, NEVER, {})
    teacher = snap.State("Overview", params=(("Group By", "Teacher"),))
    entry = snap.export_state(s, m, tmp_path, wb, teacher, {}, NEVER, {})
    assert ("Overview - Table", (), (("Group By", "Teacher"),)) in s.calls
    assert entry["status"] == "filter_ignored"


def test_an_unchanged_export_is_fine_when_the_value_covers_its_parent(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s, m = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n"), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, tmp_path, wb, default, {}, NEVER, {})
    north = snap.State("Overview", filters=(("Region", "North"),))
    assert (
        snap.export_state(s, m, tmp_path, wb, north, {}, lambda st: True, {})["status"]
        == "ok"
    )


def _coverage_manifest(tmp_path, demo_hyper):
    (tmp_path / "extract").mkdir()
    (tmp_path / "extract" / "demo.hyper").write_bytes(demo_hyper.read_bytes())
    m = _manifest()
    m.extracts = {DS: {"file": "extract/demo.hyper", "refreshed": None}}
    m.fields = {
        "Region": {"field": "region", "datasource": DS},
        "School Name": {"field": "school", "datasource": DS},
        "Is Tested": {"field": "Calculation_1", "datasource": DS},
    }
    return m


def test_coverage_is_judged_within_the_parent(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    with snap.Coverage(m, tmp_path) as covers:
        # Every Alpha student is in North, so North adds nothing under Alpha.
        assert covers(
            snap.State(
                "Overview", filters=(("School Name", "Alpha"), ("Region", "North"))
            )
        )
        assert not covers(
            snap.State(
                "Overview", filters=(("Region", "North"), ("School Name", "Alpha"))
            )
        )


def test_value_maps_skip_fields_the_extract_does_not_have(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    values = snap._value_maps(m, tmp_path)
    assert values["Region"] == ["North", "South"] and "Is Tested" not in values


def test_click_values_lose_tableau_formatting():
    data = b"Day,Score\r\n9/15/2026,80\r\n1/2/2026,20\r\n"
    assert snap.pick_click_row(data, "largest", ["Day"]) == {"Day": "2026-09-15"}


def test_export_signs_in_again_when_tableau_drops_the_session():
    # A PAT allows one session: another sign-in with it ends ours (401002).
    calls = {"populate": 0, "sign_in": 0}
    view = SimpleNamespace(name="S1", csv=[b"A\r\n1\r\n"])

    def populate_csv(v, opts):
        calls["populate"] += 1
        if calls["populate"] == 1:
            raise RuntimeError("401002: Unauthorized Access")

    server = SimpleNamespace(
        views=SimpleNamespace(populate_csv=populate_csv),
        auth=SimpleNamespace(
            sign_in=lambda a: calls.__setitem__("sign_in", calls["sign_in"] + 1)
        ),
    )
    s = snap.Session(server, snap.TEMP_CB, auth="pat", sleep=lambda w: None)
    s._views = {"S1": view}
    assert s.export_view("S1", []) == b"A\r\n1\r\n"
    assert calls == {"populate": 2, "sign_in": 1}


def test_a_filter_set_to_its_saved_default_covers_the_parent(tmp_path, demo_hyper):
    # The default view already shows only the saved default, so a state that sets
    # the same value exports the same thing: expected, not an ignored filter.
    m = _coverage_manifest(tmp_path, demo_hyper)
    m.defaults = {"Overview": {"Region": ["North"]}}
    with snap.Coverage(m, tmp_path) as covers:
        assert covers(snap.State("Overview", filters=(("Region", "North"),)))
