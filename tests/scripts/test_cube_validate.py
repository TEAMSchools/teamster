"""Tests for scripts/cube_validate.py. No live calls."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load()


# ---------------------------------------------------------------- Task 1: grains
def test_parse_twb_keeps_only_sheets_on_named_dashboards():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert [s.name for s in sheets] == ["Tardy by School", "Headcount"]


def test_parse_twb_reads_shelves_filters_and_formulas():
    tardy = cv.parse_twb(FIX / "mini.twb", ["Live"])[0]
    assert tardy.dashboards == ["Live"]
    assert tardy.datasource == "rpt_demo (kipptaf_tableau)"
    assert tardy.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert tardy.shelf_dims == ["region", "School", "calendardate@month"]
    assert tardy.filter_dims == ["gender"]
    assert tardy.other_filters == ["Region User Filter"]


def test_parse_twb_plain_column_measure_has_empty_formula():
    headcount = cv.parse_twb(FIX / "mini.twb", ["Live"])[1]
    assert headcount.measures == {"student_number": ""}


def test_propose_grains_adds_total_shelf_and_one_filter_at_a_time():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert cv.propose_grains(sheets, "# Tardy") == [
        [],
        ["region", "School", "calendardate@month"],
        ["region", "School", "calendardate@month", "gender"],
    ]


def test_grains_cli_prints_json(capsys):
    rc = cv.main(
        ["grains", str(FIX / "mini.twb"), "--dashboard", "Live", "--measure", "# Tardy"]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["measure"] == "# Tardy"
    assert [s["name"] for s in out["sheets"]] == ["Tardy by School"]
    assert out["grains"][0] == []


def test_parse_twb_reads_measures_shown_through_measure_values():
    (counts,) = cv.parse_twb(FIX / "mini.twb", ["Counts"])
    assert counts.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert counts.shelf_dims == ["team"]
    assert counts.other_filters == []


# ---------------------------------------------------------------- Task 2: checks and queries
import datetime as dt  # noqa: E402

import pytest  # noqa: E402
import yaml  # noqa: E402

WINDOW = (dt.date(2026, 7, 1), dt.date(2026, 10, 7))


def _checks():
    return cv.load_checks(FIX / "checks.yml")


def _write_variant(tmp_path, mutate):
    data = yaml.safe_load((FIX / "checks.yml").read_text())
    mutate(data)
    p = tmp_path / "checks.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_load_checks_builds_dims_and_defaults():
    c = _checks()
    assert c["dimensions"]["month"] == cv.Dim(
        "month", "attendance_date", "date_trunc(calendardate, month)", "month"
    )
    assert c["dimensions"]["team"].cube is None
    assert c["scope_measure"] == "count_students"
    assert c["students_sql"] == "count(distinct student_number)"


def test_load_checks_rejects_unknown_grain_dim(tmp_path):
    p = _write_variant(tmp_path, lambda d: d["rows"][0]["grains"].append(["nope"]))
    with pytest.raises(cv.CheckError, match="unknown dimension"):
        cv.load_checks(p)


def test_load_checks_rejects_rate_without_den(tmp_path):
    p = _write_variant(tmp_path, lambda d: d["rows"][1]["metrics"][0].pop("den"))
    with pytest.raises(cv.CheckError, match="den"):
        cv.load_checks(p)


def test_load_checks_rejects_granularity_off_the_date_member(tmp_path):
    p = _write_variant(
        tmp_path, lambda d: d["dimensions"]["month"].update(cube="other_date")
    )
    with pytest.raises(cv.CheckError, match="date member"):
        cv.load_checks(p)


def test_load_checks_rejects_two_granular_dims_in_one_grain(tmp_path):
    def mutate(d):
        d["dimensions"]["week"] = {
            "cube": "attendance_date",
            "granularity": "week",
            "sql": "date_trunc(calendardate, week)",
        }
        d["rows"][1]["grains"].append(["month", "week"])

    with pytest.raises(cv.CheckError, match="one date part"):
        cv.load_checks(_write_variant(tmp_path, mutate))


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (dt.date(2026, 10, 8), (dt.date(2026, 7, 1), dt.date(2026, 10, 7))),
        (dt.date(2026, 7, 1), (dt.date(2025, 7, 1), dt.date(2026, 6, 30))),
        (dt.date(2027, 1, 15), (dt.date(2026, 7, 1), dt.date(2027, 1, 14))),
    ],
)
def test_academic_window_(today, expected):
    assert cv.academic_window(today) == expected


def test_cube_query_puts_date_part_on_the_time_dimension():
    c = _checks()
    q = cv.cube_query(
        "demo_view",
        ["avg_daily_attendance"],
        ["region", "month"],
        c["dimensions"],
        c["hard_filters"],
        WINDOW,
    )
    assert q == {
        "measures": ["demo_view.avg_daily_attendance"],
        "dimensions": ["demo_view.regions_region_name"],
        "timeDimensions": [
            {
                "dimension": "demo_view.attendance_date",
                "dateRange": ["2026-07-01", "2026-10-07"],
                "granularity": "month",
            }
        ],
        "filters": [
            {
                "member": "demo_view.regions_region_name",
                "operator": "equals",
                "values": ["Camden", "Newark"],
            }
        ],
        "limit": cv.CUBE_LIMIT,
        "timezone": "UTC",
    }
    assert cv.cube_key("demo_view", c["dimensions"]["month"]) == (
        "demo_view.attendance_date.month"
    )


def test_truth_sql_selects_aliases_and_groups_by_position():
    c = _checks()
    metrics = c["rows"][0]["metrics"] + c["rows"][1]["metrics"]
    sql = cv.truth_sql(
        "proj.ds.rpt_demo",
        metrics,
        ["region", "school"],
        c["dimensions"],
        c["hard_filters"],
        WINDOW,
        c["students_sql"],
    )
    assert sql == (
        "select region as g0, school_abbreviation as g1, sum(is_tardy) as m0, "
        "sum(is_present) as m1_num, sum(membershipvalue) as m1_den, "
        "count(distinct student_number) as n_students "
        "from `proj.ds.rpt_demo` "
        "where calendardate between '2026-07-01' and '2026-10-07' "
        "and region in ('Camden', 'Newark') "
        "group by 1, 2"
    )


def test_truth_sql_total_has_no_group_by():
    c = _checks()
    sql = cv.truth_sql(
        "t", c["rows"][0]["metrics"], [], c["dimensions"], [], WINDOW, "count(1)"
    )
    assert "group by" not in sql


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


def test_count_must_match_exactly():
    cells = cv.compare("count", {("A",): 10.0}, {("A",): (11.0, 50)})
    assert [c.ok for c in cells] == [False]
    assert cells[0].delta == 1.0


def test_count_missing_on_one_side_counts_as_zero():
    cells = cv.compare("count", {("A",): 0.0}, {})
    assert cells[0].ok


def test_count_cell_only_in_warehouse_fails():
    # The #5692 shape: the warehouse has rows Cube never returns.
    cells = cv.compare("count", {}, {("HS",): (40.0, 40)})
    assert not cells[0].ok
    assert cells[0].cube == 0.0


def test_rate_tolerance_boundary():
    ok, bad = cv.compare(
        "rate", {("A",): 0.901, ("B",): 0.9011}, {("A",): (0.9, 50), ("B",): (0.9, 50)}
    )
    assert ok.ok and not bad.ok


def test_average_tolerance_is_a_tenth_of_a_point():
    ok, bad = cv.compare(
        "average",
        {("A",): 1488.6, ("B",): 1488.75},
        {("A",): (1488.65, 50), ("B",): (1488.6, 50)},
    )
    assert ok.ok and not bad.ok


def test_average_prints_as_a_number():
    assert cv._fmt(1487.538, "average") == "1,487.5"


def test_rate_nulls():
    cells = cv.compare(
        "rate", {("A",): None, ("B",): 0.5}, {("A",): (None, 0), ("B",): (None, 0)}
    )
    assert [c.ok for c in cells] == [True, False]


def test_cube_and_truth_cells_join_on_normalized_keys():
    month = cv.Dim("month", "attendance_date", "x", "month")
    region = cv.Dim("region", "regions_region_name", "region")
    cube = cv.cube_cells(
        [
            {
                "v.regions_region_name": "Newark",
                "v.attendance_date.month": "2026-09-01T00:00:00.000",
                "v.avg_daily_attendance": "0.9",
            }
        ],
        "v",
        [region, month],
        "avg_daily_attendance",
    )
    truth = cv.truth_cells(
        [
            {
                "g0": "Newark",
                "g1": dt.date(2026, 9, 1),
                "m0_num": 9,
                "m0_den": 10,
                "n_students": 12,
            }
        ],
        2,
        0,
        "rate",
    )
    assert cube == {("Newark", "2026-09-01"): 0.9}
    assert truth == {("Newark", "2026-09-01"): (0.9, 12)}
    assert [c.ok for c in cv.compare("rate", cube, truth)] == [True]


def test_rate_with_zero_denominator_is_null():
    truth = cv.truth_cells([{"m0_num": 0, "m0_den": 0, "n_students": 3}], 0, 0, "rate")
    assert truth == {(): (None, 3)}


def test_cancelling_errors_fail_the_row():
    # Region total matches; two schools inside it are off in opposite directions.
    region = cv.summarize(
        cv.compare("count", {("N",): 20.0}, {("N",): (20.0, 200)}), "count"
    )
    school = cv.summarize(
        cv.compare(
            "count",
            {("N", "B"): 15.0, ("N", "C"): 5.0},
            {("N", "B"): (12.0, 120), ("N", "C"): (8.0, 80)},
        ),
        "count",
    )
    grains = [
        {"grain": ["region"], "status": "fail" if region["bad"] else "pass"},
        {"grain": ["region", "school"], "status": "fail" if school["bad"] else "pass"},
    ]
    assert region["bad"] == 0 and school["bad"] == 2
    assert cv.row_verdict(grains) == "fail"


def test_summarize_orders_worst_first_and_caps_at_five():
    cube = {(str(i),): float(i) for i in range(8)}
    truth = {(str(i),): (0.0, 50) for i in range(8)}
    s = cv.summarize(cv.compare("count", cube, truth), "count")
    assert s["cells"] == 8 and s["bad"] == 7
    assert [w["key"] for w in s["worst"]] == [["7"], ["6"], ["5"], ["4"], ["3"]]


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (["pass", "pass"], "pass"),
        (["pass", "fail", "error"], "fail"),
        (["pass", "error"], "incomplete"),
        (["pass", "not_comparable"], "pass"),
        (["not_comparable"], "incomplete"),
    ],
)
def test_row_verdict(statuses, verdict):
    assert cv.row_verdict([{"status": s} for s in statuses]) == verdict


def test_rate_with_null_numerator_is_zero():
    truth = cv.truth_cells(
        [{"m0_num": None, "m0_den": 10, "n_students": 3}], 0, 0, "rate"
    )
    assert truth == {(): (0.0, 3)}


# ---------------------------------------------------------------- Task 4: run and outputs
TODAY = dt.date(2026, 10, 8)
SECRET = "x" * 32  # PyJWT warns on HS256 keys under 32 bytes


class FakeCube:
    """Answers by the shape of the Cube query; records every query."""

    def __init__(self, scope=None):
        self.queries = []
        self.scope = scope or {"Camden": "100", "Newark": "200"}

    def __call__(self, q):
        self.queries.append(q)
        v = "demo_view"
        if q["measures"] == [f"{v}.count_students"]:
            return [
                {f"{v}.regions_region_name": r, f"{v}.count_students": n}
                for r, n in self.scope.items()
            ], []
        dims = q["dimensions"]
        gran = q["timeDimensions"][0].get("granularity")
        if not dims:
            return [
                {f"{v}.count_tardy_days": "30", f"{v}.avg_daily_attendance": "0.9"}
            ], ["main_rollup"]
        if gran == "month":
            return [
                {
                    f"{v}.regions_region_name": "Camden",
                    f"{v}.attendance_date.month": "2026-09-01T00:00:00.000",
                    f"{v}.avg_daily_attendance": "0.9",
                }
            ], []
        if dims == [f"{v}.attendance_code"]:
            return [
                {f"{v}.attendance_code": "T", f"{v}.count_tardy_days": "25"},
                {f"{v}.attendance_code": "TD", f"{v}.count_tardy_days": "5"},
            ], []
        if len(dims) == 1:
            return [
                {f"{v}.regions_region_name": "Camden", f"{v}.count_tardy_days": "10"},
                {f"{v}.regions_region_name": "Newark", f"{v}.count_tardy_days": "20"},
            ], []
        return [
            {
                f"{v}.regions_region_name": "Camden",
                f"{v}.locations_abbreviation": "A",
                f"{v}.count_tardy_days": "10",
            },
            {
                f"{v}.regions_region_name": "Newark",
                f"{v}.locations_abbreviation": "B",
                f"{v}.count_tardy_days": "15",
            },
            {
                f"{v}.regions_region_name": "Newark",
                f"{v}.locations_abbreviation": "C",
                f"{v}.count_tardy_days": "5",
            },
        ], []


class FakeBQ:
    def __init__(self, fail_on=None, scope=None):
        self.fail_on = fail_on
        self.scope = scope or [
            {"g0": "Camden", "n_students": 100},
            {"g0": "Newark", "n_students": 200},
        ]

    def __call__(self, sql):
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")
        if "att_code as g0" in sql:
            return [
                {"g0": "T", "m0": 25, "n_students": 50},
                {"g0": "TD", "m0": 0, "n_students": 12},
            ]
        if " as m0" not in sql and " as m0_num" not in sql:
            return self.scope
        if " as g0" not in sql:
            if " as m0_num" in sql:  # ADA alone (rows filter)
                return [{"m0_num": 90, "m0_den": 100, "n_students": 300}]
            return [{"m0": 30, "m1_num": 90, "m1_den": 100, "n_students": 300}]
        if "date_trunc" in sql:
            return [
                {
                    "g0": "Camden",
                    "g1": dt.date(2026, 9, 1),
                    "m0_num": 45,
                    "m0_den": 50,
                    "n_students": 100,
                }
            ]
        if " as g1" not in sql:
            return [
                {"g0": "Camden", "m0": 10, "n_students": 100},
                {"g0": "Newark", "m0": 20, "n_students": 200},
            ]
        return [
            {"g0": "Camden", "g1": "A", "m0": 10, "n_students": 100},
            {"g0": "Newark", "g1": "B", "m0": 12, "n_students": 120},
            {"g0": "Newark", "g1": "C", "m0": 8, "n_students": 80},
        ]


def test_run_dashboard_verdicts_and_one_query_per_grain():
    cube = FakeCube()
    result = cv.run_dashboard(_checks(), cube, FakeBQ(), TODAY)
    tardy, ada = result["rows"]["1"], result["rows"]["2"]
    assert tardy["verdict"] == "fail"
    assert [g["status"] for g in tardy["grains"]] == [
        "pass",
        "pass",
        "fail",
        "not_comparable",
    ]
    assert ada["verdict"] == "pass"
    # scope guard + total (shared by both rows) + region + region x school + region x month
    assert len(cube.queries) == 5
    assert tardy["grains"][0]["pre_aggregations"] == ["main_rollup"]
    assert result["window"] == ["2026-07-01", "2026-10-07"]


def test_run_dashboard_grain_error_makes_row_incomplete():
    result = cv.run_dashboard(
        _checks(), FakeCube(), FakeBQ(fail_on="date_trunc"), TODAY
    )
    ada = result["rows"]["2"]
    assert ada["verdict"] == "incomplete"
    assert ada["grains"][1]["status"] == "error"
    assert "RuntimeError: boom" in ada["grains"][1]["error"]


def test_run_dashboard_rows_filter():
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY, rows={"2"})
    assert list(result["rows"]) == ["2"]


def test_scope_guard_stops_when_cube_misses_a_region_the_warehouse_has():
    with pytest.raises(cv.ScopeError, match="region=Newark"):
        cv.run_dashboard(_checks(), FakeCube(scope={"Camden": "100"}), FakeBQ(), TODAY)


def test_scope_guard_allows_a_region_with_no_data_anywhere():
    bq = FakeBQ(scope=[{"g0": "Camden", "n_students": 100}])
    result = cv.run_dashboard(
        _checks(), FakeCube(scope={"Camden": "100"}), bq, TODAY, scope_only=True
    )
    assert result["rows"] == {}


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


def test_run_cli_requires_the_secret(monkeypatch):
    monkeypatch.delenv("CUBE_API_SECRET", raising=False)
    with pytest.raises(SystemExit, match="CUBE_API_SECRET"):
        cv.main(["run", str(FIX / "checks.yml")])


# ---------------------------------------------------------------- missing Cube members
def _add_missing_member(d):
    d["rows"][0]["metrics"][0].update(
        missing_members=["team"], sql_without="countif(att_code = 'T')"
    )


def test_load_checks_missing_members_need_a_without_variant(tmp_path):
    p = _write_variant(
        tmp_path, lambda d: d["rows"][0]["metrics"][0].update(missing_members=["team"])
    )
    with pytest.raises(cv.CheckError, match="sql_without"):
        cv.load_checks(p)


def test_truth_sql_emits_the_without_variant(tmp_path):
    c = cv.load_checks(_write_variant(tmp_path, _add_missing_member))
    sql = cv.truth_sql(
        "t", c["rows"][0]["metrics"], [], c["dimensions"], [], WINDOW, "count(1)"
    )
    assert "countif(att_code = 'T') as m0_alt" in sql


def test_explain_marks_cells_the_without_variant_matches():
    cells = cv.compare(
        "count", {("B",): 15.0, ("C",): 5.0}, {("B",): (12.0, 120), ("C",): (8.0, 80)}
    )
    cv.explain(cells, "count", {("B",): (15.0, 120), ("C",): (6.0, 80)})
    assert [(c.ok, c.explained) for c in cells] == [(False, True), (False, False)]
    s = cv.summarize(cells, "count")
    assert s["bad"] == 1 and s["explained"] == 1
    assert [w["key"] for w in s["worst"]] == [["C"]]


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (["pass", "missing_member"], "missing_member"),
        (["missing_member", "fail"], "fail"),
        (["missing_member", "error"], "incomplete"),
        (["missing_member", "not_comparable"], "missing_member"),
    ],
)
def test_row_verdict_missing_member(statuses, verdict):
    assert cv.row_verdict([{"status": s} for s in statuses]) == verdict


class AltBQ(FakeBQ):
    """FakeBQ plus m0_alt: the without-variant matches Cube at the school grain."""

    def __call__(self, sql):
        rows = super().__call__(sql)
        if " as m0_alt" not in sql:
            return rows
        alt = {"B": 15, "C": 5}
        return [dict(r, m0_alt=alt.get(str(r.get("g1")), r.get("m0"))) for r in rows]


def test_run_dashboard_prints_progress_per_query(capsys):
    cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY)
    err = capsys.readouterr().err
    assert "[1/5] demo_view total" in err
    assert "[4/5] demo_view region x team: not comparable" in err


def test_cube_filters_apply_to_cube_queries_only(tmp_path):
    def mutate(d):
        d["cube_filters"] = [
            {"member": "is_in_session_day", "operator": "equals", "values": ["true"]}
        ]

    c = cv.load_checks(_write_variant(tmp_path, mutate))
    cube = FakeCube()
    cv.run_dashboard(c, cube, FakeBQ(), TODAY)
    for q in cube.queries[1:]:  # every compared grain; the scope guard is first
        assert {
            "member": "demo_view.is_in_session_day",
            "operator": "equals",
            "values": ["true"],
        } in q["filters"]


def test_tableau_only_dims_are_not_missing_members(tmp_path):
    def mutate(d):
        d["dimensions"]["team"]["tableau_only"] = True

    c = cv.load_checks(_write_variant(tmp_path, mutate))
    result = cv.run_dashboard(c, FakeCube(), FakeBQ(), TODAY)
    tardy = result["rows"]["1"]
    assert tardy["grains"][3]["status"] == "not_comparable"
    assert "team" not in tardy["missing_members"]


# ---------------------------------------------------------------- extract as the truth side
def test_load_checks_requires_extract_and_cube_source_table(tmp_path):
    with pytest.raises(cv.CheckError, match="extract"):
        cv.load_checks(_write_variant(tmp_path, lambda d: d.pop("extract")))
    with pytest.raises(cv.CheckError, match="cube_source_table"):
        cv.load_checks(_write_variant(tmp_path, lambda d: d.pop("cube_source_table")))


def test_extract_file_name_for_datasource():
    assert cv.extract_file_name(FIX / "mini.twb", "rpt_demo") == "federated_abc.hyper"
    with pytest.raises(cv.CheckError, match="no extract"):
        cv.extract_file_name(FIX / "mini.twb", "nope")


def test_to_hyper_sql_translates_and_names_the_extract_table():
    c = _checks()
    metrics = c["rows"][0]["metrics"] + c["rows"][1]["metrics"]
    sql = cv.truth_sql(
        cv.EXTRACT_TABLE,
        metrics,
        ["region", "month"],
        c["dimensions"],
        c["hard_filters"],
        WINDOW,
        c["students_sql"],
    )
    hyper = cv.to_hyper_sql(sql)
    assert '"Extract"."Extract"' in hyper
    assert "`" not in hyper
    assert "date_trunc('month', calendardate)" in hyper.lower()


def test_py_value_converts_hyper_dates():
    class HyperDate:
        def to_date(self):
            return dt.date(2026, 9, 1)

    assert cv._py_value(HyperDate()) == dt.date(2026, 9, 1)
    assert cv._py_value(5) == 5


def test_timing_guard():
    extract_at = dt.datetime(2026, 10, 8, 10, 28, tzinfo=dt.UTC)
    cv.timing_guard(extract_at, dt.datetime(2026, 10, 8, 10, 12, tzinfo=dt.UTC))
    with pytest.raises(cv.TimingError, match="Cube fact was built"):
        cv.timing_guard(extract_at, extract_at - dt.timedelta(hours=3))
    with pytest.raises(cv.TimingError, match="extract was refreshed"):
        cv.timing_guard(extract_at, extract_at + dt.timedelta(hours=3))


def test_snapshot_date_is_local():
    assert cv.snapshot_date(dt.datetime(2026, 10, 8, 3, 0, tzinfo=dt.UTC)) == dt.date(
        2026, 10, 7
    )


def test_cube_built_at_reads_tables_metadata():
    seen = []

    def bq(sql):
        seen.append(sql)
        return [{"last_modified_time": 1791462720000}]

    built = cv.cube_built_at("proj.marts.fct_demo", bq)
    assert built == dt.datetime.fromtimestamp(1791462720, dt.UTC)
    assert "`proj.marts.__TABLES__`" in seen[0] and "table_id = 'fct_demo'" in seen[0]


def test_retry_recovers_from_a_transient_failure():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("401002")
        return "ok"

    assert cv.retry(flaky, attempts=3, sleep=lambda _: None) == "ok"
    assert len(calls) == 3


def test_retry_gives_up_after_its_attempts():
    def broken():
        raise RuntimeError("401002")

    with pytest.raises(RuntimeError, match="401002"):
        cv.retry(broken, attempts=2, sleep=lambda _: None)


# ---------------------------------------------------------------- final-review fixes
class EmptyBQ(FakeBQ):
    """An extract with nothing in the window: zero students, no grouped rows."""

    def __call__(self, sql):
        rows = super().__call__(sql)
        if " as m0" not in sql and " as m0_num" not in sql:
            return rows  # the scope guard still sees students
        if " as g0" not in sql:
            return [dict(rows[0], n_students=0, m0=None, m1_num=None, m1_den=None)]
        return []


def test_empty_truth_is_incomplete_never_pass():
    result = cv.run_dashboard(_checks(), FakeCube(), EmptyBQ(), TODAY)
    for row in result["rows"].values():
        assert row["verdict"] == "incomplete"
    total = result["rows"]["1"]["grains"][0]
    assert total["status"] == "error" and "no rows" in total["error"]


def test_extract_refresh_time_reads_the_datasources_update_time():
    assert cv.extract_refresh_time(FIX / "mini.twb", "rpt_demo") == dt.datetime(
        2026, 10, 8, 10, 28, 12, tzinfo=dt.UTC
    )


def test_load_checks_rejects_one_member_with_two_definitions(tmp_path):
    def mutate(d):
        d["rows"].append(
            {
                "row_gid": "3",
                "name": "Tardy again",
                "metrics": [
                    {
                        "cube": "count_tardy_days",
                        "kind": "count",
                        "sql": "sum(is_tardy) * 2",
                    }
                ],
                "grains": [[]],
            }
        )

    with pytest.raises(cv.CheckError, match="count_tardy_days"):
        cv.load_checks(_write_variant(tmp_path, mutate))


def test_a_failing_metric_only_fails_its_own_rows():
    # ADA's numerator SQL errors; # Tardy shares the total grain and must still pass.
    result = cv.run_dashboard(
        _checks(), FakeCube(), FakeBQ(fail_on="sum(is_present)"), TODAY
    )
    tardy, ada = result["rows"]["1"], result["rows"]["2"]
    assert tardy["grains"][0]["status"] == "pass"
    assert ada["grains"][0]["status"] == "error"
    assert ada["verdict"] == "incomplete"


# ---------------------------------------------------------------- the fix digest
SNAPS = {"extract": "2026-10-08 06:28 ET", "cube": "2026-10-08 06:12 ET"}


def _diagnosed(d):
    d["rows"][0]["metrics"][0]["diagnose_by"] = {
        "cube": "attendance_code",
        "sql": "att_code",
    }


def test_load_checks_diagnose_by_needs_cube_and_sql(tmp_path):
    def mutate(d):
        d["rows"][0]["metrics"][0]["diagnose_by"] = {"cube": "attendance_code"}

    with pytest.raises(cv.CheckError, match="diagnose_by"):
        cv.load_checks(_write_variant(tmp_path, mutate))


def test_failing_rows_get_a_breakdown_by_the_diagnostic_field(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _diagnosed))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY)
    diag = result["rows"]["1"]["diagnosis"]["count_tardy_days"]
    assert diag["by"] == "attendance_code"
    assert diag["cells"] == [
        {"value": "TD", "cube": 5.0, "truth": 0.0, "n_students": 12}
    ]
    assert "diagnosis" not in result["rows"]["2"]  # ADA passes: nothing to diagnose


def test_cube_definition_reads_the_measure_from_cube_yaml():
    d = cv.cube_definition("count_tardy_days", "demo_view", FIX / "cubes")
    assert d == {
        "cube": "demo",
        "sql": "is_tardy",
        "type": "sum",
        "filters": ["{CUBE}.membership_value = 1"],
    }
    assert cv.cube_definition("nope", "demo_view", FIX / "cubes") is None


def test_comment_is_three_lines_pointing_at_the_digest():
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY, snapshots=SNAPS)
    text = cv.comment_text(result["rows"]["1"], result)
    assert text.splitlines() == [
        "Cube vs Tableau check, 2026-10-08: FAIL (extract 2026-10-08 06:28 ET, Cube 2026-10-08 06:12 ET)",
        "Investigate: 2 cells across 1 grain; details in the demo_dashboard fix digest.",
    ]
    assert cv.comment_text(result["rows"]["2"], result).splitlines()[1] == (
        "Every compared cell matches."
    )


def test_comment_names_members_to_add(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _add_missing_member))
    result = cv.run_dashboard(checks, FakeCube(), AltBQ(), TODAY)
    text = cv.comment_text(result["rows"]["1"], result)
    assert text.splitlines()[1:] == [
        "Add to Cube: team (2 cells).",
        "Nothing else to investigate.",
    ]


def test_digest_lists_members_to_add_and_gaps_to_investigate(tmp_path):
    def mutate(d):
        _add_missing_member(d)
        d["members"] = {
            "team": {
                "what": "Homeroom team name",
                "lives_in": "rpt_demo.team",
                "suggested_edit": "Add team to the enrollment dim",
            }
        }
        d["rows"][1]["metrics"][0]["diagnose_by"] = {
            "cube": "attendance_code",
            "sql": "att_code",
        }

    checks = cv.load_checks(_write_variant(tmp_path, mutate))
    result = cv.run_dashboard(checks, FakeCube(), AltBQ(), TODAY, snapshots=SNAPS)
    defs = {
        "count_tardy_days": {
            "cube": "demo",
            "sql": "is_tardy",
            "type": "sum",
            "filters": [],
        }
    }
    md = cv.digest_markdown(result, checks, defs)
    assert "## Add to Cube" in md
    assert "### team: explains 2 cells in 1 row (# Tardy)" in md
    assert "- What: Homeroom team name" in md
    assert "- Suggested edit: Add team to the enrollment dim" in md
    assert (
        "- Dashboard logic: `countif(att_code = 'T')` without it, `sum(is_tardy)` with it"
        in md
    )
    assert "## Investigate" in md
    assert "Nothing unexplained." in md  # every gap here is explained by team


def test_digest_investigate_shows_gap_breakdown_and_both_definitions(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _diagnosed))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, snapshots=SNAPS)
    defs = {
        "count_tardy_days": {
            "cube": "demo",
            "sql": "is_tardy",
            "type": "sum",
            "filters": ["{CUBE}.membership_value = 1"],
        }
    }
    md = cv.digest_markdown(result, checks, defs)
    assert "### # Tardy (1): 2 of 6 cells out of tolerance" in md
    assert "- Total matches: Cube 30, Tableau 30." in md
    assert (
        "- Worst grain: region x school, 2 cells; Newark / B: Cube 15, Tableau 12."
        in md
    )
    assert "- By attendance_code: TD Cube 5, Tableau 0." in md
    assert "- Dashboard: count_tardy_days = `sum(is_tardy)`" in md
    assert (
        "- Cube: count_tardy_days = sum of `is_tardy` where `{CUBE}.membership_value = 1`"
        in md
    )


def test_digest_hides_small_cells():
    result = cv.run_dashboard(_checks(), FakeCube(), SmallBQ(), TODAY)
    md = cv.digest_markdown(result, _checks(), {})
    assert "small cell" in md
    assert "Cube 15" not in md


class SmallBQ(FakeBQ):
    """The school grain's cells hold fewer than 10 students each."""

    def __call__(self, sql):
        rows = super().__call__(sql)
        if " as g1" in sql and "date_trunc" not in sql:
            return [dict(r, n_students=4) for r in rows]
        return rows


