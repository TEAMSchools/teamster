import contextlib
import hashlib
import json
import os
import re
import urllib.request
import xml.etree.ElementTree
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import tableauserverclient as TSC

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, pipeline, tableau

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import Warehouse

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, load_view_config

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
    sheet_field: Rate
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
        self.schools = ["A", "B"]

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
        return Compiled(sql, list(self.schools), [])

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
        if getattr(self, "fail_next", None):
            error, self.fail_next = self.fail_next, None
            raise error
        return self.updated

    def reconnect(self):
        self.reconnects = getattr(self, "reconnects", 0) + 1

    def capture(self, workbook_luid, sheet, cuts, xml_edit):
        self.captures = getattr(self, "captures", 0) + 1
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


def _identity_sql(sql):
    """Cube's compiled SQL for an identity load: no other query reads both sums."""
    return "`v__sum_attendance_value`" in sql


def test_run_prices_a_cube_load_before_it_runs(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 10.0 if _identity_sql(sql) else 0.0

    assert cli.main(["run", str(_file(tmp_path))]) == 1

    assert "5.00" in capsys.readouterr().err
    assert fakes.cube.loads == []


def test_run_cost_includes_cube_loads(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 1.0 if _identity_sql(sql) else 0.0

    assert cli.main(["run", str(_file(tmp_path)), "--max-usd", "50"]) == 0

    # 2 identity cuts, 1 load each.
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    assert json.loads(saved.read_text())["cost_usd"] == pytest.approx(2.0)
    cost = _section(capsys.readouterr().out, "## Cost", "##")
    assert "$2.00" in cost and "Cube loads" in cost and "dry-run" in cost


def test_run_names_dimensions_that_changed(fakes, tmp_path, capsys):
    fakes.bq.changed = ("dim_locations",)

    assert cli.main(["run", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    section = out.split("## Dimensions that changed between start and end")[1]
    section = section.split("##")[0]
    assert "`kipptaf_marts.dim_locations`" in section
    assert "fct_f" not in section


def test_run_sends_and_names_set_scopes(fakes, tmp_path, capsys):
    text = YML.replace(
        "    cuts: [{}, { Region: Miami }]\n",
        "    cuts: [{}, { Region: Miami }]\n"
        "    scope:\n"
        "      - { cube: membership_value, values: [1] }\n"
        "      - { cube: attendance_value, operator: set }\n",
    )

    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    wanted = [
        {"member": "v.membership_value", "operator": "equals", "values": ["1"]},
        {"member": "v.attendance_value", "operator": "set"},
    ]
    # Identity loads are compiled only to price them; scopes are a comparison's.
    compared = [q for q in fakes.cube.compiled_queries if q not in fakes.cube.loads]
    assert compared
    for query in compared:
        assert all(f in query["filters"] for f in wanted)
    section = capsys.readouterr().out.split("## Scopes applied")[1].split("##")[0]
    assert "ada-region: v.membership_value in 1" in section
    assert "ada-region: v.attendance_value is set" in section


def test_run_never_signs_in_to_tableau(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    assert fakes.signed_in == 0


def test_run_reports_cells_proofs_and_identity(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    # The Miami group is still open, so the measure line says so.
    assert (
        "`avg_daily_attendance`: matches a dashboard; validated (pass 2); "
        "1 open row group to triage"
    ) in out
    assert "ada-region: last proven 2026-10-26T12:00:00+00:00" in out
    assert "ada-ratio" in out
    assert "regions_region_name" in out and "Miami" in out
    assert list((tmp_path / "cache" / "v").glob("*/result.md"))


def _browser_section(out):
    return _section(out, "## Cuts to prove in the browser", "##")


def test_run_lists_a_proof_without_cuts_for_a_re_prove(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert "ada-region: cuts unknown (the proof records none); re-prove" in section


def test_run_lists_cuts_no_export_proved(fakes, tmp_path, capsys):
    # The Miami cut sets a parameter, say, so the export proved only `{}`.
    text = YML.replace(PROOF, PROOF + "      cuts: ['{}']\n")

    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert 'ada-region: {"Region": "Miami"} (no export proved it)' in section
    assert "ada-region: {} (" not in section and "cuts unknown" not in section


def test_run_lists_no_cut_when_every_cut_was_exported(fakes, tmp_path, capsys):
    text = YML.replace(PROOF, PROOF + """      cuts: ['{}', '{"Region": "Miami"}']\n""")

    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert "(no export proved it)" not in section and "cuts unknown" not in section


def _totals_section(out):
    return _section(out, "## Totals not proven", "##")


def test_run_lists_totals_a_proof_skipped(fakes, tmp_path, capsys):
    text = YML.replace(PROOF, PROOF + "      totals_skipped: 2\n")

    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "ada-region: totals not proven: 2 rows" in _totals_section(out)
    assert out.count("totals not proven: 2 rows") == 2  # printed, then listed


def test_run_lists_no_totals_when_none_were_skipped(fakes, tmp_path, capsys):
    text = YML.replace(PROOF, PROOF + "      totals_skipped: 0\n")

    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "totals not proven" not in out
    assert "None." in _totals_section(out)


def test_run_reads_a_proof_without_a_totals_count_as_unknown(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    section = _totals_section(capsys.readouterr().out)
    assert "ada-region: totals not proven: unknown" in section
    assert "re-prove" in section


def test_run_warns_on_a_proof_older_than_7_days(fakes, tmp_path, capsys):
    old = PROOF.replace("2026-10-26T12:00:00+00:00", "2026-10-10T12:00:00+00:00")

    assert cli.main(["run", str(_file(tmp_path, YML.replace(PROOF, old)))]) == 0

    out = capsys.readouterr().out
    assert "Warning: the proof for ada-region is more than 7 days old" in out
    assert "prove --check" in out


def test_run_does_not_warn_on_a_recent_proof(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    assert "Warning: the proof" not in capsys.readouterr().out


def test_run_reads_each_identity_cut_in_one_load(fakes, tmp_path, capsys):
    fakes.cube._load = lambda q: [_load_row(q, 0.5)]

    assert cli.main(["run", str(_file(tmp_path))]) == 0

    # 2 cuts, 1 load each: both sides come from one result.
    assert len(fakes.cube.loads) == 2
    for query in fakes.cube.loads:
        assert query["measures"] == [
            "v.avg_daily_attendance",
            "v.sum_attendance_value",
            "v.sum_membership_value",
        ]
    out = capsys.readouterr().out
    assert out.count("identity `ada-ratio`") == 2
    assert "(passes)" in out and "(fails)" not in out


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
    assert "open row group" not in out


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


def test_reordered_school_list_keeps_decisions(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    # dim_locations has no order, so Cube may list the schools either way.
    fakes.cube.schools = ["B", "A"]
    capsys.readouterr()

    assert cli.main(["run", str(path)]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "Applied:", "To re-confirm")


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
    # A region name names no person, and the group has 10+ students.
    assert "`regions_region_name` = `Miami`" in out and "12 students" in out


def test_review_reads_the_run_written_last(fakes, tmp_path, capsys):
    # The later build runs first, with no decision yet.
    fakes.bq.build = (START + timedelta(hours=3), END + timedelta(hours=3))
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    fakes.bq.build = (START, END)
    assert cli.main(["run", str(path)]) == 0
    later, earlier = sorted((tmp_path / "cache" / "v").glob("*/run.json"), reverse=True)
    os.utime(later, (1_000_000, 1_000_000))
    os.utime(earlier, (2_000_000, 2_000_000))
    capsys.readouterr()

    assert cli.main(["review", str(path), "--domain", "Registrar"]) == 0

    assert "`regions_region_name` = `Miami`" in capsys.readouterr().out


def test_review_refuses_when_decisions_changed_since_the_run(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["run", str(path)]) == 0
    path.write_text(path.read_text().replace("keeps Miami rows", "keeps Miami"))
    capsys.readouterr()

    assert cli.main(["review", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert "v: " in err and "decisions" in err and "`run`" in err


def test_review_refuses_a_run_saved_without_a_decisions_fingerprint(
    fakes, tmp_path, capsys
):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    del data["decisions_fingerprint"]
    saved.write_text(json.dumps(data))

    assert cli.main(["review", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "decisions" in capsys.readouterr().err


def test_review_refuses_a_run_saved_in_the_old_group_shape(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    assert data["applied"]["open"]
    for g in data["applied"]["open"]:
        (column, value), *_ = g.pop("dims")
        g.update(column=column, value=value)
    saved.write_text(json.dumps(data))
    capsys.readouterr()

    assert cli.main(["review", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "older validator" in capsys.readouterr().err


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


def test_check_api_prices_the_api_side_before_it_loads(fakes, tmp_path, capsys):
    # Only Cube's bound SQL itself: the SQL side wraps it, the rebuild check
    # fingerprints the tables.
    fakes.bq.cost = lambda sql: (
        10.0
        if "fct_f" in sql and "FROM (\n" not in sql and "farm_fingerprint" not in sql
        else 0.0
    )

    assert cli.main(["check-api", str(_file(tmp_path))]) == 1

    assert "5.00" in capsys.readouterr().err
    assert fakes.cube.loads == []


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
    argv = ["prove", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].proof
    assert proof is not None
    assert proof.fingerprint == formula_fingerprint(fakes.tbl.twb, "Rate by Region")
    assert proof.cells == 2
    assert proof.cuts == ["{}", '{"Region": "Miami"}']
    assert proof.totals_skipped == 0
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
    argv = ["prove", str(path), "--comparison", "ada-region"]

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
    argv = ["prove", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].proof
    assert proof.cells == 2
    # 1 total row in each of the 2 cuts.
    assert proof.totals_skipped == 2
    assert "skipped 1 total rows (All)" in capsys.readouterr().out


def test_export_cells_reads_an_unquoted_numeric_alias_key_back():
    # The live ES sheet shows grade 0 as K; an integer column's alias key is
    # stored unquoted.
    columns = [
        xml.etree.ElementTree.fromstring(
            "<column caption='Grade Level' datatype='integer' name='[grade_level]'"
            " role='dimension' type='ordinal'>"
            "<aliases><alias key='0' value='K' /></aliases></column>"
        )
    ]
    comparison = Comparison(
        id="c",
        measure="m",
        dims=[ColumnPair(dashboard="grade_level", cube="grade_level")],
    )
    rows = [
        {"Grade Level": "K", "Rate": "0.94"},
        {"Grade Level": "1", "Rate": "0.95"},
        {"Grade Level": "All", "Rate": "0.945"},
    ]
    probe = [{"grade_level": 0, "value": 0.94}, {"grade_level": 1, "value": 0.95}]

    cells, totals, _ = pipeline._export_cells(
        comparison, rows, {"Grade Level": "grade_level"}, "Rate", columns, probe
    )

    assert cells == [
        {"grade_level": "0", "value": "0.94"},
        {"grade_level": "1", "value": "0.95"},
    ]
    assert totals == 1


def test_prove_keeps_a_real_all_member(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": "All", "value": 0.9001}]
    fakes.tbl.exports = [[{"Region": "All", "Rate": "0.9001"}] for _ in range(2)]
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    argv = ["prove", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert load_view_config(path).comparisons[0].proof.cells == 2


def test_prove_asks_which_column_holds_the_value(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace("    sheet_field: Rate\n", ""))
    argv = ["prove", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1

    err = capsys.readouterr().err
    assert "Rate" in err and "Count" in err and "sheet_field" in err


def test_prove_refuses_a_cut_with_no_rows(fakes, tmp_path, capsys):
    fakes.tbl.exports = [[{"Region": "Newark", "Rate": "0.9123", "Count": "1"}], []]
    argv = [
        "prove", str(_file(tmp_path)), "--comparison", "ada-region",
    ]  # fmt: skip

    assert cli.main(argv) == 1
    assert "Miami" in capsys.readouterr().err


def test_prove_does_not_write_a_failed_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(PROOF, "    proof: null\n"))
    fakes.bq.probe = [{"region": "Newark", "value": 0.5}]
    argv = ["prove", str(path), "--comparison", "ada-region"]

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


def test_two_rows_on_one_cell_refuse():
    comparison = Comparison(
        id="c",
        measure="m",
        dims=[ColumnPair(dashboard="grade_level", cube="grade_level")],
    )
    dash = [{"grade_level": 0, "value": 0.94}, {"grade_level": "0.0", "value": 0.5}]
    cube = [{"grade_level": 0, "value": 0.94}]

    with pytest.raises(
        pipeline.Refusal, match="c .*dashboard: 2 rows share the cell 0"
    ):
        pipeline._cells(comparison, {}, dash, cube, 3)


# --- prove: sheet shape --------------------------------------------------------

UNPROVEN = YML.replace(PROOF, "    proof: null\n")
TEAM_SHELF = (
    "<rows>([federated.0sample].[none:region:nk] / "
    "[federated.0sample].[none:team:nk])</rows>"
)


def _with_team(twb):
    """Add a Team cut on the rows shelf and a Term filter left at All."""
    twb = twb.replace("<rows>[federated.0sample].[none:region:nk]</rows>", TEAM_SHELF)
    return twb.replace(
        "          <aggregation value='true' />",
        "          <column caption='Team' name='[team]' role='dimension' />\n"
        "          <column caption='Term' name='[term]' role='dimension' />\n"
        "          <filter class='categorical' column='[federated.0sample].[none:term:nk]'>"
        "<groupfilter function='level-members' level='[none:term:nk]' "
        "user:ui-enumeration='all' /></filter>\n"
        "          <aggregation value='true' />",
    )


def test_prove_records_missing_cuts_and_filters(fakes, tmp_path, capsys):
    fakes.tbl.twb = _with_team(fakes.tbl.twb)
    path = _file(tmp_path, UNPROVEN)

    assert cli.main(["prove", str(path), "--comparison", "ada-region"]) == 0

    proof = load_view_config(path).comparisons[0].proof
    assert proof.missing_cuts == ["Team"]
    assert proof.missing_filters == ["Term"]
    assert proof.restricting_filters == []
    assert "Sheet cuts with no Cube member: Team" in capsys.readouterr().out


def test_prove_sums_split_rows_of_a_long_export(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": "Newark", "value": 0.9}]
    fakes.tbl.exports = [
        [
            {"Region": "Newark", "Team": "A", "Measure Names": "Rate", "Measure Values": "0.5"},
            {"Region": "Newark", "Team": "A", "Measure Names": "Count", "Measure Values": "9"},
            {"Region": "Newark", "Team": "B", "Measure Names": "Rate", "Measure Values": "0.4"},
        ]
        for _ in range(2)
    ]  # fmt: skip
    text = UNPROVEN.replace(
        "    sheet_field: Rate\n", "    sheet_field: Rate\n    split_rows: sum\n"
    )
    path = _file(tmp_path, text)

    assert cli.main(["prove", str(path), "--comparison", "ada-region"]) == 0, (
        capsys.readouterr().err
    )

    assert load_view_config(path).comparisons[0].proof.cells == 2
    assert "summed 1 split export rows" in capsys.readouterr().out


def test_prove_refuses_split_rows_unless_asked(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": "Newark", "value": 0.9}]
    fakes.tbl.exports = [
        [
            {"Region": "Newark", "Rate": "0.5", "Count": "1"},
            {"Region": "Newark", "Rate": "0.4", "Count": "1"},
        ]
        for _ in range(2)
    ]
    path = _file(tmp_path, UNPROVEN)

    assert cli.main(["prove", str(path), "--comparison", "ada-region"]) == 1

    out = capsys.readouterr().out
    assert "2 x more than 1 export row" in out
    saved = tmp_path / "cache" / "v" / "prove-failures-ada-region.txt"
    assert saved.read_text().count("more than 1 export row") == 2


def test_prove_failure_output_is_summarized(fakes, tmp_path, capsys):
    fakes.bq.probe = [{"region": f"R{i}", "value": 0.5} for i in range(20)]
    fakes.tbl.exports = [
        [{"Region": f"R{i}", "Rate": "0.9", "Count": "1"} for i in range(20)]
        for _ in range(2)
    ]
    path = _file(tmp_path, UNPROVEN)

    assert cli.main(["prove", str(path), "--comparison", "ada-region"]) == 1

    out = capsys.readouterr().out
    assert "40 x value differs at the displayed decimals" in out
    assert "First 5 of 40:" in out
    assert out.count(": export ") == 5


def test_prove_several_comparisons_share_one_capture(fakes, tmp_path, capsys):
    block = UNPROVEN.split("comparisons:\n", 1)[1].split("identities:", 1)[0]
    text = UNPROVEN.replace(
        "identities:", block.replace("id: ada-region", "id: ada-twin") + "identities:"
    )
    path = _file(tmp_path, text)
    argv = [
        "prove",
        str(path),
        "--comparison",
        "ada-region",
        "--comparison",
        "ada-twin",
    ]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert fakes.tbl.captures == 1
    assert all(c.proof is not None for c in load_view_config(path).comparisons)


def test_prove_keeps_going_after_one_refusal(fakes, tmp_path, capsys):
    argv = ["prove", str(_file(tmp_path, UNPROVEN)), "--comparison", "nope",
            "--comparison", "ada-region"]  # fmt: skip

    assert cli.main(argv) == 1

    assert "nope" in capsys.readouterr().err
    assert load_view_config(tmp_path / "v.yml").comparisons[0].proof is not None


def test_probe_fingerprint_covers_how_the_export_is_read(tmp_path):
    def fp(text):
        cfg = load_view_config(_file(tmp_path, text))
        return pipeline.probe_fingerprint(cfg, cfg.comparisons[0])

    plain = YML.replace("    sheet_field: Rate\n", "")
    base = pipeline.decisions.sql_fingerprint(
        pipeline.probe_sql(
            load_view_config(_file(tmp_path, plain)),
            load_view_config(_file(tmp_path, plain)).comparisons[0],
            {},
        )
    )
    # Unset keys leave an older proof's fingerprint alone.
    assert fp(plain) == base
    assert fp(YML) != base
    summed = YML.replace(
        "    sheet_field: Rate\n", "    sheet_field: Rate\n    split_rows: sum\n"
    )
    assert fp(summed) not in (base, fp(YML))


# --- run: missing cuts and filters ----------------------------------------------

GAP_PROOF = (
    PROOF
    + """\
      missing_cuts: [Team]
      missing_filters: [Enroll Status]
      restricting_filters: [Enroll Status]
"""
)


def test_run_lists_missing_cuts_from_the_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(PROOF, GAP_PROOF))

    assert cli.main(["run", str(path)]) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    assert "`Team` (cut) on Rate by Region: Cube has no member; ada-region" in out
    assert "(filter, set to chosen values, not All)" in out
    assert "2 missing cuts or filters to triage" in out


def test_run_says_when_a_proof_predates_missing_cuts(fakes, tmp_path, capsys):
    assert cli.main(["run", str(_file(tmp_path))]) == 0

    assert "ada-region: missing cuts and filters unknown" in capsys.readouterr().out


def test_gap_decision_quiets_a_missing_cut(fakes, tmp_path, capsys):
    text = (
        YML.replace(PROOF, GAP_PROOF)
        + """\
decisions:
  - id: no-team
    missing_cut: Team
    call: deliberate
    reason: homeroom label only
"""
    )
    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "1 missing cut or filter to triage" in out
    assert "`no-team` (missing cut `Team`, deliberate)" in out


def test_review_carries_a_domain_owner_missing_cut(fakes, tmp_path, capsys):
    text = (
        YML.replace(PROOF, GAP_PROOF)
        + """\
decisions:
  - id: team-cut
    missing_cut: Team
    call: domain_owner
    reason: the owner decides whether ADA needs a team cut
    task: "#6150"
"""
    )
    path = _file(tmp_path, text)
    assert cli.main(["run", str(path)]) == 0
    capsys.readouterr()

    assert cli.main(["review", str(path), "--domain", "Registrar"]) == 0

    out = capsys.readouterr().out
    assert (
        "`Team` on `Rate by Region` in `v`: a sheet cut Cube has no member for" in out
    )
    assert "Missing cuts and filters: 1." in out


def test_run_names_dashboard_only_filters(fakes, tmp_path, capsys):
    text = YML.replace(
        "    rows:\n",
        "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n    rows:\n",
        1,
    )
    assert cli.main(["run", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    section = out.split("## Dashboard-only filters", 1)[1].split("## ", 1)[0]
    assert "ada-region: enroll_status IN (0)" in section
    reconcile = _reconcile(fakes.bq)
    assert "enroll_status IN (0)" in reconcile


# --- discover and prove --headers -------------------------------------------------


def _exposures(tmp_path, monkeypatch):
    exposures = tmp_path / "tableau.yml"
    exposures.write_text(
        "exposures:\n  - name: attendance\n    label: Attendance Dashboard\n"
        '    depends_on: [ref("rpt_d")]\n'
        "    config: { meta: { dagster: { asset: { metadata: { id: wb-1 } } } } }\n"
    )
    monkeypatch.setattr(cli, "EXPOSURES", exposures)


def test_discover_boosts_a_caption_and_describes_its_sheet(
    fakes, tmp_path, monkeypatch, capsys
):
    _exposures(tmp_path, monkeypatch)
    fakes.tbl.twb = (FIXTURES / "roster.twb").read_text()
    argv = ["discover", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
            "--caption", "# Tardy", "--all"]  # fmt: skip

    assert cli.main(argv) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    lines = [x for x in out.splitlines() if "Attendance Dashboard (wb-1)" in x]
    assert "'# Tardy'" in lines[0]
    assert "[Att Code (group): Tardy = T, ET; Absent = A]" in lines[0]
    assert any("'SUM(Membership)'" in x for x in lines)
    sheets = out.split("Sheets:", 1)[1]
    assert "Roster (Attendance Dashboard): rows Region, Student Number" in sheets
    assert "long (set sheet_field to a Measure Names value)" in sheets
    assert "decimals: # Tardy 0, SUM(Membership) 3" in sheets
    assert "Student Number: chosen values hidden" in sheets
    assert "999999" not in out


def test_discover_keeps_the_top_5_by_default(fakes, tmp_path, monkeypatch, capsys):
    _exposures(tmp_path, monkeypatch)
    fakes.tbl.twb = (FIXTURES / "roster.twb").read_text()
    argv = ["discover", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
            "--limit", "1", "--caption", "# Tardy"]  # fmt: skip

    assert cli.main(argv) == 0

    out = capsys.readouterr().out
    assert len([x for x in out.splitlines() if "(wb-1)" in x]) == 1


def test_prove_headers_prints_the_export_without_probing(fakes, tmp_path, capsys):
    fakes.tbl.exports = [
        [{"Region": "Newark", "Measure Names": "# Tardy", "Measure Values": "3"},
         {"Region": "Newark", "Measure Names": "# Present", "Measure Values": "90"}]
        for _ in range(2)
    ]  # fmt: skip
    path = _file(tmp_path, UNPROVEN)
    before = path.read_text()

    assert (
        cli.main(["prove", str(path), "--comparison", "ada-region", "--headers"]) == 0
    )

    out = capsys.readouterr().out
    assert "ada-region cut {}: Region, Measure Names, Measure Values" in out
    assert "Measure Names: # Present, # Tardy" in out
    assert fakes.bq.ran == [] and path.read_text() == before


# --- Tableau sessions ------------------------------------------------------------

TWIN = UNPROVEN.replace(
    "identities:",
    UNPROVEN.split("comparisons:\n", 1)[1]
    .split("identities:", 1)[0]
    .replace("id: ada-region", "id: ada-twin")
    + "identities:",
)
TWO = ["--comparison", "ada-region", "--comparison", "ada-twin"]


def test_prove_signs_in_again_after_a_401(fakes, tmp_path, capsys):
    fakes.tbl.fail_next = TSC.ServerResponseError("401002", "Unauthorized Access", "")
    path = _file(tmp_path, TWIN)

    assert cli.main(["prove", str(path), *TWO]) == 0, capsys.readouterr().err

    assert fakes.tbl.reconnects == 1
    assert all(c.proof is not None for c in load_view_config(path).comparisons)
    assert "signing in again" in capsys.readouterr().err


def test_prove_refuses_one_comparison_on_another_tableau_error(fakes, tmp_path, capsys):
    fakes.tbl.fail_next = TSC.ServerResponseError("403004", "Forbidden", "")
    path = _file(tmp_path, TWIN)

    assert cli.main(["prove", str(path), *TWO]) == 1

    assert "ada-region: Tableau answered 403004 Forbidden" in capsys.readouterr().err
    proofs = [c.proof for c in load_view_config(path).comparisons]
    assert proofs[0] is None and proofs[1] is not None


class _Server:
    def __init__(self, fail_sign_out=False):
        self.fail_sign_out = fail_sign_out
        self.signed_out = 0
        self.auth = self

    def sign_out(self):
        self.signed_out += 1
        if self.fail_sign_out:
            raise TSC.ServerResponseError("401002", "Unauthorized Access", "")


def _real_session(monkeypatch, servers):
    for name in tableau.ENV_VARS:
        monkeypatch.setenv(name, "x")
    monkeypatch.setattr(tableau, "sign_in_from_env", lambda: servers.pop(0))


def test_a_failed_sign_out_does_not_hide_the_first_error(monkeypatch, capsys):
    _real_session(monkeypatch, [_Server(fail_sign_out=True)])

    with pytest.raises(ValueError, match="the first error"):
        with REAL_TABLEAU_SESSION():
            raise ValueError("the first error")

    assert "sign-out failed" in capsys.readouterr().err


def test_reconnect_signs_in_again_and_signs_the_old_session_out(monkeypatch):
    first, second = _Server(fail_sign_out=True), _Server()
    _real_session(monkeypatch, [first, second])

    with REAL_TABLEAU_SESSION() as tbl:
        tbl.reconnect()
        assert tbl._server is second

    assert first.signed_out == 1 and second.signed_out == 1


def test_review_says_which_tasks_to_fill_in(fakes, tmp_path, capsys):
    text = (
        YML.replace(PROOF, GAP_PROOF)
        + """\
decisions:
  - id: team-cut
    missing_cut: Team
    call: domain_owner
    reason: the owner decides whether ADA needs a team cut
"""
    )
    path = _file(tmp_path, text)
    assert cli.main(["run", str(path)]) == 0
    capsys.readouterr()

    assert cli.main(["review", str(path), "--domain", "Registrar"]) == 0

    captured = capsys.readouterr()
    assert "team-cut" in captured.err and "fill in" in captured.err
    assert "fill in" not in captured.out


def test_run_probes_again_without_dashboard_filters_only_when_set(fakes, tmp_path):
    def probes():
        return [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]

    assert cli.main(["run", str(_file(tmp_path))]) == 0
    plain = len(probes())
    fakes.bq.ran.clear()
    text = YML.replace(
        "    rows:\n",
        "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n    rows:\n",
        1,
    )
    assert cli.main(["run", str(_file(tmp_path, text))]) == 0
    assert len(probes()) == 2 * plain
    assert sum("enroll_status IN (0)" not in s for s in probes()) == plain


def test_run_opens_and_quiets_cell_differences(fakes, tmp_path, capsys):
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95}]
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    out = capsys.readouterr().out
    section = out.split("## Cell differences", 1)[1].split("## ", 1)[0]
    assert "ada-region: 2 differ" in section
    assert "Cube computes `avg_daily_attendance` as" in section

    fp = _saved_fingerprints(tmp_path)
    text = (
        YML
        + f"""\
decisions:
  - id: ada-cells
    comparison: ada-region
    cells: true
    call: deliberate
    reason: known definition difference
    fingerprints: {{ cube: {fp["cube"]}, dashboard: {fp["dashboard"]} }}
"""
    )
    assert cli.main(["run", str(_file(tmp_path, text))]) == 0
    out = capsys.readouterr().out
    assert "`ada-cells` (ada-region cells, deliberate)" in out
    assert "cell differences to triage" not in out
