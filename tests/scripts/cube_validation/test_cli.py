import contextlib
import hashlib
import json
import os
import re
import urllib.request
import xml.etree.ElementTree
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import tableauserverclient as TSC

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import (
    checkpoints,
    cli,
    compare,
    coverage,
    explain,
    formula,
    latest,
    pipeline,
    rebuild,
    report,
    results,
    review,
    sort,
    tableau,
    trace,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import CostCapError, Warehouse

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, load_view_config

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import Compiled, CubeError

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.formula import (
    NO_ROWS,
    NOT_COMPARED,
    NOT_COMPOSED,
    OUTSIDE,
    RUN_FAILED,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.saved import SCRATCH_DATASET

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.tableau import Snapshot, formula_fingerprint

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import utc_literal
from google.api_core.exceptions import BadRequest, NotFound
from google.auth.exceptions import RefreshError

FIXTURES = Path(__file__).parent / "fixtures"
REAL_TABLEAU_SESSION = cli.tableau_session
START = datetime(2026, 10, 22, 20, 30, tzinfo=timezone.utc)
END = START + timedelta(minutes=14)
NOW = END + timedelta(days=1)
TIB = 2**40

REBUILD_CHECK = """\
    rebuild_check:
      fingerprint: abc
      cells: 2
      matched_at: '2026-10-26T12:00:00+00:00'
      workbook_updated_at: '2026-10-20T09:00:00+00:00'
      sheet_query_fingerprint: PROBE_FP
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
    sheet_query: avg(is_present)
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
    + REBUILD_CHECK
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
        # Each cut's rows on each side: the YML's cuts `{}` and Region Miami.
        "__s_k0_c_rows": 0,
        "__s_k0_d_rows": 30,
        "__s_k1_c_rows": 0,
        "__s_k1_d_rows": 30,
    },
]


class FakeBigQuery:
    """A `bigquery.Client` stand-in: prices dry runs, records what runs."""

    def __init__(self, cost=lambda sql: 0.0, changed=(), sheet_query=None, cells=None):
        self.cost = cost
        self.changed = changed
        self.ran: list[str] = []
        # Every dry run and run in order, as ("dry" | "run", sql).
        self.log: list[tuple[str, str]] = []
        # The next query holding this text is refused as over its cap, once.
        self.fail_once: str | None = None
        self.sheet_query = sheet_query or [{"region": "Newark", "value": 0.9123}]
        self.cells = cells
        # The reconcile's result rows: each bucket and its rows per cut.
        self.reconcile = RECONCILE_ROWS
        # Per cut index: cut 0 is `{}`, cut 1 is `{Region: Miami}`.
        self.students = [
            {"__cut": 0, "region": "Miami", "n_students": 12},
            {"__cut": 0, "region": "Newark", "n_students": 40},
            {"__cut": 1, "region": "Miami", "n_students": 3},
            {"__cut": 1, "region": "Newark", "n_students": 5},
        ]
        self.views: dict[str, str] = {}
        self.build = (START, END)
        # Each table's columns, by name, for `Warehouse.columns`.
        self.schemas: dict[str, list[str]] = {"fct_f": list(FACT_COLUMNS)}
        # Each saved table's labels, by dotted id, as the save script set them.
        self.saved: dict[str, dict[str, str]] = {}
        # The formula check's 4 queries' rows, by `Job.sql` key, without
        # `__cut`. A missing self-check answers as the run's own cells did;
        # a missing matched side, as the dashboard's cells, so by default the
        # sides agree on matched rows and coverage decides.
        self.formula: dict[str, list[dict]] = {}

    def get_table(self, ref):
        if ref in self.saved:
            return SimpleNamespace(
                table_type="TABLE", view_query=None, modified=END,
                labels=self.saved[ref], schema=[],
            )  # fmt: skip
        if f".{SCRATCH_DATASET}." in ref:
            raise NotFound(f"Not found: Table {ref}")
        name = ref.rsplit(".", 1)[-1]
        schema = [SimpleNamespace(name=c) for c in self.schemas.get(name, [])]
        if name in self.views:
            return SimpleNamespace(
                table_type="VIEW",
                view_query=self.views[name],
                modified=START - timedelta(days=2),
                schema=schema,
            )
        return SimpleNamespace(
            table_type="TABLE", view_query=None, modified=START, schema=schema
        )

    def query(self, sql, job_config=None):
        nbytes = int(self.cost(sql) / 6.25 * TIB)
        if job_config is not None and job_config.dry_run:
            self.log.append(("dry", sql))
            return SimpleNamespace(total_bytes_processed=nbytes, result=lambda: [])
        limit = job_config.maximum_bytes_billed if job_config is not None else None
        failing = self.fail_once is not None and self.fail_once in sql
        if failing:
            self.fail_once = None
        if failing or (limit is not None and nbytes > int(limit)):
            # BigQuery refuses an over-limit query before it runs, unbilled.
            def refuse():
                raise BadRequest(
                    "over the limit", errors=[{"reason": "bytesBilledLimitExceeded"}]
                )

            return SimpleNamespace(total_bytes_processed=0, result=refuse)
        self.ran.append(sql)
        self.log.append(("run", sql))
        for table, pairs in _SAVED_TABLE.findall(sql):
            self.saved[table.replace("`", "")] = dict(_LABEL.findall(pairs))
        rows = self.answer(sql)
        return SimpleNamespace(
            total_bytes_processed=nbytes, total_bytes_billed=nbytes, result=lambda: rows
        )

    def answer(self, sql):
        if cuts := _FORMULA_CUT.findall(sql):
            return self._formula(sql, cuts)
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
            return self.reconcile
        if "AS n_students" in sql:
            return self.students
        if "AS value" in sql and "fct_f" in sql:
            if self.cells is not None:
                return self.cells
            if "AS regions_region_name" in sql:
                return [{"regions_region_name": "Newark", "value": 0.91234}]
            return [{"value": 0.91234}]
        if "AS value" in sql and "rpt_d" in sql:
            return self.sheet_query
        return []

    def _formula(self, sql, cuts):
        """One of the formula check's queries: its rows per cut it computes."""
        # Only the dashboard's side reads the sheet's view past the cut tag.
        side = "dashboard" if "rpt_d" in sql.split("AS __cut", 1)[1] else "cube"
        key = side if "__matched" in sql else f"{side}_self"
        if key in self.formula:
            rows = self.formula[key]
        elif side == "dashboard":
            rows = self.sheet_query
        elif key == "cube":
            rows = [{"regions_region_name": r["region"], "value": r["value"]}
                    for r in self.sheet_query]  # fmt: skip
        else:
            rows = self.cells or [{"regions_region_name": "Newark", "value": 0.91234}]
        return [{"__cut": cut.replace("\\'", "'"), **r} for cut in cuts for r in rows]


# The fact's columns, as `Warehouse.columns` reads its schema.
FACT_COLUMNS = (
    "lea_student_identifier", "attendance_date", "attendance_value",
    "membership_value", "regions_region_name", "dates_academic_year", "is_present",
)  # fmt: skip
# A save script's table and its labels (`reconcile.reconcile_script`).
_SAVED_TABLE = re.compile(
    r"CREATE OR REPLACE TABLE (\S+)\nOPTIONS\([^\n]*?labels = \[([^\]]*)\]"
)
_LABEL = re.compile(r"\('([^']*)', '([^']*)'\)")
# A formula check query's cut tags (`formula.dashboard_side_sql`, `cube_side_sql`).
_FORMULA_CUT = re.compile(r"SELECT '((?:[^'\\]|\\.)*)' AS __cut, \* FROM")


class FakeCube:
    def __init__(self, load=None):
        self.compiled_queries: list[dict] = []
        self.loads: list[dict] = []
        self._load = load or (lambda q: [_load_row(q, 0.91234)])
        self.exprs: dict[str, str] = {}
        self.schools = ["A", "B"]
        self.dataset = "kipptaf_marts"
        self.dropped: set[str] = set()
        # Extra JOIN lines, such as a second fact the view reads.
        self.joins = ""

    def compiled(self, query):
        self.compiled_queries.append(query)
        # Cube refuses to compile a member its model no longer has.
        if gone := sorted(set(rebuild._query_members(query)) & self.dropped):
            raise CubeError(f"Cube GET /sql: {', '.join(gone)} not found")
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
            f"FROM  {self.dataset}.fct_f  AS `t`\n"
            "LEFT JOIN  kipptaf_marts.dim_locations  AS `locations` "
            "ON `locations`.k = `t`.k\n"
            f"{self.joins}"
            "WHERE (`locations`.abbreviation IN (?, ?))\n"
            "LIMIT 10000"
        )
        return Compiled(sql, list(self.schools), [])

    def load(self, query):
        self.loads.append(query)
        return self._load(query)

    def meta(self):
        return {
            "cubes": [
                {
                    "name": "v",
                    "measures": [{"name": m} for m in CUBE_MEASURES - self.dropped],
                    "dimensions": [{"name": d} for d in CUBE_DIMENSIONS - self.dropped],
                }
            ]
        }


# The members the fake Cube model has; a test drops one through `dropped`.
CUBE_MEASURES = {"v.avg_daily_attendance", "v.sum_attendance_value"}
CUBE_DIMENSIONS = {
    "v.academic_subject",
    "v.attendance_date",
    "v.attendance_value",
    "v.dates_academic_year",
    "v.lea_student_identifier",
    "v.membership_value",
    "v.regions_region_name",
}


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
        # The workbook's views as Tableau Server lists them.
        self.views = {"Rate by Region"}
        self.view_asks: list[str] = []

    def download_twb(self, luid):
        self.downloads = getattr(self, "downloads", 0) + 1
        return self.twb

    def view_names(self, luid):
        self.view_asks.append(luid)
        return set(self.views)

    def workbook_updated(self, luid):
        error = getattr(self, "fail_next", None)
        if error:
            self.fail_next = None
            raise error
        return self.updated

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

    def linked(path, data):
        """A review file written and linked as if committed and pushed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))
        return f"https://github.com/o/r/blob/abc/{path.name}"

    monkeypatch.setattr(review, "_review_file", linked)
    monkeypatch.setenv("CUBE_REST_URL", "http://cube.test/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_SECRET", "not-a-secret")
    monkeypatch.setenv("CUBE_VALIDATION_EMAIL", "analyst@example.org")
    return deps


def _file(tmp_path, text=YML):
    """Write a validation file, filling in each comparison's real probe
    fingerprint."""
    path = tmp_path / "v.yml"
    path.write_text(text)
    if "PROBE_FP" in text:
        cfg = load_view_config(path)
        fps = {c.id: pipeline.sheet_query_fingerprint(cfg, c) for c in cfg.comparisons}
        head, *entries = text.split("\n  - id: ")
        entries = [
            e.replace("PROBE_FP", fps[e.split("\n", 1)[0].strip()])
            if "PROBE_FP" in e
            else e
            for e in entries
        ]
        path.write_text("\n  - id: ".join([head, *entries]))
    return path


def _first(pattern, text):
    match = re.search(pattern, text)
    assert match is not None, pattern
    return match[1]


def _literal_after(sql, table):
    return _first(re.escape(table) + r"`[^']*?TIMESTAMP '([^']+)'", sql)


def _reconcile(bq):
    return next(s for s in bq.ran if "-- outer" in s)


def _count_branches(sql):
    """The per-cut SELECTs of the student count, parentheses stripped."""
    assert sql.startswith("(") and sql.endswith(")"), sql
    return sql[1:-1].split(") UNION ALL (")


# --- run ---------------------------------------------------------------------


def test_run_uses_start_for_dashboard_and_end_for_cube(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    assert _literal_after(reconcile, "rpt_d") == utc_literal(START)
    assert _literal_after(reconcile, "fct_f") == utc_literal(END)
    assert _literal_after(reconcile, "dim_locations") == utc_literal(END)

    probes = [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]
    cells = [s for s in fakes.bq.ran if "AS value" in s and "fct_f" in s]
    assert len(probes) == len(cells) == 2
    assert {_literal_after(s, "rpt_d") for s in probes} == {utc_literal(START)}
    assert {_literal_after(s, "fct_f") for s in cells} == {utc_literal(END)}


def test_run_skips_a_member_cube_dropped_before_it_spends(fakes, tmp_path, capsys):
    fakes.cube.dropped = {"v.attendance_value"}

    assert cli.main(["compare", str(_file(tmp_path))]) == 1

    captured = capsys.readouterr()
    assert "Skipping ada-region: Cube's model has no member for v.attendance_value" in (
        captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    assert fakes.bq.ran == [] and fakes.cube.compiled_queries == []


def test_run_emits_date_grains_as_date_on_both_sides(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    assert "DATE(`v__attendance_date`) AS attendance_date" in reconcile
    assert "DATE(calendardate) AS calendardate" in reconcile


def test_run_keeps_student_rows_in_bigquery(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    for sql in fakes.bq.ran:
        if "student_number" in sql or "lea_student_identifier" in sql:
            if "-- outer" in sql:
                assert "COUNT(DISTINCT __student)" in sql
                continue
            # The per-cell student count: each cut's branch returns only the
            # cut index, the dims and the count.
            branches = _count_branches(sql)
            assert len(branches) == 2
            for i, branch in enumerate(branches):
                assert re.fullmatch(
                    rf"SELECT {i} AS __cut, region, COUNT\(DISTINCT student_number\) "
                    r"AS n_students FROM \(SELECT \* FROM [^()]*\) WHERE .* GROUP BY 2",
                    branch,
                    re.DOTALL,
                ), branch
    out = capsys.readouterr().out
    assert "student_number" not in out


def test_run_saves_each_comparison_s_unmatched_rows_to_a_labelled_table(
    fakes, tmp_path
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    script = _reconcile(fakes.bq)
    sha = hashlib.sha256(b"ada-region").hexdigest()[:8]
    assert "CREATE TEMP TABLE __joined" in script
    assert (
        "CREATE OR REPLACE TABLE `teamster-332318`.`cube_validation_scratch`."
        f"`v__2026_10_22t204400z__ada_region_{sha}`"
    ) in script
    assert "('comparison', 'ada-region')" in script
    assert "INTERVAL 14 DAY" in script
    # The rows stay in BigQuery: the job returns only the counts.
    assert script.rstrip().split(";\n")[-1].startswith("-- outer")


def _four(tmp_path):
    """The view file with its comparison repeated as `ada-region-1` to `-4`."""
    head, rest = YML.split("  - id: ada-region\n", 1)
    blocks = "".join(f"  - id: ada-region-{i}\n" + rest for i in range(1, 5))
    return _file(tmp_path, head + blocks)


def _outer(bq):
    return [s for s in bq.ran if "-- outer" in s]


def _run_folder(tmp_path):
    """The view's one run folder: every folder but its latest results."""
    (folder,) = [
        f for f in (tmp_path / "cache" / "v").iterdir() if f.name != latest.DIR
    ]
    return folder


def test_a_stopped_run_resumes_to_the_same_result(fakes, tmp_path, monkeypatch):
    path = _four(tmp_path)
    # Baseline: an uninterrupted run in its own cache.
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "whole")
    assert cli.main(["compare", str(path)]) == 0
    whole = json.loads(next((tmp_path / "whole").glob("v/*/run.json")).read_text())

    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    folder = _run_folder(tmp_path)
    # Comparisons run in config order: 1 and 2 finished, 3 failed, 4 never began.
    assert sorted(checkpoints.read_all(folder)) == ["ada-region-1", "ada-region-2"]
    assert not (folder / "run.json").exists()

    fakes.bq.ran.clear()
    assert cli.main(["compare", str(path)]) == 0

    scripts = _outer(fakes.bq)
    assert len(scripts) == 2
    assert "ada_region_3" in scripts[0] and "ada_region_4" in scripts[1]
    resumed = json.loads((folder / "run.json").read_text())
    assert {**resumed, "cost_usd": 0} == {**whole, "cost_usd": 0}
    assert resumed["cost_usd"] == pytest.approx(checkpoints.total_spend(folder))
    assert checkpoints.find_unfinished(tmp_path / "cache", "v") is None


def test_a_resumed_run_says_so(fakes, tmp_path, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Resuming the unfinished run of" in out
    # It compares only the 2 never compared; the 2 saved kept their results.
    assert "0 of 2 comparisons saved" in out


def test_the_resume_count_names_only_checkpoints_of_confirmed_comparisons(
    fakes, tmp_path, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    folder = _run_folder(tmp_path)
    # A comparison since removed from the file left its checkpoint behind.
    checkpoints.write(folder, "gone", "f", {}, NOW)
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0

    assert "2 of 4 comparisons saved" in capsys.readouterr().out


def test_a_run_stopped_a_day_ago_waits_for_resume_or_restart(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    monkeypatch.setattr(cli, "utcnow", Clock(NOW + timedelta(hours=30)))
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 1
    assert "pass --resume to finish it at that moment, or --restart" in (
        capsys.readouterr().err
    )
    assert cli.main(["compare", str(path), "--resume"]) == 0


def test_a_resume_past_time_travel_refuses_before_any_query(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    # The checkpoints are an hour old, but the build began 7 days ago, past
    # time travel less its margin.
    monkeypatch.setattr(cli, "utcnow", Clock(START + timedelta(days=7)))
    folder = _run_folder(tmp_path)
    for f in (folder / checkpoints.DIR).glob("*.json"):
        data = json.loads(f.read_text())
        data["at"] = (START + timedelta(days=7, hours=-1)).isoformat()
        f.write_text(json.dumps(data))
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 1

    assert "pass --restart" in capsys.readouterr().err
    assert not _outer(fakes.bq)


def test_a_run_stopped_over_7_days_ago_cannot_resume(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    monkeypatch.setattr(cli, "utcnow", Clock(NOW + timedelta(days=8)))
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--resume"]) == 1

    assert "more than 7 days ago" in capsys.readouterr().err


def test_a_moment_with_an_unfinished_run_resumes_it_whatever_its_age(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    folder = _run_folder(tmp_path)
    # A newer unfinished run of another moment holds the latest checkpoint.
    other = tmp_path / "cache" / "v" / "2026-10-21T000000Z"
    other_build = report.Build(START - timedelta(days=1), START, "j0")
    checkpoints.start(other, other_build, "p0")
    checkpoints.write(other, "x", "f", {}, NOW + timedelta(hours=2))
    monkeypatch.setattr(cli, "utcnow", Clock(NOW + timedelta(hours=30)))
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--moment", END.isoformat()]) == 0

    assert "Resuming the unfinished run of" in capsys.readouterr().out
    assert len(_outer(fakes.bq)) == 2
    assert (folder / "run.json").exists()


def test_a_run_stopped_before_its_first_checkpoint_keeps_its_spend(fakes, tmp_path):
    path = _four(tmp_path)
    fakes.bq.cost = lambda sql: 0.01
    fakes.bq.fail_once = "ada_region_1"
    assert cli.main(["compare", str(path)]) == 1
    folder = _run_folder(tmp_path)
    first = checkpoints.total_spend(folder)
    assert first > 0

    assert cli.main(["compare", str(path)]) == 0

    state = json.loads((folder / checkpoints.STATE).read_text())
    assert len(state["spent"]) == 2
    run_json = json.loads((folder / "run.json").read_text())
    assert run_json["cost_usd"] == pytest.approx(sum(state["spent"].values()))
    assert run_json["cost_usd"] > first


def test_a_stopped_run_of_another_fact_is_not_resumed(fakes, tmp_path, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    fakes.cube.dataset = "zz_cbaldor_kipptaf_marts"
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert (
        cli.main(["compare", str(path), "--fact-dataset", "zz_cbaldor_kipptaf_marts"])
        == 0
    )

    assert "Resuming" not in capsys.readouterr().out
    assert len(_outer(fakes.bq)) == 4


def test_restart_clears_the_unfinished_run(fakes, tmp_path):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    fakes.bq.ran.clear()

    assert cli.main(["compare", str(path), "--restart", "--all"]) == 0

    # Without the restart, `--all` would resume and keep 1 and 2.
    assert len(_outer(fakes.bq)) == 4


def test_resume_with_nothing_unfinished_refuses(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_four(tmp_path)), "--resume"]) == 1

    assert "no unfinished run of v to resume" in capsys.readouterr().err


def test_resume_and_moment_together_refuse(fakes, tmp_path, capsys):
    assert (
        cli.main(
            ["compare", str(_four(tmp_path)), "--resume", "--moment", END.isoformat()]
        )
        == 1
    )

    assert "drop `--resume`" in capsys.readouterr().err


def test_a_comparison_edited_since_its_checkpoint_is_compared_again(
    fakes, tmp_path, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    # `workbook` is outside the probe's fingerprint, so `compare` does not refuse it.
    path.write_text(path.read_text().replace("workbook: wb-1", "workbook: wb-9", 1))
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    assert (
        "Comparison ada-region-1: its config or SQL changed since its saved result"
        in capsys.readouterr().out
    )
    # ada-region-1 again (edited), then 3 and 4 (never finished); 2 is kept.
    assert len(_outer(fakes.bq)) == 3


# --- each comparison's latest result -----------------------------------------

LATER = (START + timedelta(hours=2), END + timedelta(hours=2))


def _two(tmp_path, c2=lambda entry: entry, text=YML):
    """The view file with its comparison repeated as `c1` and `c2`; `c2` edits
    the second entry's text."""
    head, rest = text.split("  - id: ada-region\n", 1)
    return _file(tmp_path, head + f"  - id: c1\n{rest}" + c2(f"  - id: c2\n{rest}"))


def _no_rebuild_check(entry):
    return entry.replace(REBUILD_CHECK, "    rebuild_check: null\n")


def _reads_membership(entry):
    """The entry's rows read `membership_value`, which `c1` never reads."""
    return entry.replace("cube: attendance_value", "cube: membership_value")


def _second_fact_for_membership(fakes):
    """Cube's SQL joins `fct_g` for a query naming `membership_value` only."""
    compiled = fakes.cube.compiled

    def joined(query):
        named = "v.membership_value" in query.get("dimensions", [])
        fakes.cube.joins = SECOND_FACT_JOIN if named else ""
        return compiled(query)

    fakes.cube.compiled = joined


def _scripts_for(bq):
    """The comparison each reconcile saved rows for, in run order."""
    return [_first(r"__(c\d)_[0-9a-f]{8}`", s) for s in _outer(bq)]


def test_run_comparison_runs_only_that_one_and_keeps_the_others(fakes, tmp_path):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.build = LATER
    fakes.bq.ran.clear()

    assert cli.main(["compare", str(path), "--comparison", "c2"]) == 0

    assert _scripts_for(fakes.bq) == ["c2"]
    # 2 cuts of 2 sides, the reconcile and the student count: c2's alone.
    assert len(_compared(fakes.bq)) == 6
    later = report.run_dir(tmp_path / "cache", "v", report.Build(*LATER, "job-1"))
    saved = json.loads((later / "run.json").read_text())
    assert saved["moments"]["c1"]["end"] == END.isoformat()
    assert saved["moments"]["c2"]["end"] == LATER[1].isoformat()
    assert saved["missing"] == []
    assert set(saved["fingerprints"]) == {"c1", "c2"}
    assert {c["comparison"] for c in saved["diff_cells"]} <= {"c1", "c2"}


def test_the_price_line_says_what_it_leaves_out(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    assert (
        "(dry run), plus the save script's temp-table reads, capped per query."
    ) in capsys.readouterr().out


def test_a_comparison_run_composes_another_cube_cannot_compile_today(
    fakes, tmp_path, capsys
):
    path = _two(
        tmp_path,
        lambda e: e.replace(
            "measure: avg_daily_attendance", "measure: sum_attendance_value"
        ),
    )
    # Every cell differs, so composing compiles each comparison's measure.
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.5}]
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.build = LATER
    compiled = fakes.cube.compiled

    def compile_c1_measure(query):
        if query == {"measures": ["v.avg_daily_attendance"]}:
            raise CubeError("Cube GET /sql: v.avg_daily_attendance not found")
        return compiled(query)

    fakes.cube.compiled = compile_c1_measure
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--comparison", "c2"]) == 0

    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["moments"]["c2"]["end"] == LATER[1].isoformat()
    causes = [d["causes"] for d in saved["applied"]["open_cells"]]
    assert any("a measure Cube cannot compile today" in " ".join(c) for c in causes)


def test_run_json_is_written_whole(fakes, tmp_path, monkeypatch):
    written = []
    write = checkpoints.write_text

    def spy(path, text):
        written.append(path.name)
        write(path, text)

    monkeypatch.setattr(checkpoints, "write_text", spy)

    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    assert "run.json" in written


def test_a_command_reads_past_an_unreadable_run_json(fakes, tmp_path):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    good = _latest_run(tmp_path)
    # A newer run.json cut short mid-write.
    torn = good.parent.parent / "2026-10-23T000000Z" / "run.json"
    torn.parent.mkdir()
    torn.write_text('{"view": "v", "fac')
    os.utime(torn, (good.stat().st_mtime + 60,) * 2)
    cfg = load_view_config(path)

    data, found = results._saved_run(cfg, tmp_path / "cache")

    assert found == good and data["view"] == "v"


def test_last_run_reads_past_a_run_json_that_is_no_object(fakes, tmp_path):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    good = _latest_run(tmp_path)
    # A newer run.json that parses, but not to an object.
    odd = good.parent.parent / "2026-10-23T000000Z" / "run.json"
    odd.parent.mkdir()
    odd.write_text("[1]")
    os.utime(odd, (good.stat().st_mtime + 60,) * 2)

    data = results.last_run(load_view_config(path), tmp_path / "cache")

    assert data == json.loads(good.read_text())


def test_run_jsons_written_at_once_resolve_to_the_later_folder(fakes, tmp_path):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    good = _latest_run(tmp_path)
    data = json.loads(good.read_text())
    at = good.stat().st_mtime
    # Folders named before and after the run's, all written in the same instant.
    for name in ("0000-01-01T000000Z", "later-b", "9999-12-31T000000Z", "later-z"):
        copy_ = good.parent.parent / name / "run.json"
        copy_.parent.mkdir()
        copy_.write_text(json.dumps({**data, "folder": name}))
        os.utime(copy_, (at, at))
    os.utime(good, (at, at))
    cfg = load_view_config(path)

    saved, found = results._saved_run(cfg, tmp_path / "cache")

    assert found.parent.name == "later-z" and saved["folder"] == "later-z"
    assert results.last_run(cfg, tmp_path / "cache")["folder"] == "later-z"


def test_a_run_json_with_no_fact_is_older_than_any_fact_s_run(fakes, tmp_path):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    good = _latest_run(tmp_path)
    # A newer run.json saved before runs recorded their fact.
    legacy = good.parent.parent / "2026-10-23T000000Z" / "run.json"
    legacy.parent.mkdir()
    legacy.write_text(json.dumps({"view": "v", "legacy": True}))
    os.utime(legacy, (good.stat().st_mtime + 60,) * 2)
    cfg = load_view_config(path)

    data, found = results._saved_run(cfg, tmp_path / "cache")
    assert found == good and "legacy" not in data
    assert "legacy" not in results.last_run(cfg, tmp_path / "cache")

    # With no run of any fact, the legacy run is refused as an older one.
    good.unlink()
    with pytest.raises(pipeline.Refusal, match="older validator"):
        results._saved_run(cfg, tmp_path / "cache")


def test_a_comparison_without_a_proof_is_skipped_and_the_rest_run(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_two(tmp_path, _no_rebuild_check))]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: no rebuild check; run `rebuild-sheet` first." in out
    assert out.index("Skipping c2") < out.index("(dry run)")
    assert "c2: totals not matched" not in out
    assert _scripts_for(fakes.bq) == ["c1"]
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["skipped"] == [
        {"comparison": "c2", "why": "no rebuild check; run `rebuild-sheet` first"}
    ]
    assert saved["missing"] == ["c2"]


def test_a_missing_cube_member_skips_only_its_comparison(fakes, tmp_path, capsys):
    fakes.cube.dropped = {"v.membership_value"}

    assert cli.main(["compare", str(_two(tmp_path, _reads_membership))]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: Cube's model has no member for v.membership_value" in out
    assert out.index("Skipping c2") < out.index("(dry run)")
    assert _scripts_for(fakes.bq) == ["c1"]
    assert "membership_value" not in json.dumps(fakes.cube.compiled_queries)


def test_a_changed_workbook_skips_only_its_comparisons(fakes, tmp_path, capsys):
    path = _two(tmp_path, lambda e: e.replace("workbook: wb-1", "workbook: wb-2"))
    proven = fakes.tbl.updated
    published = datetime(2026, 10, 30, tzinfo=timezone.utc)  # after the proof
    fakes.tbl.workbook_updated = lambda luid: published if luid == "wb-2" else proven

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: workbook changed since its rebuild check: c2: workbook published "
        "2026-10-30T00:00:00+00:00"
    ) not in out
    assert (
        "Skipping c2: workbook changed since its rebuild check: workbook published "
        "2026-10-30T00:00:00+00:00"
    ) in out
    assert "the sheet's formulas or filters changed; re-run `rebuild-sheet`." in out
    assert out.index("Skipping c2") < out.index("(dry run)")
    assert _scripts_for(fakes.bq) == ["c1"]


def test_compare_skips_a_sheet_on_no_published_dashboard(fakes, tmp_path, capsys):
    _hide_rate_by_region(fakes.tbl)
    # c2's sheet is a view of its own.
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "  </windows>",
        "    <window class='worksheet' name='Rate Copy' />\n  </windows>",
    )
    fakes.tbl.views = {"Rate Copy"}
    path = _two(
        tmp_path, lambda e: e.replace("sheet: Rate by Region", "sheet: Rate Copy")
    )

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c1: not on a published dashboard; set unpublished: true to "
        "compare it anyway"
    ) in out
    assert "Skipping c2" not in out
    assert _scripts_for(fakes.bq) == ["c2"]


def test_compare_downloads_a_republished_workbook_once(fakes, tmp_path, capsys):
    path = _republished(fakes, tmp_path)
    head, rest = path.read_text().split("  - id: ada-region\n", 1)
    path.write_text(head + f"  - id: c1\n{rest}" + f"  - id: c2\n{rest}")

    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err

    # Both checks read the one republished file.
    assert fakes.tbl.downloads == 1
    assert _scripts_for(fakes.bq) == ["c1", "c2"]


def test_compare_asks_tableau_once_for_a_workbook_that_errs(
    fakes, tmp_path, monkeypatch, capsys
):
    asked = []

    def answer(luid):
        asked.append(luid)
        raise TSC.ServerResponseError("404", "Resource Not Found", "gone")

    monkeypatch.setattr(fakes.tbl, "workbook_updated", answer)

    assert cli.main(["compare", str(_two(tmp_path))]) == 1

    out = capsys.readouterr().out
    for cid in ("c1", "c2"):
        assert (
            f"Skipping {cid}: the workbook could not be checked: Tableau answered "
            "404 Resource Not Found"
        ) in out
    assert asked == ["wb-1"]


def test_compare_downloads_once_for_a_workbook_whose_download_errs(
    fakes, tmp_path, monkeypatch, capsys
):
    # Republished, so each comparison's check downloads its workbook.
    path = _republished(fakes, tmp_path)
    head, rest = path.read_text().split("  - id: ada-region\n", 1)
    other = rest.replace("workbook: wb-1", "workbook: wb-2")
    path.write_text(
        head + f"  - id: c1\n{rest}" + f"  - id: c2\n{other}" + f"  - id: c3\n{other}"
    )
    asked = []
    download = fakes.tbl.download_twb

    def fetch(luid):
        asked.append(luid)
        if luid == "wb-2":
            raise TSC.ServerResponseError("404", "Resource Not Found", "gone")
        return download(luid)

    monkeypatch.setattr(fakes.tbl, "download_twb", fetch)

    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    for cid in ("c2", "c3"):
        assert (
            f"Skipping {cid}: the workbook could not be checked: Tableau answered "
            "404 Resource Not Found"
        ) in out
    assert asked.count("wb-2") == 1
    # The healthy workbook's comparison still compares.
    assert "Skipping c1" not in out
    assert _scripts_for(fakes.bq) == ["c1"]


def test_unpublished_sheets_leaves_a_comparison_with_no_sheet_alone(fakes, tmp_path):
    path = _file(tmp_path, YML.replace("    sheet: Rate by Region\n", ""))
    (c,) = load_view_config(path).comparisons
    assert c.sheet is None and c.rebuild_check is not None

    assert rebuild.unpublished_sheets([c], tbl=fakes.tbl) == {}


def test_compare_downloads_no_workbook_for_a_sheet_that_is_a_view(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_two(tmp_path))]) == 0

    assert not getattr(fakes.tbl, "downloads", 0)
    # Asked once for the workbook both comparisons read.
    assert fakes.tbl.view_asks == ["wb-1"]
    assert _scripts_for(fakes.bq) == ["c1", "c2"]


