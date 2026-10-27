import contextlib
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, pipeline, tableau

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import Warehouse

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import load_view_config

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import Compiled

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.tableau import Snapshot, formula_fingerprint

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import utc_literal

FIXTURES = Path(__file__).parent / "fixtures"
REAL_TABLEAU_SESSION = cli.tableau_session
START = datetime(2026, 10, 22, 20, 30, tzinfo=timezone.utc)
END = START + timedelta(minutes=14)
NOW = END + timedelta(days=1)
TIB = 2**40

PROOF = """\
    proof:
      fingerprint: abc
      cells: 2
      proven_at: '2026-10-26T12:00:00+00:00'
      workbook_updated_at: '2026-10-20T09:00:00+00:00'
      probe_fingerprint: PROBE_FP
"""

YML = (
    """\
view: v
fact: kipptaf_marts.fct_f
time_dimension: attendance_date
comparisons:
  - id: ada-region
    measure: avg_daily_attendance
    confirmed: true
    workbook: wb-1
    sheet: Rate by Region
    dashboard_view: kipptaf_tableau.rpt_d
    probe: avg(is_present)
    decimals: 3
    dims:
      - { dashboard: region, cube: regions_region_name }
    filters:
      Academic Year: { dashboard: academic_year, cube: dates_academic_year }
      Region: { dashboard: region, cube: regions_region_name }
    defaults: { Academic Year: "2026", Region: [Camden, Newark] }
    cuts: [{}, { Region: Miami }]
    rows:
      grain:
        - { dashboard: student_number, cube: lea_student_identifier }
        - { dashboard: calendardate, cube: attendance_date }
      values:
        - { dashboard: is_present, cube: attendance_value }
"""
    + PROOF
    + """\
identities:
  - name: ada-ratio
    left: avg_daily_attendance
    right: sum_attendance_value / sum_membership_value
"""
)

RECONCILE_ROWS = [
    {
        "bucket": "match",
        "regions_region_name": "Newark",
        "n_rows": 400,
        "n_students": 40,
    },
    {
        "bucket": "dashboard_only",
        "regions_region_name": "Miami",
        "n_rows": 30,
        "n_students": 12,
    },
]


class FakeBigQuery:
    """A `bigquery.Client` stand-in: prices dry runs, records what runs."""

    def __init__(self, cost=lambda sql: 0.0, changed=(), probe=None, cells=None):
        self.cost = cost
        self.changed = changed
        self.ran: list[str] = []
        self.probe = probe or [{"region": "Newark", "value": 0.9123}]
        self.cells = cells
        self.views: dict[str, str] = {}
        self.build = (START, END)

    def get_table(self, ref):
        name = ref.rsplit(".", 1)[-1]
        if name in self.views:
            return SimpleNamespace(
                table_type="VIEW",
                view_query=self.views[name],
                modified=START - timedelta(days=2),
            )
        return SimpleNamespace(table_type="TABLE", view_query=None, modified=START)

    def query(self, sql, job_config=None):
        if job_config is not None and job_config.dry_run:
            nbytes = int(self.cost(sql) / 6.25 * TIB)
            return SimpleNamespace(total_bytes_processed=nbytes, result=lambda: [])
        self.ran.append(sql)
        rows = self.answer(sql)
        return SimpleNamespace(total_bytes_processed=0, result=lambda: rows)

    def answer(self, sql):
        if "JOBS_BY_PROJECT" in sql:
            start, end = self.build
            return [{"job_id": "job-1", "start_time": start, "end_time": end}]
        if "SELECT abbreviation" in sql:
            return [{"abbreviation": "A"}, {"abbreviation": "B"}]
        if "farm_fingerprint" in sql:
            if any(t in sql for t in self.changed):
                stamp = _first(r"TIMESTAMP '([^']+)'", sql)
                return [{"f": int(hashlib.sha256(stamp.encode()).hexdigest()[:8], 16)}]
            return [{"f": 1}]
        if "-- outer" in sql:
            return RECONCILE_ROWS
        if "AS value" in sql and "fct_f" in sql:
            if self.cells is not None:
                return self.cells
            if "AS regions_region_name" in sql:
                return [{"regions_region_name": "Newark", "value": 0.91234}]
            return [{"value": 0.91234}]
        if "AS value" in sql and "rpt_d" in sql:
            return self.probe
        return []