def test_write_outputs_writes_the_digest_and_merges_latest(tmp_path):
    (tmp_path / "latest.json").write_text(
        json.dumps(
            {
                "rows": {
                    "999": {
                        "verdict": "pass",
                        "date": "2026-10-01",
                        "dashboard": "other",
                        "name": "x",
                    }
                }
            }
        )
    )
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY)
    report = cv.write_outputs(result, tmp_path, _checks(), {})
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert set(latest["rows"]) == {"999", "1", "2"}
    assert latest["rows"]["1"]["verdict"] == "fail"
    assert report == tmp_path / "2026-10-08-demo_dashboard.md"
    assert (tmp_path / "2026-10-08-demo_dashboard.json").exists()
    assert (
        "## Investigate"
        in (tmp_path / "2026-10-08-demo_dashboard-fixes.md").read_text()
    )
    assert result["rows"]["1"]["comment"].startswith(
        "Cube vs Tableau check, 2026-10-08: FAIL"
    )


def test_cube_definition_lists_the_measures_a_derived_measure_uses():
    d = cv.cube_definition("pct_late", "demo_view", FIX / "cubes")
    assert [r["name"] for r in d["refs"]] == ["count_tardy_days", "count_days"]
    assert d["refs"][0]["filters"] == ["{CUBE}.membership_value = 1"]


