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