class FakeCube:
    def __init__(self, load=None):
        self.compiled_queries: list[dict] = []
        self.loads: list[dict] = []
        self._load = load or (lambda q: [_load_row(q, 0.91234)])
        self.exprs: dict[str, str] = {}

    def compiled(self, query):
        self.compiled_queries.append(query)
        dims = [m.split(".", 1)[1] for m in query.get("dimensions", [])]
        measures = [m.split(".", 1)[1] for m in query.get("measures", [])]
        select = ", ".join(
            [f"{self.exprs.get(d, f'`t`.{d}')} `v__{d}`" for d in dims]
            + [
                f"sum(`t`.is_present) / count(`t`.membership_value) `v__{m}`"
                for m in measures
            ]
        )
        sql = (
            f"SELECT {select}\n"
            "FROM  kipptaf_marts.fct_f  AS `t`\n"
            "LEFT JOIN  kipptaf_marts.dim_locations  AS `locations` "
            "ON `locations`.k = `t`.k\n"
            "WHERE (`locations`.abbreviation IN (?, ?))\n"
            "LIMIT 10000"
        )
        return Compiled(sql, ["A", "B"], [])

    def load(self, query):
        self.loads.append(query)
        return self._load(query)


def _load_row(query, value):
    row = {
        "v.avg_daily_attendance": str(value),
        "v.sum_attendance_value": "5",
        "v.sum_membership_value": "10",
    }
    for dim in query.get("dimensions", []):
        row[dim] = "Newark"
    return row


class FakeTableau:
    def __init__(
        self, exports=None, updated=datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    ):
        self.twb = (FIXTURES / "sheet_formats.twb").read_text()
        self.exports = exports
        self.updated = updated
        self.edited = None
        self.refresh = NOW - timedelta(hours=2)

    def download_twb(self, luid):
        return self.twb

    def workbook_updated(self, luid):
        return self.updated

    def capture(self, workbook_luid, sheet, cuts, xml_edit):
        self.edited = xml_edit(self.twb)
        exports = self.exports or [
            [{"Region": "Newark", "Rate": "0.9123", "Count": "12"}] for _ in cuts
        ]
        return Snapshot(self.refresh, "copy-1", exports)


class Clock:
    def __init__(self, start=NOW):
        self.t = start

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    """Wire fakes into the command line and return them."""
    bq = FakeBigQuery()
    cube = FakeCube()
    tbl = FakeTableau()
    deps = SimpleNamespace(bq=bq, cube=cube, tbl=tbl, signed_in=0)

    @contextlib.contextmanager
    def session():
        deps.signed_in += 1
        yield deps.tbl

    monkeypatch.setattr(cli, "make_warehouse", lambda: Warehouse(client=deps.bq))
    monkeypatch.setattr(cli, "make_cube", lambda url, secret, email: deps.cube)
    monkeypatch.setattr(cli, "tableau_session", session)
    monkeypatch.setattr(cli, "utcnow", Clock())
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setenv("CUBE_REST_URL", "http://cube.test/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_SECRET", "not-a-secret")
    monkeypatch.setenv("CUBE_VALIDATION_EMAIL", "analyst@example.org")
    return deps


def _file(tmp_path, text=YML):
    """Write a validation file, filling in the probe's real fingerprint."""
    path = tmp_path / "v.yml"
    path.write_text(text)
    if "PROBE_FP" in text:
        cfg = load_view_config(path)
        fp = pipeline.probe_fingerprint(cfg, cfg.comparisons[0])
        path.write_text(text.replace("PROBE_FP", fp))
    return path


def _first(pattern, text):
    match = re.search(pattern, text)
    assert match is not None, pattern
    return match[1]


def _literal_after(sql, table):
    return _first(re.escape(table) + r"`[^']*?TIMESTAMP '([^']+)'", sql)


def _reconcile(bq):
    return next(s for s in bq.ran if "-- outer" in s)


# --- run ---------------------------------------------------------------------