def test_digest_expands_derived_cube_measures(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _diagnosed))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY)
    defs = {
        "count_tardy_days": cv.cube_definition("pct_late", "demo_view", FIX / "cubes")
    }
    md = cv.digest_markdown(result, checks, defs)
    assert (
        "  - uses count_tardy_days = sum of `is_tardy` where `{CUBE}.membership_value = 1`"
        in md
    )


def test_total_line_says_when_a_missing_member_explains_the_gap():
    s_ = {
        "bad": 0,
        "explained": 1,
        "worst": [],
        "only": {"cube": 9709.0, "truth": 9692.0, "without": 9709.0},
    }
    assert cv._total_line(s_, "count", ["out_of_district"]) == [
        "- Total differs, explained by out_of_district: Cube 9,709, Tableau 9,692.",
        "- out_of_district accounts for 17 (Tableau 9,692 with it, 9,709 without it).",
    ]
    s_ = {"bad": 0, "explained": 0, "worst": [], "only": {"cube": 30.0, "truth": 30.0}}
    assert cv._total_line(s_, "count", []) == ["- Total matches: Cube 30, Tableau 30."]


class PartialAltBQ(FakeBQ):
    """The without-variant explains school B but not C, so a gap stays to diagnose."""

    sqls: list

    def __init__(self):
        super().__init__()
        self.sqls = []

    def __call__(self, sql):
        self.sqls.append(sql)
        rows = super().__call__(sql)
        if " as m0_alt" not in sql:
            return rows
        alt = {"B": 15, "C": 6}
        return [dict(r, m0_alt=alt.get(str(r.get("g1")), r.get("m0"))) for r in rows]