def _on_dashboard(tbl, dashboard="Standards"):
    """Put the fixture sheet in a zone of a dashboard whose window shows."""
    tbl.twb = tbl.twb.replace(
        "  </worksheets>\n",
        f"  </worksheets>\n  <dashboards><dashboard name='{dashboard}'><zones>"
        "<zone id='1' name='Rate by Region' /></zones></dashboard></dashboards>\n",
    ).replace(
        "  </windows>",
        f"    <window class='dashboard' name='{dashboard}' />\n  </windows>",
    )
    assert "<dashboards>" in tbl.twb


def test_compare_reads_published_from_the_server_views_not_the_check(
    fakes, tmp_path, capsys
):
    # The sheet's window and its dashboard's both show in the .twb, and the
    # check recorded it published, but neither is a view on the server.
    _on_dashboard(fakes.tbl)
    fakes.tbl.views = {"Other"}
    proof = REBUILD_CHECK + "      published: true\n"
    path = _two(tmp_path, text=YML.replace(REBUILD_CHECK, proof))

    assert cli.main(["compare", str(path)]) == 1

    out = capsys.readouterr().out
    for cid in ("c1", "c2"):
        assert (
            f"Skipping {cid}: not on a published dashboard; set unpublished: true "
            "to compare it anyway"
        ) in out
    assert fakes.tbl.downloads == 1
    assert _scripts_for(fakes.bq) == []

    # A zone on a dashboard that is a view publishes.
    fakes.tbl.views = {"Standards"}
    assert cli.main(["compare", str(path)]) == 0
    assert "not on a published dashboard" not in capsys.readouterr().out
    assert _scripts_for(fakes.bq) == ["c1", "c2"]


def test_compare_skips_a_workbook_whose_views_tableau_errs_on(
    fakes, tmp_path, monkeypatch, capsys
):
    asked = []

    def answer(luid):
        asked.append(luid)
        raise TSC.ServerResponseError("404", "Resource Not Found", "gone")

    monkeypatch.setattr(fakes.tbl, "view_names", answer)

    assert cli.main(["compare", str(_two(tmp_path))]) == 1

    out = capsys.readouterr().out
    for cid in ("c1", "c2"):
        assert (
            f"Skipping {cid}: the workbook could not be checked: Tableau answered "
            "404 Resource Not Found"
        ) in out
    assert asked == ["wb-1"]


def test_compare_runs_an_opted_in_unpublished_sheet(fakes, tmp_path, capsys):
    _hide_rate_by_region(fakes.tbl)
    text = YML.replace(
        "    sheet_field: Rate\n", "    sheet_field: Rate\n    unpublished: true\n"
    )

    assert cli.main(["compare", str(_two(tmp_path, text=text))]) == 0

    assert "not on a published dashboard" not in capsys.readouterr().out
    assert _scripts_for(fakes.bq) == ["c1", "c2"]


def test_a_changed_second_fact_skips_only_the_comparisons_that_read_it(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path, _reads_membership, text=ALSO_FACTS_YML)
    _second_fact_for_membership(fakes)
    assert cli.main(["compare", str(path)]) == 0
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    before = latest._file(results, "c2").read_text()
    fakes.bq.changed = ("fct_g",)
    fakes.bq.build = LATER
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: kipptaf_marts.fct_g changed during the build of "
        "kipptaf_marts.fct_f"
    ) in out
    # Its scans are priced first; its own priced queries are simply not run.
    assert out.index("(dry run)") < out.index("Skipping c2")
    assert _scripts_for(fakes.bq) == ["c1"]
    assert len(_compared(fakes.bq)) == 6
    assert latest._file(results, "c2").read_text() == before


def test_a_failed_table_scan_skips_only_the_comparisons_that_read_it(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path, _reads_membership, text=ALSO_FACTS_YML)
    _second_fact_for_membership(fakes)
    assert cli.main(["compare", str(path)]) == 0
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    before = latest._file(results, "c2").read_text()
    fakes.bq.build = LATER
    fakes.bq.ran.clear()
    capsys.readouterr()
    # The scan itself fails, after its dry run priced it.
    _bigquery_refuses(fakes, "`fct_g` AS t", dry=False)

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: a scan of kipptaf_marts.fct_g failed in BigQuery "
        "(job ?, invalidQuery); compare it again later."
    ) in out
    assert "12345" not in out
    assert _scripts_for(fakes.bq) == ["c1"]
    assert latest._file(results, "c2").read_text() == before
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert [s["comparison"] for s in saved["skipped"]] == ["c2"]


@pytest.mark.parametrize("dry", [True, False])
def test_a_comparison_reading_2_failed_scans_is_skipped_once(
    fakes, tmp_path, capsys, dry
):
    path = _two(tmp_path, _reads_membership, text=ALSO_FACTS_YML)
    _second_fact_for_membership(fakes)
    # c2 reads both tables; c1 reads only dim_locations.
    _bigquery_refuses(fakes, "`fct_g` AS t", dry=dry)
    _bigquery_refuses(fakes, "`dim_locations` AS t", dry=dry)

    cli.main(["compare", str(path)])

    out = capsys.readouterr().out
    assert out.count("Skipping c2: ") == 1 and out.count("Skipping c1: ") == 1


def test_a_plain_run_with_only_a_skipped_comparison_left_compares_nothing(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path, _no_rebuild_check)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: no rebuild check; run `rebuild-sheet` first." in out
    assert (
        "Every comparison not skipped has a current latest result; pass --all to "
        "compare every one again."
    ) in out
    assert "Composing run.json again" not in out
    assert not _compared(fakes.bq)


def test_a_comparison_missing_a_key_it_needs_is_skipped(fakes, tmp_path, capsys):
    path = _two(tmp_path, lambda e: e.replace("    decimals: 3\n", ""))

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: it has no decimals." in out
    assert out.index("Skipping c2") < out.index("(dry run)")
    assert _scripts_for(fakes.bq) == ["c1"]


def test_run_refuses_when_every_comparison_is_skipped(fakes, tmp_path, capsys):
    path = _two(tmp_path, text=YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))

    assert cli.main(["compare", str(path)]) == 1

    captured = capsys.readouterr()
    assert "Skipping c1: no rebuild check" in captured.out
    assert "Skipping c2: no rebuild check" in captured.out
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    assert fakes.bq.ran == [] and fakes.cube.compiled_queries == []


def _drop_rebuild_check(path, comparison):
    """Clear one comparison's proof in a written validation file."""
    head, entry = path.read_text().split(f"  - id: {comparison}\n", 1)
    entry = re.sub(
        r"    rebuild_check:\n(?:      .*\n)+",
        "    rebuild_check: null\n",
        entry,
        count=1,
    )
    path.write_text(f"{head}  - id: {comparison}\n{entry}")


