"""Tests for scripts/cube_validate.py. No live calls."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate.py"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load()
SECRET = "x" * 32  # PyJWT warns on HS256 keys under 32 bytes


# ---------------------------------------------------------------- Task 3: comparison
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "∅"),
        ("2026-09-01T00:00:00.000", "2026-09-01"),
        (dt.date(2026, 9, 1), "2026-09-01"),
        ("5", "5"),
        (5, "5"),
        (5.0, "5"),
        ("5.000", "5"),
        (True, "true"),
        ("False", "false"),
        (" Newark ", "Newark"),
    ],
)
def test_norm_key_(value, expected):
    assert cv.norm_key(value) == expected


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, bodies):
        self.bodies, self.calls = list(bodies), []

    def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        return FakeResponse(self.bodies.pop(0))


def test_cube_client_polls_continue_wait_and_sends_raw_token():
    http = FakeHttp(
        [
            {"error": "Continue wait"},
            {"data": [{"a": "1"}], "usedPreAggregations": {"r1": {}}},
        ]
    )
    client = cv.CubeClient(
        "https://cube/api/", SECRET, "me@example.org", http=http, sleep=lambda _: None
    )
    rows, preaggs = client.load({"measures": []})
    assert rows == [{"a": "1"}] and preaggs == ["r1"]
    url, body, headers = http.calls[0]
    assert url == "https://cube/api/load" and body == {"query": {"measures": []}}
    assert not headers["Authorization"].startswith("Bearer")


def test_cube_client_row_limit_errors():
    http = FakeHttp([{"data": [{}] * cv.CUBE_LIMIT}])
    client = cv.CubeClient("u", SECRET, "e", http=http, sleep=lambda _: None)
    with pytest.raises(cv.CubeError, match="row limit"):
        client.load({})


def test_cube_client_error_body_raises():
    client = cv.CubeClient(
        "u", SECRET, "e", http=FakeHttp([{"error": "bad member"}]), sleep=lambda _: None
    )
    with pytest.raises(cv.CubeError, match="bad member"):
        client.load({})


def test_py_value_converts_hyper_dates():
    class HyperDate:
        def to_date(self):
            return dt.date(2026, 9, 1)

    assert cv._py_value(HyperDate()) == dt.date(2026, 9, 1)
    assert cv._py_value(5) == 5


class StatusHttp(FakeHttp):
    def __init__(self, replies):
        super().__init__([])
        self.replies = list(replies)

    def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        body, status = self.replies.pop(0)
        return FakeResponse(body, status)


def test_cube_client_backs_off_when_cube_is_overloaded():
    waits = []
    http = StatusHttp(
        [({"error": "Too many requests"}, 429), ({"data": [{"a": "1"}]}, 200)]
    )
    client = cv.CubeClient(
        "https://cube/api", SECRET, "me@example.org", http=http, sleep=waits.append
    )
    rows, _ = client.load({"measures": []})
    assert rows == [{"a": "1"}] and waits and waits[0] >= 1


def test_cube_client_gives_each_thread_its_own_http_client():
    made = []
    client = cv.CubeClient(
        "https://cube/api",
        SECRET,
        "me@example.org",
        http_factory=lambda: made.append(1) or object(),
    )
    a = client._http()
    b = []
    t = threading.Thread(target=lambda: b.append(client._http()))
    t.start()
    t.join()
    assert a is client._http() and b[0] is not a and len(made) == 2


def test_filtered_handles_count_star_and_countif():
    assert cv._filtered("count(*)", "x = 1") == "COUNTIF(x = 1)"
    assert cv._filtered("countif(y = 2)", "x = 1") == "COUNTIF(x = 1 AND y = 2)"


def test_to_hyper_sql_names_the_extract_table():
    out = cv.to_hyper_sql(
        f"select count(distinct x) as n from `{cv.EXTRACT_TABLE}` where cast(y as string) = 'a'"
    )
    assert '"Extract"."Extract"' in out and "TEXT" in out.upper()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("9/15/2026", "2026-09-15"),
        ("1,234", "1234"),
        ("Newark", "Newark"),
        (None, "∅"),
        ("5", "5"),
    ],
)
def test_norm_dim_reads_tableau_formats(value, expected):
    assert cv.norm_dim(value) == expected


def test_fix_sides_groups_mismatches():
    sides = cv.fix_sides(
        {"mismatches": {"a": {"fix": "cube"}, "b": {"fix": "dashboard"}}}
    )
    assert (
        sides["cube"] == {"a"}
        and sides["dashboard"] == {"b"}
        and sides["source"] == frozenset()
    )


def test_cube_client_keeps_the_last_refresh_time():
    http = FakeHttp([{"data": [], "lastRefreshTime": "2026-10-09T10:00:00.000Z"}])
    client = cv.CubeClient("u", SECRET, "e", http=http, sleep=lambda _: None)
    assert client.last_refresh is None
    client.load({"measures": []})
    assert client.last_refresh == "2026-10-09T10:00:00.000Z"


def test_table_modified_reads_bigquery_metadata():
    from types import SimpleNamespace

    at = dt.datetime(2026, 10, 9, 10, tzinfo=dt.UTC)
    fake = SimpleNamespace(get_table=lambda t: SimpleNamespace(modified=at))
    assert cv.table_modified("p.d.t", client=fake) == at


DS = "rpt_demo (kipptaf_tableau)"
CHECKS = {
    "workbook": "Demo",
    "workbook_luid": "w1",
    "student_count": "demo.count_students",
    "scope": {"filter": "Region"},
    "filters": {"Region": {"cube": "demo.region"}},
    "rows": {"111": ["demo.avg_score"]},
    "sheets": {
        "Overview - Table": {
            "datasource": DS,
            "dims": {
                "Region": {"cube": "demo.region", "sql": "region"},
                "School Name": {"cube": "demo.school", "sql": "school"},
                "Student": {"cube": None, "sql": "student_name", "person": True},
            },
            "measures": {
                "Avg Score": {
                    "cube": "demo.avg_score",
                    "sql": "avg(score)",
                    "round": 2,
                },
                "% Complete": {
                    "cube": "demo.pct_complete",
                    "num": "count(distinct if(is_complete = 1, student_number, null))",
                    "den": "count(distinct student_number)",
                },
            },
        }
    },
    "mismatches": {},
}


def _write(tmp_path, d):
    p = tmp_path / "checks.yml"
    p.write_text(yaml.safe_dump(d, sort_keys=False))
    return p


def test_load_checks_builds_sheet_maps(tmp_path):
    c = cv.load_checks(_write(tmp_path, CHECKS))
    s = c["sheets"]["Overview - Table"]
    assert s.dims["School Name"] == cv.Dim("demo.school", "school")
    assert s.dims["Student"].person is True
    assert s.measures["Avg Score"].round == 2
    assert s.measures["% Complete"].num.startswith("count(distinct")
    assert c["cube_filters"] == [] and c["extract_filters"] == []


def test_load_checks_rejects_a_measure_without_sql(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["sheets"]["Overview - Table"]["measures"]["Avg Score"].pop("sql")
    with pytest.raises(cv.CheckError, match="give sql, or num and den"):
        cv.load_checks(_write(tmp_path, bad))


def test_load_checks_checks_mismatches_and_variants(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["mismatches"] = {"dup": {"title": "fix(cube): x", "what": "y", "fix": "nobody"}}
    with pytest.raises(cv.CheckError, match="fix must be one of"):
        cv.load_checks(_write(tmp_path, bad))
    bad["mismatches"]["dup"]["fix"] = "cube"
    bad["sheets"]["Overview - Table"]["measures"]["Avg Score"]["variants"] = [
        {"explains": ["other"], "sql": "avg(x)"}
    ]
    with pytest.raises(cv.CheckError, match="unknown other"):
        cv.load_checks(_write(tmp_path, bad))


def test_load_checks_rows_must_name_mapped_members(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["rows"] = {"111": ["demo.nope"]}
    with pytest.raises(cv.CheckError, match="demo.nope"):
        cv.load_checks(_write(tmp_path, bad))


def test_read_export_keeps_repeated_columns():
    e = cv.read_export(
        b"\xef\xbb\xbfGrade Level,Schoolid,Schoolid,Mastery\r\n5,A,B,0.5\r\n"
    )
    assert e.columns == ["Grade Level", "Schoolid", "Schoolid (2)", "Mastery"]
    assert e.rows == [
        {"Grade Level": "5", "Schoolid": "A", "Schoolid (2)": "B", "Mastery": "0.5"}
    ]


def test_read_export_of_nothing_is_empty():
    assert cv.read_export(b"") == cv.Export([], [])
    assert cv.read_export(b"A,B\r\n") == cv.Export(["A", "B"], [])


@pytest.mark.parametrize(
    ("text", "round_to", "value", "decimals"),
    [
        ("36.24%", None, 0.3624, 4),
        ("100%", None, 1.0, 2),
        ("1,234", None, 1234.0, 0),
        ("0.362381", None, 0.362381, None),
        ("36.24", 2, 36.24, 2),
        ("-1.5", None, -1.5, None),
    ],
)
def test_parse_shown(text, round_to, value, decimals):
    s = cv.parse_shown(text, round_to)
    assert s.value == pytest.approx(value) and s.decimals == decimals


@pytest.mark.parametrize("text", ["", "All", "*", "Newark", None])
def test_parse_shown_rejects_non_numbers(text):
    assert cv.parse_shown(text) is None


def test_matches_shown_uses_the_shown_precision():
    assert cv.matches_shown(0.362381, cv.parse_shown("36.24%"))
    assert not cv.matches_shown(0.3630, cv.parse_shown("36.24%"))
    # A raw "1" means exactly 1, never "anything that rounds to 1".
    assert not cv.matches_shown(0.6, cv.parse_shown("1"))
    assert cv.matches_shown(1.0000000001, cv.parse_shown("1"))
    assert cv.matches_shown(None, None) and not cv.matches_shown(
        None, cv.parse_shown("1")
    )


def test_matches_raw():
    assert cv.matches_raw(0.8, 0.8000000001) and not cv.matches_raw(0.8, 0.81)
    assert cv.matches_raw(None, None) and not cv.matches_raw(None, 0.0)


def _checks(tmp_path, **extra):
    d = json.loads(json.dumps(CHECKS))
    d.update(extra)
    return cv.load_checks(_write(tmp_path, d))


def test_state_filters_translate_captions_all_and_blank(tmp_path):
    c = _checks(tmp_path)
    entry = {
        "state": {
            "dashboard": "Overview",
            "filters": {"Region": "North", "School Name": cv.ALL},
        },
        "click_filters": {"School Name": "Alpha"},
    }
    filters, missing = cv.state_filters(entry, c)
    assert filters == [
        {"member": "demo.region", "operator": "equals", "values": ["North"]},
        {"member": "demo.school", "operator": "equals", "values": ["Alpha"]},
    ]
    assert missing == []
    blank = {"state": {"dashboard": "Overview", "filters": {"Region": cv.BLANK}}}
    assert cv.state_filters(blank, c)[0] == [
        {"member": "demo.region", "operator": "notSet"}
    ]


def test_state_filters_report_captions_with_no_member(tmp_path):
    c = _checks(tmp_path)
    entry = {"state": {"dashboard": "Overview", "filters": {"Grade Level": "5"}}}
    assert cv.state_filters(entry, c) == ([], ["Grade Level"])


def test_parameters_add_filters_only_when_mapped(tmp_path):
    pf = {
        "Subject": {
            "Math": [
                {"member": "demo.subject", "operator": "equals", "values": ["Math"]}
            ]
        }
    }
    c = _checks(tmp_path, param_filters=pf)
    entry = {
        "state": {
            "dashboard": "Overview",
            "params": {"Subject": "Math", "Group By": "Teacher"},
        }
    }
    assert cv.state_filters(entry, c)[0] == pf["Subject"]["Math"]


def test_hard_filters_apply_per_datasource(tmp_path):
    c = _checks(
        tmp_path,
        cube_filters=[
            {"member": "demo.is_test", "operator": "equals", "values": ["false"]},
            {"member": "demo.other", "operator": "set", "datasource": "elsewhere"},
        ],
    )
    assert cv.hard_filters(c, DS) == [
        {"member": "demo.is_test", "operator": "equals", "values": ["false"]}
    ]


def test_scope_guard_stops_when_cube_misses_a_region(tmp_path):
    c = _checks(tmp_path)
    load = lambda q: ([{"demo.region": "North", "demo.count_students": "40"}], [])  # noqa: E731
    cv.scope_guard(load, c, {"North": 40, "South": 0})
    with pytest.raises(cv.ScopeError, match="South"):
        cv.scope_guard(load, c, {"North": 40, "South": 12})


def _sheet(tmp_path, **measure_extra):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["measures"]["Avg Score"].update(measure_extra)
    c = cv.load_checks(_write(tmp_path, d))
    return c, c["sheets"]["Overview - Table"]


class FakeCube:
    """Answers each query from rows keyed by the school, or the total."""

    def __init__(self, by_school, total):
        self.by_school, self.total, self.queries = by_school, total, []

    def __call__(self, q):
        self.queries.append(q)
        if "demo.school" in q["dimensions"]:
            return [{"demo.school": k, **v} for k, v in self.by_school.items()], [
                "rollup_a"
            ]
        return [dict(self.total)], []


def _row(avg, n=20):
    return {
        "demo.avg_score": str(avg),
        "demo.count_students": str(n),
        "demo.pct_complete": "0.8",
    }


def test_compare_matches_rows_and_totals(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(
        b"School Name,Avg Score\r\nAlpha,48.50\r\nBeta,50.00\r\nAll,49.25\r\n"
    )
    cube = FakeCube({"Alpha": _row(48.5), "Beta": _row(50)}, _row(49.25, 40))
    cells = cv.compare_export(sheet, "s1", export, cube, [], [], c)
    assert [(x.key, x.status) for x in cells] == [
        ({"School Name": "Alpha"}, "match"),
        ({"School Name": "Beta"}, "match"),
        ({"School Name": "All"}, "match"),
    ]
    assert len(cube.queries) == 2 and cube.queries[1]["dimensions"] == []
    assert cells[0].n_students == 20 and cells[0].rollups == ["rollup_a"]


def test_compare_flags_value_gaps_and_one_sided_slices(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\nGamma,30.00\r\n")
    cube = FakeCube({"Alpha": _row(47.0), "Beta": _row(50)}, _row(0))
    cells = {
        x.key["School Name"]: x
        for x in cv.compare_export(sheet, "s1", export, cube, [], [], c)
    }
    assert cells["Alpha"].status == "mismatch" and cells["Alpha"].cube == 47.0
    assert cells["Gamma"].reason == "Tableau shows this slice; Cube does not"
    assert cells["Beta"].reason == "Cube has this slice; Tableau does not"
    assert cells["Beta"].tableau is None


def test_multi_value_marks_and_unmapped_columns_are_not_comparable(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score,Mystery\r\n*,48.50,1\r\n")
    cells = cv.compare_export(sheet, "s1", export, FakeCube({}, _row(0)), [], [], c)
    reasons = sorted(x.reason for x in cells if x.status == "not_comparable")
    assert reasons == ["multi-value mark", "unmapped column"]


def test_a_filter_with_no_member_blocks_the_state(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\n")
    cells = cv.compare_export(
        sheet, "s1", export, FakeCube({}, _row(0)), [], ["Grade Level"], c
    )
    assert cells[0].status == "not_comparable" and "Grade Level" in cells[0].reason


def test_a_dimension_with_no_member_is_a_missing_member(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"Student,Avg Score\r\nsomeone,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, FakeCube({}, _row(0)), [], [], c)
    assert cells[0].status == "missing_member" and "Student" in cells[0].reason


def test_an_empty_export_still_shows_cubes_rows(tmp_path):
    c, sheet = _sheet(tmp_path)
    for data in (b"", b"School Name,Avg Score\r\n"):
        cells = cv.compare_export(
            sheet,
            "s1",
            cv.read_export(data),
            FakeCube({"Alpha": _row(48.5)}, _row(0)),
            [],
            [],
            c,
        )
        assert any(x.reason == "Cube has this slice; Tableau does not" for x in cells)


def test_percent_of_total_is_rebuilt_from_cubes_rows(tmp_path):
    c, sheet = _sheet(tmp_path, table_calc="percent_of_total", round=None)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,25%\r\nBeta,75%\r\n")
    cube = FakeCube({"Alpha": _row(10), "Beta": _row(30)}, _row(0))
    cells = cv.compare_export(sheet, "s1", export, cube, [], [], c)
    assert [x.status for x in cells] == ["match", "match"]


def test_cells_round_trip(tmp_path):
    cell = cv.Cell("S", "s1", {"A": "x"}, "M", "1", 1.0, 1.0, 20, "match")
    cv.write_cells(tmp_path / "cells.jsonl", [cell])
    assert cv.read_cells(tmp_path / "cells.jsonl") == [cell]


TREES = {DS: {"region": ["region", "school", "grade_level"]}}
CROSS = {DS: ["iep_status"]}
FIELDS = {
    "Region": {"field": "region", "datasource": DS},
    "School Name": {"field": "school", "datasource": DS},
    "Grade Level": {"field": "grade_level", "datasource": DS},
    "IEP": {"field": "iep_status", "datasource": DS},
}
KIDS = {
    "school": [("Alpha", 30), ("Beta", 20), ("Gamma", 12), ("Tiny", 4)],
    "grade_level": [("5", 15), ("6", 15)],
    "iep_status": [("No IEP", 25), ("Has IEP", 5)],
}


def _entry(filters, status="ok"):
    return {
        "state": {"dashboard": "Overview", "filters": filters},
        "status": status,
        "sheets": {},
    }


def children(ds, where, f):
    return KIDS[f]


def test_a_matching_node_samples_its_largest_and_smallest_children():
    states = {"n": _entry({"Region": "North"})}
    out = cv.next_states(states, {"n": "match"}, TREES, CROSS, FIELDS, children)
    assert [s["filters"]["School Name"] for s in out] == ["Alpha", "Gamma"]


def test_a_mismatching_node_gets_every_child_above_the_small_cell_size():
    states = {"n": _entry({"Region": "North"})}
    out = cv.next_states(states, {"n": "mismatch"}, TREES, CROSS, FIELDS, children)
    assert [s["filters"]["School Name"] for s in out] == ["Alpha", "Beta", "Gamma"]


def test_a_narrowed_gap_is_split_by_each_cross_cut():
    states = {
        "n": _entry({"Region": "North"}),
        "a": _entry({"Region": "North", "School Name": "Alpha"}),
        "b": _entry({"Region": "North", "School Name": "Beta"}),
    }
    out = cv.next_states(
        states,
        {"n": "mismatch", "a": "match", "b": "match"},
        TREES,
        CROSS,
        FIELDS,
        children,
    )
    iep = [
        s
        for s in out
        if "IEP" in s["filters"] and s["filters"].get("School Name") is None
    ]
    assert [s["filters"]["IEP"] for s in iep] == ["No IEP"]  # "Has IEP" has 5 students


def test_states_already_exported_are_not_proposed_again():
    states = {
        "n": _entry({"Region": "North"}),
        "a": _entry({"Region": "North", "School Name": "Alpha"}),
        "g": _entry({"Region": "North", "School Name": "Gamma"}),
    }
    out = cv.next_states(
        states,
        {"n": "match", "a": "match", "g": "match"},
        TREES,
        CROSS,
        FIELDS,
        children,
    )
    assert all(
        s["filters"].get("School Name") not in ("Alpha", "Gamma")
        or "Grade Level" in s["filters"]
        for s in out
    )


def test_non_tree_states_and_failed_exports_do_not_descend():
    states = {
        "p": {
            "state": {"dashboard": "Overview", "params": {"Group By": "Teacher"}},
            "status": "ok",
            "sheets": {},
        },
        "x": _entry({"Region": "North"}, status="filter_ignored"),
    }
    assert (
        cv.next_states(
            states, {"p": "mismatch", "x": "mismatch"}, TREES, CROSS, FIELDS, children
        )
        == []
    )


def test_state_status():
    cells = [
        cv.Cell("S", "a", {}, "M", "1", 1, 1, 20, "match"),
        cv.Cell("S", "a", {}, "M", "1", 1, 2, 20, "mismatch"),
        cv.Cell("S", "b", {}, "M", "1", 1, 1, 20, "match"),
    ]
    assert cv.state_status(cells) == {"a": "mismatch", "b": "match"}


def test_child_values_sql_filters_and_groups():
    sql = cv.child_values_sql([("region", "North"), ("iep_status", cv.BLANK)], "school")
    assert "cast(region as string) = 'North'" in sql and "iep_status is null" in sql
    assert sql.rstrip().endswith("group by 1")


def test_extract_sql_selects_grain_and_measure():
    _, sheet = _sheet_plain()
    sql = cv.extract_sql(
        sheet,
        sheet.measures["% Complete"],
        ["School Name"],
        ["(cast(region as string) = 'North')"],
    )
    assert sql.startswith("select school as g0, count(distinct if(is_complete = 1")
    assert "as m_num" in sql and "as m_den" in sql and sql.endswith("group by 1")


def _sheet_plain():
    import tempfile

    d = Path(tempfile.mkdtemp())
    c = cv.load_checks(_write(d, CHECKS))
    return c, c["sheets"]["Overview - Table"]


def test_extract_values_divides_num_by_den():
    rows = [
        {"g0": "Alpha", "m_num": 16, "m_den": 20},
        {"g0": "Beta", "m_num": 0, "m_den": 0},
    ]
    assert cv.extract_values(rows, 1) == {("Alpha",): 0.8, ("Beta",): None}


def test_state_where_translates_filters_and_hides_private_ones(tmp_path):
    c = _checks(
        tmp_path,
        extract_filters=[{"sql": "not is_test", "private": True}, {"sql": "enrolled"}],
    )
    sheet = c["sheets"]["Overview - Table"]
    entry = {
        "state": {"dashboard": "Overview", "filters": {"Region": "North"}},
        "click_filters": {"School Name": "Alpha"},
    }
    fields = {"Region": {"field": "region", "datasource": DS}}
    assert cv.state_where(entry, c, fields, sheet) == [
        "cast(region as string) = 'North'",
        "cast(school as string) = 'Alpha'",
        "not is_test",
        "enrolled",
    ]
    assert "not is_test" not in cv.state_where(
        entry, c, fields, sheet, public_only=True
    )


def test_cell_verdict_by_who_fixes():
    sides = {
        "cube": frozenset({"a"}),
        "dashboard": frozenset({"b"}),
        "source": frozenset({"c"}),
        "undecided": frozenset({"d"}),
    }
    meas = cv.Measure("M", "demo.m", sql="x", missing_members=["demo.extra"])
    cell = lambda names: cv.Cell(
        "S", "s", {}, "M", "1", 1, 2, 20, "mismatch", explained_by=names
    )  # noqa: E731
    assert cv.cell_verdict(cell([]), sides, meas) == "fail"
    assert cv.cell_verdict(cell(["a", "b"]), sides, meas) == "fix_cube"
    assert cv.cell_verdict(cell(["c"]), sides, meas) == "fix_source"
    assert cv.cell_verdict(cell(["d"]), sides, meas) == "undecided"
    assert cv.cell_verdict(cell(["demo.extra"]), sides, meas) == "missing_member"
    assert cv.cell_verdict(cell(["b"]), sides, meas) == "pass"


def _timing(tmp_path, live_value, cube_at):
    c = _checks(tmp_path)
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 49.0, 40, "mismatch"
    )
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    live = cv.Live(
        rows=lambda ds, sql: [{"m": live_value}],
        modified=lambda ds: dt.datetime(2026, 10, 9, 10, tzinfo=dt.UTC),
        cube_refreshed=lambda q: cube_at,
    )
    cv.explain_cells(
        [cell], c, states, {}, lambda ds, sql: [{"m": 48.5}], lambda q: ([], []), live
    )
    return cell


def test_cube_matching_the_live_table_is_a_timing_pass(tmp_path):
    cell = _timing(tmp_path, 49.0, dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC))
    assert cell.verdict == "pass" and cell.reason.startswith("timing")


def test_stale_cube_is_incomplete_not_fail(tmp_path):
    cell = _timing(tmp_path, 48.0, dt.datetime(2026, 10, 9, 8, tzinfo=dt.UTC))
    assert cell.verdict == "incomplete" and "older than the live table" in cell.reason


def test_fresh_cube_that_differs_from_the_live_table_fails(tmp_path):
    cell = _timing(tmp_path, 48.0, dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC))
    assert cell.verdict == "fail" and "2026-10-09 10:00" in cell.reason