def test_diagnosis_runs_without_the_missing_members_logic(tmp_path):
    def mutate(d):
        _add_missing_member(d)
        _diagnosed(d)

    checks = cv.load_checks(_write_variant(tmp_path, mutate))
    bq = PartialAltBQ()
    result = cv.run_dashboard(checks, FakeCube(), bq, TODAY)
    assert result["rows"]["1"]["verdict"] == "fail"
    diag_sql = [q for q in bq.sqls if "att_code as g0" in q]
    assert len(diag_sql) == 1
    assert "countif(att_code = 'T') as m0" in diag_sql[0]
    assert (
        result["rows"]["1"]["diagnosis"]["count_tardy_days"]["basis"] == "without team"
    )


def test_total_line_skips_a_share_that_rounds_to_nothing():
    s_ = {
        "bad": 0,
        "explained": 0,
        "worst": [],
        "only": {"cube": 0.849, "truth": 0.8491, "without": 0.8492},
    }
    assert cv._total_line(s_, "rate", ["out_of_district"]) == [
        "- Total matches: Cube 84.9%, Tableau 84.9%."
    ]


class TotalShareBQ(FakeBQ):
    """The total fails (Cube 30, dashboard 28) and the without-variant moves it to 29:
    the missing member changes the total without explaining any cell on its own."""

    def __call__(self, sql):
        rows = super().__call__(sql)
        if " as g0" not in sql and " as m0" in sql and " as m0_alt" in sql:
            return [dict(rows[0], m0=28, m0_alt=29)]
        if " as m0_alt" in sql:
            return [dict(r, m0_alt=r.get("m0")) for r in rows]
        return rows