def test_a_skipped_comparison_keeps_its_previous_result(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    before = latest._file(results, "c2").read_text()
    _drop_rebuild_check(path, "c2")
    fakes.bq.build = LATER
    fakes.bq.ran.clear()

    assert cli.main(["compare", str(path), "--all"]) == 0

    assert _scripts_for(fakes.bq) == ["c1"]
    assert latest._file(results, "c2").read_text() == before
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["moments"]["c1"]["end"] == LATER[1].isoformat()
    assert saved["moments"]["c2"]["end"] == END.isoformat()
    assert saved["skipped"] == [
        {"comparison": "c2", "why": "no rebuild check; run `rebuild-sheet` first"}
    ]
    assert "Skipped this run, each keeping its latest result: c2 (no rebuild check" in (
        capsys.readouterr().out
    )


def test_a_comparison_whose_sql_cannot_be_built_is_skipped_before_any_spend(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    # c2's Cube SQL now reads a second fact the file does not list.
    _second_fact_for_membership(fakes)
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: its SQL cannot be built today: " in out
    assert "Comparison c2:" not in out
    assert not _compared(fakes.bq)

    fakes.bq.build = LATER
    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: its SQL cannot be built today: " in out
    assert out.index("Skipping c2") < out.index("(dry run)")
    assert _scripts_for(fakes.bq) == ["c1"]


def test_a_never_compared_comparison_whose_sql_cannot_be_built_is_skipped(
    fakes, tmp_path, capsys
):
    _second_fact_for_membership(fakes)

    assert cli.main(["compare", str(_two(tmp_path, _reads_membership))]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: its SQL cannot be built today: " in out
    assert "fct_g" in out and "also_facts" in out
    assert _scripts_for(fakes.bq) == ["c1"]


def _bigquery_refuses(fakes, marker, *, dry):
    """BigQuery refuses every dry run (`dry`) or run of a query holding
    `marker`, with a message that quotes a value."""
    query = fakes.bq.query

    def refusing(sql, job_config=None):
        is_dry = bool(job_config is not None and job_config.dry_run)
        if marker in sql and is_dry == dry:
            raise BadRequest(
                "No matching signature for value 'Student 12345'",
                errors=[{"reason": "invalidQuery"}],
            )
        return query(sql, job_config)

    fakes.bq.query = refusing


def test_a_failed_dry_run_skips_only_its_comparison(fakes, tmp_path, capsys):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    before = latest._file(results, "c2").read_text()
    fakes.bq.build = LATER
    fakes.bq.ran.clear()
    capsys.readouterr()
    # Only c2's rows read membership_value as a column.
    _bigquery_refuses(fakes, "`v__membership_value`", dry=True)

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: its dry run failed in BigQuery (job ?, invalidQuery); "
        "compare it again later."
    ) in out
    assert "12345" not in out
    assert _scripts_for(fakes.bq) == ["c1"]
    assert latest._file(results, "c2").read_text() == before
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert [s["comparison"] for s in saved["skipped"]] == ["c2"]


def _says_nothing_of_c2(out, tmp_path):
    """No uncoverable-cells line for skipped `c2`, but its totals line stays,
    printed and in run.json: the latest result it keeps has the same gap."""
    assert "Comparison c2: its cells cannot be covered" not in out
    assert "c2: totals not matched: unknown" in out
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert [t for t in saved["totals"] if t.startswith("c2:")] != []
    assert [t for t in saved["totals"] if t.startswith("c1:")] != []


def test_a_skipped_comparison_keeps_its_totals_line_but_no_uncoverable_cells_line(
    fakes, tmp_path, monkeypatch, capsys
):
    # Every comparison's cells read uncoverable, and neither rebuild check
    # records a totals count.
    monkeypatch.setattr(coverage, "unplaceable", lambda c: "a reason")
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    assert "Comparison c1: its cells cannot be covered" in capsys.readouterr().out
    capsys.readouterr()

    # Skipped before the price: its SQL cannot be built today.
    _second_fact_for_membership(fakes)
    fakes.bq.build = LATER
    assert cli.main(["compare", str(path), "--all"]) == 0
    out = capsys.readouterr().out
    assert "Skipping c2: its SQL cannot be built today: " in out
    _says_nothing_of_c2(out, tmp_path)


def test_a_comparison_skipped_after_the_price_keeps_its_totals_line(
    fakes, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(coverage, "unplaceable", lambda c: "a reason")
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.build = LATER
    capsys.readouterr()
    _bigquery_refuses(fakes, "`v__membership_value`", dry=True)

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: its dry run failed in BigQuery" in out
    _says_nothing_of_c2(out, tmp_path)


def test_sql_that_cannot_be_built_at_the_run_s_moment_skips_its_comparison(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path)
    plan_one = compare._plan_one

    def plan(cfg, comparison, *, build, **kwargs):
        if comparison.id == "c2":
            raise pipeline.ViewHistoryError("no CREATE_VIEW job for d.v before then")
        return plan_one(cfg, comparison, build=build, **kwargs)

    monkeypatch.setattr(compare, "_plan_one", plan)

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: its SQL cannot be built today: no CREATE_VIEW job for d.v "
        "before then."
    ) in out
    assert _scripts_for(fakes.bq) == ["c1"]


LOOKUP_FAILED = (
    "Skipping c2: its SQL cannot be built today: a lookup failed in BigQuery "
    "(job ?, notFound)."
)


def _lookup_fails(comparison):
    if comparison.id == "c2":
        raise BadRequest(
            "Not found: value 'Student 12345'", errors=[{"reason": "notFound"}]
        )


def test_a_bigquery_error_building_sql_skips_its_comparison_before_the_price(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fingerprints = pipeline.side_fingerprints

    def failing(cfg, comparison, **kwargs):
        _lookup_fails(comparison)
        return fingerprints(cfg, comparison, **kwargs)

    monkeypatch.setattr(results, "side_fingerprints", failing)
    monkeypatch.setattr(compare, "side_fingerprints", failing)
    capsys.readouterr()

    # A plain compare checks the held result's SQL (`stale_comparisons`);
    # `--all` builds every comparison's (`_sql_skips`).
    for args in ([], ["--all"]):
        fakes.bq.build = LATER
        assert cli.main(["compare", str(path), *args]) == 0
        out = capsys.readouterr().out
        assert LOOKUP_FAILED in out
        assert "12345" not in out


def test_a_bigquery_error_building_sql_at_the_run_s_moment_skips_it(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path)
    plan_one = compare._plan_one

    def plan(cfg, comparison, *, build, **kwargs):
        _lookup_fails(comparison)
        return plan_one(cfg, comparison, build=build, **kwargs)

    monkeypatch.setattr(compare, "_plan_one", plan)

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert LOOKUP_FAILED in out and "12345" not in out
    assert _scripts_for(fakes.bq) == ["c1"]


def test_a_held_checkpoint_whose_sql_cannot_be_built_skips_its_comparison(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    fakes.bq.ran.clear()
    capsys.readouterr()
    fingerprints = pipeline.side_fingerprints

    def broken(cfg, comparison, *, build, **kwargs):
        # Only at the run's moment: the check at today's builds it fine.
        if comparison.id == "ada-region-1" and build.job_id != "now":
            raise pipeline.ViewHistoryError("no CREATE_VIEW job for d.v before then")
        return fingerprints(cfg, comparison, build=build, **kwargs)

    monkeypatch.setattr(results, "side_fingerprints", broken)
    monkeypatch.setattr(compare, "side_fingerprints", broken)

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "Skipping ada-region-1: its SQL cannot be built today: " in out
    assert [_first(r"__(ada_region_\d)_", s) for s in _outer(fakes.bq)] == [
        "ada_region_3",
        "ada_region_4",
    ]


def test_a_tableau_error_on_one_workbook_skips_only_its_comparison(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path, lambda e: e.replace("workbook: wb-1", "workbook: wb-2"))
    updated = fakes.tbl.workbook_updated

    def answer(luid):
        if luid == "wb-2":
            raise TSC.ServerResponseError("404", "Resource Not Found", "gone")
        return updated(luid)

    monkeypatch.setattr(fakes.tbl, "workbook_updated", answer)

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: the workbook could not be checked: Tableau answered 404 "
        "Resource Not Found"
    ) in out
    assert _scripts_for(fakes.bq) == ["c1"]


def test_a_bigquery_error_while_comparing_skips_it_and_keeps_its_spend(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    before = latest._file(results, "c2").read_text()
    fakes.bq.build = LATER
    fakes.bq.cost = lambda sql: 0.01
    fakes.bq.ran.clear()
    capsys.readouterr()
    # c2's reconcile, which saves its rows to a table named for it.
    _bigquery_refuses(fakes, "__c2_", dry=False)

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert (
        "Skipping c2: a query failed in BigQuery (job ?, invalidQuery); compare it "
        "again later."
    ) in out
    assert "12345" not in out
    assert _scripts_for(fakes.bq) == ["c1"]
    assert latest._file(results, "c2").read_text() == before
    folder = report.run_dir(tmp_path / "cache", "v", report.Build(*LATER, "job-1"))
    saved = json.loads((folder / "run.json").read_text())
    assert [s["comparison"] for s in saved["skipped"]] == ["c2"]
    # c1's 6 queries and c2's 4 cell queries ran before c2's reconcile failed;
    # every query that ran is in the run's spend.
    assert len(_compared(fakes.bq)) == 10
    assert saved["cost_usd"] == pytest.approx(0.01 * len(fakes.bq.ran), rel=1e-3)


def test_two_rows_on_one_cell_skip_only_their_comparison(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    answer = fakes.bq.answer

    def doubled(sql):
        # c2's dashboard cells, after c1's reconcile: one region twice.
        c1_done = any("-- outer" in q and "__c1_" in q for q in fakes.bq.ran)
        if c1_done and "AS value" in sql and "rpt_d" in sql:
            return [
                {"region": "Newark", "value": 0.9},
                {"region": "Newark", "value": 0.5},
            ]
        return answer(sql)

    fakes.bq.answer = doubled

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: " in out and "2 rows share the cell" in out
    # The terminal names the cell; the skip, which ask-owner posts, does not.
    assert "c2 {} dashboard: 2 rows share the cell Newark;" in out
    assert "Skipping c2: {} dashboard: 2 rows share the cell;" in out
    assert "c2: c2" not in out
    saved = json.loads(_latest_run(tmp_path).read_text())
    (skip,) = saved["skipped"]
    assert skip["comparison"] == "c2"
    assert "2 rows share the cell" in skip["why"] and "Newark" not in skip["why"]
    assert _scripts_for(fakes.bq) == ["c1"]
    results = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    assert latest._file(results, "c1").exists()
    assert not latest._file(results, "c2").exists()


def test_sort_and_review_go_on_past_a_comparison_skipped_for_a_missing_member(
    fakes, tmp_path, capsys
):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.dropped = {"v.membership_value"}
    fakes.bq.ran.clear()
    capsys.readouterr()

    # Nothing else to compare, but the skip is recorded for `ask-owner`.
    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: Cube's model has no member for v.membership_value" in out
    assert "Composing run.json again to record the comparisons skipped" in out
    assert not _compared(fakes.bq)
    why = (
        "Cube's model has no member for v.membership_value; fix the mapping, then run "
        "`rebuild-sheet` again"
    )
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["skipped"] == [{"comparison": "c2", "why": why}]

    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0
    assert f"v: comparison c2 not compared: {why}" in capsys.readouterr().out
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    section = capsys.readouterr().out.split("## Still with the analyst", 1)[1]
    assert (
        "- `c2` in `v`: not compared: Cube's model has no member for "
        "v.membership_value; fix the mapping, then run rebuild-sheet again\n"
    ) in section

    # Recorded once: the next plain run compares and writes nothing.
    assert cli.main(["compare", str(path)]) == 0
    assert "Every comparison not skipped has a current latest result" in (
        capsys.readouterr().out
    )


def _view_history_breaks_c2(monkeypatch, message):
    """c2's SQL cannot be built: each build raises `message(n)`, n counting
    the calls from 1."""
    fingerprints = pipeline.side_fingerprints
    calls = []

    def broken(cfg, comparison, **kwargs):
        if comparison.id == "c2":
            calls.append(1)
            raise pipeline.ViewHistoryError(message(len(calls)))
        return fingerprints(cfg, comparison, **kwargs)

    monkeypatch.setattr(results, "side_fingerprints", broken)
    monkeypatch.setattr(compare, "side_fingerprints", broken)


def test_a_skip_whose_job_or_time_varies_is_recorded_once(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    # The moment the lookup reads, and a job id, differ on every call.
    _view_history_breaks_c2(
        monkeypatch,
        lambda n: (
            f"no CREATE_VIEW job for d.v before "
            f"{utc_literal(START + timedelta(minutes=n))} (job j-{n})"
        ),
    )
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0
    assert "Composing run.json again to record the comparisons skipped" in (
        capsys.readouterr().out
    )

    # Skipped again for the same reason: nothing to write.
    assert cli.main(["compare", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Skipping c2: its SQL cannot be built today: " in out
    assert "Composing run.json again" not in out
    assert "Every comparison not skipped has a current latest result" in out


def test_a_skip_whose_reason_changes_is_recorded_again(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    # The same head, its SQL cannot be built today, for another view.
    _view_history_breaks_c2(
        monkeypatch, lambda n: f"no CREATE_VIEW job for d.v{n} before then"
    )
    capsys.readouterr()
    assert cli.main(["compare", str(path)]) == 0
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    assert "Composing run.json again to record the comparisons skipped" in (
        capsys.readouterr().out
    )
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["skipped"][0]["why"].endswith("d.v2 before then")


def test_triage_names_a_member_cube_dropped_since_the_run(fakes, tmp_path):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.dropped = {"v.membership_value"}

    stale = _sorted_stale(path, tmp_path)

    assert stale["c2"].startswith("its SQL cannot be built today: ")
    assert "v.membership_value" in stale["c2"] and "c1" not in stale


def test_sort_with_the_trace_waits_for_a_comparison_whose_member_cube_dropped(
    fakes, tmp_path, capsys
):
    # Cube dropped c2's member after the compare, which did not skip it. c1's
    # rows all match, so only c2 has row groups for the trace.
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.reconcile = [RECONCILE_ROWS[0]]
    fakes.bq.build = LATER
    assert cli.main(["compare", str(path), "--comparison", "c1"]) == 0
    fakes.cube.dropped = {"v.membership_value"}
    capsys.readouterr()

    code = cli.main(
        ["sort", str(path), "--no-explanations", "--manifest", str(tmp_path / "m")]
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "v: comparison c2 its SQL cannot be built today" in captured.out


def test_sort_with_the_trace_waits_for_a_comparison_whose_cube_sql_changed(
    fakes, tmp_path, capsys
):
    fakes.bq.views = {"rpt_d": VIEW_D}
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.exprs = {"regions_region_name": "UPPER(`t`.regions_region_name)"}
    capsys.readouterr()

    code = cli.main(
        ["sort", str(path), "--no-explanations", "--manifest", str(tmp_path / "m")]
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "v: comparison c1 Cube's SQL changed" in captured.out


def test_triage_neither_checks_nor_traces_a_skipped_comparison_s_groups(
    fakes, tmp_path, monkeypatch
):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.dropped = {"v.membership_value"}
    assert cli.main(["compare", str(path)]) == 0  # records c2's skip
    run = results._run_from_json(json.loads(_latest_run(tmp_path).read_text()))
    seen = {}

    def ready(*args, skip=frozenset(), **kwargs):
        seen["ready"] = set(skip)

    def traced(cfg, run_, *, skip, **kwargs):
        seen["trace"] = set(skip)
        return trace.TraceResult({})

    monkeypatch.setattr(trace, "check_ready", ready)
    monkeypatch.setattr(trace, "trace_run", traced)

    assert cli.main(["sort", str(path), "--no-explanations"]) == 0

    keys = {
        cid: {trace.item_key(g) for g in run.applied.open if g.comparison_id == cid}
        for cid in ("c1", "c2")
    }
    assert keys["c1"] and keys["c2"]
    assert seen["ready"] == seen["trace"] == keys["c2"]


def test_triage_gives_the_proofs_and_the_trace_one_ticker(fakes, tmp_path, monkeypatch):
    path = _two(tmp_path, _reads_membership)
    assert cli.main(["compare", str(path)]) == 0
    seen = []

    def stored(*args, ticker=None, **kwargs):
        seen.append(ticker)
        return []

    def traced(*args, ticker=None, **kwargs):
        seen.append(ticker)
        return trace.TraceResult({})

    monkeypatch.setattr(trace, "check_ready", lambda *a, **k: None)
    monkeypatch.setattr(explain, "run_stored", stored)
    monkeypatch.setattr(trace, "trace_run", traced)

    assert cli.main(["sort", str(path)]) == 0

    assert len(seen) == 2 and seen[0] is seen[1]
    assert isinstance(seen[0], report.Ticker)


def test_review_posts_the_masked_lead_of_an_item_with_the_analyst(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    lead = "lead: relaxing main: region = 'Miami' brings back {} of 30 rows"
    item = {
        **_sorted_item(lead.format(3), "investigate", "j"),
        "evidence_posted": [lead.format("<10")],
    }
    _write_sorted_everywhere(tmp_path, [_sorted_item("e"), item])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    body = capsys.readouterr().out
    section = body.split("## Still with the analyst", 1)[1].split("## Proposed")[0]
    assert "- `ada-region` in `v` (group): 1 listed item\n" in section
    # The items one by one go to a file beside the review JSON, linked.
    detail = tmp_path / "reviews" / "v-still-with-analyst.md"
    assert f"[{detail.name}](https://github.com/o/r/blob/abc/{detail.name})" in (
        section
    )
    text = detail.read_text()
    # An item with no exact count posted keeps its lead's scope, not its counts.
    assert "- `j`; lead: relaxing a step in main\n" in text
    assert "of 30" not in body + text and "region = " not in text


def test_ask_owner_lists_formulas_not_compared_and_record_answers_ignores_them(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    for run_json in (tmp_path / "cache" / "v").glob("*/run.json"):
        _write_sorted(run_json, [_sorted_item("e")])
        triage = run_json.parent / "triage.json"
        loaded = json.loads(triage.read_text())
        loaded["formulas_not_compared"] = {"ada-region": {"no rows both sides hold": 3}}
        triage.write_text(json.dumps(loaded))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    body = capsys.readouterr().out
    section = body.split("## Still with the analyst", 1)[1]
    assert (
        "- `ada-region` in `v`: formulas not compared: no rows both sides hold; "
        "<10 cells closed by coverage only\n" in section
    )
    assert "3 cells" not in body
    assert "formulas not compared" not in body.split("## Still with the analyst")[0]
    owner = _owner_file(tmp_path)
    comment = _comment(tmp_path, [_answer(["miami-scope"], "fix_cube", "ok")])
    assert _record([owner], comment) == 0


def _predating_the_formula_check(tmp_path):
    """Compare, then write a triage as a `sort` before the formula check did:
    no `formulas_not_compared` at all."""
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e"), _gap_sorted_item()])
    triage = run_json.parent / "triage.json"
    loaded = json.loads(triage.read_text())
    del loaded["formulas_not_compared"]
    triage.write_text(json.dumps(loaded))
    return path


@pytest.mark.parametrize("held", [None, 0])
def test_ask_owner_and_decide_refuse_a_triage_of_older_posted_masking(
    fakes, tmp_path, capsys, held
):
    # Its posted evidence was masked by an older rule, and ask-owner posts it
    # as stored.
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e"), _gap_sorted_item()])
    triage = run_json.parent / "triage.json"
    loaded = json.loads(triage.read_text())
    if held is None:
        del loaded["posted_version"]
    else:
        loaded["posted_version"] = held
    triage.write_text(json.dumps(loaded))
    approved = _approved(
        tmp_path,
        [{"id": "no-team", "call": "deliberate", "reason": "A label only.",
          "task": "", "item": "cut:Team"}],
    )  # fmt: skip
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1
    assert "posted evidence was masked by an older rule; run `sort`" in (
        capsys.readouterr().err
    )
    assert cli.main(["decide", str(path), str(approved)]) == 1
    assert "posted evidence was masked by an older rule" in capsys.readouterr().err
    assert load_view_config(path).decisions == []

    # A fresh sort writes the version, and the review goes ahead.
    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0
    assert json.loads(triage.read_text())["posted_version"] == sort.POSTED_VERSION
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0


def test_ask_owner_refuses_a_triage_that_predates_the_formula_check(
    fakes, tmp_path, capsys
):
    # Its cells closed by coverage alone, with nothing to say so.
    path = _predating_the_formula_check(tmp_path)
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert "v: the triage predates the formula check; run `sort` for" in err


def test_decide_refuses_a_triage_that_predates_the_formula_check(
    fakes, tmp_path, capsys
):
    path = _predating_the_formula_check(tmp_path)
    approved = _approved(
        tmp_path,
        [{"id": "no-team", "call": "deliberate", "reason": "A label only.",
          "task": "", "item": "cut:Team"}],
    )  # fmt: skip
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 1

    assert "the triage predates the formula check" in capsys.readouterr().err
    assert load_view_config(path).decisions == []


def test_triage_and_review_name_a_skipped_comparison(fakes, tmp_path, capsys):
    path = _two(tmp_path, _no_rebuild_check)
    assert cli.main(["compare", str(path)]) == 0
    capsys.readouterr()

    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0

    out = capsys.readouterr().out
    assert (
        "v: comparison c2 not compared: no rebuild check; run `rebuild-sheet` first"
        in out
    )
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    body = capsys.readouterr().out
    section = body.split("## Still with the analyst", 1)[1]
    assert (
        "- `c2` in `v`: not compared: no rebuild check; run rebuild-sheet first\n"
        in section
    )


def test_run_refuses_a_comparison_it_does_not_hold(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_two(tmp_path)), "--comparison", "nope"]) == 1

    assert "--comparison: nope is no confirmed comparison of v" in (
        capsys.readouterr().err
    )
    assert fakes.bq.ran == []


def test_a_plain_run_runs_only_stale_and_never_run_comparisons(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path), "--comparison", "c1"]) == 0
    first = json.loads(next((tmp_path / "cache").glob("v/*/run.json")).read_text())
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert first["missing"] == ["c2"]
    assert "Comparison c2: never compared." in out
    assert "Comparison c1:" not in out
    assert out.index("Comparison c2: never compared.") < out.index("(dry run)")
    assert _scripts_for(fakes.bq) == ["c2"]


def test_run_all_runs_every_comparison(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.ran.clear()

    assert cli.main(["compare", str(path), "--all"]) == 0

    assert _scripts_for(fakes.bq) == ["c1", "c2"]
    assert cli.main(["compare", str(path), "--all", "--comparison", "c1"]) == 2


def test_a_new_build_alone_is_not_stale(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.build = LATER
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert (
        "Every comparison's latest result is current; pass --all to compare every "
        "one again." in out
    )
    assert not _outer(fakes.bq)
    assert len(list((tmp_path / "cache").glob("v/*/run.json"))) == 1


def test_a_changed_view_definition_is_stale(fakes, tmp_path, capsys):
    fakes.bq.views = {"rpt_d": "select * from `teamster-332318`.`kipptaf_int`.`int_d`"}
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.views = {"rpt_d": "select * from `teamster-332318`.`kipptaf_int`.`int_e`"}
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Comparison c1: the dashboard SQL changed." in out
    assert "Comparison c2: the dashboard SQL changed." in out
    assert _scripts_for(fakes.bq) == ["c1", "c2"]


def test_an_edited_entry_is_stale(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    # `workbook` is outside the probe's fingerprint, so `compare` does not refuse it.
    path.write_text(path.read_text().replace("workbook: wb-1", "workbook: wb-9", 1))
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    assert "Comparison c1: its entry or rebuild check changed." in (
        capsys.readouterr().out
    )
    assert _scripts_for(fakes.bq) == ["c1"]


def test_triage_records_and_prints_the_stale_comparisons(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path), "--comparison", "c1"]) == 0
    capsys.readouterr()

    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0

    assert "v: comparison c2 never compared" in capsys.readouterr().out
    (saved,) = (tmp_path / "cache" / "v").glob("*/triage.json")
    assert json.loads(saved.read_text())["stale"] == {"c2": "never compared"}


VIEW_D = "select * from `teamster-332318`.`kipptaf_int`.`int_d`"
VIEW_E = VIEW_D.replace("int_d", "int_e")
DEV = "zz_cbaldor_kipptaf_marts"


def _sorted_stale(path, tmp_path):
    """Triage the view's latest run and return the stale list it wrote."""
    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0
    saved = max(
        (tmp_path / "cache" / "v").glob("*/triage.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return json.loads(saved.read_text())["stale"]


def test_triage_judges_staleness_from_the_composed_run(fakes, tmp_path):
    fakes.bq.views = {"rpt_d": VIEW_D}
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.bq.views = {"rpt_d": VIEW_E}
    fakes.bq.fail_once = "__c2_"
    # c1's new result is kept, but the run stops before it composes run.json.
    assert cli.main(["compare", str(path)]) == 1

    assert _sorted_stale(path, tmp_path) == {
        "c1": "the dashboard SQL changed",
        "c2": "the dashboard SQL changed",
    }


def test_run_composes_again_when_its_results_are_newer_than_its_run(
    fakes, tmp_path, monkeypatch, capsys
):
    fakes.bq.views = {"rpt_d": VIEW_D}
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    first = json.loads(_latest_run(tmp_path).read_text())
    fakes.bq.views = {"rpt_d": VIEW_E}
    apply = pipeline.decisions.apply

    def refuse(*args, **kwargs):
        raise ValueError("2 decisions claim one group")

    # Both comparisons compare and keep their results; composing refuses.
    monkeypatch.setattr(pipeline.decisions, "apply", refuse)
    assert cli.main(["compare", str(path)]) == 1
    monkeypatch.setattr(pipeline.decisions, "apply", apply)
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Composing run.json again from the latest results" in out
    assert not _outer(fakes.bq)
    again = json.loads(_latest_run(tmp_path).read_text())
    assert again["fingerprints"] != first["fingerprints"]
    assert checkpoints.find_unfinished(tmp_path / "cache", "v") is None
    capsys.readouterr()
    assert cli.main(["compare", str(path)]) == 0
    assert "Every comparison's latest result is current" in capsys.readouterr().out


def test_a_dev_build_keeps_its_results_apart_from_production(fakes, tmp_path, capsys):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.dataset = DEV
    fakes.bq.build = LATER

    argv = ["compare", str(path), "--comparison", "c2", "--fact-dataset", DEV]
    assert cli.main(argv) == 0

    dev = json.loads(_latest_run(tmp_path).read_text())
    assert dev["fact"] == f"{DEV}.fct_f" and dev["missing"] == ["c1"]
    fakes.cube.dataset = "kipptaf_marts"
    fakes.bq.ran.clear()
    capsys.readouterr()
    # Production's results are untouched: a new build alone is not stale.
    assert cli.main(["compare", str(path)]) == 0
    assert "Every comparison's latest result is current" in capsys.readouterr().out
    assert not _outer(fakes.bq)

    # Each command reads the latest run of the fact it was given, though the
    # dev run's is newer: a plain triage reads production's.
    prod_folder = report.run_dir(tmp_path / "cache", "v", report.Build(START, END, "j"))
    dev_folder = report.run_dir(tmp_path / "cache", "v", report.Build(*LATER, "j"))
    assert _sorted_stale(path, tmp_path) == {}
    assert (prod_folder / "triage.json").exists()
    assert not (dev_folder / "triage.json").exists()
    fakes.cube.dataset = DEV
    argv = ["sort", str(path), "--no-trace", "--no-explanations", "--fact-dataset", DEV]
    assert cli.main(argv) == 0
    dev_triage = json.loads((dev_folder / "triage.json").read_text())
    assert dev_triage["stale"] == {"c1": "never compared"}


def test_review_refuses_a_dev_build_s_run_for_production(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    fakes.cube.dataset = DEV
    assert cli.main(["compare", str(path), "--fact-dataset", DEV]) == 0
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert (
        f"v: no saved run of kipptaf_marts.fct_f; the latest run read {DEV}.fct_f"
        in err
    )


def test_a_comparison_whose_sql_no_longer_builds_waits_and_triage_goes_on(
    fakes, tmp_path
):
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    # Cube now reads a second fact the file does not list: its SQL refuses.
    fakes.cube.joins = SECOND_FACT_JOIN

    stale = _sorted_stale(path, tmp_path)

    assert set(stale) == {"c1", "c2"}
    assert stale["c1"].startswith("its SQL cannot be built today: ")
    assert "fct_g" in stale["c1"]


def test_triage_names_which_side_s_sql_changed(fakes, tmp_path):
    fakes.bq.views = {"rpt_d": VIEW_D}
    path = _two(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    fakes.cube.exprs = {"regions_region_name": "UPPER(`t`.regions_region_name)"}

    assert _sorted_stale(path, tmp_path)["c1"] == "Cube's SQL changed"

    fakes.bq.views = {"rpt_d": VIEW_E}
    assert _sorted_stale(path, tmp_path)["c1"] == (
        "Cube's SQL changed and the dashboard SQL changed"
    )


def test_a_measure_with_a_comparison_never_compared_says_so(fakes, tmp_path, capsys):
    path = _two(tmp_path)

    assert cli.main(["compare", str(path), "--comparison", "c1"]) == 0

    assert "- `avg_daily_attendance`: not compared yet" in capsys.readouterr().out
    saved = json.loads(_latest_run(tmp_path).read_text())
    assert saved["measures"][0]["verdict"] == "not compared yet"


def test_a_resumed_older_moment_never_replaces_a_newer_result(fakes, tmp_path):
    path = _two(tmp_path)
    fakes.bq.fail_once = "__c2_"
    assert cli.main(["compare", str(path)]) == 1  # c1 kept at the first build
    fakes.bq.build = LATER
    argv = [
        "compare",
        str(path),
        "--comparison",
        "c1",
        "--moment",
        LATER[1].isoformat(),
    ]
    assert cli.main(argv) == 0
    fakes.bq.build = (START, END)

    # Resumes the first build's folder, which holds c1's older checkpoint.
    assert cli.main(["compare", str(path), "--all", "--moment", END.isoformat()]) == 0

    kept = latest.read_all(
        latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f"),
        "kipptaf_marts.fct_f",
    )
    assert kept["c1"].moment.end == LATER[1]
    assert kept["c2"].moment.end == END


def test_run_cube_rows_are_ungrouped_and_unlimited(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    row_queries = [q for q in fakes.cube.compiled_queries if q.get("ungrouped")]
    # Built once to check it builds today, once to plan: 1 query either way.
    assert len({json.dumps(q, sort_keys=True) for q in row_queries}) == 1
    assert "LIMIT 10000" not in _reconcile(fakes.bq)
    # One reconcile covers both cuts, so a row is never counted twice.
    assert "or" in row_queries[0]["filters"][0]


@pytest.mark.parametrize("command", ["compare", "rebuild-sheet"])
@pytest.mark.parametrize(
    "dataset",
    [
        "kipptaf_staging",
        "kipptaf_marts; DROP",
        "zz__kipptaf_marts",
        "ZZ_a_kipptaf_marts",
    ],
)
def test_fact_dataset_outside_allowed_names_is_refused(
    fakes, tmp_path, capsys, command, dataset
):
    extra = ["--comparison", "ada-region"] if command == "rebuild-sheet" else []

    code = cli.main([command, str(_file(tmp_path)), "--fact-dataset", dataset, *extra])

    assert code == 1
    assert "fact dataset" in capsys.readouterr().err
    assert fakes.bq.ran == []
    assert fakes.cube.compiled_queries == []
    assert fakes.signed_in == 0


def test_run_without_the_flag_uses_the_files_fact_as_written(fakes, tmp_path, capsys):
    fakes.cube.dataset = "zz_other_kipptaf_marts"
    path = _file(
        tmp_path, YML.replace("kipptaf_marts.fct_f", "zz_other_kipptaf_marts.fct_f")
    )

    assert cli.main(["compare", str(path)]) == 0

    jobs = next(s for s in fakes.bq.ran if "JOBS_BY_PROJECT" in s)
    assert "dataset_id = 'zz_other_kipptaf_marts'" in jobs
    assert "Fact: zz_other_kipptaf_marts.fct_f" in capsys.readouterr().out


def test_run_output_names_cube_host_and_fact(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    assert "Cube: cube.test" in out
    assert "Fact: kipptaf_marts.fct_f" in out


def test_run_against_a_dev_build_searches_and_expects_that_dataset(
    fakes, tmp_path, capsys
):
    fakes.cube.dataset = "zz_cbaldor_kipptaf_marts"

    code = cli.main(
        ["compare", str(_file(tmp_path)), "--fact-dataset", "zz_cbaldor_kipptaf_marts"]
    )

    assert code == 0
    jobs = next(s for s in fakes.bq.ran if "JOBS_BY_PROJECT" in s)
    assert "dataset_id = 'zz_cbaldor_kipptaf_marts'" in jobs
    assert "table_id = 'fct_f'" in jobs
    assert "Fact: zz_cbaldor_kipptaf_marts.fct_f" in capsys.readouterr().out


def test_run_refuses_a_cube_still_reading_prod_when_a_dev_build_is_named(
    fakes, tmp_path, capsys
):
    code = cli.main(
        ["compare", str(_file(tmp_path)), "--fact-dataset", "zz_cbaldor_kipptaf_marts"]
    )

    assert code == 1
    captured = capsys.readouterr()
    assert "Skipping ada-region: its SQL cannot be built today: " in captured.out
    assert "other than zz_cbaldor_kipptaf_marts.fct_f" in captured.out
    assert "v: every comparison was skipped; see the reasons above" in captured.err


def test_run_skips_comparison_without_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))

    assert cli.main(["compare", str(path)]) == 1

    captured = capsys.readouterr()
    assert (
        "Skipping ada-region: no rebuild check; run `rebuild-sheet` first."
        in captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    assert fakes.bq.ran == [] and fakes.cube.compiled_queries == []


def test_run_prices_before_running(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 10.0 if "-- outer" in sql else 0.001

    assert cli.main(["compare", str(_file(tmp_path)), "--max-usd-per-day", "1000"]) == 1

    err = capsys.readouterr().err
    assert "$" in err and "5.00" in err
    assert not any("-- outer" in s for s in fakes.bq.ran)


def test_run_max_usd_sets_the_cap(fakes, tmp_path):
    fakes.bq.cost = lambda sql: 10.0 if "-- outer" in sql else 0.001

    assert (
        cli.main(
            [
                "compare",
                str(_file(tmp_path)),
                "--max-usd",
                "50",
                "--max-usd-per-day",
                "1000",
            ]
        )
        == 0
    )


def _compared(bq):
    """The queries a comparison bills: its cells, unmatched rows and counts."""
    return [
        q for q in bq.ran if "AS value" in q or "-- outer" in q or "AS n_students" in q
    ]


def _billed(bq):
    """Every query `compare` prices: a comparison's and each table fingerprint."""
    return _compared(bq) + [q for q in bq.ran if "farm_fingerprint" in q]


def test_run_skips_a_changed_workbook_before_any_query(fakes, tmp_path, capsys):
    path = _republished(fakes, tmp_path)
    fakes.tbl.updated = datetime(2026, 10, 30, tzinfo=timezone.utc)  # after the proof
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "SUM([is_present]) / SUM([is_enrolled])", "SUM([is_present])"
    )

    assert cli.main(["compare", str(path)]) == 1

    captured = capsys.readouterr()
    assert (
        "Skipping ada-region: workbook changed since its rebuild check: workbook "
        "published" in captured.out
    )
    assert (
        "the sheet's formulas or filters changed; re-run `rebuild-sheet`."
        in captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    assert fakes.bq.ran == [] and fakes.cube.compiled_queries == []


def test_run_prices_every_query_first_and_refuses_over_the_cap(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 2.0 if "rpt_d" in sql else 0.0

    args = [
        "compare",
        str(_file(tmp_path)),
        "--max-usd",
        "1",
        "--max-usd-per-day",
        "100",
    ]
    assert cli.main(args) == 1

    assert "would pass the $1.00 cap" in capsys.readouterr().err
    assert not _compared(fakes.bq)


def test_run_dry_runs_every_billed_query_before_the_first_runs(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    kinds = [kind for kind, _ in fakes.bq.log]
    first_billed = next(
        i
        for i, (kind, sql) in enumerate(fakes.bq.log)
        if kind == "run" and sql in _billed(fakes.bq)
    )
    assert "dry" not in kinds[first_billed:]
    dry = [sql for kind, sql in fakes.bq.log if kind == "dry"]
    # 2 cuts of 2 sides, the unmatched rows, the student count, and
    # dim_locations' fingerprint at each end of the build.
    assert len(dry) == 8
    assert len([s for s in _billed(fakes.bq) if "farm_fingerprint" in s]) == 2
    for sql in _billed(fakes.bq):
        # The save script is priced by its join alone: its table is not made yet.
        assert sql in dry or "CREATE TEMP TABLE" in sql


def test_run_prices_a_second_facts_fingerprint_before_it_scans(fakes, tmp_path, capsys):
    fakes.cube.joins = SECOND_FACT_JOIN
    fakes.bq.cost = lambda sql: 10.0 if "farm_fingerprint" in sql else 0.0

    path = _file(tmp_path, ALSO_FACTS_YML)
    assert cli.main(["compare", str(path), "--max-usd-per-day", "100"]) == 1

    assert "would pass the $5.00 cap" in capsys.readouterr().err
    assert not _billed(fakes.bq)


def test_run_fingerprints_a_shared_dimension_once_per_end(fakes, tmp_path):
    fakes.bq.views = {"rpt_d": SHARED_VIEW}

    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    # The rows' moved check and the dims check share 1 scan at each end.
    scans = [s for s in fakes.bq.ran if "farm_fingerprint" in s]
    assert len(scans) == 2 and all("dim_locations" in s for s in scans)
    dry = [sql for kind, sql in fakes.bq.log if kind == "dry"]
    assert all(s in dry for s in scans)


def test_run_keeps_each_cuts_dashboard_and_cube_price_with_its_query(fakes, tmp_path):
    text = YML.replace(
        "    rows:\n",
        "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n"
        "    rows:\n",
        1,
    )

    def cost(sql):
        if "AS value" not in sql:
            return 0.0
        if "fct_f" in sql:
            return 0.2
        miami = 0.01 if "'Miami'" in sql else 0.0
        return (0.1 if "enroll_status" in sql else 0.3) + miami

    fakes.bq.cost = cost
    args = ["compare", str(_file(tmp_path, text)), "--max-usd", "50"]
    assert cli.main(args + ["--max-usd-per-day", "50"]) == 0

    usd = _saved_run(tmp_path)["cell_sql_usd"]["ada-region"]
    assert usd["{}"] == pytest.approx([0.1, 0.2])
    assert usd['{"Region": "Miami"}'] == pytest.approx([0.11, 0.2])


def test_execute_refuses_prices_its_queries_do_not_use(fakes, tmp_path):
    path = _file(tmp_path)
    cfg = load_view_config(path)
    wh = Warehouse(client=fakes.bq)
    build = report.Build(START, END, "j")
    plan = compare._plan_one(
        cfg, cfg.comparisons[0], wh=wh, cube=fakes.cube, build=build, schools={"A", "B"}
    )
    prices = [0.0] * (len(plan.queries()) + 1)

    with pytest.raises(RuntimeError, match="prices left over: .*queries"):
        compare._execute(cfg, plan, wh=wh, build=build, prices=prices)


def test_run_builds_its_warehouse_before_it_signs_in_to_tableau(
    fakes, tmp_path, monkeypatch
):
    signed_in_then = []

    def warehouse():
        signed_in_then.append(fakes.signed_in)
        return Warehouse(client=fakes.bq)

    monkeypatch.setattr(cli, "make_warehouse", warehouse)

    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    assert signed_in_then == [0] and fakes.signed_in == 1


def test_run_prints_the_priced_total_then_a_progress_line_per_comparison(
    fakes, tmp_path, capsys
):
    fakes.bq.cost = lambda sql: 0.25 if "FOR SYSTEM_TIME" in sql else 0.0

    args = [
        "compare",
        str(_four(tmp_path)),
        "--max-usd",
        "50",
        "--max-usd-per-day",
        "50",
    ]
    assert cli.main(args) == 0

    out = capsys.readouterr().out
    # 6 queries a comparison, and dim_locations scanned at each end.
    assert "Compare: 26 queries, $6.50 (dry run)" in out
    lines = re.findall(
        r"\[\d\d:\d\d:\d\d UTC \+\d+m\d\ds\] compare (ada-region-\d): "
        r"\$\d+\.\d\d spent",
        out,
    )
    assert lines == [f"ada-region-{i}" for i in range(1, 5)]
    assert out.index("(dry run)") < out.index("] compare ada-region-1:")
    saved = json.loads(next((tmp_path / "cache").glob("v/*/run.json")).read_text())
    ran = [s for s in fakes.bq.ran if "FOR SYSTEM_TIME" in s]
    assert saved["cost_usd"] == pytest.approx(0.25 * len(ran), abs=0.01)


def test_a_resumed_run_prices_only_the_comparisons_left(fakes, tmp_path, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    capsys.readouterr()

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    # Comparisons 3 and 4, and the dims scan, which covers the held ones too.
    assert "Compare: 14 queries" in out
    assert "] compare ada-region-1:" not in out
    assert "] compare ada-region-3:" in out and "] compare ada-region-4:" in out


def test_a_failed_scan_dry_run_skips_every_comparison_reading_the_table(
    fakes, tmp_path, capsys
):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["compare", str(path)]) == 1
    fakes.bq.ran.clear()
    capsys.readouterr()
    # The scan of a dimension table every comparison's Cube SQL reads.
    _bigquery_refuses(fakes, "`dim_locations` AS t", dry=True)

    # `--all` resumes the stopped run, holding the checkpoints of 1 and 2.
    assert cli.main(["compare", str(path), "--all"]) == 1

    captured = capsys.readouterr()
    out = captured.out
    assert "every comparison was skipped" in captured.err
    # Held checkpoints 1 and 2 as well as 3 and 4, left to compare.
    for i in range(1, 5):
        assert (
            f"Skipping ada-region-{i}: the dry run of a scan of "
            "kipptaf_marts.dim_locations failed in BigQuery (job ?, invalidQuery); "
            "compare it again later."
        ) in out
    assert "12345" not in out
    assert not _compared(fakes.bq)


def test_run_names_dimensions_that_changed(fakes, tmp_path, capsys):
    fakes.bq.changed = ("dim_locations",)

    assert cli.main(["compare", str(_file(tmp_path))]) == 0

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

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    wanted = [
        {"member": "v.membership_value", "operator": "equals", "values": ["1"]},
        {"member": "v.attendance_value", "operator": "set"},
    ]
    compared = fakes.cube.compiled_queries
    assert compared
    for query in compared:
        assert all(f in query["filters"] for f in wanted)
    section = capsys.readouterr().out.split("## Scopes applied")[1].split("##")[0]
    assert "ada-region: v.membership_value in 1" in section
    assert "ada-region: v.attendance_value is set" in section


def test_run_signs_in_to_tableau_once_for_its_workbook_check(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    assert fakes.signed_in == 1


def test_run_reports_cells_and_proofs(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    # The Miami group is still open, so the measure line says so.
    assert ("`avg_daily_attendance`: differs (pass 2); 1 open row group to sort") in out
    assert "ada-region: last matched 2026-10-26T12:00:00+00:00" in out
    assert "regions_region_name" in out and "Miami" in out
    assert list((tmp_path / "cache" / "v").glob("*/result.md"))


def test_run_names_a_comparison_whose_cells_cannot_be_covered(fakes, tmp_path, capsys):
    rows = YML[YML.index("    rows:\n") : YML.index(REBUILD_CHECK)]
    assert cli.main(["compare", str(_file(tmp_path, YML.replace(rows, "")))]) == 0

    out = capsys.readouterr().out
    assert (
        "Comparison ada-region: its cells cannot be covered (the comparison has "
        "no rows); its differing cells stay open."
    ) in out
    assert "cannot be covered" not in _run_out(fakes, tmp_path / "with-rows", capsys)


def _run_out(fakes, tmp_path, capsys):
    tmp_path.mkdir()
    assert cli.main(["compare", str(_file(tmp_path)), "--restart"]) == 0
    return capsys.readouterr().out


def _browser_section(out):
    return _section(out, "## Cuts to check in the browser", "##")


def test_run_lists_a_proof_without_cuts_for_a_re_prove(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert (
        "ada-region: cuts unknown (the rebuild check records none); re-run "
        "`rebuild-sheet`" in section
    )


def test_run_lists_cuts_no_export_proved(fakes, tmp_path, capsys):
    # The Miami cut sets a parameter, say, so the export proved only `{}`.
    text = YML.replace(REBUILD_CHECK, REBUILD_CHECK + "      cuts: ['{}']\n")

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert 'ada-region: {"Region": "Miami"} (no export matched it)' in section
    assert "ada-region: {} (" not in section and "cuts unknown" not in section


def test_run_lists_no_cut_when_every_cut_was_exported(fakes, tmp_path, capsys):
    text = YML.replace(
        REBUILD_CHECK, REBUILD_CHECK + """      cuts: ['{}', '{"Region": "Miami"}']\n"""
    )

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    section = _browser_section(capsys.readouterr().out)
    assert "(no export matched it)" not in section and "cuts unknown" not in section


def _totals_section(out):
    return _section(out, "## Totals not matched", "##")


def test_run_lists_totals_a_proof_skipped(fakes, tmp_path, capsys):
    text = YML.replace(REBUILD_CHECK, REBUILD_CHECK + "      totals_skipped: 2\n")

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "ada-region: totals not matched: 2 rows" in _totals_section(out)
    assert out.count("totals not matched: 2 rows") == 2  # printed, then listed


def test_run_lists_no_totals_when_none_were_skipped(fakes, tmp_path, capsys):
    text = YML.replace(REBUILD_CHECK, REBUILD_CHECK + "      totals_skipped: 0\n")

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "totals not matched" not in out
    assert "None." in _totals_section(out)


def test_run_reads_a_proof_without_a_totals_count_as_unknown(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    section = _totals_section(capsys.readouterr().out)
    assert "ada-region: totals not matched: unknown" in section
    assert "re-run `rebuild-sheet`" in section


def test_run_cells_that_differ_fail_the_dashboard_check(fakes, tmp_path, capsys):
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.5}]

    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    assert "differs" in capsys.readouterr().out


def test_run_refuses_without_email(fakes, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CUBE_VALIDATION_EMAIL")

    assert cli.main(["compare", str(_file(tmp_path))]) == 1

    err = capsys.readouterr().err
    assert "--email" in err and "CUBE_VALIDATION_EMAIL" in err


def test_run_refuses_without_cube_url(fakes, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CUBE_REST_URL")

    assert cli.main(["compare", str(_file(tmp_path))]) == 1
    assert "CUBE_REST_URL" in capsys.readouterr().err


def test_run_refuses_a_moment_outside_the_window(fakes, tmp_path, capsys):
    path = str(_file(tmp_path))

    assert cli.main(["compare", path, "--moment", "2026-10-01T00:00:00Z"]) == 1
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
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    out = capsys.readouterr().out
    fp = _saved_fingerprints(tmp_path)
    assert len(fp["cube"]) == len(fp["dashboard"]) == 64
    shown = _section(out, "Fingerprints a new decision records", "##")
    assert (
        f"ada-region: {{ cube: {fp['cube']}, dashboard: {fp['dashboard']} }}" in shown
    )


def test_decision_fingerprints_ignore_the_moment(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    fakes.bq.build = (START + timedelta(hours=3), END + timedelta(hours=3))
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "Applied:", "To re-confirm")
    assert "No open groups." in out
    assert "open row group" not in out


def test_dashboard_view_edit_asks_to_reconfirm(fakes, tmp_path, capsys):
    body = "select * from `teamster-332318`.`kipptaf_int`.`int_d` where keep"
    fakes.bq.views = {"rpt_d": body}
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0
    assert "miami-scope" in _section(
        capsys.readouterr().out, "Applied:", "To re-confirm"
    )

    fakes.bq.views = {"rpt_d": body.replace("where keep", "where keep and not dropped")}
    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "To re-confirm", "No longer needed")
    assert "`regions_region_name` = `Miami`" in _section(out, "## Sort", "##")


def test_reordered_school_list_keeps_decisions(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    # dim_locations has no order, so Cube may list the schools either way.
    fakes.cube.schools = ["B", "A"]
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "Applied:", "To re-confirm")


def test_cube_row_dimension_edit_asks_to_reconfirm(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="deliberate")
    # attendance_value is read by the row query only, never by the cells.
    fakes.cube.exprs["attendance_value"] = "coalesce(`t`.attendance_value, 0)"
    capsys.readouterr()

    assert cli.main(["compare", str(path), "--all"]) == 0

    out = capsys.readouterr().out
    assert "miami-scope" in _section(out, "To re-confirm", "No longer needed")


def test_run_skips_a_probe_changed_since_its_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    path.write_text(path.read_text().replace("avg(is_present)", "sum(is_present)"))

    assert cli.main(["compare", str(path)]) == 1

    captured = capsys.readouterr()
    assert (
        "Skipping ada-region: the sheet query is not the one its rebuild check "
        "covers; run "
        "`rebuild-sheet` again." in captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    assert fakes.bq.ran == []


SHARED_VIEW = (
    "select * from `teamster-332318`.`kipptaf_int`.`int_d` "
    "join `teamster-332318`.`kipptaf_marts`.`dim_locations` using (k)"
)


def test_run_reads_a_table_both_sides_share_at_1_moment(fakes, tmp_path):
    fakes.bq.views = {"rpt_d": SHARED_VIEW}

    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    reconcile = _reconcile(fakes.bq)
    stamps = set(re.findall(r"dim_locations`[^']*?TIMESTAMP '([^']+)'", reconcile))
    assert stamps == {utc_literal(START)}
    assert _literal_after(reconcile, "fct_f") == utc_literal(END)
    # The cells query reads Cube as of the end, as before.
    cells = [s for s in fakes.bq.ran if "AS value" in s and "fct_f" in s]
    assert {_literal_after(s, "dim_locations") for s in cells} == {utc_literal(END)}


def test_run_skips_a_shared_table_that_changed_during_the_build(
    fakes, tmp_path, capsys
):
    fakes.bq.views = {"rpt_d": SHARED_VIEW}
    fakes.bq.changed = ("dim_locations",)

    assert cli.main(["compare", str(_file(tmp_path))]) == 1
    captured = capsys.readouterr()
    assert (
        "Skipping ada-region: both sides read kipptaf_marts.dim_locations, which "
        "changed during the build" in captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err


def test_a_changed_shared_table_skips_only_the_comparisons_that_read_it(
    fakes, tmp_path, capsys
):
    # Only c2's dashboard view reads the dimension Cube reads too.
    fakes.bq.views = {"rpt_e": SHARED_VIEW}
    fakes.bq.changed = ("dim_locations",)
    path = _two(
        tmp_path,
        lambda e: e.replace(
            "dashboard_view: kipptaf_tableau.rpt_d",
            "dashboard_view: kipptaf_tableau.rpt_e",
        ),
    )

    assert cli.main(["compare", str(path)]) == 0

    out = capsys.readouterr().out
    assert "Skipping c2: both sides read kipptaf_marts.dim_locations" in out
    assert out.index("(dry run)") < out.index("Skipping c2")
    assert _scripts_for(fakes.bq) == ["c1"]
    assert len(_compared(fakes.bq)) == 6


SECOND_FACT_JOIN = "LEFT JOIN  kipptaf_marts.fct_g  AS `g` ON `g`.k = `t`.k\n"
ALSO_FACTS_YML = YML.replace(
    "fact: kipptaf_marts.fct_f\n",
    "fact: kipptaf_marts.fct_f\nalso_facts: [kipptaf_marts.fct_g]\n",
)


def test_run_reads_a_listed_second_fact_that_held_during_the_build(fakes, tmp_path):
    fakes.cube.joins = SECOND_FACT_JOIN

    assert cli.main(["compare", str(_file(tmp_path, ALSO_FACTS_YML))]) == 0

    checks = [s for s in fakes.bq.ran if "farm_fingerprint" in s and "fct_g" in s]
    # Once at each end of the build: the dims check after the comparisons
    # does not scan it again.
    assert sorted(_first(r"TIMESTAMP '([^']+)'", s) for s in checks) == sorted(
        [utc_literal(START), utc_literal(END)]
    )


def test_run_skips_a_listed_second_fact_that_changed_during_the_build(
    fakes, tmp_path, capsys
):
    fakes.cube.joins = SECOND_FACT_JOIN
    fakes.bq.changed = ("fct_g",)

    assert cli.main(["compare", str(_file(tmp_path, ALSO_FACTS_YML))]) == 1

    captured = capsys.readouterr()
    assert (
        "Skipping ada-region: kipptaf_marts.fct_g changed during the build of "
        "kipptaf_marts.fct_f" in captured.out
    )
    assert "v: every comparison was skipped; see the reasons above" in captured.err
    # Refused before any comparison spent on a query.
    assert not [s for s in fakes.bq.ran if "-- outer" in s or "AS value" in s]


def test_run_skips_a_second_fact_the_file_does_not_list(fakes, tmp_path, capsys):
    fakes.cube.joins = SECOND_FACT_JOIN

    assert cli.main(["compare", str(_file(tmp_path))]) == 1

    captured = capsys.readouterr()
    assert "Skipping ada-region: its SQL cannot be built today: " in captured.out
    assert "kipptaf_marts.fct_g" in captured.out and "also_facts" in captured.out
    assert "v: every comparison was skipped; see the reasons above" in captured.err


def test_run_skips_sql_it_cannot_time_travel(fakes, tmp_path, capsys):
    text = YML.replace(
        "    sheet_query: avg(is_present)\n",
        "    sheet_query_sql: SELECT region, avg(x) AS value FROM ({rows}) AS r "
        "JOIN kipptaf_x.lookup USING (region) WHERE {where} GROUP BY 1\n",
    )

    assert cli.main(["compare", str(_file(tmp_path, text))]) == 1
    captured = capsys.readouterr()
    assert "Skipping ada-region: its SQL cannot be built today: " in captured.out
    assert "kipptaf_x.lookup" in captured.out
    assert "v: every comparison was skipped; see the reasons above" in captured.err


def test_unexpected_error_is_not_reported_as_a_refusal(fakes, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise KeyError("bug")

    monkeypatch.setattr(compare, "compare", broken)

    with pytest.raises(KeyError):
        cli.main(["compare", str(_file(tmp_path))])


def test_missing_validation_file_is_refused(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(tmp_path / "nope.yml")]) == 1
    assert "nope.yml" in capsys.readouterr().err


def test_tableau_sign_in_names_the_missing_variables(monkeypatch):
    for name in tableau.ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(pipeline.Refusal, match="TABLEAU_SERVER_ADDRESS"):
        with REAL_TABLEAU_SESSION():
            pass


# --- review ------------------------------------------------------------------


def test_review_never_posts(fakes, tmp_path, monkeypatch, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)
    capsys.readouterr()

    def no_network(*args, **kwargs):
        raise AssertionError("review must not call out")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", no_network)
    monkeypatch.setattr(cli, "make_cube", no_network)
    monkeypatch.setattr(cli, "make_warehouse", no_network)
    monkeypatch.setattr(cli, "tableau_session", no_network)

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("## What and why")
    assert "The Registrar team owns the rule behind 1 question" in out
    # A region name names no person, and the group has 10+ students.
    assert "`regions_region_name` = `Miami`" in out and "10+ students" in out
    assert "12 students" not in out


def test_record_answers_takes_a_review_whose_counts_are_bounds(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    # The owner's JSON carries bounds, never the group's exact 30 rows.
    (question,) = json.loads((tmp_path / "reviews" / "v.json").read_text())
    assert question["counts"][0].endswith("<10 row groups, 10+ rows, 10+ students")
    assert "30 rows" not in json.dumps(question)
    comment = _comment(tmp_path, [_answer(["miami-scope"], "deliberate", "ok")])
    capsys.readouterr()

    assert _record([path], comment, "--yes") == 0, capsys.readouterr().err

    (d,) = load_view_config(path).decisions
    assert (d.id, d.call) == ("miami-scope", "deliberate")


def test_review_carries_triage_evidence_in_its_json(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    run_json = next((tmp_path / "cache" / "v").glob("*/run.json"))
    stub = {
        "comparison": "ada-region",
        "group": {"column": "regions_region_name", "values": ["Miami"]},
    }
    item = {"id": "i", "kind": "group", "comparison": "ada-region", "label": "l",
            "stub": stub, "suggestion": "cause", "evidence": ["the fact drops them"],
            "candidates": [], "cause": [STEP], "proof": dict(STORED_EXPLANATION)}  # fmt: skip
    _write_sorted(run_json, [item])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    out = capsys.readouterr().out
    assert "[v.json](https://github.com/o/r/blob/abc/v.json)" in out
    block = (tmp_path / "reviews" / "v.json").read_text()
    (question,) = json.loads(block)
    assert question["decisions"] == ["miami-scope"]
    assert question["evidence"] == ["the fact drops them"]
    assert '"stub"' not in out + block


def test_review_quotes_the_masked_copy_of_exact_triage_evidence(
    fakes, tmp_path, capsys
):
    # triage.json shows exact counts; the review issue is GitHub-bound.
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    run_json = next((tmp_path / "cache" / "v").glob("*/run.json"))
    item = {
        **_sorted_item("lead: relaxing x brings back 3 of 40 rows"),
        "evidence_posted": ["lead: relaxing x brings back <10 of 40 rows"],
    }
    _write_sorted(run_json, [item])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    # Everything posted: the body and the review file it links.
    out = capsys.readouterr().out + (tmp_path / "reviews" / "v.json").read_text()
    assert "brings back <10 of 40 rows" in out
    assert "3 of 40" not in out


STEP = {"side": "dashboard", "step": "dashboard:main:1", "label": "x", "n_rows": 12}


# The Miami group's triage item id, which a cause decision lists as its key.
MIAMI = "ada-region:regions_region_name=Miami"


EXPLANATION_TEXT = "-- cause x = dashboard: x\nSELECT item_key, 'x' AS cause, 1 AS n FROM {unmatched}\n"


@pytest.fixture(autouse=True)
def _explanation_file(monkeypatch, tmp_path):
    """Give every proven fixture item a stored proof file, as `explain` does."""
    path = tmp_path / "explanations" / "ada-region__dashboard_only.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXPLANATION_TEXT)
    monkeypatch.setitem(globals(), "STORED_EXPLANATION", _explanation_of(path))


def _explanation_of(path):
    return {
        "kind": "query",
        "path": str(path),
        "fingerprint": explain.file_fingerprint(path),
    }


STORED_EXPLANATION: dict = {}


def _sorted_item(evidence, suggestion="cause", item_id=MIAMI):
    stub = {
        "comparison": "ada-region",
        "group": {"column": "regions_region_name", "values": ["Miami"]},
    }
    cause = [STEP] if suggestion == "cause" else None
    return {"id": item_id, "kind": "group", "comparison": "ada-region",
            "label": "l", "stub": stub, "suggestion": suggestion,
            "evidence": [evidence], "candidates": [], "cause": cause,
            "proof": dict(STORED_EXPLANATION) if cause else None}  # fmt: skip


def _write_sorted(run_json, items=(), open_keys=None):
    """Write the triage `sort` would write beside `run_json`, holding `items`.

    `open_keys` defaults to every open item of that run.
    """
    run = results._run_from_json(json.loads(run_json.read_text()))
    # Each item of an open group carries its stable key, as `sort` writes.
    keys = {i.id: i.key for i in sort.open_items(run)}
    items = [{"key": keys.get(i["id"], ""), **i} for i in items]
    (run_json.parent / "triage.json").write_text(
        json.dumps(
            {
                "view": run.view,
                "moment": sort._moment(run),
                "decisions_fingerprint": run.decisions_fingerprint,
                "open": sort.open_keys(run) if open_keys is None else open_keys,
                "items": list(items),
                "formulas_not_compared": {},
                "posted_version": sort.POSTED_VERSION,
            }
        )
    )


def _write_sorted_everywhere(tmp_path, items=()):
    """Write a triage holding `items` beside every saved run of view `v`."""
    for run_json in (tmp_path / "cache" / "v").glob("*/run.json"):
        _write_sorted(run_json, items)


def test_review_refuses_a_triage_missing_an_open_item_of_the_run(
    fakes, tmp_path, capsys
):
    # Same moment, but the run was re-run after triage: its open groups are new.
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e")], open_keys=[])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert "v: 1 open item of the latest run is not in its sort" in err
    assert "run `sort` for" in err


def test_add_decisions_refuses_a_cause_item_with_no_cause(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    for empty in (None, []):
        _write_sorted(run_json, [{**_sorted_item("e"), "cause": empty}])
        approved = _approved(
            tmp_path, [{"id": "a", "call": "deliberate", "reason": "r", "item": "i"}]
        )
        capsys.readouterr()

        assert cli.main(["decide", str(path), str(approved)]) == 1

        assert "v: 1 `cause` item has no cause" in capsys.readouterr().err
    assert load_view_config(path).decisions == []


def test_review_refuses_a_view_never_triaged(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    captured = capsys.readouterr()
    assert "v: no sort of the latest run" in captured.err
    assert "run `sort` for" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("stale", [True, False])
def test_ask_owner_leaves_no_stale_open_items_file_when_nothing_is_open(
    fakes, tmp_path, capsys, stale
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    _write_sorted_everywhere(tmp_path, [_sorted_item("e")])
    old = tmp_path / "reviews" / "v-still-with-analyst.md"
    if stale:
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text("# Still with the analyst: `v`\n\n- `x`, 40 rows; no lead yet\n")
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    body = capsys.readouterr().out
    assert old.name not in body
    if stale:
        assert old.read_text() == (
            "# Still with the analyst: `v`\n\nNothing is with the analyst.\n"
        )
    else:
        assert not old.exists()


def test_review_lists_items_in_investigate_still_with_the_analyst(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(
        tmp_path,
        [
            _sorted_item("e"),
            _sorted_item("x", "investigate", "j"),
            _sorted_item("y", "investigate", "k"),
        ],  # fmt: skip
    )
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    body = capsys.readouterr().out
    section = body.split("## Still with the analyst", 1)[1].split("## Proposed")[0]
    assert "- `ada-region` in `v` (group): 2 listed items\n" in section
    text = (tmp_path / "reviews" / "v-still-with-analyst.md").read_text()
    assert "- `j`; no lead yet\n- `k`; no lead yet\n" in text
    assert "Q1." in body.split("## Still with the analyst", 1)[0]


def test_review_refuses_a_triage_from_before_the_investigate_pile(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path, [_sorted_item("e", "owner")])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    assert "re-run `sort`" in capsys.readouterr().err


def test_review_refuses_a_triage_from_an_older_moment(fakes, tmp_path, capsys):
    # Triage ran on the earlier build; the latest run lands on a later one.
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (earlier,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(earlier, [_sorted_item("from the earlier build")])
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    fakes.bq.build = (START + timedelta(hours=3), END + timedelta(hours=3))
    assert cli.main(["compare", str(path), "--all"]) == 0
    assert len(list((tmp_path / "cache" / "v").glob("*/run.json"))) == 2
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1
    assert cli.main(["decide", str(path), str(_approved(tmp_path, []))]) == 1

    captured = capsys.readouterr()
    assert captured.err.count("v: no sort of the latest run") == 2
    assert "run `sort` for" in captured.err and captured.out == ""


def test_review_refuses_a_triage_whose_moment_is_not_the_runs(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e")])
    saved = json.loads((run_json.parent / "triage.json").read_text())
    saved["moment"]["job_id"] = "another-build"
    (run_json.parent / "triage.json").write_text(json.dumps(saved))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert "v: triage.json is of another moment" in err and "run `sort` for" in err


def test_review_names_questions_left_without_evidence(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    assert "Q1: no triage evidence" in capsys.readouterr().err


def test_review_refuses_an_unreadable_triage_file(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    run_json = next((tmp_path / "cache" / "v").glob("*/run.json"))
    (run_json.parent / "triage.json").write_text("{not json")
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    assert "v: triage.json is unreadable; re-run `sort`" in capsys.readouterr().err


def test_review_refuses_a_triage_file_that_is_not_an_object(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    run_json = next((tmp_path / "cache" / "v").glob("*/run.json"))
    (run_json.parent / "triage.json").write_text("[]")
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    assert "v: triage.json is unreadable; re-run `sort`" in capsys.readouterr().err


def _review_json(path, capsys):
    capsys.readouterr()
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    capsys.readouterr()
    return json.loads((path.parent / "reviews" / "v.json").read_text())


def test_review_says_expired_by_the_command_lines_clock(
    fakes, tmp_path, monkeypatch, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)

    monkeypatch.setattr(cli, "utcnow", lambda: START + timedelta(days=1))
    assert _review_json(path, capsys)[0]["expired"] is False
    monkeypatch.setattr(cli, "utcnow", lambda: START + timedelta(days=8))
    assert _review_json(path, capsys)[0]["expired"] is True


def test_review_warns_when_the_body_nears_githubs_cap(
    fakes, tmp_path, monkeypatch, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    assert "65,536" not in capsys.readouterr().err

    long = pipeline.report.BODY_WARN_CHARS + 1
    monkeypatch.setattr(report, "render_review_issue", lambda *a: "x" * long)
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("x" * long)
    assert f"{long:,} characters" in captured.err and "65,536" in captured.err


def test_review_reads_the_run_written_last(fakes, tmp_path, capsys):
    # The later build runs first, with no decision yet.
    fakes.bq.build = (START + timedelta(hours=3), END + timedelta(hours=3))
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    fakes.bq.build = (START, END)
    assert cli.main(["compare", str(path), "--all"]) == 0
    _write_sorted_everywhere(tmp_path)
    later, earlier = sorted((tmp_path / "cache" / "v").glob("*/run.json"), reverse=True)
    os.utime(later, (1_000_000, 1_000_000))
    os.utime(earlier, (2_000_000, 2_000_000))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    assert "`regions_region_name` = `Miami`" in capsys.readouterr().out


def test_review_refuses_when_decisions_changed_since_the_run(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["compare", str(path), "--all"]) == 0
    path.write_text(path.read_text().replace("keeps Miami rows", "keeps Miami"))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    err = capsys.readouterr().err
    assert "v: " in err and "decisions" in err and "`compare`" in err


def test_review_refuses_a_run_saved_without_a_decisions_fingerprint(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    del data["decisions_fingerprint"]
    saved.write_text(json.dumps(data))

    assert cli.main(["ask-owner", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "decisions" in capsys.readouterr().err


def test_review_refuses_a_run_saved_in_the_old_group_shape(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    assert data["applied"]["open"]
    for g in data["applied"]["open"]:
        (column, value), *_ = g.pop("dims")
        g.update(column=column, value=value)
    saved.write_text(json.dumps(data))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "older validator" in capsys.readouterr().err


def test_review_refuses_a_view_never_run(fakes, tmp_path, capsys):
    assert cli.main(["ask-owner", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "run" in capsys.readouterr().err


# --- prove -------------------------------------------------------------------


def test_prove_writes_the_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof is not None
    assert proof.fingerprint == formula_fingerprint(fakes.tbl.twb, "Rate by Region")
    assert proof.cells == 2
    assert proof.cuts == ["{}", '{"Region": "Miami"}']
    assert proof.totals_skipped == 0
    assert proof.workbook_updated_at.startswith("2026-10-20")
    cfg = load_view_config(path)
    assert proof.sheet_query_fingerprint == pipeline.sheet_query_fingerprint(
        cfg, cfg.comparisons[0]
    )
    probes = [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]
    assert {_literal_after(s, "rpt_d") for s in probes} == {
        utc_literal(fakes.tbl.refresh)
    }
    # The copy drops the sheet's number formats.
    assert "default-format" not in fakes.tbl.edited.split("<worksheets>")[1]


def test_rebuild_sheet_refuses_a_text_measure_before_any_export(
    fakes, tmp_path, capsys
):
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "<cols>(",
        "<cols>([federated.0sample].[attr:region:nk] + ",
    )
    path = _file(
        tmp_path,
        YML.replace(REBUILD_CHECK, "    rebuild_check: null\n").replace(
            "sheet_field: Rate", "sheet_field: Region"
        ),
    )
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1
    assert "text measures are not compared" in capsys.readouterr().err
    assert not getattr(fakes.tbl, "captures", 0)


def test_rebuild_sheet_refuses_an_unwritable_comparison_before_any_export(
    fakes, tmp_path, capsys
):
    head = YML.split("comparisons:\n", 1)[0]
    flow = (
        "comparisons: [{id: ada-region, measure: avg_daily_attendance, "
        "workbook: wb-1, sheet: Rate by Region, "
        "dashboard_view: kipptaf_tableau.rpt_d, decimals: 3}]\n"
    )
    # Loads through the config loader, but no line edit can find the item.
    path = _file(tmp_path, head + flow)
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1
    assert (
        "comparisons: 'ada-region' cannot be edited by line; write it as a block list"
    ) in capsys.readouterr().err
    assert not getattr(fakes.tbl, "captures", 0)


def _hide_rate_by_region(tbl):
    """Hide the fixture sheet's window, so the server lists no view for it."""
    tbl.twb = tbl.twb.replace(
        "<window class='worksheet' name='Rate by Region'>",
        "<window class='worksheet' hidden='true' name='Rate by Region'>",
    )
    tbl.views = set()


def test_rebuild_sheet_refuses_an_unpublished_sheet_before_any_export(
    fakes, tmp_path, capsys
):
    _hide_rate_by_region(fakes.tbl)
    path = _file(tmp_path, NO_REBUILD_CHECK)
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1
    assert (
        "comparison 'ada-region': sheet 'Rate by Region' is not on a published "
        "dashboard; set unpublished: true to compare it anyway"
    ) in capsys.readouterr().err
    assert not getattr(fakes.tbl, "captures", 0)
    assert "published" not in path.read_text()


def test_rebuild_sheet_records_published(fakes, tmp_path, capsys):
    path = _file(tmp_path, NO_REBUILD_CHECK)
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof is not None and proof.published is True

    # An opted-in unpublished sheet is compared, and the check says so.
    _hide_rate_by_region(fakes.tbl)
    path = _file(
        tmp_path,
        NO_REBUILD_CHECK.replace(
            "    sheet_field: Rate\n", "    sheet_field: Rate\n    unpublished: true\n"
        ),
    )

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof is not None and proof.published is False


def test_prove_unhides_a_dashboard_only_sheet_on_the_copy(fakes, tmp_path, capsys):
    _hide_rate_by_region(fakes.tbl)
    fakes.tbl.twb = fakes.tbl.twb.replace(
        "  </worksheets>\n",
        "  </worksheets>\n  <dashboards><dashboard name='Overview'><zones>"
        "<zone id='1' name='Rate by Region' /></zones></dashboard></dashboards>\n",
    )
    assert "<dashboards>" in fakes.tbl.twb
    fakes.tbl.views = {"Overview"}
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert "hidden=" not in fakes.tbl.edited
    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof is not None and proof.published is True


def test_rebuild_sheet_refuses_a_shown_sheet_the_server_does_not_publish(
    fakes, tmp_path, capsys
):
    # Its window and its dashboard's show in the .twb; neither is a view.
    _on_dashboard(fakes.tbl)
    fakes.tbl.views = {"Other"}
    path = _file(tmp_path, NO_REBUILD_CHECK)
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1
    assert (
        "comparison 'ada-region': sheet 'Rate by Region' is not on a published "
        "dashboard; set unpublished: true to compare it anyway"
    ) in capsys.readouterr().err
    assert not getattr(fakes.tbl, "captures", 0)


def test_rebuild_sheet_asks_a_workbook_s_views_once_per_run(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _two(tmp_path, text=NO_REBUILD_CHECK)
    argv = ["rebuild-sheet", str(path), "--comparison", "c1", "--comparison", "c2"]

    assert cli.main(argv) == 0, capsys.readouterr().err
    assert fakes.tbl.view_asks == ["wb-1"]

    # An error is kept too: each comparison is refused, Tableau asked once.
    asked = []

    def answer(luid):
        asked.append(luid)
        raise TSC.ServerResponseError("404", "Resource Not Found", "gone")

    monkeypatch.setattr(fakes.tbl, "view_names", answer)
    assert cli.main(argv) == 1
    err = capsys.readouterr().err
    assert err.count("Tableau answered 404 Resource Not Found") == 2
    assert asked == ["wb-1"]


def test_rebuild_sheet_refuses_when_tableau_errs_on_the_views(
    fakes, tmp_path, monkeypatch, capsys
):
    def answer(luid):
        raise TSC.ServerResponseError("404", "Resource Not Found", "gone")

    monkeypatch.setattr(fakes.tbl, "view_names", answer)
    path = _file(tmp_path, NO_REBUILD_CHECK)
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1
    assert (
        "refused: ada-region: Tableau answered 404 Resource Not Found"
    ) in capsys.readouterr().err
    assert not getattr(fakes.tbl, "captures", 0)


def test_rebuild_sheet_prints_the_blank_cells_it_skipped(fakes, tmp_path, capsys):
    # Camden is blank in the export and absent from the sheet query.
    fakes.tbl.exports = [
        [
            {"Region": "Newark", "Rate": "0.9123", "Count": "12"},
            {"Region": "Camden", "Rate": "", "Count": ""},
        ]
        for _ in range(2)
    ]
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert (
        "Skipped 2 blank cells (blank in the export, NULL in the sheet query)"
        in capsys.readouterr().out
    )
    assert load_view_config(path).comparisons[0].rebuild_check.cells == 2


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
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof.cells == 2
    # 1 total row in each of the 2 cuts.
    assert proof.totals_skipped == 2
    assert "skipped 1 total rows (All, *)" in capsys.readouterr().out


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

    cells, totals, _ = rebuild._export_cells(
        comparison,
        rows,
        {"Grade Level": "grade_level"},
        "Rate",
        columns,
        probe,
        shelf_dims=set(),
        ignored=set(),
    )

    assert cells == [
        {"grade_level": "0", "value": "0.94"},
        {"grade_level": "1", "value": "0.95"},
    ]
    assert totals == 1


def test_export_cells_count_identical_pane_rows_once():
    # A dual axis exports one row per pane; identical rows are one cell.
    comparison = Comparison(
        id="c",
        measure="m",
        dims=[ColumnPair(dashboard="region", cube="region_name")],
    )
    rows = [
        {"Region": "Camden", "Title": "A", "Distance": "0.12"},
        {"Region": "Camden", "Title": "A", "Distance": "0.12"},
        {"Region": "Newark", "Title": "A", "Distance": "0.3"},
        {"Region": "Newark", "Title": "B", "Distance": "0.3"},
    ]

    cells, _, _ = rebuild._export_cells(
        comparison,
        rows,
        {"Region": "region"},
        "Distance",
        [],
        [],
        shelf_dims=set(),
        ignored=set(),
    )

    assert cells == [
        {"region": "Camden", "value": "0.12"},
        {"region": "Newark", "value": "0.3"},
        {"region": "Newark", "value": "0.3"},
    ]


def test_export_cells_sum_every_split_row_even_identical_ones():
    # Summed split rows count each row: 2 that match in every exported column
    # are 2 rows of the split, not 2 panes of 1 row.
    comparison = Comparison(
        id="c",
        measure="m",
        dims=[ColumnPair(dashboard="region", cube="region_name")],
        split_rows="sum",
    )
    rows = [
        {"Region": "Camden", "Count": "5"},
        {"Region": "Camden", "Count": "5"},
    ]

    cells, _, summed = rebuild._export_cells(
        comparison,
        rows,
        {"Region": "region"},
        "Count",
        [],
        [],
        shelf_dims=set(),
        ignored=set(),
    )

    assert cells == [{"region": "Camden", "value": "10"}]
    assert summed == 1


def test_cell_keys_read_tableau_export_dates_as_the_same_day():
    # Tableau's export writes a date as M/D/YYYY; the probe and Cube write ISO.
    assert pipeline.value_key("9/21/2026") == "2026-09-21"
    assert pipeline.value_key("09/07/2026") == pipeline.value_key("2026-09-07")
    assert pipeline.value_key("2026-09-21T00:00:00.000") == "2026-09-21"
    assert pipeline.value_key("9/21") == "9/21"
    assert pipeline.value_key("13/45/2026") == "13/45/2026"


def test_prove_keeps_a_real_all_member(fakes, tmp_path, capsys):
    fakes.bq.sheet_query = [{"region": "All", "value": 0.9001}]
    fakes.tbl.exports = [[{"Region": "All", "Rate": "0.9001"}] for _ in range(2)]
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert load_view_config(path).comparisons[0].rebuild_check.cells == 2


def test_prove_asks_which_column_holds_the_value(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace("    sheet_field: Rate\n", ""))
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1

    err = capsys.readouterr().err
    assert "Rate" in err and "Count" in err and "sheet_field" in err


def test_prove_refuses_a_cut_with_no_rows(fakes, tmp_path, capsys):
    fakes.tbl.exports = [[{"Region": "Newark", "Rate": "0.9123", "Count": "1"}], []]
    argv = [
        "rebuild-sheet", str(_file(tmp_path)), "--comparison", "ada-region",
    ]  # fmt: skip

    assert cli.main(argv) == 1
    assert "Miami" in capsys.readouterr().err


def test_prove_does_not_write_a_failed_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, "    rebuild_check: null\n"))
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.5}]
    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region"]

    assert cli.main(argv) == 1

    assert load_view_config(path).comparisons[0].rebuild_check is None
    assert "sheet query" in capsys.readouterr().out


def _workbook_check(fakes, path, ids=None):
    cfg = load_view_config(path)
    chosen = [c for c in cfg.comparisons if ids is None or c.id in ids]
    return rebuild.workbook_check(chosen, tbl=fakes.tbl)


def test_prove_requires_a_comparison(fakes, tmp_path, capsys):
    assert cli.main(["rebuild-sheet", str(_file(tmp_path))]) == 2


def test_workbook_check_lists_stale_proofs(fakes, tmp_path):
    fakes.tbl.updated = datetime(2026, 10, 25, tzinfo=timezone.utc)

    (line,) = _workbook_check(fakes, _file(tmp_path))

    assert line.startswith("ada-region") and "re-run `rebuild-sheet`" in line


def test_workbook_check_is_empty_when_current(fakes, tmp_path, capsys):
    assert _workbook_check(fakes, _file(tmp_path)) == []
    assert capsys.readouterr().out == ""


def test_workbook_check_lists_only_the_comparisons_asked(fakes, tmp_path):
    head, rest = YML.split("  - id: ada-region\n", 1)
    path = _file(tmp_path, head + "  - id: first\n" + rest + "  - id: second\n" + rest)
    fakes.tbl.updated = datetime(2026, 10, 25, tzinfo=timezone.utc)

    lines = _workbook_check(fakes, path, {"first"})

    assert len(lines) == 1 and lines[0].startswith("first:")


DS_END = "        <calculation class='tableau' formula='COUNTD([row_key])' />\n      </column>\n    </datasource>"
DS_FILTER = (
    "        <calculation class='tableau' formula='COUNTD([row_key])' />\n      </column>\n"
    "      <filter class='categorical' column='[federated.0sample].[region]' />\n"
    "    </datasource>"
)


def _republished(fakes, tmp_path, source=True):
    from cube_validation.tableau import source_fingerprint

    twb = fakes.tbl.twb
    proof = REBUILD_CHECK.replace(
        "fingerprint: abc", f"fingerprint: {formula_fingerprint(twb, 'Rate by Region')}"
    )
    if source:
        proof += (
            f"      source_fingerprint: {source_fingerprint(twb, 'Rate by Region')}\n"
        )
    fakes.tbl.updated = datetime(2026, 10, 25, tzinfo=timezone.utc)
    return _file(tmp_path, YML.replace(REBUILD_CHECK, proof))


def test_workbook_check_keeps_a_proof_when_a_republish_left_the_sheet_alone(
    fakes, tmp_path, capsys
):
    path = _republished(fakes, tmp_path)

    assert _workbook_check(fakes, path) == []

    out = capsys.readouterr().out
    assert "ada-region: republished 2026-10-25T00:00:00+00:00, sheet unchanged" in out


def test_workbook_check_stales_a_proof_whose_datasource_filters_changed(
    fakes, tmp_path
):
    path = _republished(fakes, tmp_path)
    assert DS_END in fakes.tbl.twb
    fakes.tbl.twb = fakes.tbl.twb.replace(DS_END, DS_FILTER)

    (line,) = _workbook_check(fakes, path)

    assert (
        "a datasource's connection or filters changed; re-run `rebuild-sheet`" in line
    )


def test_workbook_check_stales_a_proof_that_predates_the_datasource_check(
    fakes, tmp_path
):
    path = _republished(fakes, tmp_path, source=False)

    (line,) = _workbook_check(fakes, path)

    assert "predates the datasource check; re-run `rebuild-sheet` once" in line


def test_workbook_check_stales_a_proof_whose_formulas_changed(fakes, tmp_path):
    fakes.tbl.updated = datetime(2026, 10, 25, tzinfo=timezone.utc)

    (line,) = _workbook_check(fakes, _file(tmp_path))

    assert "the sheet's formulas or filters changed; re-run `rebuild-sheet`" in line


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
            ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance"]
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "no_luid" in out
    assert "Attendance Rate" in out and "wb-1" in out
    assert fakes.cube.compiled_queries == [{"measures": ["v.avg_daily_attendance"]}]


@pytest.mark.parametrize(
    "argv", [[], ["compare"], ["nope", "x.yml"], ["rebuild-sheet", "x.yml"]]
)
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
        compare._cells(comparison, {}, dash, cube, 3)


# --- prove: sheet shape --------------------------------------------------------

NO_REBUILD_CHECK = YML.replace(REBUILD_CHECK, "    rebuild_check: null\n")
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
    path = _file(tmp_path, NO_REBUILD_CHECK)

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 0

    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof.missing_cuts == ["Team"]
    assert proof.missing_filters == ["Term"]
    assert proof.restricting_filters == []
    assert "Sheet cuts with no Cube member: Team" in capsys.readouterr().out


def test_prove_sums_split_rows_of_a_long_export(fakes, tmp_path, capsys):
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.9}]
    fakes.tbl.exports = [
        [
            {"Region": "Newark", "Team": "A", "Measure Names": "Rate", "Measure Values": "0.5"},
            {"Region": "Newark", "Team": "A", "Measure Names": "Count", "Measure Values": "9"},
            {"Region": "Newark", "Team": "B", "Measure Names": "Rate", "Measure Values": "0.4"},
        ]
        for _ in range(2)
    ]  # fmt: skip
    text = NO_REBUILD_CHECK.replace(
        "    sheet_field: Rate\n", "    sheet_field: Rate\n    split_rows: sum\n"
    )
    path = _file(tmp_path, text)

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 0, (
        capsys.readouterr().err
    )

    assert load_view_config(path).comparisons[0].rebuild_check.cells == 2
    assert "summed 1 split export rows" in capsys.readouterr().out


def test_prove_refuses_split_rows_unless_asked(fakes, tmp_path, capsys):
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.9}]
    fakes.tbl.exports = [
        [
            {"Region": "Newark", "Rate": "0.5", "Count": "1"},
            {"Region": "Newark", "Rate": "0.4", "Count": "1"},
        ]
        for _ in range(2)
    ]
    path = _file(tmp_path, NO_REBUILD_CHECK)

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 1

    out = capsys.readouterr().out
    assert "2 x more than 1 export row" in out
    saved = tmp_path / "cache" / "v" / "rebuild-failures-ada-region.txt"
    assert saved.read_text().count("more than 1 export row") == 2


def test_prove_failure_output_is_summarized(fakes, tmp_path, capsys):
    fakes.bq.sheet_query = [{"region": f"R{i}", "value": 0.5} for i in range(20)]
    fakes.tbl.exports = [
        [{"Region": f"R{i}", "Rate": "0.9", "Count": "1"} for i in range(20)]
        for _ in range(2)
    ]
    path = _file(tmp_path, NO_REBUILD_CHECK)

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 1

    out = capsys.readouterr().out
    assert "40 x value differs at the displayed decimals" in out
    assert "First 5 of 40:" in out
    assert out.count(": export ") == 5


def test_prove_several_comparisons_share_one_capture(fakes, tmp_path, capsys):
    block = NO_REBUILD_CHECK.split("comparisons:\n", 1)[1]
    text = NO_REBUILD_CHECK + block.replace("id: ada-region", "id: ada-twin")
    path = _file(tmp_path, text)
    argv = [
        "rebuild-sheet",
        str(path),
        "--comparison",
        "ada-region",
        "--comparison",
        "ada-twin",
    ]

    assert cli.main(argv) == 0, capsys.readouterr().err

    assert fakes.tbl.captures == 1
    assert all(c.rebuild_check is not None for c in load_view_config(path).comparisons)


def test_prove_keeps_going_after_one_refusal(fakes, tmp_path, capsys):
    argv = ["rebuild-sheet", str(_file(tmp_path, NO_REBUILD_CHECK)), "--comparison", "nope",
            "--comparison", "ada-region"]  # fmt: skip

    assert cli.main(argv) == 1

    assert "nope" in capsys.readouterr().err
    assert load_view_config(tmp_path / "v.yml").comparisons[0].rebuild_check is not None


def test_probe_fingerprint_covers_how_the_export_is_read(tmp_path):
    def fp(text):
        cfg = load_view_config(_file(tmp_path, text))
        return pipeline.sheet_query_fingerprint(cfg, cfg.comparisons[0])

    plain = YML.replace("    sheet_field: Rate\n", "")
    base = pipeline.decisions.sql_fingerprint(
        pipeline.sheet_query(
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


COMPUTED = YML.replace(
    "    dashboard_view: kipptaf_tableau.rpt_d\n",
    "    dashboard_view: kipptaf_tableau.rpt_d\n"
    "    dashboard_columns:\n"
    "      level3: \"if(band >= 3, 'At/Above', 'Below')\"\n",
)


def test_dashboard_columns_reach_every_dashboard_read(tmp_path):
    cfg = load_view_config(_file(tmp_path, COMPUTED))
    comparison = cfg.comparisons[0]
    derived = (
        "(SELECT *, if(band >= 3, 'At/Above', 'Below') AS level3 "
        f"FROM `{pipeline.PROJECT}`.`kipptaf_tableau`.`rpt_d`)"
    )

    assert derived in pipeline.dashboard_rows_sql(cfg, comparison)
    assert derived in pipeline.sheet_query(cfg, comparison, {})


def test_dashboard_columns_do_not_change_the_explanation_key(tmp_path):
    # trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
    from cube_validation.config import explanation_key

    plain = load_view_config(_file(tmp_path, YML)).comparisons[0]
    computed = load_view_config(_file(tmp_path, COMPUTED)).comparisons[0]

    assert explanation_key(plain) == explanation_key(computed)


# --- run: missing cuts and filters ----------------------------------------------

GAP_REBUILD_CHECK = (
    REBUILD_CHECK
    + """\
      missing_cuts: [Team]
      missing_filters: [Enroll Status]
      restricting_filters: [Enroll Status]
"""
)


def test_run_lists_missing_cuts_from_the_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, GAP_REBUILD_CHECK))

    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    assert "`Team` (cut) on Rate by Region: Cube has no member; ada-region" in out
    assert "(filter, set to chosen values, not All)" in out
    assert "2 missing cuts or filters to sort" in out


def test_run_says_when_a_proof_predates_missing_cuts(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    assert "ada-region: missing cuts and filters unknown" in capsys.readouterr().out


def test_gap_decision_quiets_a_missing_cut(fakes, tmp_path, capsys):
    text = (
        YML.replace(REBUILD_CHECK, GAP_REBUILD_CHECK)
        + """\
decisions:
  - id: no-team
    missing_cut: Team
    call: deliberate
    reason: homeroom label only
"""
    )
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    out = capsys.readouterr().out
    assert "1 missing cut or filter to sort" in out
    assert "`no-team` (missing cut `Team`, deliberate)" in out


def test_review_carries_a_domain_owner_missing_cut(fakes, tmp_path, capsys):
    text = (
        YML.replace(REBUILD_CHECK, GAP_REBUILD_CHECK)
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
    assert cli.main(["compare", str(path)]) == 0
    _write_sorted_everywhere(tmp_path)
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

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
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

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
    argv = ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
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


def test_discover_reads_a_local_workbook_without_tableau(
    fakes, tmp_path, monkeypatch, capsys
):
    def no_tableau():
        raise AssertionError("discover --twb must not sign in to Tableau")

    monkeypatch.setattr(cli, "tableau_session", no_tableau)
    twb = tmp_path / "roster.twb"
    twb.write_text((FIXTURES / "roster.twb").read_text())
    argv = ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
            "--caption", "# Tardy", "--twb", str(twb)]  # fmt: skip

    assert cli.main(argv) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    assert "'# Tardy'" in out
    assert "Roster (roster.twb): rows Region, Student Number" in out
    assert fakes.cube.compiled_queries == [{"measures": ["v.avg_daily_attendance"]}]


def test_find_field_marks_an_unpublished_sheet(fakes, tmp_path, monkeypatch, capsys):
    _exposures(tmp_path, monkeypatch)
    fakes.tbl.twb = (FIXTURES / "roster.twb").read_text()
    fakes.tbl.views = {"Other"}
    argv = ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
            "--caption", "# Tardy"]  # fmt: skip

    assert cli.main(argv) == 0, capsys.readouterr().err

    sheets = capsys.readouterr().out.split("Sheets:", 1)[1].splitlines()
    at = next(i for i, x in enumerate(sheets) if x.startswith("  Roster ("))
    assert sheets[at + 1] == "    not on a published dashboard"

    # A view on the server, the sheet publishes.
    fakes.tbl.views = {"Roster"}
    assert cli.main(argv) == 0
    assert "not on a published dashboard" not in capsys.readouterr().out

    def answer(luid):
        raise TSC.ServerResponseError("404", "Resource Not Found", "gone")

    monkeypatch.setattr(fakes.tbl, "view_names", answer)
    assert cli.main(argv) == 0
    sheets = capsys.readouterr().out.split("Sheets:", 1)[1].splitlines()
    at = next(i for i, x in enumerate(sheets) if x.startswith("  Roster ("))
    assert sheets[at + 1] == (
        "    published: not checked: Tableau answered 404 Resource Not Found"
    )


def test_find_field_does_not_guess_published_from_a_local_workbook(
    fakes, tmp_path, capsys
):
    twb = tmp_path / "roster.twb"
    twb.write_text((FIXTURES / "roster.twb").read_text())
    argv = ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
            "--caption", "# Tardy", "--twb", str(twb)]  # fmt: skip

    assert cli.main(argv) == 0, capsys.readouterr().err

    out = capsys.readouterr().out
    assert f"Sheets ({tableau.NOT_CHECKED}):" in out
    assert "not on a published dashboard" not in out


def test_discover_keeps_the_top_5_by_default(fakes, tmp_path, monkeypatch, capsys):
    _exposures(tmp_path, monkeypatch)
    fakes.tbl.twb = (FIXTURES / "roster.twb").read_text()
    argv = ["find-field", str(_file(tmp_path)), "--measure", "avg_daily_attendance",
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
    path = _file(tmp_path, NO_REBUILD_CHECK)
    before = path.read_text()

    assert (
        cli.main(
            ["rebuild-sheet", str(path), "--comparison", "ada-region", "--headers"]
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "ada-region cut {}: Region, Measure Names, Measure Values" in out
    assert "Measure Names: # Present, # Tardy" in out
    assert fakes.bq.ran == [] and path.read_text() == before


# --- Tableau sessions ------------------------------------------------------------

TWIN = NO_REBUILD_CHECK + NO_REBUILD_CHECK.split("comparisons:\n", 1)[1].replace(
    "id: ada-region", "id: ada-twin"
)
TWO = ["--comparison", "ada-region", "--comparison", "ada-twin"]


def test_prove_keeps_what_it_proved_when_tableau_ends_the_session(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path, TWIN)
    real = fakes.tbl.workbook_updated
    calls = []

    def workbook_updated(luid):
        # The second comparison finds the session gone for good.
        calls.append(luid)
        if len(calls) > 1:
            raise tableau.SessionEnded("Tableau ended the session again (401002)")
        return real(luid)

    fakes.tbl.workbook_updated = workbook_updated

    assert cli.main(["rebuild-sheet", str(path), *TWO]) == 1

    err = capsys.readouterr().err
    assert "during ada-twin. Matched and kept: ada-region." in err
    assert f"Rebuild the rest with: rebuild-sheet {path} --comparison ada-twin" in err
    proofs = [c.rebuild_check for c in load_view_config(path).comparisons]
    assert proofs[0] is not None and proofs[1] is None


def test_prove_refuses_one_comparison_on_another_tableau_error(fakes, tmp_path, capsys):
    fakes.tbl.fail_next = TSC.ServerResponseError("403004", "Forbidden", "")
    path = _file(tmp_path, TWIN)

    assert cli.main(["rebuild-sheet", str(path), *TWO]) == 1

    assert "ada-region: Tableau answered 403004 Forbidden" in capsys.readouterr().err
    proofs = [c.rebuild_check for c in load_view_config(path).comparisons]
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
        YML.replace(REBUILD_CHECK, GAP_REBUILD_CHECK)
        + """\
decisions:
  - id: team-cut
    missing_cut: Team
    call: domain_owner
    reason: the owner decides whether ADA needs a team cut
"""
    )
    path = _file(tmp_path, text)
    assert cli.main(["compare", str(path)]) == 0
    _write_sorted_everywhere(tmp_path)
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    captured = capsys.readouterr()
    assert "team-cut" in captured.err and "fill in" in captured.err
    assert "fill in" not in captured.out


def test_run_probes_again_without_dashboard_filters_only_when_set(fakes, tmp_path):
    def probes():
        return [s for s in fakes.bq.ran if "AS value" in s and "rpt_d" in s]

    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    plain = len(probes())
    fakes.bq.ran.clear()
    text = YML.replace(
        "    rows:\n",
        "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n    rows:\n",
        1,
    )
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0
    assert len(probes()) == 2 * plain
    assert sum("enroll_status IN (0)" not in s for s in probes()) == plain


def test_run_opens_cell_differences(fakes, tmp_path, capsys):
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95}]
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    out = capsys.readouterr().out
    section = out.split("## Cell differences", 1)[1].split("## ", 1)[0]
    # No unmatched row lies in a Newark cell: a formula difference.
    assert "ada-region formula difference: 2 differ" in section
    assert "Cube computes `avg_daily_attendance` as" in section


DEFINED = YML.replace(
    "    rows:\n",
    '    definitions: { dashboard: "present days over days", cube: "sum over count" }\n'
    "    rows:\n",
    1,
)
NEWARK_MATCHES = [RECONCILE_ROWS[0]]


def _latest_run(tmp_path):
    saved = sorted(
        (tmp_path / "cache" / "v").glob("*/run.json"), key=lambda p: p.stat().st_mtime
    )
    return saved[-1]


def _sorted_items(path, tmp_path):
    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    loaded = json.loads((_latest_run(tmp_path).parent / "triage.json").read_text())
    return {i["id"]: i for i in loaded["items"]}


def test_a_cell_whose_rows_all_match_is_a_formula_difference(fakes, tmp_path):
    # Newark differs in both cuts; the reconcile's only unmatched rows are Miami's.
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95}]
    path = _file(tmp_path, DEFINED)
    assert cli.main(["compare", str(path)]) == 0

    saved = json.loads(_latest_run(tmp_path).read_text())
    (formula,) = saved["applied"]["open_cells"]
    assert (formula["kind"], formula["counts"]) == ("formula", {"differs": 2})
    # Each saved cell says which item holds it, for link_cells and hand checks.
    assert {c["kind"] for c in saved["diff_cells"]} == {"formula"}
    assert formula["causes"][0] == "2 differing cells hold no unmatched row"
    assert formula["causes"][-1] == (
        "Recorded definitions: dashboard present days over days; Cube sum over count"
    )

    items = _sorted_items(path, tmp_path)
    item = items["ada-region:formula"]
    assert (item["kind"], item["suggestion"]) == ("formula", "cause")
    assert item["proof"]["kind"] == "formula"
    assert item["stub"] == {"comparison": "ada-region", "formula": True}
    assert "ada-region:cells" not in items


def test_a_cell_that_gains_a_row_leaves_the_formula_claim(fakes, tmp_path, capsys):
    # Run 1: Newark (cell A) and Camden (cell B) differ with every row matched.
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.9123},
                      {"region": "Camden", "value": 0.9}]  # fmt: skip
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95},
                      {"regions_region_name": "Camden", "value": 0.95}]  # fmt: skip
    fakes.bq.reconcile = NEWARK_MATCHES
    path = _file(tmp_path, DEFINED)
    assert cli.main(["compare", str(path)]) == 0
    assert set(_sorted_items(path, tmp_path)) == {"ada-region:formula"}
    approved = _approved(tmp_path, [{"id": "which-rate", "call": "domain_owner",
                                     "reason": "Which rate is right?",
                                     "item": "ada-region:formula"}])  # fmt: skip
    assert cli.main(["decide", str(path), str(approved)]) == 0
    (decision,) = load_view_config(path).decisions
    assert decision.formula and decision.fingerprints == _saved_fingerprints(tmp_path)

    # Run 2: an unproven Cube-only group lands in Newark under the default cut.
    fakes.bq.reconcile = NEWARK_MATCHES + [
        {"bucket": "cube_only", "regions_region_name": "Newark", "n_rows": 5,
         "n_students": 5, "__s_k0_c_rows": 5, "__s_k0_d_rows": 0,
         "__s_k1_c_rows": 0, "__s_k1_d_rows": 0},
    ]  # fmt: skip
    # Changed data alone leaves the result current: compare it again on purpose.
    assert cli.main(["compare", str(path), "--all"]) == 0

    saved = json.loads(_latest_run(tmp_path).read_text())
    applied = saved["applied"]
    (cells,) = applied["open_cells"]
    assert (cells["kind"], cells["counts"]) == ("cells", {"differs": 1})
    kinds = {(c["cut"], c["key"]): c["kind"] for c in saved["diff_cells"]}
    assert kinds == {
        ("{}", "regions_region_name=Camden"): "formula",
        ("{}", "regions_region_name=Newark"): "cells",
        ('{"Region": "Miami"}', "regions_region_name=Camden"): "formula",
        ('{"Region": "Miami"}', "regions_region_name=Newark"): "formula",
    }
    ((d, quiet),) = applied["quiet_cells"]
    assert d["id"] == "which-rate"
    # Camden under both cuts, Newark under the Miami cut, where it has no row.
    assert (quiet["kind"], quiet["counts"]) == ("formula", {"differs": 3})
    items = _sorted_items(path, tmp_path)
    assert items["ada-region:cells"]["suggestion"] == "investigate"
    assert "ada-region:formula" not in items


def test_a_run_saved_before_formula_differences_reads_its_cells_as_cell_sets(
    fakes, tmp_path
):
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95}]
    path = _file(tmp_path, DEFINED)
    assert cli.main(["compare", str(path)]) == 0
    saved = json.loads(_latest_run(tmp_path).read_text())
    (formula,) = saved["applied"]["open_cells"]
    decision = {"id": "f", "comparison": "ada-region", "call": "deliberate",
                "reason": "r"}  # fmt: skip
    saved["applied"]["quiet_cells"] = [[decision, dict(formula)]]
    for diff in (formula, saved["applied"]["quiet_cells"][0][1]):
        del diff["kind"]
    for cell in saved["diff_cells"]:
        del cell["kind"]

    run = results._run_from_json(saved)

    assert [d.kind for d in run.applied.open_cells] == ["cells"]
    assert [d.kind for _, d in run.applied.quiet_cells] == ["cells"]


def test_an_unplaceable_cell_is_never_a_formula_difference(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.95}]
    text = (
        YML.split("    rows:\n", 1)[0] + REBUILD_CHECK + YML.split(REBUILD_CHECK, 1)[1]
    )
    path = _file(tmp_path, text)
    assert cli.main(["compare", str(path)]) == 0

    (diff,) = json.loads(_latest_run(tmp_path).read_text())["applied"]["open_cells"]
    assert (diff["kind"], diff["counts"]) == ("cells", {"differs": 2})
    assert not any("hold no unmatched row" in c for c in diff["causes"])


def _saved_run(tmp_path):
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    return json.loads(saved.read_text())


def test_run_saves_differing_cells_and_their_pinned_sql(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    saved = _saved_run(tmp_path)
    first = saved["diff_cells"][0]
    assert first == {
        "comparison": "ada-region",
        "cut": "{}",
        "key": "regions_region_name=Miami",
        "dims": [["regions_region_name", "Miami"]],
        "dashboard": None,
        "cube": 0.95,
        "n_students": 12,
        # The Miami group's dashboard-side rows lie in it.
        "kind": "cells",
    }
    # Each cell carries its own cut's count, not one shared across cuts.
    assert [(c["cut"], c["key"], c["n_students"]) for c in saved["diff_cells"]] == [
        ("{}", "regions_region_name=Miami", 12),
        ("{}", "regions_region_name=Newark", 40),
        ('{"Region": "Miami"}', "regions_region_name=Miami", 3),
        ('{"Region": "Miami"}', "regions_region_name=Newark", 5),
    ]
    (count,) = [s for s in fakes.bq.ran if "AS n_students" in s and "-- outer" not in s]
    every, miami = _count_branches(count)
    assert "FOR SYSTEM_TIME AS OF" in every
    assert _literal_after(every, "rpt_d") == utc_literal(START)
    assert "'Camden', 'Newark'" in every and "'Miami'" not in every
    assert "'Miami'" in miami and "'Newark'" not in miami

    sql = saved["cell_sql"]["ada-region"]
    assert set(sql) == {"{}", '{"Region": "Miami"}'}
    dashboard, cube = sql["{}"]
    assert "FOR SYSTEM_TIME AS OF" in dashboard and "rpt_d" in dashboard
    assert "FOR SYSTEM_TIME AS OF" in cube and "AS value FROM (" in cube
    assert dashboard in fakes.bq.ran and cube in fakes.bq.ran
    usd = saved["cell_sql_usd"]["ada-region"]
    assert set(usd) == set(sql) and all(len(v) == 2 for v in usd.values())
    # A cell is sized by coverage, from each group's rows per cut.
    assert "cell_rows" not in saved and "cell_students" not in saved
    (group,) = saved["applied"]["open"]
    assert group["cut_rows"] == [["{}", 0, 30], ['{"Region": "Miami"}', 0, 30]]


def test_run_counts_a_cells_students_under_its_dashboard_filters(fakes, tmp_path):
    text = YML.replace(
        "    rows:\n",
        "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n    rows:\n",
        1,
    )
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    (count,) = [s for s in fakes.bq.ran if "AS n_students" in s and "-- outer" not in s]
    assert all("enroll_status IN (0)" in b for b in _count_branches(count))


def test_run_saves_each_sides_dry_run_price_outside_the_cap(fakes, tmp_path):
    fakes.bq.cost = lambda sql: 0.5 if "FOR SYSTEM_TIME" in sql else 0.0
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    args = [
        "compare",
        str(_file(tmp_path)),
        "--max-usd",
        "50",
        "--max-usd-per-day",
        "50",
    ]
    assert cli.main(args) == 0

    saved = _saved_run(tmp_path)
    assert saved["cell_sql_usd"]["ada-region"]["{}"] == pytest.approx([0.5, 0.5])
    ran = [s for s in fakes.bq.ran if "FOR SYSTEM_TIME" in s]
    assert saved["cost_usd"] == pytest.approx(0.5 * len(ran), abs=0.01)
    ledger = json.loads((tmp_path / "cache" / "spend.json").read_text())
    assert sum(ledger.values()) == pytest.approx(saved["cost_usd"], abs=0.01)


def test_run_without_rows_leaves_n_students_none(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    text = (
        YML.split("    rows:\n", 1)[0] + REBUILD_CHECK + YML.split(REBUILD_CHECK, 1)[1]
    )
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    saved = _saved_run(tmp_path)
    assert saved["diff_cells"]
    assert all(c["n_students"] is None for c in saved["diff_cells"])
    assert not any("n_students" in s for s in fakes.bq.ran)
    assert set(saved["cell_sql"]["ada-region"]) == {"{}", '{"Region": "Miami"}'}


STUDENT_GRAIN = (
    "        - { dashboard: student_number, cube: lea_student_identifier }\n"
)
DATE_GRAIN = "        - { dashboard: calendardate, cube: attendance_date }\n"


def test_run_counts_the_grains_student_column_wherever_it_sits(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    text = YML.replace(STUDENT_GRAIN + DATE_GRAIN, DATE_GRAIN + STUDENT_GRAIN)
    assert text != YML
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    (count,) = [s for s in fakes.bq.ran if "AS n_students" in s and "-- outer" not in s]
    assert "COUNT(DISTINCT student_number)" in count
    assert "COUNT(DISTINCT calendardate)" not in count


def test_run_without_a_student_grain_leaves_n_students_none(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    text = YML.replace(STUDENT_GRAIN, "")
    assert text != YML
    assert cli.main(["compare", str(_file(tmp_path, text))]) == 0

    saved = _saved_run(tmp_path)
    assert saved["diff_cells"]
    assert all(c["n_students"] is None for c in saved["diff_cells"])
    assert not any("COUNT(DISTINCT" in s and "-- outer" not in s
                   for s in fakes.bq.ran if "AS n_students" in s)  # fmt: skip


def test_run_saves_no_cell_that_passes(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0

    assert _saved_run(tmp_path)["diff_cells"] == []


def test_old_run_json_without_new_fields_still_loads(fakes, tmp_path):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    saved = _saved_run(tmp_path)
    for name in ("diff_cells", "cell_sql", "cell_sql_usd"):
        del saved[name]

    result = results._run_from_json(saved)

    assert result.diff_cells == [] and result.cell_sql == {}
    assert result.cell_sql_usd == {}


@pytest.mark.parametrize("key", ["strongest", "findings"])
def test_an_old_run_json_with_a_measure_s_findings_is_older(
    fakes, tmp_path, capsys, key
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    data["measures"][0][key] = []
    saved.write_text(json.dumps(data))
    capsys.readouterr()

    assert cli.main(["ask-owner", str(_file(tmp_path)), "--domain", "Registrar"]) == 1
    assert "older validator" in capsys.readouterr().err


def test_run_json_round_trips_the_hand_check_fields(fakes, tmp_path):
    fakes.bq.cells = [{"regions_region_name": "Miami", "value": 0.95}]
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    saved = _saved_run(tmp_path)

    result = results._run_from_json(saved)

    assert result.diff_cells == saved["diff_cells"]
    assert result.cell_sql == saved["cell_sql"]
    assert result.cell_sql_usd == saved["cell_sql_usd"]


def test_prove_sets_a_parameter_on_the_copy(fakes, tmp_path, capsys):
    text = NO_REBUILD_CHECK.replace(
        "    sheet_field: Rate\n",
        "    sheet_field: Rate\n    parameters: { Basis: Year end }\n",
    )
    path = _file(tmp_path, text)

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 0, (
        capsys.readouterr().err
    )

    assert "value='&quot;Year end&quot;'" in fakes.tbl.edited
    assert load_view_config(path).comparisons[0].rebuild_check is not None


def test_comparisons_with_different_parameters_capture_apart(fakes, tmp_path, capsys):
    year_end = TWIN.replace(
        "  - id: ada-twin\n", "  - id: ada-twin\n    parameters: { Basis: Year end }\n"
    )
    path = _file(tmp_path, year_end)

    assert cli.main(["rebuild-sheet", str(path), *TWO]) == 0, capsys.readouterr().err
    assert fakes.tbl.captures == 2


def test_probe_fingerprint_covers_parameters(tmp_path):
    def fp(text):
        cfg = load_view_config(_file(tmp_path, text))
        return pipeline.sheet_query_fingerprint(cfg, cfg.comparisons[0])

    with_param = YML.replace(
        "    sheet_field: Rate\n",
        "    sheet_field: Rate\n    parameters: { Basis: Year end }\n",
    )
    assert fp(with_param) != fp(YML)


RESHAPED = "    shelves: { drop: [Team, Region], add: { cols: [Region] } }\n"


def _reshaped(text):
    return text.replace("    sheet_field: Rate\n", "    sheet_field: Rate\n" + RESHAPED)


def test_prove_reshapes_the_copy_and_records_it(fakes, tmp_path, capsys):
    fakes.tbl.twb = _with_team(fakes.tbl.twb)
    path = _file(tmp_path, _reshaped(NO_REBUILD_CHECK))

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 0, (
        capsys.readouterr().err
    )

    assert "<rows />" in fakes.tbl.edited
    # Region crosses in front of the measures, as Tableau writes a dimension
    # against measures.
    assert "([federated.0sample].[none:region:nk] * (" in fakes.tbl.edited
    assert "+ [federated.0sample].[usr:Calculation_1002:qk]))" in fakes.tbl.edited
    proof = load_view_config(path).comparisons[0].rebuild_check
    assert proof.shelves == {"drop": ["Team", "Region"], "add": {"cols": ["Region"]}}
    # Team left the copy's shelves, so it is no longer a missing cut.
    assert proof.missing_cuts == []


def test_prove_headers_shows_the_reshaped_sheet(fakes, tmp_path, capsys):
    fakes.tbl.twb = _with_team(fakes.tbl.twb)
    path = _file(tmp_path, _reshaped(NO_REBUILD_CHECK))

    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region", "--headers"]
    assert cli.main(argv) == 0, capsys.readouterr().err

    assert "ada-region reshaped: rows none; columns Region" in capsys.readouterr().out


def test_prove_headers_names_the_table_calcs_a_reshape_changes(fakes, tmp_path, capsys):
    fakes.tbl.twb = (FIXTURES / "dki_grid.twb").read_text()
    fakes.tbl.views = {"Mastery Grid"}
    text = (
        NO_REBUILD_CHECK.replace("sheet: Rate by Region", "sheet: Mastery Grid")
        .replace(
            "    sheet_field: Rate\n",
            "    sheet_field: Rate\n    shelves: { drop: [Week Start Monday], "
            "add: { rows: [Subject Area] } }\n",
        )
        .replace(
            "      - { dashboard: region, cube: regions_region_name }\n    filters:",
            "      - { dashboard: region, cube: regions_region_name }\n"
            "      - { dashboard: subject_area, cube: academic_subject }\n    filters:",
        )
    )
    path = _file(tmp_path, text)

    argv = ["rebuild-sheet", str(path), "--comparison", "ada-region", "--headers"]
    assert cli.main(argv) == 0, capsys.readouterr().err

    assert (
        "ada-region reshaped: rows Grade Level, Subject Area; columns Module Code, "
        "School; removed the table calcs Difference in Avg. Is Mastery Int (along "
        "Week Start Monday, Module Code); recomputes along the new rows: "
        "Difference in Avg. Is Mastery Int"
    ) in capsys.readouterr().out


def test_prove_refuses_a_drop_off_the_sheet(fakes, tmp_path, capsys):
    path = _file(tmp_path, _reshaped(NO_REBUILD_CHECK))

    assert cli.main(["rebuild-sheet", str(path), "--comparison", "ada-region"]) == 1

    assert "'Team' is not on the rows or columns" in capsys.readouterr().err


def test_probe_fingerprint_covers_shelves(tmp_path):
    def fp(text):
        cfg = load_view_config(_file(tmp_path, text))
        return pipeline.sheet_query_fingerprint(cfg, cfg.comparisons[0])

    other = _reshaped(YML).replace("drop: [Team, Region]", "drop: [Region]")
    cleared = _reshaped(YML).replace("add:", "clear_filters: [Team], add:")
    assert len({fp(YML), fp(_reshaped(YML)), fp(other), fp(cleared)}) == 4


def test_reshape_text_names_cleared_filters():
    shelves = {"drop": ["Week"], "clear_filters": ["Discipline", "Term"]}
    assert (
        rebuild.reshape_text(shelves)
        == "dropped Week; cleared the filters on Discipline, Term"
    )


def test_reshape_text_names_removed_and_recomputed_table_calcs():
    reshaped = tableau.Reshaped(
        "<workbook />",
        removed=("Difference in Avg. X (along Week)",),
        recomputed={"rows": ("Difference in Avg. X",), "columns": ("Rank of Y",)},
    )

    assert rebuild.reshape_text({"drop": ["Week"]}, reshaped) == (
        "dropped Week; removed the table calcs Difference in Avg. X (along Week); "
        "recomputes along the new rows: Difference in Avg. X; recomputes along "
        "the new columns: Rank of Y"
    )


def test_run_names_a_reshaped_proof(fakes, tmp_path, capsys):
    path = _file(tmp_path, _reshaped(YML))

    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err

    section = (
        capsys.readouterr().out.split("## Rebuild checks", 1)[1].split("## ", 1)[0]
    )
    assert (
        "ada-region: last matched 2026-10-26T12:00:00+00:00; matched on a reshaped "
        "copy: dropped Team, Region; added Region to columns" in section
    )
    assert results._run_from_json(_saved_run(tmp_path)).reshaped == {
        "ada-region": "dropped Team, Region; added Region to columns"
    }


def test_the_daily_cap_refuses_a_run_across_runs(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 4.0 if "fct_f" in sql else 0.0
    assert cli.main(["compare", str(_file(tmp_path)), "--max-usd", "50"]) == 1

    err = capsys.readouterr().err
    assert "daily cap" in err and "--max-usd-per-day" in err


# --- triage ------------------------------------------------------------------


def test_triage_re_runs_the_stored_proofs_unless_told_not_to(
    fakes, tmp_path, monkeypatch
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    seen = []
    monkeypatch.setattr(
        explain, "run_stored", lambda cfg, run, d, **k: seen.append(d) or []
    )

    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    assert cli.main(["sort", str(path), "--no-trace", "--no-explanations"]) == 0

    assert seen == [path.parent / "explanations" / "v"]


def test_triage_of_one_comparison_prints_its_items_and_keeps_every_item(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _four(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    seen = []
    monkeypatch.setattr(
        explain, "run_stored", lambda cfg, run, d, **k: seen.append(k) or []
    )
    capsys.readouterr()

    assert (
        cli.main(["sort", str(path), "--no-trace", "--comparison", "ada-region-2"]) == 0
    )

    out = capsys.readouterr().out
    assert "ada-region-2:" in out and "ada-region-1:" not in out
    (saved,) = (tmp_path / "cache" / "v").glob("*/triage.json")
    kept = {i["comparison"] for i in json.loads(saved.read_text())["items"]}
    assert {"ada-region-1", "ada-region-2"} <= kept
    (kwargs,) = seen
    assert kwargs["comparisons"] == {"ada-region-2"}
    assert kwargs["progress_dir"] == saved.parent


def test_triage_refuses_a_comparison_the_view_lacks(fakes, tmp_path, capsys):
    path = _four(tmp_path)
    assert cli.main(["compare", str(path)]) == 0

    assert cli.main(["sort", str(path), "--no-trace", "--comparison", "nope"]) == 1

    assert "nope" in capsys.readouterr().err


def test_triage_proves_first_and_traces_only_what_no_proof_explains(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(saved.read_text()))
    (group,) = run.applied.open
    proof = explain.Explanation(
        path.parent / "explanations" / "v" / f"ada-region__{group.bucket}.sql",
        "ada-region",
        group.bucket,
        {"C1": ("dashboard", "the sheet drops them")},
        "SELECT 1",
    )
    order = []

    def stored(cfg, run_, d, **k):
        order.append("proofs")
        items = explain._bucket_items(run_, "ada-region", group.bucket)
        found = {i: explain.Outcome(g.n_rows, Counter({"C1": g.n_rows}))
                 for i, g in items}  # fmt: skip
        return [explain.Ran(proof, items, found)]

    def traced(cfg, run_, *, skip, **k):
        order.append("trace")
        assert skip == {trace.item_key(group)}
        # A cap stops the trace: it never un-proves what a proof explained.
        return trace.TraceResult({})

    monkeypatch.setattr(explain, "run_stored", stored)
    monkeypatch.setattr(trace, "trace_run", traced)
    monkeypatch.setattr(trace, "check_ready", lambda *a, **k: order.append("ready"))

    assert cli.main(["sort", str(path)]) == 0

    # The trace's own refusals come before any proof spends.
    assert order == ["ready", "proofs", "trace"]
    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    (item,) = [i for i in items if i["kind"] == "group"]
    assert item["suggestion"] == "cause"
    assert item["proof"]["path"] == f"explanations/v/ada-region__{group.bucket}.sql"


def test_triage_classifies_a_group_a_group_decision_closes(
    fakes, tmp_path, monkeypatch
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(saved.read_text()))
    assert run.applied.open == []
    ((_, group),) = run.applied.quiet
    proof = explain.Explanation(
        path.parent / "explanations" / "v" / f"ada-region__{group.bucket}.sql",
        "ada-region",
        group.bucket,
        {"C1": ("dashboard", "the sheet drops them")},
        "SELECT 1",
    )

    def stored(cfg, run_, d, **k):
        items = explain._bucket_items(run_, "ada-region", group.bucket)
        found = {i: explain.Outcome(g.n_rows, Counter({"C1": g.n_rows}))
                 for i, g in items}  # fmt: skip
        return [explain.Ran(proof, items, found)]

    monkeypatch.setattr(explain, "run_stored", stored)
    monkeypatch.setattr(trace, "trace_run", lambda *a, **k: trace.TraceResult({}))
    monkeypatch.setattr(trace, "check_ready", lambda *a, **k: None)

    assert cli.main(["sort", str(path)]) == 0

    loaded = json.loads((saved.parent / "triage.json").read_text())
    # Closed, so never an item; the proof still says which causes it holds.
    assert not [i for i in loaded["items"] if i["kind"] == "group"]
    (closed,) = loaded["closed"]
    assert closed["key"] == sort._open_key(group)
    assert closed["cause"] == [
        {"side": "dashboard", "step": "C1", "label": "the sheet drops them",
         "n_rows": group.n_rows}
    ]  # fmt: skip
    assert closed["proof"]["path"] == f"explanations/v/ada-region__{group.bucket}.sql"


def test_triage_confirm_reaches_its_command(fakes, tmp_path, monkeypatch):
    path = _file(tmp_path)
    seen = {}
    monkeypatch.setattr(
        explain, "explain", lambda cfg, view_file, **k: seen.update(k) or 0
    )

    assert (
        cli.main(
            ["explain", str(path), "--comparison", "ada-region",
             "--bucket", "cube_only", "--cause", "C1=cube:words",
             "--items", "a,b", "--items", "c"]
        )
        == 0
    )  # fmt: skip

    assert seen["comparison"] == "ada-region" and seen["bucket"] == "cube_only"
    assert seen["causes"] == ["C1=cube:words"] and seen["items"] == ["a", "b", "c"]
    assert "cells" not in seen


def test_explain_requires_a_bucket(fakes, tmp_path, monkeypatch):
    path = _file(tmp_path)
    monkeypatch.setattr(explain, "explain", lambda *a, **k: pytest.fail("explain ran"))

    # Every explanation explains one bucket.
    assert cli.main(["explain", str(path), "--comparison", "ada-region"]) == 2


def test_triage_command_writes_triage_json_beside_latest_run(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    capsys.readouterr()

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    out = capsys.readouterr().out
    written = json.loads((saved.parent / "triage.json").read_text())
    assert written["view"] == "v"
    assert (
        written["decisions_fingerprint"]
        == json.loads(saved.read_text())["decisions_fingerprint"]
    )
    assert set(written["moment"]) == {"start", "end", "job_id", "moments"}
    assert written["moment"]["moments"] == {"ada-region": "2026-10-22T204400Z"}
    run = results._run_from_json(json.loads(saved.read_text()))
    assert written["open"] == sort.open_keys(run) and written["open"]
    item = written["items"][0]
    assert set(item) == {
        "id", "kind", "comparison", "label", "stub",
        "suggestion", "evidence", "evidence_posted", "candidates", "cause",
        "proof", "key", "decisions", "decided", "default_call",
    }  # fmt: skip
    assert item["stub"]["group"]["values"] == ["Miami"]
    assert (item["suggestion"], item["cause"]) == ("investigate", None)
    assert "investigate (" in out and item["label"] in out


def test_triage_refuses_when_decisions_changed_since_run(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    capsys.readouterr()

    assert cli.main(["sort", str(path)]) == 1

    err = capsys.readouterr().err
    assert "decisions" in err and "`compare`" in err
    assert not list((tmp_path / "cache" / "v").glob("*/triage.json"))


def test_triage_takes_fact_dataset_and_refuses_a_bad_one(fakes, tmp_path, capsys):
    code = cli.main(["sort", str(_file(tmp_path)), "--fact-dataset", "kipptaf_staging"])

    assert code == 1
    assert "fact dataset" in capsys.readouterr().err


def test_triage_runs_a_value_check_and_records_the_verdict(fakes, tmp_path, capsys):
    proof = REBUILD_CHECK + (
        "      missing_cuts: []\n"
        "      missing_filters: [School Level]\n"
        "      restricting_filters: [School Level]\n"
        "      missing_columns: { School Level: school_level }\n"
    )
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, proof))
    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    fakes.cube.meta = lambda: {
        "cubes": [
            {
                "name": "v",
                "dimensions": [{"name": "v.school_level", "title": "School Level"}],
            }
        ]
    }
    fakes.cube._load = lambda q: [{"v.school_level": "MS"}]
    fakes.bq.ran.clear()
    capsys.readouterr()

    assert cli.main(["sort", str(path), "--no-trace"]) == 0, capsys.readouterr().err

    assert any("DISTINCT CAST(school_level AS STRING)" in s for s in fakes.bq.ran)
    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    (gap,) = [i for i in items if i["kind"] == "gap"]
    assert "school_level: same field, different coding" in gap["evidence"]
    assert "MS" not in json.dumps(items)


def test_triage_no_trace_skips_the_trace(fakes, tmp_path, capsys, monkeypatch):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    monkeypatch.setattr(trace, "trace_run", lambda *a, **k: pytest.fail("traced"))

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    (group,) = [i for i in items if i["kind"] == "group"]
    assert group["suggestion"] == "investigate"
    assert group["evidence"][0] == sort.NOT_TRACED


def test_triage_traces_the_rows_by_default(fakes, tmp_path, capsys, monkeypatch):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(saved.read_text()))
    seen = {}

    def traced(
        cfg, run_, *, wh, cube, manifest_path, max_minutes, skip, prepared, ticker
    ):
        seen["manifest"], seen["minutes"] = manifest_path, max_minutes
        found = {}
        for g in run_.applied.open:
            t = trace.ItemTrace("dashboard", g.n_rows)
            t.steps["dashboard:main:1"] = g.n_rows
            t.labels["dashboard:main:1"] = "main: region <> 'Miami'"
            found[trace.item_key(g)] = t
        return trace.TraceResult(found)

    monkeypatch.setattr(trace, "trace_run", traced)
    monkeypatch.setattr(trace, "check_ready", lambda *a, **k: None)
    manifest = tmp_path / "m.json"
    capsys.readouterr()

    assert (
        cli.main(
            [
                "sort",
                str(path),
                "--manifest",
                str(manifest),
                "--trace-max-minutes",
                "5",
            ]
        )
        == 0
    )

    assert seen == {"manifest": manifest, "minutes": 5.0}
    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    groups = [i for i in items if i["kind"] == "group"]
    assert len(groups) == len(run.applied.open)
    # The trace leads; it never proves.
    assert {i["suggestion"] for i in groups} == {"investigate"}
    assert groups[0]["cause"] is None
    assert groups[0]["evidence"][0].startswith(
        "lead: relaxing main: region <> 'Miami' brings back "
    )
    assert "investigate (" in capsys.readouterr().out


# The real one: `_cache_in_tmp` replaces it in every test.
_CACHE_ROOT = cli.cache_root


def test_cache_root_follows_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(cli.CACHE_VAR, str(tmp_path / "copy"))
    assert _CACHE_ROOT() == tmp_path / "copy"

    monkeypatch.delenv(cli.CACHE_VAR)
    assert _CACHE_ROOT() == report.CACHE_ROOT


def test_a_moved_cache_keeps_the_machine_s_spend_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv(cli.CACHE_VAR, str(tmp_path / "copy"))
    monkeypatch.setattr(cli, "cache_root", _CACHE_ROOT)
    monkeypatch.setattr(report, "CACHE_ROOT", tmp_path / "default")
    monkeypatch.setattr(cli, "make_warehouse", lambda: Warehouse(client=object()))

    wh = cli._warehouse(SimpleNamespace(max_usd_per_day=3.0))
    wh._record(0.5)

    assert (tmp_path / "default" / "spend.json").exists()
    assert not (tmp_path / "copy" / "spend.json").exists()


def test_triage_writes_its_batch_when_the_trace_stops(
    fakes, tmp_path, capsys, monkeypatch
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(saved.read_text()))
    (open_group,) = run.applied.open
    stopped = trace.ItemTrace("dashboard", open_group.n_rows)
    stopped.unknown = open_group.n_rows
    stopped.stopped = "the trace passed its time limit"
    monkeypatch.setattr(trace, "check_ready", lambda *a, **k: None)
    monkeypatch.setattr(
        trace,
        "trace_run",
        lambda *a, **k: trace.TraceResult({trace.item_key(open_group): stopped}),
    )

    assert cli.main(["sort", str(path)]) == 0

    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    (group,) = [i for i in items if i["kind"] == "group"]
    assert group["suggestion"] == "investigate"
    assert "trace stopped: the trace passed its time limit" in group["evidence"]


def test_a_value_check_past_the_cap_still_writes_the_batch(
    fakes, tmp_path, capsys, monkeypatch
):
    # N10: a cap hit in the value checks leaves the trace's work in place.
    proof = REBUILD_CHECK + (
        "      missing_cuts: []\n"
        "      missing_filters: [School Level]\n"
        "      restricting_filters: [School Level]\n"
        "      missing_columns: { School Level: school_level }\n"
    )
    path = _file(tmp_path, YML.replace(REBUILD_CHECK, proof))
    assert cli.main(["compare", str(path)]) == 0, capsys.readouterr().err
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    fakes.cube.meta = lambda: {
        "cubes": [
            {
                "name": "v",
                "dimensions": [{"name": "v.school_level", "title": "School Level"}],
            }
        ]
    }

    def capped(*a, **k):
        raise CostCapError("spent $5.00, over the $5.00 cap")

    monkeypatch.setattr(sort, "value_check", capped)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0, capsys.readouterr().err

    items = json.loads((saved.parent / "triage.json").read_text())["items"]
    (gap,) = [i for i in items if i["kind"] == "gap"]
    assert any(e.startswith("school_level: not checked:") for e in gap["evidence"])


def _miami_differs(fakes, tmp_path, path=None):
    """Compare a run whose Miami cells differ, each holding the dashboard-only
    Miami group, while Newark passes."""
    fakes.bq.sheet_query = [{"region": "Newark", "value": 0.9123},
                            {"region": "Miami", "value": 0.5}]  # fmt: skip
    fakes.bq.cells = [{"regions_region_name": "Newark", "value": 0.91234},
                      {"regions_region_name": "Miami", "value": 0.95}]  # fmt: skip
    path = path or _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    return path


# A formula check query: each cut's tag (`formula.dashboard_side_sql`).
FORMULA_QUERY = "AS __cut, * FROM"


def _formula_runs(bq, since=0):
    return [
        sql for kind, sql in bq.log[since:] if kind == "run" and FORMULA_QUERY in sql
    ]


def _triage(tmp_path):
    return json.loads((_latest_run(tmp_path).parent / "triage.json").read_text())


def test_sort_prices_the_formula_check_with_the_explanations(
    fakes, tmp_path, capsys, monkeypatch
):
    path = _miami_differs(fakes, tmp_path)
    # A stored explanation of the Miami group, priced at $2 against the
    # formula check's $4, so only the two together pass a $5 cap.
    explained = path.parent / "explanations" / "v" / "ada-region__dashboard_only.sql"
    explained.parent.mkdir(parents=True, exist_ok=True)
    explained.write_text(
        "-- cause C1 = dashboard: the sheet drops them\n"
        "SELECT u.__row, CASE WHEN TRUE THEN 'C1' ELSE 'UNEXPLAINED' END AS cause\n"
        "FROM {unmatched} AS u\n"
    )
    fakes.bq.cost = lambda sql: (
        1.0 if FORMULA_QUERY in sql else 2.0 if "AS cause" in sql else 0.0
    )
    stored = explain.run_stored
    priced = []

    def run_stored(*a, also_usd=0.0, **k):
        priced.append(also_usd)
        return stored(*a, also_usd=also_usd, **k)

    monkeypatch.setattr(explain, "run_stored", run_stored)
    since = len(fakes.bq.log)
    capsys.readouterr()

    def capped(usd):
        return ["--max-usd", usd, "--max-usd-per-day", "50"]

    # One cap refusal covers the explanations and the formula check.
    assert cli.main(["sort", str(path), "--no-trace", *capped("5")]) == 1
    out, err = capsys.readouterr()
    assert "Formula check: 4 queries, $4.00 (dry run)." in out
    assert "Explanations: 1 to run, $2.00 (dry run)" in out
    assert "these queries ($6.00) would pass the $5.00 cap" in err
    assert priced == [pytest.approx(4.0)]
    # With explanations off, the check alone is still capped up front.
    assert (
        cli.main(["sort", str(path), "--no-trace", "--no-explanations", *capped("3")])
        == 1
    )
    assert "these queries ($4.00) would pass the $3.00 cap" in capsys.readouterr().err
    assert _formula_runs(fakes.bq, since) == []

    # Under the same $5 cap the check alone runs: only the sum passed it.
    argv = ["sort", str(path), "--no-trace", "--no-explanations", *capped("5")]
    assert cli.main(argv) == 0
    assert len(_formula_runs(fakes.bq, since)) == 4


def test_sort_files_a_decided_cell_whose_formulas_differ_as_formula(fakes, tmp_path):
    # The DDI goal shape: each Miami cell holds a row group a decision closes,
    # so coverage alone would close the cells; but on matched rows the 2 sides
    # still differ, so the cells differ by their formulas.
    _miami_differs(fakes, tmp_path)
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    before = json.loads(_latest_run(tmp_path).read_text())
    assert before["applied"]["open"] == [] and before["applied"]["quiet"]
    assert {c["kind"] for c in before["diff_cells"]} == {"cells"}
    fakes.bq.formula = {
        "dashboard": [{"region": "Newark", "value": 0.9123},
                      {"region": "Miami", "value": 0.6}],
        "cube": [{"regions_region_name": "Newark", "value": 0.91234},
                 {"regions_region_name": "Miami", "value": 0.95}],
    }  # fmt: skip

    items = _sorted_items(path, tmp_path)

    assert "ada-region:cells" not in items
    item = items["ada-region:formula"]
    assert (item["suggestion"], item["proof"]["kind"]) == ("cause", "formula")
    assert item["cause"][0]["label"] == sort.MATCHED_LABEL
    assert item["evidence_posted"][0] == (
        f"<10 {sort.MATCHED_LABEL}: with their unmatched rows left out, the 2 sides "
        "still differ"
    )
    assert "Miami" not in json.dumps(item["evidence_posted"])
    after = json.loads(_latest_run(tmp_path).read_text())
    assert {c["kind"] for c in after["diff_cells"]} == {"formula"}
    (diff,) = after["applied"]["open_cells"]
    assert (diff["kind"], diff["matched_only"]) == ("formula", 2)
    assert _triage(tmp_path)["formulas_not_compared"] == {}


def test_a_formula_decision_is_asked_again_once_the_check_files_more_cells(
    fakes, tmp_path, capsys
):
    _miami_differs(fakes, tmp_path)
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    fakes.bq.formula = {
        "dashboard": [{"region": "Newark", "value": 0.9123},
                      {"region": "Miami", "value": 0.6}],
        "cube": [{"regions_region_name": "Newark", "value": 0.91234},
                 {"regions_region_name": "Miami", "value": 0.95}],
    }  # fmt: skip
    assert "ada-region:formula" in _sorted_items(path, tmp_path)
    approved = _approved(tmp_path, [{"id": "which-rate", "call": "domain_owner",
                                     "reason": "Which rate is right?",
                                     "item": "ada-region:formula"}])  # fmt: skip

    assert cli.main(["decide", str(path), str(approved)]) == 0

    (decision,) = [d for d in load_view_config(path).decisions if d.formula]
    assert decision.fingerprints == {
        **_saved_fingerprints(tmp_path),
        "matched_only": "2",
    }
    applied = json.loads(_latest_run(tmp_path).read_text())["applied"]
    assert [d["id"] for d, _ in applied["quiet_cells"]] == ["which-rate"]

    # Recorded with fewer cells than the check has filed since (here, as a
    # decision written before the count was): asked again.
    text = path.read_text()
    path.write_text(text.replace("matched_only: '2'", "matched_only: '1'"))
    assert cli.main(["reapply", str(path)]) == 0

    applied = json.loads(_latest_run(tmp_path).read_text())["applied"]
    assert [d["id"] for d in applied["reconfirm"]] == ["which-rate"]
    assert applied["quiet_cells"] == []
    assert [d["kind"] for d in applied["open_cells"]] == ["formula"]
    # Out of the questions while it waits; ask-owner says so on stderr.
    assert "ada-region:formula" in _sorted_items(path, tmp_path)
    capsys.readouterr()
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0
    out, err = capsys.readouterr()
    assert ("v: 1 decision to re-confirm, left out of the questions: which-rate") in err
    assert "re-confirm" not in out

    # As the runbook says: delete it and decide the item again under a new
    # id, so the owner's session does not skip it as answered.
    path.write_text(text)
    with_it = load_view_config(path)
    lines = text.splitlines()
    (start,) = [i for i, line in enumerate(lines) if line.endswith("- id: which-rate")]
    item = lines[start][: lines[start].index("-")]
    stop = next(
        (
            i
            for i in range(start + 1, len(lines))
            if not lines[i].startswith(item + " ")
        ),
        len(lines),
    )
    path.write_text("\n".join(lines[:start] + lines[stop:]) + "\n")
    assert [d.id for d in load_view_config(path).decisions] == [
        d.id for d in with_it.decisions if d.id != "which-rate"
    ]
    assert cli.main(["reapply", str(path)]) == 0
    assert "ada-region:formula" in _sorted_items(path, tmp_path)
    again = _approved(tmp_path, [{"id": "which-rate-2", "call": "domain_owner",
                                  "reason": "Which rate is right?",
                                  "item": "ada-region:formula"}])  # fmt: skip
    assert cli.main(["decide", str(path), str(again)]) == 0
    (decision,) = [d for d in load_view_config(path).decisions if d.formula]
    assert decision.id == "which-rate-2"
    assert decision.fingerprints["matched_only"] == "2"


def test_sort_reuses_a_stored_check_without_spending(fakes, tmp_path):
    path = _miami_differs(fakes, tmp_path)
    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    assert len(_formula_runs(fakes.bq)) == 4
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    check = latest.read_all(held, "kipptaf_marts.fct_f")["ada-region"].data[
        "formula_check"
    ]
    # The sides agree on matched rows: coverage decides.
    assert len(check["coverage"]) == 2 and check["formula"] == []
    since = len(fakes.bq.log)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    assert not [sql for _, sql in fakes.bq.log[since:] if FORMULA_QUERY in sql]
    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {} and loaded["stale"] == {}


def _stored_formula_check(tmp_path) -> dict:
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    return latest.read_all(held, "kipptaf_marts.fct_f")["ada-region"].data[
        "formula_check"
    ]


def _keep_formula_check(tmp_path, check: dict) -> None:
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    latest.add_formula_check(held, "ada-region", check)


def _older(check: dict, version) -> dict:
    """The check as an older validator kept it: `None` for one with no
    version at all."""
    older = {k: v for k, v in check.items() if k != "version"}
    return older if version is None else {**older, "version": version}


@pytest.mark.parametrize(
    ("version", "uncompared"), [(None, True), (0, True), (None, False), (0, False)]
)
def test_sort_runs_an_older_stored_check_again(fakes, tmp_path, version, uncompared):
    path = _miami_differs(fakes, tmp_path)
    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    check = _stored_formula_check(tmp_path)
    # As an older validator kept it: one that found no matched rows, or one
    # that decided every cell, whose verdicts the update may change.
    if uncompared:
        check = {**check, "coverage": [], "not_compared": {NO_ROWS: check["coverage"]}}
    _keep_formula_check(tmp_path, _older(check, version))
    since = len(fakes.bq.log)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    # The validator updated, the check runs again and any label goes.
    assert len(_formula_runs(fakes.bq, since)) == 4
    assert _triage(tmp_path)["formulas_not_compared"] == {}
    assert _stored_formula_check(tmp_path)["version"] == formula.CHECK_VERSION


def test_sort_reuses_a_stored_check_with_uncompared_cells_of_this_version(
    fakes, tmp_path
):
    path = _miami_differs(fakes, tmp_path)
    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    check = _stored_formula_check(tmp_path)
    assert check["version"] == formula.CHECK_VERSION
    no_rows = {**check, "coverage": [], "not_compared": {NO_ROWS: check["coverage"]}}
    _keep_formula_check(tmp_path, no_rows)
    since = len(fakes.bq.log)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    # Nothing changed since it ran: neither priced nor run again.
    assert not [sql for _, sql in fakes.bq.log[since:] if FORMULA_QUERY in sql]
    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {"ada-region": {NO_ROWS: 2}}
    assert loaded["stale"] == {}
    assert _stored_formula_check(tmp_path) == no_rows


@pytest.mark.parametrize("falls", ["plan", "dry run", "run"])
def test_a_re_run_that_falls_back_keeps_the_stored_check_s_verdicts(
    fakes, tmp_path, capsys, monkeypatch, falls
):
    _miami_differs(fakes, tmp_path)
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    fakes.bq.formula = {
        "dashboard": [{"region": "Newark", "value": 0.9123},
                      {"region": "Miami", "value": 0.6}],
        "cube": [{"regions_region_name": "Newark", "value": 0.91234},
                 {"regions_region_name": "Miami", "value": 0.95}],
    }  # fmt: skip
    assert cli.main(["sort", str(path), "--no-trace"]) == 0
    check = _stored_formula_check(tmp_path)
    filed, no_rows = check["formula"]
    # An older validator's check: 1 cell filed as formula, 1 with no rows
    # both sides hold. Composed again, the run files the first as formula.
    older = _older(
        {**check, "formula": [filed], "not_compared": {NO_ROWS: [no_rows]},
         "lines": check["lines"][:1]},
        None,
    )  # fmt: skip
    _keep_formula_check(tmp_path, older)
    run_json = _latest_run(tmp_path)
    results.recompose(
        load_view_config(path),
        tmp_path / "cache",
        results._run_from_json(json.loads(run_json.read_text())),
        run_json,
        cube=fakes.cube,
    )
    # Re-planned for its version, the check cannot run this time.
    if falls == "plan":
        monkeypatch.setattr(
            formula,
            "plan",
            lambda cfg, run, c, *, fingerprint, **k: formula.not_compared(
                c.id, fingerprint, formula.checkable_cells(run, c), formula.SAVED_GONE
            ),
        )
    else:
        _bigquery_refuses(fakes, "__matched", dry=falls == "dry run")
    capsys.readouterr()

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    why = (
        formula.SAVED_GONE
        if falls == "plan"
        else "BigQuery refused it (job ?, invalidQuery); sort again"
    )
    out = capsys.readouterr().out
    assert (
        f"Formula check of ada-region: kept the stored check; this run fell back: "
        f"{why}\n"
    ) in out
    assert "12345" not in out
    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {"ada-region": {NO_ROWS: 1}}
    after = json.loads(_latest_run(tmp_path).read_text())
    kinds = {(c["cut"], c["key"]): c["kind"] for c in after["diff_cells"]}
    assert kinds == {tuple(filed): "formula", tuple(no_rows): "cells"}
    # The fallback is not kept: the next sort tries again.
    assert _stored_formula_check(tmp_path) == older


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Cube timed out"),
        pipeline.Refusal("the run is not composed from the latest results"),
    ],
)
def test_sort_keeps_its_checks_labelled_when_composing_again_fails(
    fakes, tmp_path, capsys, monkeypatch, error
):
    _miami_differs(fakes, tmp_path)
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    fakes.bq.formula = {
        "dashboard": [{"region": "Newark", "value": 0.9123},
                      {"region": "Miami", "value": 0.6}],
        "cube": [{"regions_region_name": "Newark", "value": 0.91234},
                 {"regions_region_name": "Miami", "value": 0.95}],
    }  # fmt: skip

    def failed(*a, **k):
        raise error

    monkeypatch.setattr(results, "recompose", failed)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    assert str(error) in capsys.readouterr().out
    assert _triage(tmp_path)["formulas_not_compared"] == {
        "ada-region": {NOT_COMPOSED: 2}
    }
    # The run still files the cells as a cell set; the check that ran stays
    # beside its result, for the next compose to file.
    after = json.loads(_latest_run(tmp_path).read_text())
    assert {c["kind"] for c in after["diff_cells"]} == {"cells"}
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    check = latest.read_all(held, "kipptaf_marts.fct_f")["ada-region"].data[
        "formula_check"
    ]
    assert len(check["formula"]) == 2 and check["not_compared"] == {}


def test_sort_labels_a_run_not_composed_from_the_latest_results_unpriced(
    fakes, tmp_path
):
    path = _miami_differs(fakes, tmp_path)
    # As a compare stopped after keeping a newer result, before composing.
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    file = latest._file(held, "ada-region")
    kept = json.loads(file.read_text())
    file.write_text(json.dumps({**kept, "entry": "a newer entry"}))
    since = len(fakes.bq.log)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {"ada-region": {NOT_COMPOSED: 2}}
    # Neither priced nor run: a check of this run would be filed by a compose
    # that replaces it.
    assert not [sql for _, sql in fakes.bq.log[since:] if FORMULA_QUERY in sql]
    assert (
        "formula_check"
        not in latest.read_all(held, "kipptaf_marts.fct_f")["ada-region"].data
    )


def test_a_formula_dry_run_bigquery_refuses_leaves_its_cells_to_coverage(
    fakes, tmp_path, capsys
):
    path = _miami_differs(fakes, tmp_path)
    _bigquery_refuses(fakes, "__matched", dry=True)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    why = "BigQuery refused it (job ?, invalidQuery); sort again"
    loaded = _triage(tmp_path)
    assert loaded["stale"] == {}
    assert loaded["formulas_not_compared"] == {"ada-region": {why: 2}}
    assert _formula_runs(fakes.bq) == []
    assert "12345" not in json.dumps(loaded) and "12345" not in capsys.readouterr().out


def test_sort_comparison_checks_only_the_comparisons_named(fakes, tmp_path):
    path = _miami_differs(fakes, tmp_path, _four(tmp_path))
    since = len(fakes.bq.log)

    argv = ["sort", str(path), "--no-trace", "--comparison", "ada-region-2"]
    assert cli.main(argv) == 0

    assert len(_formula_runs(fakes.bq, since)) == 4
    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {
        f"ada-region-{i}": {OUTSIDE: 2} for i in (1, 3, 4)
    }
    items = {i["id"]: i for i in loaded["items"]}
    assert items["ada-region-1:cells"]["evidence"][0] == (
        f"formulas not compared: {OUTSIDE} (2 cells closed by coverage only)"
    )
    assert items["ada-region-1:cells"]["evidence_posted"][0] == (
        f"formulas not compared: {OUTSIDE} (<10 cells closed by coverage only)"
    )
    # Checked: the sides agree on matched rows, so coverage decides.
    assert not items["ada-region-2:cells"]["evidence"][0].startswith(NOT_COMPARED)


def test_a_formula_dry_run_that_fails_outside_bigquery_leaves_sort_running(
    fakes, tmp_path, capsys
):
    path = _miami_differs(fakes, tmp_path)
    query = fakes.bq.query

    def expired(sql, job_config=None):
        if FORMULA_QUERY in sql and job_config is not None and job_config.dry_run:
            raise RefreshError("Reauthentication is needed.")
        return query(sql, job_config)

    fakes.bq.query = expired

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    loaded = _triage(tmp_path)
    assert loaded["formulas_not_compared"] == {"ada-region": {RUN_FAILED: 2}}
    cells = {i["id"]: i for i in loaded["items"]}["ada-region:cells"]
    assert cells["evidence_posted"][0] == (
        f"formulas not compared: {RUN_FAILED} (<10 cells closed by coverage only)"
    )
    assert "Reauthentication is needed." in capsys.readouterr().out
    assert _formula_runs(fakes.bq) == []


def test_a_failed_check_neither_refuses_sort_nor_makes_the_comparison_stale(
    fakes, tmp_path, capsys
):
    path = _miami_differs(fakes, tmp_path)
    _bigquery_refuses(fakes, "__matched", dry=False)

    assert cli.main(["sort", str(path), "--no-trace"]) == 0

    why = "BigQuery refused it (job ?, invalidQuery); sort again"
    loaded = _triage(tmp_path)
    assert loaded["stale"] == {}
    assert loaded["formulas_not_compared"] == {"ada-region": {why: 2}}
    cells = {i["id"]: i for i in loaded["items"]}["ada-region:cells"]
    assert cells["evidence_posted"][0] == (
        f"formulas not compared: {why} (<10 cells closed by coverage only)"
    )
    assert "12345" not in json.dumps(loaded) and "12345" not in capsys.readouterr().out
    # Nothing ran to keep: the next sort tries again.
    held = latest.folder(tmp_path / "cache" / "v", "kipptaf_marts.fct_f")
    assert (
        "formula_check"
        not in latest.read_all(held, "kipptaf_marts.fct_f")["ada-region"].data
    )


# --- add-decisions and record-answers ----------------------------------------


def _gap_sorted_item():
    return {"id": "cut:Team", "kind": "gap", "comparison": "", "label": "l",
            "stub": {"missing_cut": "Team"}, "suggestion": "filters_nothing",
            "evidence": [], "candidates": []}  # fmt: skip


def _approved(tmp_path, entries):
    path = tmp_path / "approved.json"
    path.write_text(json.dumps(entries))
    return path


def test_add_decisions_takes_stub_from_triage_and_fingerprints_from_run(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e"), _gap_sorted_item()])
    approved = _approved(
        tmp_path,
        [
            {
                "id": "miami-scope",
                "call": "fix_cube",
                "reason": "Cube drops Miami.",
                "task": "#6150",
                "item": MIAMI,
            },
            {
                "id": "no-team",
                "call": "deliberate",
                "reason": "A label only.",
                "task": "",
                "item": "cut:Team",
            },
        ],  # fmt: skip
    )
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 0

    cfg = load_view_config(path)
    miami, team = cfg.decisions
    assert (miami.comparison, miami.call, miami.task) == (
        "ada-region",
        "fix_cube",
        "#6150",
    )
    # A proven group becomes a decision on its cause, never on the group.
    assert miami.group == {}
    assert miami.cause == {"side": "dashboard", "label": "x"}
    assert miami.fingerprints == {
        **_saved_fingerprints(tmp_path),
        "explanation": STORED_EXPLANATION["fingerprint"],
    }
    assert (team.missing_cut, team.comparison, team.fingerprints) == ("Team", "", {})
    assert cfg.comparisons[0].rebuild_check is not None
    out = capsys.readouterr().out
    assert "miami-scope" in out and "no-team" in out
    assert "`compare`" in out.rstrip().splitlines()[-1]

    # The next run lists it; the triage, not the run, says what it decides.
    assert cli.main(["compare", str(path), "--all"]) == 0
    assert "miami-scope" in _section(capsys.readouterr().out, "Applied:", "To re-")


def test_add_decisions_re_applies_to_the_saved_run_offline(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e")])
    approved = _approved(
        tmp_path,
        [{"id": "miami-scope", "call": "deliberate", "reason": "r", "item": MIAMI}],
    )
    calls = _client_calls(fakes)
    _no_clients(monkeypatch)
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 0

    out = capsys.readouterr().out
    assert "Re-applied decisions to the saved run of" in out
    # A cause decision never closes a group in the run; the triage marks it.
    assert "1 open groups" in out
    applied = json.loads(run_json.read_text())["applied"]
    assert [d["id"] for d in applied["causes"]] == ["miami-scope"]
    assert _client_calls(fakes) == calls
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0


def _sorted_run(path, tmp_path):
    """Run the file and give its run a triage listing the Miami group as `i`."""
    assert cli.main(["compare", str(path), "--all"]) == 0
    saved = sorted(
        (tmp_path / "cache" / "v").glob("*/run.json"), key=lambda p: p.stat().st_mtime
    )
    _write_sorted(saved[-1], [_sorted_item("e")])


def test_add_decisions_refuses_a_decision_overlapping_one_in_the_file(
    fakes, tmp_path, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    # Stale, so the group stays open and triage proves its cause; the cause
    # decision's other call still refuses.
    path = _with_decision({"cube": "stale", "dashboard": "stale"}, tmp_path)
    _sorted_run(path, tmp_path)
    approved = _approved(
        tmp_path,
        [{"id": "miami-again", "call": "deliberate", "reason": "r", "item": MIAMI}],
    )
    before = path.read_text()
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 1

    err = capsys.readouterr().err
    assert "miami-scope" in err and "miami-again" in err and "nothing written" in err
    assert path.read_text() == before


def test_add_decisions_refuses_two_in_one_batch_claiming_one_group(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    _sorted_run(path, tmp_path)
    approved = _approved(
        tmp_path,
        [
            {"id": "one", "call": "deliberate", "reason": "r", "item": MIAMI},
            {"id": "two", "call": "deliberate", "reason": "r", "item": MIAMI},
        ],
    )
    before = path.read_text()
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 1

    assert "approved twice" in capsys.readouterr().err
    assert path.read_text() == before


def test_add_decisions_without_a_usable_run_still_writes(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _file(tmp_path)
    _sorted_run(path, tmp_path)
    approved = _approved(
        tmp_path, [{"id": "a", "call": "deliberate", "reason": "r", "item": MIAMI}]
    )
    # A run saved before re-applying existed: add-decisions reads it, reapply
    # cannot.
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    del data["applied"]["quiet_cells"]
    saved.write_text(json.dumps(data))
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(approved)]) == 0

    out, err = capsys.readouterr()
    assert [d.id for d in load_view_config(path).decisions] == ["a"]
    assert "not re-applied" in err and "not re-applied" not in out


def test_add_decisions_refuses_an_unknown_item_and_writes_nothing(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    _write_sorted(run_json, [_sorted_item("e")])
    approved = _approved(
        tmp_path,
        [
            {"id": "miami-scope", "call": "deliberate", "reason": "r", "item": MIAMI},
            {"id": "other", "call": "deliberate", "reason": "r", "item": "gone"},
        ],
    )
    before = path.read_text()

    assert cli.main(["decide", str(path), str(approved)]) == 1

    assert "gone" in capsys.readouterr().err
    assert path.read_text() == before


def test_add_decisions_writes_what_is_ready_while_an_item_waits_in_investigate(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    _write_sorted_everywhere(
        tmp_path, [_sorted_item("e"), _sorted_item("x", "investigate", "j")]
    )
    waiting = _approved(
        tmp_path, [{"id": "b", "call": "deliberate", "reason": "r", "item": "j"}]
    )
    before = path.read_text()
    capsys.readouterr()

    # The item still in `investigate` takes no decision.
    assert cli.main(["decide", str(path), str(waiting)]) == 1

    err = capsys.readouterr().err
    assert "item 'j' is still in `investigate`" in err
    assert "see `explain` in the cube-validation skill" in err
    assert path.read_text() == before

    # The proven item writes; the other stays open.
    ready = _approved(
        tmp_path, [{"id": "a", "call": "deliberate", "reason": "r", "item": MIAMI}]
    )
    assert cli.main(["decide", str(path), str(ready)]) == 0
    assert [d.id for d in load_view_config(path).decisions] == ["a"]


def _closed_by_a_group_decision(tmp_path):
    """A run whose Miami group a `group` decision (fix_cube) closes.

    Its triage lists no Miami item: the stored proof classified the closed
    group under `closed`, and proved open item `other` on the same cause.
    """
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path, call="fix_cube")
    assert cli.main(["reapply", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(run_json.read_text()))
    ((_, miami),) = run.applied.quiet
    _write_sorted(run_json, [_sorted_item("e", item_id="other")])
    found = run_json.parent / "triage.json"
    loaded = json.loads(found.read_text())
    key = sort._open_key(miami)
    loaded["closed"] = [
        {"id": key, "key": key, "kind": "group", "comparison": "ada-region",
         "closed": True, "suggestion": "cause", "cause": [STEP],
         "proof": dict(STORED_EXPLANATION)}
    ]  # fmt: skip
    found.write_text(json.dumps(loaded))
    return path


def _cause_on_other(tmp_path, call):
    entry = {"id": "no-section", "call": call, "reason": "r", "item": "other"}
    return _approved(
        tmp_path, [{**entry, "task": "#6150"} if call != "deliberate" else entry]
    )


def test_add_decisions_refuses_a_cause_disagreeing_with_a_closed_group(
    fakes, tmp_path, capsys
):
    path = _closed_by_a_group_decision(tmp_path)
    before = path.read_text()
    capsys.readouterr()

    assert (
        cli.main(["decide", str(path), str(_cause_on_other(tmp_path, "deliberate"))])
        == 1
    )

    err = capsys.readouterr().err
    assert "'miami-scope' (fix_cube) and 'no-section' (deliberate) disagree" in err
    assert "regions_region_name" in err and "nothing written" in err
    assert "Miami" not in err
    assert path.read_text() == before


def test_add_decisions_writes_a_cause_agreeing_with_a_closed_group(
    fakes, tmp_path, capsys
):
    path = _closed_by_a_group_decision(tmp_path)

    assert (
        cli.main(["decide", str(path), str(_cause_on_other(tmp_path, "fix_cube"))]) == 0
    )

    assert [d.id for d in load_view_config(path).decisions] == [
        "miami-scope",
        "no-section",
    ]


def test_reapply_refuses_a_hand_edit_making_a_cause_disagree_with_a_closed_group(
    fakes, tmp_path, capsys
):
    path = _closed_by_a_group_decision(tmp_path)
    assert (
        cli.main(["decide", str(path), str(_cause_on_other(tmp_path, "fix_cube"))]) == 0
    )
    text = path.read_text()
    # The cause decision is written last: flip its call only.
    at = text.rindex("call: fix_cube")
    path.write_text(text[:at] + "call: fix_source" + text[at + len("call: fix_cube") :])
    capsys.readouterr()

    assert cli.main(["reapply", str(path)]) == 1

    err = capsys.readouterr().err
    assert "'miami-scope' (fix_cube) and 'no-section' (fix_source) disagree" in err
    assert "Miami" not in err


WHOLE_ENTRY = {"id": "old-sheet", "comparison": "ada-region", "call": "deliberate",
               "reason": "an old sheet no one reads"}  # fmt: skip


def test_decide_closes_a_whole_comparison_and_ask_owner_lists_it(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    # The comparison's only row group is still in `investigate`.
    _write_sorted_everywhere(tmp_path, [_sorted_item("e", "investigate")])

    assert cli.main(["decide", str(path), str(_approved(tmp_path, [WHOLE_ENTRY]))]) == 0

    (d,) = load_view_config(path).decisions
    assert (d.id, d.comparison, d.all_groups, d.call) == (
        "old-sheet", "ada-region", True, "deliberate"
    )  # fmt: skip
    assert "  - id: old-sheet\n    comparison: ada-region\n    all_groups: true\n" in (
        path.read_text()
    )
    run, _ = results.latest_run(load_view_config(path), tmp_path / "cache")
    assert run.applied.open == []
    assert [x.id for x, _ in run.applied.quiet] == ["old-sheet"]
    # The run report (terminal and local cache) lists it once, with how many
    # groups it closed, exactly.
    assert (
        "- `old-sheet` (ada-region every open row group, deliberate): an old sheet "
        "no one reads (1 row group)\n"
    ) in report.render_local(run)
    capsys.readouterr()

    # The closed group is no longer with the analyst, and the owner sees the
    # decision with masked counts only.
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0

    body = capsys.readouterr().out
    line = next(x for x in body.splitlines() if "every open row group" in x)
    # Bounds only, never the exact 30 rows or 12 students.
    assert line.startswith(
        "- every open row group of `ada-region` in `v` (dashboard_only): "
        "<10 row groups, 10+ rows, at least 10 students: an intended difference"
    )
    assert line.endswith("Reason: an old sheet no one reads.")
    assert MIAMI not in body


def test_decide_refuses_a_whole_comparison_disagreeing_with_a_cause_decision(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    _write_sorted_everywhere(tmp_path, [_sorted_item("e")])
    cause = {"id": "cause", "call": "fix_cube", "reason": "r", "task": "#6150",
             "item": MIAMI}  # fmt: skip
    assert cli.main(["decide", str(path), str(_approved(tmp_path, [cause]))]) == 0
    before = path.read_text()
    capsys.readouterr()

    assert cli.main(["decide", str(path), str(_approved(tmp_path, [WHOLE_ENTRY]))]) == 1

    err = capsys.readouterr().err
    assert "'old-sheet' (deliberate) and 'cause' (fix_cube) disagree" in err
    assert path.read_text() == before


def test_a_hand_group_decision_on_an_unexplained_group_still_refuses(
    fakes, tmp_path, capsys
):
    # Only a comparison decision may close a group no one explained.
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    assert cli.main(["reapply", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    run = results._run_from_json(json.loads(run_json.read_text()))
    ((_, miami),) = run.applied.quiet
    item = {**_sorted_item("e", "investigate"), "key": sort._open_key(miami)}
    _write_sorted(run_json, [item])
    capsys.readouterr()

    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 1

    assert "which the sort holds in `investigate`" in capsys.readouterr().err


def test_add_decisions_refuses_a_view_never_triaged(fakes, tmp_path, capsys):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    approved = _approved(
        tmp_path, [{"id": "a", "call": "deliberate", "reason": "r", "item": MIAMI}]
    )

    assert cli.main(["decide", str(path), str(approved)]) == 1

    assert "sort" in capsys.readouterr().err


# --- reapply ------------------------------------------------------------------


def _client_calls(fakes):
    return (
        len(fakes.bq.ran),
        len(fakes.cube.loads),
        len(fakes.cube.compiled_queries),
        fakes.signed_in,
    )


def _no_clients(monkeypatch):
    """Fail any attempt to build a BigQuery, Cube or Tableau client."""

    def refuse(*_args, **_kwargs):
        raise AssertionError("re-applying decisions must not query")

    monkeypatch.setattr(cli, "make_warehouse", refuse)
    monkeypatch.setattr(cli, "make_cube", refuse)
    monkeypatch.setattr(cli, "tableau_session", refuse)


def test_reapply_quiets_a_newly_decided_group_and_review_accepts_it(
    fakes, tmp_path, monkeypatch, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    before = _saved_run(tmp_path)
    (measure,) = before["measures"]
    assert measure["open_groups"] > 0
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    calls = _client_calls(fakes)
    _no_clients(monkeypatch)
    capsys.readouterr()

    assert cli.main(["reapply", str(path)]) == 0

    after = _saved_run(tmp_path)
    assert [d["id"] for d, _ in after["applied"]["quiet"]] == ["miami-scope"]
    assert after["applied"]["open"] == []
    assert after["measures"][0]["open_groups"] == 0
    assert measure["verdict"] == "differs"
    assert after["measures"][0]["verdict"] == "validated"
    assert after["cube_host"] == before["cube_host"]
    assert after["decisions_fingerprint"] != before["decisions_fingerprint"]
    out = capsys.readouterr().out
    assert "Re-applied decisions to the saved run of" in out
    assert "0 open groups" in out
    (result_md,) = (tmp_path / "cache" / "v").glob("*/result.md")
    text = result_md.read_text()
    assert "miami-scope" in _section(text, "Applied:", "To re-confirm")
    assert "## Cells" in text
    assert _client_calls(fakes) == calls

    _write_sorted_everywhere(tmp_path)
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0


def test_reapply_marks_a_measure_validated_once_its_last_group_is_decided(
    fakes, tmp_path, monkeypatch
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (before,) = _saved_run(tmp_path)["measures"]
    assert before["open_groups"] > 0
    (result_md,) = (tmp_path / "cache" / "v").glob("*/result.md")
    assert "`avg_daily_attendance`: differs" in result_md.read_text()
    path = _with_decision(_saved_fingerprints(tmp_path), tmp_path)
    _no_clients(monkeypatch)

    assert cli.main(["reapply", str(path)]) == 0

    assert "`avg_daily_attendance`: validated" in result_md.read_text()


def test_reapply_keeps_a_decision_whose_sql_changed_open(
    fakes, tmp_path, monkeypatch, capsys
):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    open_before = _saved_run(tmp_path)["applied"]["open"]
    path = _with_decision({"cube": "stale", "dashboard": "stale"}, tmp_path)
    _no_clients(monkeypatch)

    assert cli.main(["reapply", str(path)]) == 0

    applied = _saved_run(tmp_path)["applied"]
    assert applied["quiet"] == []
    assert [d["id"] for d in applied["reconfirm"]] == ["miami-scope"]
    assert applied["open"] == open_before


def test_reapply_refuses_a_view_never_run(fakes, tmp_path, capsys):
    assert cli.main(["reapply", str(_file(tmp_path))]) == 1
    assert "no saved run" in capsys.readouterr().err


def test_reapply_refuses_a_run_saved_before_it_kept_cell_diffs(fakes, tmp_path, capsys):
    assert cli.main(["compare", str(_file(tmp_path))]) == 0
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    del data["applied"]["quiet_cells"]
    saved.write_text(json.dumps(data))

    assert cli.main(["reapply", str(_file(tmp_path))]) == 1
    assert "older validator" in capsys.readouterr().err


OWNER_DECISIONS = """\
decisions:
  - id: miami-scope
    comparison: ada-region
    group: { column: regions_region_name, values: [Miami] }
    call: domain_owner
    reason: The dashboard keeps Miami rows the fact drops.
    task: "#7"
    fingerprints: { cube: abc, dashboard: def }
  - id: newark-scope
    comparison: ada-region
    group: { column: regions_region_name, values: [Newark] }
    call: domain_owner
    reason: Newark counts differ.
    task: "#7"
    fingerprints: { cube: abc, dashboard: def }
  - id: camden-scope
    comparison: ada-region
    group: { column: regions_region_name, values: [Camden] }
    call: domain_owner
    reason: Camden counts differ.
    task: "#7"
    fingerprints: { cube: abc, dashboard: def }
  - id: paterson-scope
    comparison: ada-region
    group: { column: regions_region_name, values: [Paterson] }
    call: domain_owner
    reason: Paterson counts differ.
    task: "#7"
    fingerprints: { cube: abc, dashboard: def }
  - id: no-team
    missing_cut: Team
    call: domain_owner
    reason: Cube has no team.
    task: "#7"
  - id: settled
    missing_cut: Homeroom
    call: deliberate
    reason: A label only.
"""
TASKS = "tasks:\n  cube_fix: '#6150'\n  dashboard_fix: https://app.asana.com/0/1/2\n"


def _owner_file(tmp_path, tasks=TASKS, view="v"):
    tmp_path.mkdir(exist_ok=True)
    text = YML.replace("view: v\n", f"view: {view}\n") + OWNER_DECISIONS + tasks
    return _file(tmp_path, text)


def _comment(tmp_path, answers):
    path = tmp_path / "comment.md"
    path.write_text(
        "Thanks! My answers:\n\n- Q1: the dashboard is right\n\n```json\n"
        + json.dumps(answers, indent=1)
        + "\n```\n"
    )
    return path


def _answer(decisions, call, note="", task=""):
    out = {"question": "Q1", "decisions": decisions, "call": call, "note": note}
    return {**out, "task": task} if task else out


def _record(path, comment, *extra):
    return cli.main(
        ["record-answers", *map(str, path), "--comment", str(comment),
         "--author", "owner-login", *extra]
    )  # fmt: skip


def test_record_answers_dry_run_prints_author_and_changes_writes_nothing(
    tmp_path, capsys
):
    path = _owner_file(tmp_path)
    before = path.read_text()
    comment = _comment(
        tmp_path, [_answer(["miami-scope"], "fix_cube", "the fact drops them")]
    )

    assert _record([path], comment) == 0

    out = capsys.readouterr().out
    assert out.startswith("Comment by owner-login\n")
    assert "miami-scope: call domain_owner -> fix_cube" in out
    assert "miami-scope: task #7 -> #6150" in out
    assert "Owner: the fact drops them" in out
    assert "--yes" in out.rstrip().splitlines()[-1]
    assert path.read_text() == before


def test_record_answers_maps_calls_to_tasks_block(tmp_path, capsys):
    path = _owner_file(tmp_path)
    comment = _comment(
        tmp_path,
        [
            _answer(["miami-scope"], "fix_cube", "the fact drops them"),
            _answer(["newark-scope"], "fix_dashboard", "the sheet double counts"),
            _answer(["camden-scope"], "fix_source", "tardies coded wrong", "#9001"),
            _answer(["paterson-scope"], "domain_owner", "need to talk on 2026-11-02"),
            _answer(["no-team"], "deliberate"),
        ],
    )

    assert _record([path], comment, "--yes") == 0

    by_id = {d.id: d for d in load_view_config(path).decisions}
    assert (by_id["miami-scope"].call, by_id["miami-scope"].task) == (
        "fix_cube",
        "#6150",
    )
    assert by_id["miami-scope"].reason == (
        "The dashboard keeps Miami rows the fact drops. Owner: the fact drops them"
    )
    assert (by_id["newark-scope"].call, by_id["newark-scope"].task) == (
        "fix_dashboard",
        "https://app.asana.com/0/1/2",
    )
    assert (by_id["camden-scope"].call, by_id["camden-scope"].task) == (
        "fix_source",
        "#9001",
    )
    paterson = by_id["paterson-scope"]
    assert (paterson.call, paterson.task) == ("domain_owner", "#7")
    assert paterson.reason.endswith("Owner: need to talk on 2026-11-02")
    no_team = by_id["no-team"]
    assert (no_team.call, no_team.task, no_team.reason) == (
        "deliberate",
        "#7",
        "Cube has no team.",
    )
    assert by_id["settled"].reason == "A label only."
    # No saved run: the decisions are written, and stderr says to `compare`.
    err = capsys.readouterr().err
    assert "not re-applied" in err and "`compare`" in err


def test_record_answers_refuses_a_fix_call_with_no_tasks_entry(tmp_path, capsys):
    path = _owner_file(tmp_path, tasks="tasks:\n  cube_fix: '#6150'\n")
    before = path.read_text()
    comment = _comment(tmp_path, [_answer(["newark-scope"], "fix_dashboard", "n")])

    assert _record([path], comment, "--yes") == 1

    assert "dashboard_fix" in capsys.readouterr().err
    assert path.read_text() == before


SHARED = """\
  - id: shared
    missing_cut: Grade
    call: domain_owner
    reason: Cube has no grade.
"""


@pytest.mark.parametrize(
    "bad, match",
    [
        (_answer(["gone"], "deliberate", "n"), "gone"),
        (_answer(["settled"], "fix_cube", "n"), "settled"),
        (_answer(["miami-scope"], "deliberate", "again"), "miami-scope"),
        (_answer(["shared"], "deliberate", "n"), "shared"),
        (_answer(["paterson-scope"], "deliberate", "mail a@b.org"), "email"),
    ],
)
def test_record_answers_refuses_whole_comment_on_any_mismatch(
    tmp_path, capsys, bad, match
):
    files = []
    for folder, view, decisions in (
        ("a", "v", OWNER_DECISIONS),
        ("b", "w", OWNER_DECISIONS.replace("id: ", "id: w-")),
    ):
        (tmp_path / folder).mkdir()
        text = YML.replace("view: v\n", f"view: {view}\n") + decisions + SHARED + TASKS
        files.append(_file(tmp_path / folder, text))
    before = [f.read_text() for f in files]
    comment = _comment(
        tmp_path,
        [
            _answer(["miami-scope"], "fix_cube", "the fact drops them"),
            _answer(["w-camden-scope"], "fix_cube", "same"),
            bad,
        ],
    )

    assert _record(files, comment, "--yes") == 1

    assert match in capsys.readouterr().err
    assert [f.read_text() for f in files] == before


@pytest.mark.parametrize(
    "note, refused",
    [
        ("ask jane.doe@example.org", True),
        ("student 1234567 was missed", True),
        ("call 555-123-4567", True),
        ("checked on 2026-10-27; Cube is right", False),
    ],
)
def test_record_answers_refuses_email_and_number_runs_in_notes(
    tmp_path, capsys, note, refused
):
    path = _owner_file(tmp_path)
    before = path.read_text()
    comment = _comment(tmp_path, [_answer(["miami-scope"], "fix_cube", note)])

    assert _record([path], comment, "--yes") == (1 if refused else 0)

    err = capsys.readouterr().err
    if refused:
        assert "Q1" in err and path.read_text() == before
    else:
        assert load_view_config(path).decisions[0].reason.endswith(note)


def test_record_answers_restores_every_file_when_a_later_write_fails(
    tmp_path, monkeypatch
):
    files = []
    for folder, view, decisions in (
        ("a", "v", OWNER_DECISIONS),
        ("b", "w", OWNER_DECISIONS.replace("id: ", "id: w-")),
    ):
        (tmp_path / folder).mkdir()
        text = YML.replace("view: v\n", f"view: {view}\n") + decisions + TASKS
        files.append(_file(tmp_path / folder, text))
    before = [f.read_text() for f in files]
    real = cli.write_decision

    def flaky(path, decision):
        if path == files[1]:
            raise OSError("disk full")
        real(path, decision)

    monkeypatch.setattr(cli, "write_decision", flaky)
    comment = _comment(
        tmp_path,
        [
            _answer(["miami-scope"], "fix_cube", "the fact drops them"),
            _answer(["w-camden-scope"], "fix_cube", "same"),
        ],
    )

    with pytest.raises(OSError):
        _record(files, comment, "--yes")

    assert [f.read_text() for f in files] == before


def test_record_answers_re_applies_to_the_saved_run_offline(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _owner_file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    calls = _client_calls(fakes)
    _no_clients(monkeypatch)
    comment = _comment(
        tmp_path, [_answer(["miami-scope"], "fix_cube", "the fact drops them")]
    )
    capsys.readouterr()

    assert _record([path], comment, "--yes") == 0

    assert "Re-applied decisions to the saved run of" in capsys.readouterr().out
    assert _client_calls(fakes) == calls
    _write_sorted_everywhere(tmp_path)
    assert cli.main(["ask-owner", str(path), "--domain", "Registrar"]) == 0


def test_record_answers_twice_adds_the_note_once(tmp_path, capsys):
    path = _owner_file(tmp_path)
    comment = _comment(
        tmp_path, [_answer(["paterson-scope"], "domain_owner", "need to talk")]
    )

    assert _record([path], comment, "--yes") == 0
    assert _record([path], comment, "--yes") == 0

    by_id = {d.id: d for d in load_view_config(path).decisions}
    assert by_id["paterson-scope"].reason == (
        "Paterson counts differ. Owner: need to talk"
    )
    assert "already recorded" in capsys.readouterr().out


CAUSE_OWNER = """\
decisions:
  - id: no-section
    comparison: ada-region
    cause:
      side: cube
      label: score has no section
    call: domain_owner
    reason: Should a score with no section count?
    task: "#7"
    fingerprints: { cube: abc, dashboard: def, explanation: "0f" }
"""


def test_record_answers_writes_onto_the_cause_decision(tmp_path, capsys):
    path = _file(tmp_path, YML + CAUSE_OWNER + TASKS)
    comment = _comment(
        tmp_path, [_answer(["no-section"], "fix_cube", "a score needs its section")]
    )

    assert _record([path], comment, "--yes") == 0

    (d,) = load_view_config(path).decisions
    assert (d.call, d.task, d.answer) == ("fix_cube", "#6150", "fix_cube")
    assert d.reason.endswith("Owner: a score needs its section")
    assert d.cause == {"side": "cube", "label": "score has no section"}
    assert d.fingerprints == {"cube": "abc", "dashboard": "def", "explanation": "0f"}


def test_record_answers_updates_a_missing_filter_decision_decide_wrote(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    (run_json,) = (tmp_path / "cache" / "v").glob("*/run.json")
    gap = {**_gap_sorted_item(), "id": "filter:Team",
           "stub": {"missing_filter": "Team"}}  # fmt: skip
    _write_sorted(run_json, [gap])
    entry = {"id": "no-team-filter", "call": "domain_owner", "reason": "Ask.",
             "item": "filter:Team"}  # fmt: skip
    assert cli.main(["decide", str(path), str(_approved(tmp_path, [entry]))]) == 0
    assert "  - id: no-team-filter\n    missing_filter: Team\n" in path.read_text()
    path.write_text(path.read_text() + TASKS)
    comment = _comment(
        tmp_path, [_answer(["no-team-filter"], "deliberate", "a label only")]
    )

    assert _record([path], comment, "--yes") == 0

    (d,) = load_view_config(path).decisions
    assert (d.missing_filter, d.call) == ("Team", "deliberate")
    assert d.reason == "Ask. Owner: a label only"


def test_record_answers_ends_stdout_with_nothing_written_when_a_write_refuses(
    tmp_path, monkeypatch, capsys
):
    path = _owner_file(tmp_path)
    before = path.read_text()

    def refuse(path, decision):
        raise cli.ConfigError("cannot write")

    monkeypatch.setattr(cli, "write_decision", refuse)
    comment = _comment(tmp_path, [_answer(["miami-scope"], "fix_cube", "n")])

    assert _record([path], comment, "--yes") == 1

    out, err = capsys.readouterr()
    assert "miami-scope: call domain_owner -> fix_cube" in out
    assert out.rstrip().splitlines()[-1] == "Nothing written."
    assert "cannot write" in err
    assert path.read_text() == before


def _approve(path, tmp_path, entry):
    return cli.main(["decide", str(path), str(_approved(tmp_path, [entry]))])


def test_a_changed_proof_re_opens_a_cause_decision_for_re_approval(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    _sorted_run(path, tmp_path)
    first = {"id": "a", "call": "domain_owner", "reason": "r", "item": MIAMI}
    assert _approve(path, tmp_path, first) == 0
    _sorted_run(path, tmp_path)
    # Approving a decided item again writes nothing; another call refuses.
    before = path.read_text()
    assert _approve(path, tmp_path, {**first, "id": "b"}) == 0
    assert path.read_text() == before
    assert _approve(path, tmp_path, {**first, "id": "b", "call": "deliberate"}) == 1
    assert "is decided domain_owner in 'a'" in capsys.readouterr().err

    # The proof file changes; the next triage carries its new fingerprint.
    proof = Path(STORED_EXPLANATION["path"])
    proof.write_text(EXPLANATION_TEXT.replace("1 AS n", "2 AS n"))
    STORED_EXPLANATION.update(_explanation_of(proof))
    _sorted_run(path, tmp_path)
    capsys.readouterr()
    again = {"id": "b", "call": "fix_cube", "reason": "r2", "task": "#1", "item": MIAMI}

    assert _approve(path, tmp_path, again) == 0, capsys.readouterr().err

    (d,) = load_view_config(path).decisions
    assert (d.id, d.call, d.reason) == ("a", "fix_cube", "r2")
    assert d.fingerprints["explanation"] == STORED_EXPLANATION["fingerprint"]
    assert "re-approved a" in capsys.readouterr().out


def test_an_answered_cause_decision_is_never_re_approved_on_a_changed_proof(
    fakes, tmp_path, capsys
):
    path = _file(tmp_path)
    _sorted_run(path, tmp_path)
    assert _approve(path, tmp_path, {"id": "a", "call": "domain_owner",
                                     "reason": "r", "item": MIAMI}) == 0  # fmt: skip
    path.write_text(path.read_text().replace("    call: domain_owner\n",
                                             "    call: domain_owner\n    answer: domain_owner\n"))  # fmt: skip
    proof = Path(STORED_EXPLANATION["path"])
    proof.write_text(EXPLANATION_TEXT.replace("1 AS n", "2 AS n"))
    STORED_EXPLANATION.update(_explanation_of(proof))
    _sorted_run(path, tmp_path)
    before = path.read_text()
    capsys.readouterr()

    assert _approve(path, tmp_path, {"id": "b", "call": "domain_owner",
                                     "reason": "r", "item": MIAMI}) == 1  # fmt: skip

    assert "owner answered 'a'" in capsys.readouterr().err
    assert path.read_text() == before


def test_a_trace_refusal_comes_before_any_proof_runs(
    fakes, tmp_path, monkeypatch, capsys
):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0

    def refuse(*a, **k):
        raise pipeline.Refusal("no dbt manifest")

    monkeypatch.setattr(trace, "check_ready", refuse)
    monkeypatch.setattr(
        explain, "run_stored", lambda *a, **k: pytest.fail("a proof ran first")
    )

    assert cli.main(["sort", str(path)]) == 1
    assert "no dbt manifest" in capsys.readouterr().err


def _drop_nulls(tmp_path):
    (saved,) = (tmp_path / "cache" / "v").glob("*/run.json")
    data = json.loads(saved.read_text())
    for g in data["applied"]["open"]:
        del g["nulls"]
    saved.write_text(json.dumps(data))
    return data["moment"]["start"]


@pytest.mark.parametrize(
    "command",
    [
        ["sort", "{path}", "--no-trace"],
        [
            "explain",
            "{path}",
            "--comparison",
            "ada-region",
            "--bucket",
            "cube_only",
        ],
        ["decide", "{path}", "{approved}"],
    ],
)
def test_a_run_saved_before_null_aware_groups_refuses(fakes, tmp_path, capsys, command):
    path = _file(tmp_path)
    assert cli.main(["compare", str(path)]) == 0
    start = _drop_nulls(tmp_path)
    approved = _approved(tmp_path, [])
    capsys.readouterr()

    argv = [a.format(path=path, approved=approved) for a in command]
    assert cli.main(argv) == 1

    err = capsys.readouterr().err
    assert "this run predates NULL-aware groups; run again" in err
    assert f"`compare --moment {start}`" in err and "proof" not in err


@pytest.mark.parametrize(
    "old, new",
    [("discover", "find-field"), ("preflight", "read-sheet"),
     ("prove", "rebuild-sheet"), ("run", "compare"), ("triage", "sort"),
     ("add-decisions", "decide"), ("review", "ask-owner")],
)  # fmt: skip
def test_an_old_command_is_refused_with_its_new_name(old, new, capsys):
    assert cli.main([old, "x.yml"]) == 2
    assert f"`{old}` is now `{new}`" in capsys.readouterr().err


def test_triage_confirm_is_refused_as_explain(capsys):
    assert cli.main(["triage", "confirm", "x.yml", "--comparison", "c"]) == 2
    assert "`triage confirm` is now `explain`" in capsys.readouterr().err


def test_the_old_no_proofs_flag_is_refused_with_its_new_name(capsys):
    assert cli.main(["sort", "x.yml", "--no-proofs"]) == 2
    assert "`--no-proofs` is now `--no-explanations`" in capsys.readouterr().err


def test_decide_help_names_every_key_an_approved_entry_takes(capsys):
    cli.main(["decide", "--help"])

    help_text = " ".join(capsys.readouterr().out.split())
    assert '{"id", "call", "reason", "task", "item", "cause"}' in help_text
    assert '{"id", "comparison", "call": "deliberate", "reason"}' in help_text


def test_skip_lines_never_end_in_a_doubled_period(capsys):
    compare._say_skips([pipeline.Skip("a", "why.")])

    assert capsys.readouterr().out == "Skipping a: why.\n"