def test_run_uses_start_for_dashboard_and_end_for_cube(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    assert _literal_after(reconcile, "rpt_d") == utc_literal(START)
    assert _literal_after(reconcile, "fct_f") == utc_literal(END)
    assert _literal_after(reconcile, "dim_locations") == utc_literal(END)

    probes = [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]
    cells = [s for s in fakes.bq.ran if "AS value" in s and "fct_f" in s]
    assert len(probes) == len(cells) == 2
    assert {_literal_after(s, "rpt_d") for s in probes} == {utc_literal(START)}
    assert {_literal_after(s, "fct_f") for s in cells} == {utc_literal(END)}


def test_run_emits_date_grains_as_date_on_both_sides(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    assert "DATE(`v__attendance_date`) AS attendance_date" in reconcile
    assert "DATE(calendardate) AS calendardate" in reconcile


def test_run_keeps_student_rows_in_bigquery(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    for sql in fakes.bq.ran:
        if "student_number" in sql or "lea_student_identifier" in sql:
            assert "-- outer" in sql and "COUNT(DISTINCT __student)" in sql
    out = capsys.readouterr().out
    assert "student_number" not in out


def test_run_cube_rows_are_ungrouped_and_unlimited(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    row_queries = [q for q in fakes.cube.compiled_queries if q.get("ungrouped")]
    assert len(row_queries) == 1
    assert "LIMIT 10000" not in _reconcile(fakes.bq)
    # One reconcile covers both cuts, so a row is never counted twice.
    assert "or" in row_queries[0]["filters"][0]


def test_run_refuses_comparison_without_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))

    assert cli.main(["run", str(path)]) == 1

    err = capsys.readouterr().err
    assert "ada-region" in err and "prove" in err
    assert fakes.bq.ran == [] and fakes.cube.compiled_queries == []


def test_run_prices_before_running(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 10.0 if "-- outer" in sql else 0.001

    assert cli.main(["run", str(_file(tmp_path))]) == 1

    err = capsys.readouterr().err
    assert "$" in err and "5.00" in err
    assert not any("-- outer" in s for s in fakes.bq.ran)


def test_run_max_usd_sets_the_cap(fakes, tmp_path):
    fakes.bq.cost = lambda sql: 10.0 if "-- outer" in sql else 0.001

    assert cli.main(["run", str(_file(tmp_path)), "--max-usd", "50"]) == 0


def test_run_names_dimensions_that_changed(fakes, tmp_path, capsys):
    fakes.bq.changed = ("dim_locations",)

    assert cli.main(["run", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    section = out.split("## Dimensions that changed between start and end")[1]
    section = section.split("##")[0]
    assert "`kipptaf_marts.dim_locations`" in section
    assert "fct_f" not in section


def test_run_never_signs_in_to_tableau(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    assert fakes.signed_in == 0


def test_run_reports_cells_proofs_and_identity(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    assert "`avg_daily_attendance`: matches a dashboard; validated" in out
    assert "ada-region: last proven 2026-10-26T12:00:00+00:00" in out
    assert "ada-ratio" in out
    assert "regions_region_name" in out and "Miami" in out
    assert list((tmp_path / "cache" / "v").glob("*/result.md"))


def test_run_cells_that_differ_fail_the_dashboard_check(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": "Newark", "value": 0.5}]

    assert cli.main(["run", str(_file(tmp_path))]) == 0

    assert "matches a dashboard; differs" in capsys.readouterr().out


def test_run_refuses_without_email(fakes, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CUBE_VALIDATION_EMAIL")

    assert cli.main(["run", str(_file(tmp_path))]) == 1

    err = capsys.readouterr().err
    assert "--email" in err and "CUBE_VALIDATION_EMAIL" in err


def test_run_refuses_without_cube_url(fakes, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CUBE_REST_URL")

    assert cli.main(["run", str(_file(tmp_path))]) == 1
    assert "CUBE_REST_URL" in capsys.readouterr().err


def test_run_refuses_a_moment_outside_the_window(fakes, tmp_path, capsys):
    path = str(_file(tmp_path))

    assert cli.main(["run", path, "--moment", "2026-10-01T00:00:00Z"]) == 1
    assert "2026-10-01" in capsys.readouterr().err


def _saved_fingerprints(tmp_path):
    saved = sorted((tmp_path / "cache" / "v").glob("*/run.json"))
    return json.loads(saved[-1].read_text())["fingerprints"]["ada-region"]


def _with_decision(fp, tmp_path, call="domain_owner", text=YML):
    decision = f"""\
decisions:
  - id: miami-scope
    comparison: ada-region
    group: {{ column: regions_region_name, values: [Miami] }}
    call: {call}
    reason: The dashboard keeps Miami rows the fact drops.
    task: https://github.com/example/issues/1
    fingerprints: {{ cube: {fp["cube"]}, dashboard: {fp["dashboard"]} }}
"""
    return _file(tmp_path, text + decision)


def _section(out, start, end):
    return out.split(start)[1].split(end)[0]


def test_run_shows_the_fingerprints_a_decision_records(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    fp = _saved_fingerprints(tmp_path)
    assert len(fp["cube"]) == len(fp["dashboard"]) == 64
    shown = _section(out, "Fingerprints a new decision records", "##")
    assert (
        f"ada-region: {{ cube: {fp['cube']}, dashboard: {fp['dashboard']} }}" in shown
    )


def test_decision_fingerprints_ignore_the_moment(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    fakes.bq.build = (START + timedelta(hours=3), END + timedelta(hours=3))
    capsys.readouterr()

    assert cli.main(["run", str(path)]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "Applied:", "To re-confirm")
    assert "No open groups." in out


def test_dashboard_view_edit_asks_to_reconfirm(fakes, tmp_path, capsys):
    body = "select * from `teamster-332318`.`kipptaf_int`.`int_d` where keep"
    fakes.bq.views = {"rpt_d": body}
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    capsys.readouterr()

    assert cli.main(["run", str(path)]) == 0
    assert "miami-scope" in _section(
        capsys.readouterr().out, "Applied:", "To re-confirm"
    )

    fakes.bq.views = {"rpt_d": body.replace("where keep", "where keep and not dropped")}
    assert cli.main(["run", str(path)]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "To re-confirm", "No longer needed")
    assert "`regions_region_name` = `Miami`" in _section(out, "## Triage", "##")


def test_cube_row_dimension_edit_asks_to_reconfirm(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    # attendance_value is read by the row query only, never by the cells.
    fakes.cube.exprs["attendance_value"] = "coalesce(`t`.attendance_value, 0)"
    capsys.readouterr()

    assert cli.main(["run", str(path)]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "To re-confirm", "No longer needed")


def test_run_refuses_a_probe_changed_since_its_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    path.write_text(path.read_text().replace("avg(is_present)", "sum(is_present)"))

    assert cli.main(["run", str(path)]) == 1

    err = capsys.readouterr().err
    assert "ada-region" in err and "prove" in err
    assert fakes.bq.ran == []


SHARED_VIEW = (
    "select * from `teamster-332318`.`kipptaf_int`.`int_d` "
    "join `teamster-332318`.`kipptaf_marts`.`dim_locations` using (k)"
)


def test_run_reads_a_table_both_sides_share_at_1_moment(fakes, tmp_path):
    fakes.bq.views = {"rpt_d": SHARED_VIEW}

    assert cli.main(["run", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    stamps = set(re.findall(r"dim_locations`[^']*?TIMESTAMP '([^']+)'", reconcile))
    assert stamps == {utc_literal(START)}
    assert _literal_after(reconcile, "fct_f") == utc_literal(END)
    # The cells query reads Cube as of the end, as before.
    cells = [s for s in fakes.bq.ran if "AS value" in s and "fct_f" in s]
    assert {_literal_after(s, "dim_locations") for s in cells} == {utc_literal(END)}


def test_run_refuses_a_shared_table_that_changed_during_the_build(
    fakes, tmp_path, capsys
):
    fakes.bq.views = {"rpt_d": SHARED_VIEW}
    fakes.bq.changed = ("dim_locations",)

    assert cli.main(["run", str(_file(tmp_path))]) == 1
    err = capsys.readouterr().err
    assert "kipptaf_marts.dim_locations" in err and "changed during the build" in err


def test_run_refuses_sql_it_cannot_time_travel(fakes, tmp_path, capsys):
    text = YML.replace(
        "    probe: avg(is_present)\n",
        "    probe_sql: SELECT region, avg(x) AS value FROM ({rows}) AS r "
        "JOIN kipptaf_x.lookup USING (region) WHERE {where} GROUP BY 1\n",
    )

    assert cli.main(["run", str(_file(tmp_path, text))]) == 1
    assert "kipptaf_x.lookup" in capsys.readouterr().err


def test_unexpected_error_is_not_reported_as_a_refusal(fakes, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise KeyError("bug")

    monkeypatch.setattr(pipeline, "run", broken)

    with pytest.raises(KeyError):
        cli.main(["run", str(_file(tmp_path))])


def test_missing_validation_file_is_refused(fakes, tmp_path, capsys):
    assert cli.main(["run", str(tmp_path / "nope.yml")]) == 1
    assert "nope.yml" in capsys.readouterr().err


def test_tableau_sign_in_names_the_missing_variables(monkeypatch):
    for name in tableau.ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(pipeline.Refusal, match="TABLEAU_SERVER_ADDRESS"):
        with REAL_TABLEAU_SESSION():
            pass


# --- review ------------------------------------------------------------------


def test_review_never_posts(fakes, tmp_path, monkeypatch, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["run", str(path)]) == 0
    capsys.readouterr()

    def no_network(*args, **kwargs):
        raise AssertionError("review must not call out")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(cli, "make_cube", no_network)
    monkeypatch.setattr(cli, "make_warehouse", no_network)
    monkeypatch.setattr(cli, "tableau_session", no_network)

    assert cli.main(["review", str(path), "--domain", "Registrar"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("## What and why")
    assert "The Registrar team owns the rule behind 1 items" in out
    # The column name reads as an identifier, so its values stay hidden.
    assert "`regions_region_name` = `<redacted>`" in out and "12 students" in out


def test_review_refuses_a_view_never_run(fakes, tmp_path, capsys):
    assert cli.main(["review", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "run" in capsys.readouterr().err


# --- check-api ---------------------------------------------------------------


def test_check_api_agrees_on_three_cuts(fakes, tmp_path, capsys):
    assert cli.main(["check-api", str(_file(tmp_path))]) == 0

    assert len(fakes.cube.loads) == 3
    sql_runs = [s for s in fakes.bq.ran if "AS value" in s]
    assert len(sql_runs) == 3
    assert not any("FOR SYSTEM_TIME" in s for s in sql_runs)
    assert "3 of 3" in capsys.readouterr().out


def test_check_api_refuses_disagreement(fakes, tmp_path, capsys):
    fakes.cube._load = lambda q: [_load_row(q, 0.8)]

    assert cli.main(["check-api", str(_file(tmp_path))]) == 1
    assert "disagree" in capsys.readouterr().err


def test_check_api_refuses_when_a_table_rebuilt(fakes, tmp_path, capsys):
    fakes.bq.changed = ("fct_f",)

    assert cli.main(["check-api", str(_file(tmp_path))]) == 1
    assert "kipptaf_marts.fct_f" in capsys.readouterr().err


# --- prove -------------------------------------------------------------------


def test_prove_writes_the_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    argv = ["prove", str(path), "--comparison", "ada-region", "--value-column", "Rate"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].proof
    assert proof is not None
    assert proof.fingerprint == formula_fingerprint(fakes.tbl.twb, "Rate by Region")
    assert proof.cells == 2
    assert proof.workbook_updated_at.startswith("2026-10-20")
    cfg = load_view_config(path)
    assert proof.probe_fingerprint == pipeline.probe_fingerprint(
        cfg, cfg.comparisons[0]
    )
    probes = [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]
    assert {_literal_after(s, "rpt_d") for s in probes} == {
        utc_literal(fakes.tbl.refresh)
    }
    # The copy drops the sheet's number formats.
    assert "default-format" not in fakes.tbl.edited.split("<worksheets>")[1]


def test_prove_unhides_a_dashboard_only_sheet_on_the_copy(fakes, tmp_path, capsys):
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "<window class='worksheet' name='Rate by Region'>",
        "<window class='worksheet' hidden='true' name='Rate by Region'>",
    )
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    argv = ["prove", str(path), "--comparison", "ada-region", "--value-column", "Rate"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert "hidden=" not in fakes.tbl.edited


def test_prove_reads_aliases_back_and_skips_total_rows(fakes, tmp_path, capsys):
    region = "<column caption='Region' datatype='string' name='[region]' role='dimension' type='nominal' />"
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "            " + region,
        "            "
        + region.replace(" />", ">")
        + "<aliases><alias key='&quot;Newark&quot;' value='NWK' /></aliases></column>",
    )
    fakes.tbl.exports = [
        [
            {"Region": "NWK", "Rate": "0.9123", "Count": "12"},
            {"Region": "All", "Rate": "0.9001", "Count": "40"},
        ]
        for _ in range(2)
    ]
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    argv = ["prove", str(path), "--comparison", "ada-region", "--value-column", "Rate"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert load_view_config(path).comparisons[0].proof.cells == 2
    assert "skipped 1 total rows (All)" in capsys.readouterr().out


def test_prove_keeps_a_real_all_member(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": "All", "value": 0.9001}]
    fakes.tbl.exports = [[{"Region": "All", "Rate": "0.9001"}] for _ in range(2)]
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    argv = ["prove", str(path), "--comparison", "ada-region", "--value-column", "Rate"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert load_view_config(path).comparisons[0].proof.cells == 2


def test_prove_asks_which_column_holds_the_value(fakes, tmp_path, capsys):
    argv = ["prove", str(_file(tmp_path)), "--comparison", "ada-region"]

    assert cli.main(argv) == 1

    err = capsys.readouterr().err
    assert "Rate" in err and "Count" in err and "--value-column" in err


def test_prove_refuses_a_cut_with_no_rows(fakes, tmp_path, capsys):
    fakes.tbl.exports = [[{"Region": "Newark", "Rate": "0.9123", "Count": "1"}], []]
    argv = [
        "prove", str(_file(tmp_path)), "--comparison", "ada-region",
        "--value-column", "Rate",
    ]  # fmt: skip

    assert cli.main(argv) == 1
    assert "Miami" in capsys.readouterr().err


def test_prove_does_not_write_a_failed_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    fakes.bq.probe = [{"region": "Newark", "value": 0.5}]
    argv = ["prove", str(path), "--comparison", "ada-region", "--value-column", "Rate"]

    assert cli.main(argv) == 1

    assert load_view_config(path).comparisons[0].proof is None
    assert "probe" in capsys.readouterr().out


def test_prove_check_lists_stale_proofs(fakes, tmp_path, capsys):
    fakes.tbl.updated = datetime(2026, 10, 25, tzinfo=timezone.utc)

    assert cli.main(["prove", str(_file(tmp_path)), "--check"]) == 0

    out = capsys.readouterr().out
    assert "ada-region" in out and "re-prove" in out
    assert fakes.signed_in == 1


def test_prove_check_quiet_when_current(fakes, tmp_path, capsys):
    assert cli.main(["prove", str(_file(tmp_path)), "--check"]) == 0
    assert "current" in capsys.readouterr().out


# --- discover and usage ------------------------------------------------------


def test_discover_prints_candidates_and_skipped(fakes, tmp_path, monkeypatch, capsys):
    exposures = tmp_path / "tableau.yml"
    exposures.write_text(
        """
exposures:
  - name: attendance
    label: Attendance Dashboard
    depends_on: [ref("rpt_d")]
    config: { meta: { dagster: { asset: { metadata: { id: wb-1 } } } } }
  - name: no_luid
    label: No Luid
    depends_on: [ref("rpt_x")]
"""
    )
    monkeypatch.setattr(cli, "EXPOSURES", exposures)
    fakes.tbl.twb = (FIXTURES / "calcs.twb").read_text()

    assert (
        cli.main(
            ["discover", str(_file(tmp_path)), "--measure", "avg_daily_attendance"]
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "no_luid" in out
    assert "Attendance Rate" in out and "wb-1" in out
    assert fakes.cube.compiled_queries == [{"measures": ["v.avg_daily_attendance"]}]


@pytest.mark.parametrize("argv", [[], ["run"], ["nope", "x.yml"], ["prove", "x.yml"]])
def test_usage_errors_return_2(argv, fakes, capsys):
    assert cli.main(argv) == 2