def test_a_member_that_changes_the_total_reopens_the_row(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _add_missing_member))
    result = cv.run_dashboard(checks, FakeCube(), TotalShareBQ(), TODAY)
    tardy = result["rows"]["1"]
    assert tardy["verdict"] == "fail"
    assert tardy["missing_members"]["team"]["explains_cells"] == 0
    assert tardy["missing_members"]["team"]["changes_total"] is True
    cv.write_outputs(result, tmp_path / "out", checks, {})
    latest = json.loads((tmp_path / "out" / "latest.json").read_text())
    assert latest["rows"]["1"]["reopen_for"] == ["team"]
    assert latest["rows"]["2"]["reopen_for"] == []
    md = (tmp_path / "out" / "2026-10-08-demo_dashboard-fixes.md").read_text()
    assert "### team: changes the total in 1 row (# Tardy)" in md


def test_blocked_only_members_do_not_reopen(tmp_path):
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY)
    cv.write_outputs(result, tmp_path, _checks(), {})
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["rows"]["1"]["missing_members"] == ["team"]  # blocks a grain only
    assert latest["rows"]["1"]["reopen_for"] == []


# ---------------------------------------------------------------- academic-year windows
def _year_window(d):
    d["window"] = {"academic_years": [2024, 2025]}
    d["dimensions"]["academic_year"] = {"cube": "academic_year", "sql": "academic_year"}
    d["truth_filters"] = ["results_type = 'Actual'"]
    for row in d["rows"]:
        row["grains"] = [g for g in row["grains"] if "month" not in g]


def test_year_window_filters_by_academic_year_on_both_sides(tmp_path):
    c = cv.load_checks(_write_variant(tmp_path, _year_window))
    window = cv.resolve_window(c, TODAY)
    q = cv.cube_query(
        "demo_view", ["count_tardy_days"], ["region"], c["dimensions"], [], window
    )
    assert q["timeDimensions"] == []
    assert {
        "member": "demo_view.academic_year",
        "operator": "equals",
        "values": ["2024", "2025"],
    } in q["filters"]
    sql = cv.truth_sql(
        "t",
        c["rows"][0]["metrics"],
        ["region"],
        c["dimensions"],
        [],
        window,
        "count(1)",
        c["truth_filters"],
    )
    assert "academic_year in (2024, 2025)" in sql
    assert "results_type = 'Actual'" in sql
    assert "calendardate" not in sql


def test_year_window_needs_an_academic_year_dimension(tmp_path):
    def mutate(d):
        _year_window(d)
        del d["dimensions"]["academic_year"]

    with pytest.raises(cv.CheckError, match="academic_year"):
        cv.load_checks(_write_variant(tmp_path, mutate))


def test_year_window_labels_the_run(tmp_path):
    c = cv.load_checks(_write_variant(tmp_path, _year_window))
    result = cv.run_dashboard(c, FakeCube(), FakeBQ(), TODAY)
    assert result["window"] == ["2024-25", "2025-26"]


def test_one_year_window_reads_as_that_year(tmp_path):
    def one_year(d):
        _year_window(d)
        d["window"] = {"academic_years": [2025]}

    c = cv.load_checks(_write_variant(tmp_path, one_year))
    result = cv.run_dashboard(c, FakeCube(), FakeBQ(), TODAY)
    assert "Window: 2025-26." in cv.digest_markdown(result, c, {})
    assert "window 2025-26." in cv.report_markdown(result)


# ---------------------------------------------------------------- Tableau constructs
def _sheet(name):
    sheets = cv.parse_twb(FIX / "constructs.twb", ["Main"])
    return next(s for s in sheets if s.name == name)


def test_parse_twb_splits_rows_and_cols():
    geo = _sheet("Geo")
    assert geo.rows_dims == ["region", "School"]
    assert geo.cols_dims == ["Calendardate@year"]
    assert geo.shelf_dims == ["region", "School", "Calendardate@year"]


def test_parse_twb_resolves_copies_to_the_source_field():
    assert _sheet("Levels").cols_dims == ["School"]


def test_bin_field_is_not_read_as_a_copy():
    assert _sheet("Bins").shelf_dims == ["Score (bin)"]


def test_parse_twb_reads_a_quick_table_calc_as_its_measure():
    assert "# Absent" in _sheet("Shares").measures


def test_table_calc_token_without_a_suffix_still_classifies():
    columns = {("federated.abc", "[Calculation_abs]"): ("# Absent", "SUM([is_absent])")}
    kind, label, _ = cv._classify(
        "federated.abc", "pcto:usr:Calculation_abs:qk", columns
    )
    assert (kind, label) == ("measure", "# Absent")


def _keys(sheet):
    return {c.key for c in sheet.constructs}


def test_groups_are_constructs_with_their_bins():
    (g,) = [c for c in _sheet("Codes").constructs if c.kind == "group"]
    assert g.name == "Code Group"
    assert g.detail == {
        "of": "att_code",
        "of_formula": None,
        "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]},
    }


def test_numeric_bins_are_constructs():
    (b,) = [c for c in _sheet("Bins").constructs if c.kind == "bin"]
    assert b.detail == {"of": "score", "size": 10}


def test_lod_and_table_calc_formulas_are_constructs():
    assert {"lod: Days FIXED", "table_calc: Share"} <= _keys(_sheet("Shares"))


def test_viewer_functions_are_found_through_a_filter_calc():
    assert "viewer_function: Permissions" in _keys(_sheet("Codes"))


def test_fiscal_year_on_a_year_date_part():
    (f,) = [c for c in _sheet("Geo").constructs if c.kind == "fiscal_year"]
    assert f.name == "Calendardate@year"
    assert f.detail == {"start_month": 7}


def test_unexpandable_parameter_field_is_a_construct():
    keys = _keys(_sheet("Levels"))
    assert "parameter: Odd Column" in keys
    assert "parameter: Level Column" not in keys


def test_filters_carry_their_mode():
    cs = {c.key: c for c in _sheet("Codes").constructs}
    assert cs["filter: att_code"].detail["mode"] == "exclude"
    assert cs["filter: att_code"].detail["nulls"] is True
    assert cs["filter: Permissions"].detail["context"] is True
    # An all-values quick filter is the viewer's control, not a construct.
    assert "filter: gender" not in cs


def test_sets_and_user_filters():
    cs = {c.key: c for c in _sheet("Codes").constructs}
    assert cs["set: Exclude OD"].detail == {
        "mode": "exclude",
        "members": ["OD"],
        "of": "school_level",
    }
    assert "viewer_function: User Filter 1" in cs


def test_quick_table_calc_top_n_range_filter_and_blend():
    shares = {c.key: c for c in _sheet("Shares").constructs}
    assert shares["table_calc: # Absent"].detail == {"quick": "PctTotal"}
    bins = {c.key: c for c in _sheet("Bins").constructs}
    assert {"top_n: region", "filter: score", "blend: other"} <= set(bins)
    assert bins["filter: score"].detail["range"] == {"min": "10"}


def test_source_filters_reach_every_sheet_on_the_datasource():
    key = "source_filter: rpt_demo (kipptaf_tableau): region_type"
    for name in ("Codes", "Geo", "Levels", "Shares", "Bins", "Shown"):
        assert key in _keys(_sheet(name))


def test_measure_names_alias_is_a_construct():
    shown = _sheet("Shown")
    assert shown.measure_aliases == {"Absences Shown": "# Absent"}
    assert "alias: Absences Shown" in _keys(shown)


def test_plain_subtotals_are_grains_not_constructs():
    # Geo's visual total is a construct; its plain subtotal on region is not.
    totals = [c for c in _sheet("Geo").constructs if c.kind == "total"]
    assert [c.name for c in totals] == ["# Absent"]


def test_parameter_branches_parse():
    assert _sheet("Levels").param_dims["Level Column"] == {
        "parameter": "Parameter 1",
        "branches": {"Region": "region", "School": "School", "Network": None},
        "default": "Region",
    }


def test_grains_expand_parameter_branches_and_drill_levels():
    grains = cv.propose_grains(
        cv.parse_twb(FIX / "constructs.twb", ["Main"]), "# Absent"
    )
    sets = {frozenset(g) for g in grains}
    assert frozenset({"region", "Odd Column"}) in sets
    assert frozenset({"region", "School", "Odd Column"}) in sets
    assert not any("Level Column" in g for g in grains)


def test_grains_add_drill_levels_and_subtotals():
    geo = _sheet("Geo")
    assert cv._shelves(geo) == [
        ["region", "Calendardate@year"],
        ["region", "School", "Calendardate@year"],
    ]
    assert cv._subtotal_grains(geo) == [["region", "Calendardate@year"]]


def test_grains_include_sheets_showing_the_measure_under_an_alias():
    # region heads the Geo drill path, so the sheet also drills down to School.
    assert cv.propose_grains([_sheet("Shown")], "Absences Shown") == [
        [],
        ["region"],
        ["region", "School"],
    ]


def test_group_dimension_compiles_to_a_case(tmp_path):
    def m(d):
        d["dimensions"]["code_group"] = {
            "cube": None,
            "kind": "relabel",
            "group": {
                "of": "att_code",
                "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]},
            },
        }

    dim = cv.load_checks(_write_variant(tmp_path, m))["dimensions"]["code_group"]
    assert dim.sql == (
        "case when att_code in ('A', 'AD') then 'Absent' "
        "when att_code in ('P') or att_code is null then 'Present' "
        "else cast(att_code as string) end"
    )
    assert dim.group_kind == "relabel"


def test_group_over_a_number_casts_the_kept_value():
    sql = cv.group_case_sql("lvl", {"Not Proficient": [1, 2], "Proficient": [4, 5]})
    assert sql == (
        "case when lvl in (1, 2) then 'Not Proficient' "
        "when lvl in (4, 5) then 'Proficient' else cast(lvl as string) end"
    )
    assert cv.group_case_sql("lvl", {"Low": [1]}, other="Other").endswith(
        "else 'Other' end"
    )


def test_bin_dimension_compiles_to_floor(tmp_path):
    def m(d):
        d["dimensions"]["score_bin"] = {
            "cube": None,
            "bin": {"of": "score", "size": 10},
        }

    dim = cv.load_checks(_write_variant(tmp_path, m))["dimensions"]["score_bin"]
    assert dim.sql == "floor((score) / 10) * 10"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda d: d["dimensions"].update(
                g={
                    "cube": None,
                    "sql": "x",
                    "kind": "rule",
                    "group": {"of": "x", "bins": {}},
                }
            ),
            "not both",
        ),
        (
            lambda d: d["dimensions"].update(
                g={"cube": None, "group": {"of": "x", "bins": {}}}
            ),
            "relabel or rule",
        ),
        (
            lambda d: d["rows"][0].update(
                not_checked=[{"construct": "widget: x", "why": "y"}]
            ),
            "unknown construct",
        ),
        (lambda d: d["rows"][0].update(not_checked=[{"construct": "group: x"}]), "why"),
        (lambda d: d.update(handled={"nonsense": "x"}), "unknown construct"),
    ],
)
def test_load_checks_rejects_bad_construct_entries(tmp_path, mutate, message):
    with pytest.raises(cv.CheckError, match=message):
        cv.load_checks(_write_variant(tmp_path, mutate))


def test_load_checks_normalizes_tableau_captions(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["tableau"] = "# Tardy"

    c = cv.load_checks(_write_variant(tmp_path, m))
    assert c["rows"][0]["metrics"][0]["tableau"] == ["# Tardy"]
    assert c["rows"][1]["metrics"][0]["tableau"] == []
    assert c["dashboards"] == [] and c["handled"] == {}
    assert c["rows"][0]["not_checked"] == []


ALL_KEYS = {
    "group: Code Group",
    "filter: Permissions",
    "viewer_function: Permissions",
    "set: Exclude OD",
    "filter: att_code",
    "viewer_function: User Filter 1",
    "source_filter: rpt_demo (kipptaf_tableau): region_type",
    "fiscal_year: Calendardate@year",
    "parameter: Odd Column",
    "table_calc: # Absent",
    "bin: Score (bin)",
    "top_n: region",
    "filter: score",
    "blend: other",
    "alias: Absences Shown",
    "total: # Absent",
    "filter: student_name",
}


def _ref(audit, gid, name):
    return next(c["ref"] for c in audit[gid]["unaccounted"] if c["key"] == name)


def _audited(tmp_path, mutate=None):
    def m(d):
        d["dashboards"] = ["Main"]
        for row in d["rows"]:
            for metric in row["metrics"]:
                metric["tableau"] = "# Absent"
        if mutate:
            mutate(d)

    checks = cv.load_checks(_write_variant(tmp_path, m))
    return checks, cv.audit_rows(checks, FIX / "constructs.twb")


def test_audit_lists_every_construct_on_the_rows_sheets(tmp_path):
    _, audit = _audited(tmp_path)
    assert {c["key"] for c in audit["1"]["unaccounted"]} == ALL_KEYS


def test_audit_splits_handled_and_not_checked(tmp_path):
    _, first = _audited(tmp_path)
    group = _ref(first, "1", "group: Code Group")
    att = _ref(first, "1", "filter: att_code")

    def m(d):
        d["handled"] = {group: "dimension code_group"}
        d["rows"][0]["not_checked"] = [{"construct": att, "why": "excluded codes"}]

    _, audit = _audited(tmp_path, m)
    keys = {c["key"] for c in audit["1"]["unaccounted"]}
    assert "group: Code Group" not in keys
    assert "filter: att_code" not in keys
    (nc,) = audit["1"]["not_checked"]
    assert (nc["ref"], nc["sheets"], nc["why"]) == (att, ["Codes"], "excluded codes")


def test_a_handled_ref_stops_matching_when_the_construct_changes():
    a = cv.Construct("filter", "Region", detail={"members": ["Camden"]})
    b = cv.Construct("filter", "Region", detail={"members": ["Camden", "Miami"]})
    assert a.key == b.key and a.ref != b.ref
    s1 = cv.Sheet("one", ["Main"], constructs=[a])
    s2 = cv.Sheet("two", ["Main"], constructs=[b])
    assert len(cv.merge_constructs([s1, s2])) == 2


def test_measure_scoped_constructs_attach_only_to_their_row(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["tableau"] = "Share"

    _, audit = _audited(tmp_path, m)
    assert {c["key"] for c in audit["1"]["unaccounted"]} == {
        "table_calc: Share",
        "source_filter: rpt_demo (kipptaf_tableau): region_type",
    }


def test_filter_members_never_reach_outputs(tmp_path, capsys):
    checks, audit = _audited(tmp_path)
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, audit=audit)
    digest = cv.digest_markdown(result, checks, {})
    assert "Student A" not in digest
    assert "filter: student_name [" in digest and "(exclude; 1 member)" in digest
    assert "Student A" not in json.dumps(result, default=str)
    twb = str(FIX / "constructs.twb")
    cv.main(["grains", twb, "--dashboard", "Main", "--measure", "# Absent"])
    assert "Student A" not in capsys.readouterr().out
    cv.main(["grains", twb, "--dashboard", "Main"])
    assert "Student A" not in capsys.readouterr().out


def test_visual_totals_are_read_and_inventoried():
    geo = _sheet("Geo")
    assert list(geo.measures) == ["# Absent"]
    (t,) = [c for c in geo.constructs if c.kind == "total"]
    assert (t.name, t.detail, t.scope) == (
        "# Absent",
        {"visual_totals": "avg"},
        ["# Absent"],
    )


def test_sheet_local_calcs_are_indexed():
    assert "table_calc: Adhoc" in _keys(_sheet("Shares"))


def test_subtotal_on_a_parameter_field_is_expanded():
    grains = {frozenset(g) for g in cv.propose_grains([_sheet("Levels")], "# Absent")}
    assert frozenset({"region", "School"}) in grains
    assert frozenset({"School"}) in grains


def test_audit_finds_sheets_through_a_measure_names_alias(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["tableau"] = "Absences Shown"

    _, audit = _audited(tmp_path, m)
    assert {c["key"] for c in audit["1"]["unaccounted"]} == {
        "alias: Absences Shown",
        "source_filter: rpt_demo (kipptaf_tableau): region_type",
    }


def test_audit_needs_a_tableau_caption(tmp_path):
    def m(d):
        d["rows"][1]["metrics"][0]["tableau"] = []

    _, audit = _audited(tmp_path, m)
    assert "tableau:" in audit["2"]["error"]


def test_audit_without_dashboards_names_the_reason(tmp_path):
    def m(d):
        d["dashboards"] = []

    checks, audit = _audited(tmp_path, m)
    assert "names no dashboards" in audit["1"]["error"]
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, audit=audit)
    assert result["rows"]["2"]["verdict"] == "incomplete"
    assert "names no dashboards" in result["rows"]["2"]["audit_error"]


def test_unaccounted_construct_makes_a_passing_row_incomplete_but_a_fail_stays_fail(
    tmp_path,
):
    _, audit = _audited(tmp_path)
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY, audit=audit)
    assert result["rows"]["1"]["verdict"] == "fail"
    assert result["rows"]["2"]["verdict"] == "incomplete"
    assert len(result["rows"]["2"]["unaccounted"]) == len(ALL_KEYS)


def test_comment_and_digest_list_unaccounted_and_not_checked(tmp_path):
    _, first = _audited(tmp_path)
    att = _ref(first, "2", "filter: att_code")

    def m(d):
        d["rows"][1]["not_checked"] = [{"construct": att, "why": "excluded codes"}]

    checks, audit = _audited(tmp_path, m)
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, audit=audit)
    row = result["rows"]["2"]
    text = cv.comment_text(row, result)
    assert (
        f"Unaccounted Tableau constructs: {len(ALL_KEYS) - 1}; see the fix digest."
        in text
    )
    assert "Not checked: 1 Tableau construct; see the fix digest." in text
    digest = cv.digest_markdown(result, checks, {})
    assert "## Unaccounted Tableau constructs" in digest
    assert "- group: Code Group [" in digest
    assert "] on Codes (2 bins over att_code)" in digest
    assert "## Not checked" in digest
    assert ": excluded codes" in digest
    report = cv.report_markdown(result)
    assert "Unaccounted: " in report and f"Not checked: {att}." in report


def test_rule_groups_are_listed_as_decisions(tmp_path):
    def m(d):
        d["dimensions"]["code_group"] = {
            "cube": None,
            "kind": "rule",
            "group": {"of": "att_code", "bins": {"Absent": ["A"]}},
        }
        d["rows"][0]["grains"].append(["code_group"])

    checks = cv.load_checks(_write_variant(tmp_path, m))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY)
    digest = cv.digest_markdown(result, checks, {})
    assert "### Definitions to decide" in digest
    assert "- code_group: blocks 1 grain in 1 row" in digest


def test_grains_cli_lists_constructs_with_dimension_snippets(capsys):
    twb = str(FIX / "constructs.twb")
    assert (
        cv.main(["grains", twb, "--dashboard", "Main", "--measure", "Absences Shown"])
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["resolves_to"] == ["# Absent"]
    assert cv.main(["grains", twb, "--dashboard", "Main", "--measure", "# Absent"]) == 0
    out = json.loads(capsys.readouterr().out)
    group = next(c for c in out["constructs"] if c["key"] == "group: Code Group")
    assert group["sheets"] == ["Codes"]
    assert group["dimension"] == {
        "group": {
            "of": "att_code",
            "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]},
        },
        "kind": "relabel or rule: decide",
        "cube": None,
    }


def test_drill_paths_match_the_field_not_its_label():
    # The Geo path holds the School copy, so the plain school field is not in it.
    assert _sheet("Plain").drill_paths == []
    assert _sheet("Levels").drill_paths == [["region", "School"]]


def test_filters_join_only_the_grain_the_sheet_opens_at():
    levels = _sheet("Levels")
    assert cv._base_shelf(levels) == ["region", "Odd Column", "School"]
    grains = cv.propose_grains([levels], "# Absent")
    assert [g for g in grains if "gender" in g] == [
        ["region", "Odd Column", "School", "gender"]
    ]
    # The same fields in another order are the same cut, queried once.
    assert len({tuple(sorted(g)) for g in grains}) == len(grains)


def test_person_dimensions_never_reach_outputs(tmp_path):
    def m(d):
        d["dimensions"]["school"]["person"] = True

    checks = cv.load_checks(_write_variant(tmp_path, m))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY)
    grain = next(
        g for g in result["rows"]["1"]["grains"] if g["grain"] == ["region", "school"]
    )
    worst = [c for s in grain["metrics"].values() for c in s["worst"]]
    assert worst and all(c["key"][1] == "a student" for c in worst)
    assert all(c["key"][0] in ("Camden", "Newark") for c in worst)


def test_workbook_excludes_read_members_from_the_workbook(tmp_path):
    def m(d):
        d["dashboards"] = ["Main"]
        d["workbook_excludes"] = [
            {"construct": "filter: student_name", "sql": "student_name"},
            {"construct": "filter: att_code", "sql": "att_code", "pattern": r"^(\w)"},
        ]

    checks = cv.load_checks(_write_variant(tmp_path, m))
    assert cv.workbook_exclusions(checks, FIX / "constructs.twb") == [
        "student_name not in ('Student A')",
        "att_code not in ('X')",
    ]


def test_workbook_excludes_fail_loudly_when_the_filter_is_gone(tmp_path):
    def m(d):
        d["dashboards"] = ["Main"]
        d["workbook_excludes"] = [{"construct": "filter: nothing", "sql": "x"}]

    checks = cv.load_checks(_write_variant(tmp_path, m))
    with pytest.raises(cv.CheckError, match="filter: nothing"):
        cv.workbook_exclusions(checks, FIX / "constructs.twb")


# ---------------------------------------------------------------- per-metric extracts
class WeeklyBQ(FakeBQ):
    """A second extract whose school-grain tardies agree with Cube."""

    def __init__(self):
        super().__init__()
        self.sql = []

    def __call__(self, sql):
        self.sql.append(sql)
        rows = super().__call__(sql)
        if " as g1" in sql and " as m0" in sql and "date_trunc" not in sql:
            return [
                {"g0": "Camden", "g1": "A", "m0": 10, "n_students": 100},
                {"g0": "Newark", "g1": "B", "m0": 15, "n_students": 120},
                {"g0": "Newark", "g1": "C", "m0": 5, "n_students": 80},
            ]
        return rows


def _weekly_metric(d):
    d["rows"][0]["metrics"].append(
        {
            "cube": "count_tardy_days",
            "kind": "count",
            "sql": "sum(is_tardy)",
            "datasource": "rpt_weekly",
        }
    )


def test_load_checks_keys_metrics_by_datasource(tmp_path):
    c = cv.load_checks(_write_variant(tmp_path, _weekly_metric))
    a, b = c["rows"][0]["metrics"]
    assert (a["key"], a["datasource"]) == ("count_tardy_days", "rpt_demo")
    assert (b["key"], b["datasource"]) == (
        "count_tardy_days @ rpt_weekly",
        "rpt_weekly",
    )


def test_load_checks_rejects_the_same_metric_twice_on_one_extract(tmp_path):
    def m(d):
        d["rows"][0]["metrics"].append(dict(d["rows"][0]["metrics"][0]))

    with pytest.raises(cv.CheckError, match="twice"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_each_metric_reads_its_own_extract(tmp_path):
    checks = cv.load_checks(_write_variant(tmp_path, _weekly_metric))
    weekly = WeeklyBQ()
    result = cv.run_dashboard(
        checks, FakeCube(), {"rpt_demo": FakeBQ(), "rpt_weekly": weekly}, TODAY
    )
    grain = next(
        g for g in result["rows"]["1"]["grains"] if g["grain"] == ["region", "school"]
    )
    assert grain["metrics"]["count_tardy_days"]["bad"] == 2
    assert grain["metrics"]["count_tardy_days @ rpt_weekly"]["bad"] == 0
    assert weekly.sql and all(" as m1" not in q for q in weekly.sql)
    digest = cv.digest_markdown(result, checks, {})
    assert "- Dashboard: count_tardy_days @ rpt_weekly = `sum(is_tardy)`" in digest


def test_unpack_extracts_finds_each_datasources_hyper(tmp_path):
    import zipfile

    twb = """<?xml version='1.0' encoding='utf-8' ?>
<workbook><datasources>
  <datasource caption='rpt_demo (kipptaf_tableau)' name='federated.a'>
    <extract enabled='true'><connection class='hyper' dbname='Data/Extracts/a.hyper' update-time='10/08/2026 10:00:00 AM' /></extract>
  </datasource>
  <datasource caption='rpt_weekly (kipptaf_tableau)' name='federated.b'>
    <extract enabled='true'><connection class='hyper' dbname='Data/Extracts/b.hyper' update-time='10/08/2026 11:00:00 AM' /></extract>
  </datasource>
</datasources></workbook>"""
    twbx = tmp_path / "workbook.twbx"
    with zipfile.ZipFile(twbx, "w") as z:
        z.writestr("Book.twb", twb)
        z.writestr("Data/Extracts/a.hyper", b"A")
        z.writestr("Data/Extracts/b.hyper", b"B")
    out = cv.unpack_extracts(twbx, ["rpt_demo", "rpt_weekly"], tmp_path / "out")
    assert out["rpt_demo"][0].read_bytes() == b"A"
    assert out["rpt_weekly"][0].read_bytes() == b"B"
    assert out["rpt_weekly"][1] == dt.datetime(2026, 10, 8, 11, 0, tzinfo=dt.UTC)
