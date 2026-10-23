# Cube validation redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cell-first Cube validator with a tool that captures both
sides once in a dashboard's evening window, reconciles rows into named buckets,
then compares each exported Tableau number with Cube's and explains gaps by the
rows.

**Architecture:** A package `scripts/cube_validate/` with one module per job.
Capture writes a frozen snapshot (extract `.hyper`, Cube rows in a second
`.hyper`, Tableau CSV exports, Cube answers, `manifest.json`). Analysis attaches
both `.hyper` files to one Hyper session, builds a joined `rows` table with a
bucket per row, judges cells against it, and writes a report and a hand-check
list. Nothing in analysis calls Tableau, Cube or BigQuery.

**Tech Stack:** Python 3.13, `tableauhyperapi` (added per run with
`uv run --with tableauhyperapi`), `tableauserverclient`, `httpx`, `pyjwt`,
`google-cloud-bigquery`, `pyyaml`, `defusedxml` (all already in `uv.lock`),
pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md`

## Global Constraints

- Run everything with `uv run`; Hyper code with `uv run --with tableauhyperapi`.
  Add nothing to `pyproject.toml`.
- Ported code comes from commit `68c59490a5` (`git show 68c59490a5:<path>`), the
  last commit holding the old scripts.
- Snapshots live in `~/.cache/cube-validate/<dashboard>/<snapshot>/`. They hold
  student-level rows: never commit them, never paste their values outside the
  terminal or `#data_team`.
- The report shows any count from 1 to 9 as `<10`.
- Review copies go to TEMP-CB only (`ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`),
  named `ZZ-REVIEW <YYYY-MM-DD> <HHMM> <workbook>`. The tool deletes nothing on
  Tableau.
- Cube row queries: ungrouped, `limit: 50000`, `total: true`, 1 part per day.
  Aggregate queries always include `<view>.count_students`. 8 workers.
- Analysis never calls Tableau, Cube or BigQuery.
- Tests make no live calls. Hyper tests use
  `pytest.importorskip("tableauhyperapi")`.
- Docstrings follow the Google style (`src/teamster/CLAUDE.md`).
- Credentialed commands run inside a throwaway `tests/test_zz_*.py` (the secrets
  fixture); never call `op`.

## Review Focus

- **No student-count column on any sheet.** Predicate proof cannot run, so every
  cut is "mapping unproven". Expected: the report says why in one line, not a
  wall of unproven cells. Test in Task 7
  (`test_cut_without_a_student_count_is_unproven_with_one_reason`).
- **A cut showing last year while rows cover this year.** The cell's rows are
  empty on both sides. Expected: "no captured rows", never "formula gap". Test
  in Task 7 (`test_cell_outside_the_captured_rows_is_not_a_formula_gap`).
- **Tableau rounds half up, Python rounds half to even.** 94.25 shown as `94.3%`
  must equal Cube's 0.9425. Test in Task 7
  (`test_display_equal_rounds_half_up`).
- **Duplicate keys on one side** (an inclusive `exitdate` join). Expected: the
  extra copy lands in "dashboard only" and a cause can claim it by `t__dup > 1`;
  totals still balance. Test in Task 5
  (`test_duplicate_dashboard_row_is_dashboard_only_and_claimable`).
- **A Cube part returning fewer rows than its `total`.** Expected: capture fails
  naming the part; it never writes a short snapshot. Test in Task 10
  (`test_short_part_fails_capture_naming_the_day`).

---

## File structure

| File                                                            | Responsibility                                                   |
| --------------------------------------------------------------- | ---------------------------------------------------------------- |
| `scripts/cube_validate/__init__.py`                             | Package docstring only                                           |
| `scripts/cube_validate/__main__.py`                             | `python -m scripts.cube_validate` entry                          |
| `scripts/cube_validate/cli.py`                                  | Commands: `plan`, `run`, `answers`, `analyze`, `close`           |
| `scripts/cube_validate/config.py`                               | Load and check the checks file into dataclasses; SQL helpers     |
| `scripts/cube_validate/snapshot.py`                             | Snapshot folders and `manifest.json`                             |
| `scripts/cube_validate/hyper.py`                                | Write `.hyper` tables; a Hyper session with files attached       |
| `scripts/cube_validate/workbook.py`                             | Read the `.twb`; build the review copy; unpack extracts (ported) |
| `scripts/cube_validate/cuts.py`                                 | Draft the cut list from the workbook and extract                 |
| `scripts/cube_validate/rows.py`                                 | Rows layer: join, buckets, causes, invariants                    |
| `scripts/cube_validate/cells.py`                                | Cells layer: exports, Cube queries, predicates, verdicts         |
| `scripts/cube_validate/handchecks.py`                           | Pick and write hand checks; read results                         |
| `scripts/cube_validate/report.py`                               | `report.md` with small-cell suppression and the trust verdict    |
| `scripts/cube_validate/capture_cube.py`                         | Cube client (ported), row pull, answers                          |
| `scripts/cube_validate/preflight.py`                            | Window, cost, clock map                                          |
| `scripts/cube_validate/capture_tableau.py`                      | Tableau session (ported), download, review copy, exports         |
| `tests/scripts/cube_validate/conftest.py`                       | Loads the package as `cube_validate`                             |
| `tests/scripts/cube_validate/test_*.py`                         | One test file per module                                         |
| `.claude/skills/cube-dashboard/SKILL.md`                        | Runbook, rewritten                                               |
| `.claude/skills/cube-dashboard/checks/attendance_dashboard.yml` | Attendance checks file                                           |

Deleted: `scripts/cube_validate.py`, `scripts/cube_validate_snapshot.py`,
`tests/scripts/test_cube_validate.py`,
`tests/scripts/test_cube_validate_snapshot.py`,
`.claude/skills/cube-dashboard/checks/ddi_suite.yml`. Kept:
`tests/scripts/fixtures/cube_validate/` (workbook tests use it).

---

### Task 1: Package skeleton, test loader, old tool removed

**Files:**

- Create: `scripts/cube_validate/__init__.py`,
  `scripts/cube_validate/__main__.py`, `scripts/cube_validate/cli.py`
- Create: `tests/scripts/cube_validate/__init__.py`,
  `tests/scripts/cube_validate/conftest.py`,
  `tests/scripts/cube_validate/test_package.py`
- Delete: `scripts/cube_validate.py`, `scripts/cube_validate_snapshot.py`,
  `tests/scripts/test_cube_validate.py`,
  `tests/scripts/test_cube_validate_snapshot.py`,
  `.claude/skills/cube-dashboard/checks/ddi_suite.yml`
- Modify: `scripts/CLAUDE.md` (catalog rows for the 2 old scripts)

**Interfaces:**

- Produces: importable package `cube_validate` in tests;
  `cube_validate.cli.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

`tests/scripts/cube_validate/__init__.py`: empty file.

`tests/scripts/cube_validate/conftest.py`:

```python
"""Loads scripts/cube_validate as the package `cube_validate` for these tests.

scripts/ has no __init__.py by design, and tests/scripts/ is itself a package
named `scripts`, so the tool is registered under its own name instead.
"""

import importlib.util
import sys
from pathlib import Path

PKG = Path(__file__).parents[3] / "scripts" / "cube_validate"


def _load() -> None:
    if "cube_validate" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "cube_validate", PKG / "__init__.py", submodule_search_locations=[str(PKG)]
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registered before exec_module so dataclasses and relative imports resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)


_load()
```

`tests/scripts/cube_validate/test_package.py`:

```python
"""The package loads and its CLI rejects an unknown command."""

import pytest

from cube_validate import cli  # registered by conftest.py


def test_cli_rejects_an_unknown_command():
    with pytest.raises(SystemExit) as e:
        cli.main(["nope"])
    assert e.value.code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/cube_validate/test_package.py -v` Expected:
FAIL (`FileNotFoundError` or `ModuleNotFoundError`: no package yet).

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/__init__.py`:

```python
"""Validate Cube against what a Tableau dashboard shows, on frozen snapshots.

Runbook: .claude/skills/cube-dashboard/SKILL.md. Design:
docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md.
"""
```

`scripts/cube_validate/__main__.py`:

```python
"""Entry point: uv run --with tableauhyperapi python -m scripts.cube_validate."""

from .cli import main

raise SystemExit(main())
```

`scripts/cube_validate/cli.py`:

```python
"""Command line: plan, run, answers, analyze, close."""

from __future__ import annotations

import argparse

COMMANDS = ("plan", "run", "answers", "analyze", "close")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        s = sub.add_parser(name)
        s.add_argument("checks", help="path to checks/<dashboard>.yml")
        s.add_argument("--snapshot", help="snapshot folder (default: newest)")
        s.add_argument(
            "--period",
            help="START:END dates to capture, e.g. 2025-07-01:2026-06-30",
        )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    raise NotImplementedError(args.command)  # replaced in Task 13
```

Delete the old tool:

```bash
git rm -q scripts/cube_validate.py scripts/cube_validate_snapshot.py \
  tests/scripts/test_cube_validate.py tests/scripts/test_cube_validate_snapshot.py \
  .claude/skills/cube-dashboard/checks/ddi_suite.yml
```

In `scripts/CLAUDE.md`, replace the 2 catalog rows `cube_validate.py` and
`cube_validate_snapshot.py` with one row:

```markdown
| `cube_validate/` | Validate Cube against what a Tableau dashboard shows:
capture both sides once in the dashboard's evening window (extract, exports,
Cube rows and answers), reconcile rows into named buckets, compare each exported
number with Cube's, and write a report plus hand checks.
`python -m scripts.cube_validate <plan|run|answers|analyze|close>`. Runbook: the
`cube-dashboard` skill. |
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/cube_validate/test_package.py -v` Expected:
PASS (argparse exits 2 on an unknown command).

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate tests/scripts/cube_validate scripts/CLAUDE.md
git commit -m "refactor(cube): start the cube_validate package and remove the cell-first tool"
```

---

### Task 2: Hyper read and write

**Files:**

- Create: `scripts/cube_validate/hyper.py`
- Test: `tests/scripts/cube_validate/test_hyper.py`

**Interfaces:**

- Produces:
  - `EXTRACT_TABLE = '"Extract"."Extract"'`
  - `write_table(path: Path, schema: str, table: str, columns: list[tuple[str, str]], rows: Iterable[Sequence]) -> int`
    — column types are `"text" | "double" | "bigint" | "date" | "bool"`;
    replaces the file; returns rows written.
  - `class Workspace(scratch: Path, attach: dict[str, Path])` — context manager
    whose own tables are always `create temporary table` (Hyper resolves
    unqualified names only for temporary tables once files are attached);
    manager; `.execute(sql) -> None`, `.query(sql) -> list[tuple]`,
    `.dicts(sql) -> list[dict]`, `.columns(alias, schema, table) -> list[str]`,
    `.count(sql_from_where: str) -> int`.

Reused deliberately: the old `Hyper` reader (`68c59490a5`,
`scripts/cube_validate_snapshot.py:441-468`) becomes `Workspace`, which also
attaches several files and writes the scratch database.

- [ ] **Step 1: Write the failing test**

`tests/scripts/cube_validate/test_hyper.py`:

```python
"""Hyper write and attach. Needs tableauhyperapi (uv run --with)."""

import datetime as dt

import pytest

pytest.importorskip("tableauhyperapi")

from cube_validate import hyper  # noqa: E402


def test_write_then_join_two_files(tmp_path):
    a, b = tmp_path / "a.hyper", tmp_path / "b.hyper"
    hyper.write_table(
        a, "Extract", "Extract", [("k", "bigint"), ("d", "date")],
        [(1, dt.date(2026, 10, 6)), (2, dt.date(2026, 10, 7))],
    )
    n = hyper.write_table(b, "cube", "rows", [("k", "bigint"), ("v", "text")], [(2, "x"), (3, None)])
    assert n == 2
    with hyper.Workspace(tmp_path / "work.hyper", {"tab": a, "cub": b}) as ws:
        got = ws.dicts(
            'select coalesce(t.k, c.k) as k, t.d, c.v from "tab"."Extract"."Extract" t '
            'full outer join "cub"."cube"."rows" c on t.k = c.k order by 1'
        )
        assert got == [
            {"k": 1, "d": dt.date(2026, 10, 6), "v": None},
            {"k": 2, "d": dt.date(2026, 10, 7), "v": "x"},
            {"k": 3, "d": None, "v": None},
        ]
        assert ws.columns("cub", "cube", "rows") == ["k", "v"]
        ws.execute('create temporary table t2 as select * from "cub"."cube"."rows"')
        assert ws.count("t2 where v is null") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_hyper.py -v`
Expected: FAIL with `ImportError: cannot import name 'hyper'`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/hyper.py`:

```python
"""Read and write .hyper files with the Hyper API, added per run with --with."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

EXTRACT_TABLE = '"Extract"."Extract"'


def _api():
    # trunk-ignore(pyright/reportMissingImports): added per run with uv run --with
    import tableauhyperapi

    return tableauhyperapi


def _sql_type(api, name: str):
    return {
        "text": api.SqlType.text(),
        "double": api.SqlType.double(),
        "bigint": api.SqlType.big_int(),
        "date": api.SqlType.date(),
        "bool": api.SqlType.bool(),
    }[name]


def _py(v):
    """Hyper's Date and Timestamp values as Python's."""
    for attr in ("to_date", "to_datetime"):
        if hasattr(v, attr):
            return getattr(v, attr)()
    return v


def write_table(
    path: Path,
    schema: str,
    table: str,
    columns: list[tuple[str, str]],
    rows: Iterable[Sequence],
) -> int:
    """Write one table to a new .hyper file, replacing any file at path.

    Args:
        path: The .hyper file to create.
        schema: Schema name, e.g. "cube".
        table: Table name, e.g. "rows".
        columns: (name, type) pairs; type is text, double, bigint, date or bool.
        rows: Row values in column order.

    Returns:
        The number of rows written.
    """
    api = _api()
    definition = api.TableDefinition(
        api.TableName(schema, table),
        [
            api.TableDefinition.Column(n, _sql_type(api, t), api.NULLABLE)
            for n, t in columns
        ],
    )
    n = 0
    with api.HyperProcess(api.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with api.Connection(
            hp.endpoint, str(path), api.CreateMode.CREATE_AND_REPLACE
        ) as con:
            con.catalog.create_schema(schema)
            con.catalog.create_table(definition)
            with api.Inserter(con, definition) as ins:
                for r in rows:
                    ins.add_row(list(r))
                    n += 1
                ins.execute()
    return n


class Workspace:
    """A Hyper session over a scratch database, with other files attached.

    Args:
        scratch: The database created (replaced) for this session's tables.
        attach: Alias to .hyper file; query them as "<alias>"."<schema>"."<table>".
    """

    def __init__(self, scratch: Path, attach: dict[str, Path]):
        self.scratch, self.attach = Path(scratch), dict(attach)

    def __enter__(self) -> Workspace:
        api = _api()
        self._hp = api.HyperProcess(api.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU)
        self._con = api.Connection(
            self._hp.endpoint, str(self.scratch), api.CreateMode.CREATE_AND_REPLACE
        )
        for alias, path in self.attach.items():
            self._con.catalog.attach_database(str(path), alias=alias)
        return self

    def __exit__(self, *exc) -> None:
        self._con.close()
        self._hp.close()

    def execute(self, sql: str) -> None:
        self._con.execute_command(sql)

    def query(self, sql: str) -> list[tuple]:
        with self._con.execute_query(sql) as result:
            return [tuple(_py(v) for v in r) for r in result]

    def dicts(self, sql: str) -> list[dict]:
        with self._con.execute_query(sql) as result:
            names = [c.name.unescaped for c in result.schema.columns]
            return [dict(zip(names, (_py(v) for v in r), strict=True)) for r in result]

    def columns(self, alias: str, schema: str, table: str) -> list[str]:
        api = _api()
        d = self._con.catalog.get_table_definition(api.TableName(alias, schema, table))
        return [c.name.unescaped for c in d.columns]

    def count(self, from_where: str) -> int:
        """count(*) over `<table> [where ...]`."""
        return int(self.query(f"select count(*) from {from_where}")[0][0])
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_hyper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/hyper.py tests/scripts/cube_validate/test_hyper.py
git commit -m "feat(cube): hyper read, write and attach for the validation snapshot"
```

---

### Task 3: Checks file and snapshot layout

**Files:**

- Create: `scripts/cube_validate/config.py`, `scripts/cube_validate/snapshot.py`
- Test: `tests/scripts/cube_validate/test_config.py`,
  `tests/scripts/cube_validate/test_snapshot.py`

**Interfaces:**

- Produces (`config.py`):
  - `class ConfigError(ValueError)`
  - dataclasses `Window`, `Expr`, `FieldMap`, `ParamValue`, `MeasureMap`,
    `SheetMap`, `Click`, `Cut`, `Cause`, `CubeRows`, `Checks` (fields below)
  - `load_checks(path: str | Path) -> Checks`
  - `side_sql(expr: str, prefix: str) -> str` — a bare column name becomes
    `"<prefix><name>"`; anything else is SQL with `{p}` replaced by `prefix`.
  - `lit(value: str | None) -> str` — a single-quoted SQL literal, or `NULL`.
  - `OWNERS = ("cube", "dashboard", "source", "undecided")`,
    `RESERVED = ("match", "value_differs", "dashboard_only", "cube_only", "outside_scope", "unexplained")`
- Produces (`snapshot.py`):
  - `SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"`
  - `class Snapshot(dir: Path)` with properties `twbx`, `extract`, `cube`,
    `cube_parts`, `answers`, `manifest_path`, `analysis`, and
    `export_path(cut_id, sheet) -> Path`
  - `new_snapshot(dashboard: str, now: datetime, tag: str = "", root: Path = SNAPSHOT_ROOT) -> Snapshot`
  - `latest_snapshot(dashboard: str, root: Path = SNAPSHOT_ROOT) -> Snapshot`
  - `read_manifest(snap) -> dict`, `write_manifest(snap, m: dict) -> None`
  - `slug(s: str) -> str`

The checks file format (this is also the Attendance skeleton's shape in Task
14):

```yaml
dashboard: attendance_dashboard # exposure name; the snapshot folder
workbook: Attendance Dashboard # Tableau workbook name
workbook_luid: 87c13e78-a912-40a4-95dd-33248fc1cbd3
review_project_luid: ddc817c2-6bc7-4bca-8be9-e385f95b9ebc
dashboards: [Overview] # Tableau dashboard tabs in scope
datasource: rpt_tableau__attendance_dashboard (kipptaf_tableau)
dashboard_table: teamster-332318.kipptaf_tableau.rpt_tableau__attendance_dashboard
period_start: 2026-07-01 # rows captured from here to today
window:
  { start: "15:30", end: "06:00", extract_after: "15:00", tz: America/New_York }
cost_cap_gb: 50
tableau_quiet_minutes: [0, 10]
cube:
  view: student_attendance_enrollment_daily_view
  date: attendance_date
  members: [lea_student_identifier, attendance_date, locations_abbreviation]
  filters: [] # Cube filters on every row part
rows:
  student_key: student # which key part is the student
  date_key: day # which key part is the day
  scope_key: school # key part Cube's scope is checked on
  key:
    student: { tableau: student_number, cube: lea_student_identifier }
    day: { tableau: calendardate, cube: attendance_date }
    school: { tableau: school_abbreviation, cube: locations_abbreviation }
  compare:
    is_absent: { tableau: is_absent, cube: is_absent }
  labels:
    region: { tableau: region, cube: regions_region_name }
causes: [] # {id, description, where, owner}
filters: {} # caption -> field map
params: {} # caption -> value -> {tableau, cube_column, cube_filters}
sheets: {} # sheet -> {view?, students?, dims, measures}
cuts:
  - { id: default }
excluded_sheets: {} # sheet -> reason
```

A field map (`filters.<caption>`, `sheets.<sheet>.dims.<header>`):
`{tableau: <column or SQL with {p}>, cube: <member short name>, cube_column: <captured Cube column or SQL with {p}>, values: {<Tableau label>: <stored value>}, cube_values: {<Tableau label>: <Cube value>}}`.
A measure map (`sheets.<sheet>.measures.<header>`):
`{cube: <member short name>, scale: 1.0}`.

- [ ] **Step 1: Write the failing tests**

`tests/scripts/cube_validate/test_config.py`:

```python
"""Checks file loading."""

import datetime as dt

import pytest
import yaml

from cube_validate import config

BASE = {
    "dashboard": "attendance_dashboard",
    "workbook": "Attendance Dashboard",
    "workbook_luid": "87c13e78",
    "review_project_luid": "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc",
    "dashboards": ["Overview"],
    "datasource": "rpt (ds)",
    "dashboard_table": "p.d.t",
    "period_start": "2026-07-01",
    "window": {"start": "15:30", "end": "06:00", "extract_after": "15:00", "tz": "America/New_York"},
    "cost_cap_gb": 50,
    "cube": {"view": "v", "date": "attendance_date", "members": ["lea_student_identifier"]},
    "rows": {
        "student_key": "student",
        "date_key": "day",
        "scope_key": "school",
        "key": {
            "student": {"tableau": "student_number", "cube": "lea_student_identifier"},
            "day": {"tableau": "calendardate", "cube": "attendance_date"},
            "school": {"tableau": "school_abbreviation", "cube": "locations_abbreviation"},
        },
        "compare": {"is_absent": {"tableau": "is_absent", "cube": "is_absent"}},
    },
    "cuts": [{"id": "default"}],
}


def _write(tmp_path, **over):
    data = {**BASE, **over}
    p = tmp_path / "c.yml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_loads_a_minimal_checks_file(tmp_path):
    c = config.load_checks(_write(tmp_path))
    assert c.period_start == dt.date(2026, 7, 1)
    assert c.window.start == dt.time(15, 30) and c.window.tz == "America/New_York"
    assert [e.name for e in c.key] == ["student", "day", "school"]
    assert c.quiet_minutes == (0, 10)
    assert c.cuts[0].id == "default" and c.causes == ()


def test_first_cut_must_be_a_bare_default(tmp_path):
    with pytest.raises(config.ConfigError, match="first cut"):
        config.load_checks(_write(tmp_path, cuts=[{"id": "x", "filters": {"A": "1"}}]))


def test_cause_needs_a_known_owner_and_a_free_id(tmp_path):
    bad_owner = [{"id": "x", "description": "d", "where": "true", "owner": "me"}]
    with pytest.raises(config.ConfigError, match="owner"):
        config.load_checks(_write(tmp_path, causes=bad_owner))
    reserved = [{"id": "unexplained", "description": "d", "where": "true", "owner": "cube"}]
    with pytest.raises(config.ConfigError, match="reserved"):
        config.load_checks(_write(tmp_path, causes=reserved))


def test_student_and_date_keys_must_be_key_parts(tmp_path):
    rows = {**BASE["rows"], "student_key": "pupil"}
    with pytest.raises(config.ConfigError, match="student_key"):
        config.load_checks(_write(tmp_path, rows=rows))


def test_sheet_maps_read_dims_measures_and_view(tmp_path):
    sheets = {
        "ADA by School": {
            "students": "Student Count",
            "dims": {"School": {"tableau": "school_abbreviation", "cube": "locations_abbreviation",
                                "cube_column": "locations_abbreviation"}},
            "measures": {"ADA": {"cube": "avg_daily_attendance"}},
        }
    }
    c = config.load_checks(_write(tmp_path, sheets=sheets))
    s = c.sheets["ADA by School"]
    assert s.view == "v" and s.students == "Student Count"
    assert s.dims["School"].cube == "locations_abbreviation"
    assert s.measures["ADA"].scale == 1.0


def test_side_sql_and_lit():
    assert config.side_sql("grade_level", "t_") == '"t_grade_level"'
    assert config.side_sql('"{p}grade_level" >= 9', "c_") == '"c_grade_level" >= 9'
    assert config.lit("O'Neil") == "'O''Neil'"
    assert config.lit(None) == "NULL"
```

`tests/scripts/cube_validate/test_snapshot.py`:

```python
"""Snapshot folders and manifest."""

import datetime as dt

from cube_validate import snapshot


def test_new_and_latest_snapshot(tmp_path):
    a = snapshot.new_snapshot("dash", dt.datetime(2026, 10, 15, 16, 5), root=tmp_path)
    b = snapshot.new_snapshot("dash", dt.datetime(2026, 10, 15, 21, 0), "2025-26", root=tmp_path)
    assert a.dir.name == "2026-10-15T1605" and b.dir.name == "2026-10-15T2100-2025-26"
    assert snapshot.latest_snapshot("dash", root=tmp_path).dir == b.dir


def test_manifest_round_trip_and_export_path(tmp_path):
    s = snapshot.new_snapshot("dash", dt.datetime(2026, 10, 15, 16, 5), root=tmp_path)
    snapshot.write_manifest(s, {"cuts": {"default": {}}})
    assert snapshot.read_manifest(s) == {"cuts": {"default": {}}}
    p = s.export_path("default", "ADA by School")
    assert p == s.dir / "exports" / "default" / "ada-by-school.csv" and p.parent.is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run pytest tests/scripts/cube_validate/test_config.py tests/scripts/cube_validate/test_snapshot.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/config.py`:

```python
"""Load and check a dashboard's checks file, and the SQL helpers that read it."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

OWNERS = ("cube", "dashboard", "source", "undecided")
RESERVED = (
    "match",
    "value_differs",
    "dashboard_only",
    "cube_only",
    "outside_scope",
    "unexplained",
)
DEFAULT_QUIET = (0, 10)
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(ValueError):
    """The checks file is missing a key or holds a value the tool cannot use."""


@dataclass(frozen=True)
class Window:
    start: dt.time
    end: dt.time
    extract_after: dt.time
    tz: str


@dataclass(frozen=True)
class Expr:
    """One named value read from each side: a column name, or SQL with {p}."""

    name: str
    tableau: str
    cube: str


@dataclass(frozen=True)
class FieldMap:
    caption: str
    tableau: str | None = None
    cube: str | None = None
    cube_column: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    cube_values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParamValue:
    tableau: str | None = None
    cube_column: str | None = None
    cube_filters: tuple[dict, ...] = ()


@dataclass(frozen=True)
class MeasureMap:
    column: str
    cube: str | None
    scale: float = 1.0


@dataclass(frozen=True)
class SheetMap:
    name: str
    view: str
    dims: dict[str, FieldMap]
    measures: dict[str, MeasureMap]
    students: str | None = None


@dataclass(frozen=True)
class Click:
    source_sheet: str
    mark: str = "largest"


@dataclass(frozen=True)
class Cut:
    id: str
    filters: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    click: Click | None = None


@dataclass(frozen=True)
class Cause:
    id: str
    description: str
    where: str
    owner: str


@dataclass(frozen=True)
class CubeRows:
    view: str
    date: str
    members: tuple[str, ...]
    filters: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Checks:
    dashboard: str
    workbook: str
    workbook_luid: str
    review_project_luid: str
    dashboards: tuple[str, ...]
    datasource: str
    dashboard_table: str
    period_start: dt.date
    window: Window
    cost_cap_gb: float
    quiet_minutes: tuple[int, int]
    cube: CubeRows
    key: tuple[Expr, ...]
    compare: tuple[Expr, ...]
    labels: tuple[Expr, ...]
    student_key: str
    date_key: str
    scope_key: str | None
    causes: tuple[Cause, ...]
    filters: dict[str, FieldMap]
    params: dict[str, dict[str, ParamValue]]
    sheets: dict[str, SheetMap]
    cuts: tuple[Cut, ...]
    excluded_sheets: dict[str, str]


def side_sql(expr: str, prefix: str) -> str:
    """SQL for one side's value: a bare column gets the prefix, SQL gets {p}."""
    if _IDENT.match(expr):
        return f'"{prefix}{expr}"'
    return expr.replace("{p}", prefix)


def lit(value: str | None) -> str:
    """A SQL literal. Always quoted, so Hyper coerces it to the column's type."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _time(s: str) -> dt.time:
    h, m = str(s).split(":")
    return dt.time(int(h), int(m))


def _req(d: dict, key: str, where: str = "checks file"):
    if key not in d or d[key] in (None, ""):
        raise ConfigError(f"{where}: missing {key}")
    return d[key]


def _exprs(d: dict | None, where: str) -> tuple[Expr, ...]:
    out = []
    for name, v in (d or {}).items():
        out.append(Expr(name, _req(v, "tableau", f"{where}.{name}"), _req(v, "cube", f"{where}.{name}")))
    return tuple(out)


def _field(caption: str, v: dict) -> FieldMap:
    return FieldMap(
        caption=caption,
        tableau=v.get("tableau"),
        cube=v.get("cube"),
        cube_column=v.get("cube_column"),
        values={str(k): str(x) for k, x in (v.get("values") or {}).items()},
        cube_values={str(k): str(x) for k, x in (v.get("cube_values") or {}).items()},
    )


def _cut(i: int, v: dict) -> Cut:
    click = v.get("click")
    return Cut(
        id=str(_req(v, "id", f"cuts[{i}]")),
        filters={str(k): str(x) for k, x in (v.get("filters") or {}).items()},
        params={str(k): str(x) for k, x in (v.get("params") or {}).items()},
        click=Click(click["source_sheet"], click.get("mark", "largest")) if click else None,
    )


def load_checks(path: str | Path) -> Checks:
    """Read a checks file and refuse what the tool cannot use.

    Args:
        path: The checks YAML file.

    Returns:
        The checks as dataclasses.

    Raises:
        ConfigError: A key is missing, a cause is malformed, or the cuts do not
            start with a bare default.
    """
    d = yaml.safe_load(Path(path).read_text()) or {}
    w = _req(d, "window")
    cube = _req(d, "cube")
    rows = _req(d, "rows")
    key = _exprs(_req(rows, "key", "rows"), "rows.key")
    names = {e.name for e in key}
    for k in ("student_key", "date_key"):
        if _req(rows, k, "rows") not in names:
            raise ConfigError(f"rows.{k} must name a key part ({', '.join(sorted(names))})")
    scope_key = rows.get("scope_key")
    if scope_key is not None and scope_key not in names:
        raise ConfigError("rows.scope_key must name a key part")

    causes = []
    for i, c in enumerate(d.get("causes") or []):
        cid = str(_req(c, "id", f"causes[{i}]"))
        if cid in RESERVED:
            raise ConfigError(f"cause id {cid} is reserved for a bucket")
        if c.get("owner") not in OWNERS:
            raise ConfigError(f"cause {cid}: owner must be one of {', '.join(OWNERS)}")
        causes.append(Cause(cid, _req(c, "description", cid), _req(c, "where", cid), c["owner"]))
    if len({c.id for c in causes}) != len(causes):
        raise ConfigError("cause ids must be unique")

    cuts = tuple(_cut(i, c) for i, c in enumerate(_req(d, "cuts")))
    first = cuts[0]
    if first.id != "default" or first.filters or first.params or first.click:
        raise ConfigError("the first cut must be {id: default} with no filters, params or click")
    if len({c.id for c in cuts}) != len(cuts):
        raise ConfigError("cut ids must be unique")

    view = _req(cube, "view", "cube")
    sheets = {}
    for name, s in (d.get("sheets") or {}).items():
        s = s or {}
        sheets[name] = SheetMap(
            name=name,
            view=s.get("view") or view,
            dims={h: _field(h, v or {}) for h, v in (s.get("dims") or {}).items()},
            measures={
                h: MeasureMap(h, (v or {}).get("cube"), float((v or {}).get("scale", 1.0)))
                for h, v in (s.get("measures") or {}).items()
            },
            students=s.get("students"),
        )
    params = {
        cap: {
            str(val): ParamValue(
                (pv or {}).get("tableau"),
                (pv or {}).get("cube_column"),
                tuple((pv or {}).get("cube_filters") or ()),
            )
            for val, pv in (vals or {}).items()
        }
        for cap, vals in (d.get("params") or {}).items()
    }
    quiet = d.get("tableau_quiet_minutes") or DEFAULT_QUIET
    return Checks(
        dashboard=_req(d, "dashboard"),
        workbook=_req(d, "workbook"),
        workbook_luid=_req(d, "workbook_luid"),
        review_project_luid=_req(d, "review_project_luid"),
        dashboards=tuple(_req(d, "dashboards")),
        datasource=_req(d, "datasource"),
        dashboard_table=_req(d, "dashboard_table"),
        period_start=dt.date.fromisoformat(str(_req(d, "period_start"))),
        window=Window(_time(_req(w, "start", "window")), _time(_req(w, "end", "window")),
                      _time(_req(w, "extract_after", "window")), _req(w, "tz", "window")),
        cost_cap_gb=float(_req(d, "cost_cap_gb")),
        quiet_minutes=(int(quiet[0]), int(quiet[1])),
        cube=CubeRows(view, _req(cube, "date", "cube"), tuple(_req(cube, "members", "cube")),
                      tuple(cube.get("filters") or ())),
        key=key,
        compare=_exprs(rows.get("compare"), "rows.compare"),
        labels=_exprs(rows.get("labels"), "rows.labels"),
        student_key=rows["student_key"],
        date_key=rows["date_key"],
        scope_key=scope_key,
        causes=tuple(causes),
        filters={cap: _field(cap, v or {}) for cap, v in (d.get("filters") or {}).items()},
        params=params,
        sheets=sheets,
        cuts=cuts,
        excluded_sheets={str(k): str(v) for k, v in (d.get("excluded_sheets") or {}).items()},
    )
```

`scripts/cube_validate/snapshot.py`:

```python
"""Snapshot folders: everything one capture froze, and what analysis wrote."""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


@dataclass(frozen=True)
class Snapshot:
    dir: Path

    @property
    def twbx(self) -> Path:
        return self.dir / "live.twbx"

    @property
    def extract(self) -> Path:
        return self.dir / "extract.hyper"

    @property
    def cube(self) -> Path:
        return self.dir / "cube.hyper"

    @property
    def cube_parts(self) -> Path:
        p = self.dir / "cube_parts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def answers(self) -> Path:
        return self.dir / "answers.json"

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def analysis(self) -> Path:
        p = self.dir / "analysis"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def export_path(self, cut_id: str, sheet: str) -> Path:
        p = self.dir / "exports" / slug(cut_id) / f"{slug(sheet)}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def new_snapshot(
    dashboard: str, now: dt.datetime, tag: str = "", root: Path = SNAPSHOT_ROOT
) -> Snapshot:
    name = now.strftime("%Y-%m-%dT%H%M") + (f"-{tag}" if tag else "")
    d = Path(root) / dashboard / name
    d.mkdir(parents=True, exist_ok=False)
    return Snapshot(d)


def latest_snapshot(dashboard: str, root: Path = SNAPSHOT_ROOT) -> Snapshot:
    base = Path(root) / dashboard
    dirs = sorted(p for p in base.iterdir() if p.is_dir() and p.name != "plan") if base.exists() else []
    if not dirs:
        raise FileNotFoundError(f"no snapshot for {dashboard} under {base}")
    return Snapshot(dirs[-1])


def read_manifest(snap: Snapshot) -> dict:
    return json.loads(snap.manifest_path.read_text()) if snap.manifest_path.exists() else {}


def write_manifest(snap: Snapshot, m: dict) -> None:
    snap.manifest_path.write_text(json.dumps(m, indent=2, sort_keys=True, default=str))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
`uv run pytest tests/scripts/cube_validate/test_config.py tests/scripts/cube_validate/test_snapshot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/config.py scripts/cube_validate/snapshot.py \
  tests/scripts/cube_validate/test_config.py tests/scripts/cube_validate/test_snapshot.py
git commit -m "feat(cube): checks file and snapshot layout for the redesigned validator"
```

---

### Task 4: Workbook reading, review copy, extract unpacking (ported)

**Files:**

- Create: `scripts/cube_validate/workbook.py`
- Test: `tests/scripts/cube_validate/test_workbook.py`

**Interfaces:**

- Produces: `FilterCard`, `Param`, `Action`, `SheetFilter`, `Workbook`,
  `read_workbook(twb_text: str) -> Workbook`,
  `review_copy(twb_text, dashboards, sheets=None) -> str`,
  `views_to_hide(twb_text, keep: set[str]) -> list[str]`,
  `build_review_twbx(live_twbx: Path, out_dir: Path, dashboards: list[str], listed: set[str] | None) -> tuple[Path, list[str]]`,
  `unpack_extracts(twbx: Path, out_dir: Path) -> dict[str, dict]` (caption →
  `{"file", "refreshed"}`), `twb_text(twbx: Path) -> str`, and new
  `formulas(twb_text: str) -> dict[str, str]` (column caption → calculation
  formula), `ReviewCopyError`.

Reused deliberately (spec lists the download and `.hyper` reader; this task adds
the workbook parser and review-copy builder, both proven on the DDI run).

- [ ] **Step 1: Port the code verbatim**

```bash
src=scripts/cube_validate_snapshot.py
{
  printf '"""Read a Tableau workbook, build its review copy, unpack its extracts.\n\nPorted from the cell-first tool (68c59490a5); proven on the DDI Suite run.\n"""\n\nfrom __future__ import annotations\n\n'
  printf 'import datetime as dt\nimport re\nimport subprocess\nimport zipfile\nfrom dataclasses import dataclass, field\nfrom pathlib import Path\n\nimport defusedxml.ElementTree as SafeET\n\n'
  git show 68c59490a5:$src | sed -n '35,38p'
  echo
  git show 68c59490a5:$src | sed -n '956,962p'      # _is_number
  echo
  git show 68c59490a5:$src | sed -n '41,323p'       # dataclasses .. _action
  echo
  git show 68c59490a5:$src | sed -n '326,369p'      # ReviewCopyError .. _strip_click_filters
  git show 68c59490a5:$src | sed -n '383,436p'      # review_copy, views_to_hide
  echo
  printf 'REPO = Path(__file__).resolve().parents[2]\nXML_SCRIPTS = REPO / "docs" / "tableau-xml" / "scripts"\n\n\n'
  git show 68c59490a5:$src | sed -n '1155,1236p'    # _run, build_review_twbx, unpack_extracts
} > scripts/cube_validate/workbook.py
```

Then edit `workbook.py`:

1. In `_run`, replace `raise SessionError(` with `raise ReviewCopyError(`.
2. Append:

```python
def twb_text(twbx: Path) -> str:
    """The .twb inside a .twbx."""
    with zipfile.ZipFile(twbx) as z:
        return z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode("utf-8")


def formulas(twb_text: str) -> dict[str, str]:
    """Each calculated column's caption and formula, for formula-gap cells."""
    root = SafeET.fromstring(twb_text)
    out: dict[str, str] = {}
    for c in root.iter("column"):
        calc = c.find("calculation")
        if calc is None or not calc.get("formula"):
            continue
        name = (c.get("name") or "").strip("[]")
        out.setdefault(caption_of(c, name), calc.get("formula") or "")
    return out
```

Run
`uv run python -c "import ast,sys; ast.parse(open('scripts/cube_validate/workbook.py').read())"`
and `uv run ruff check scripts/cube_validate/workbook.py` (fix unused imports
only; behavior stays verbatim).

- [ ] **Step 2: Port the tests and add one for `formulas`**

Create `tests/scripts/cube_validate/test_workbook.py` from these test functions
of `git show 68c59490a5:tests/scripts/test_cube_validate_snapshot.py`, with the
module alias `snap` replaced by `workbook` and the helpers they use copied too
(`FIX`, and any `_twb`/`_wb` builders they call):
`test_read_workbook_lists_each_dashboards_sheets`,
`test_review_copy_exposes_dashboard_sheets_only`,
`test_review_copy_exposes_only_the_listed_sheets`,
`test_review_copy_sets_on_empty_all_and_strips_click_filters`,
`test_review_copy_is_valid_xml_and_leaves_the_rest_alone`,
`test_review_copy_refuses_a_dashboard_it_cannot_find`,
`test_review_copy_detects_a_sheet_left_hidden`,
`test_views_to_hide_keeps_only_the_named_views`,
`test_read_workbook_reads_each_sheets_saved_filters`,
`test_read_workbook_lists_groups_with_their_bins`. Header of the file:

```python
"""Workbook parsing and review copy (ported tests) plus formulas."""

from pathlib import Path

import pytest

from cube_validate import workbook

FIX = Path(__file__).parents[1] / "fixtures" / "cube_validate"
```

Add:

```python
def test_formulas_maps_captions_to_calculations():
    twb = (
        "<workbook><datasources><datasource name='d' caption='D'>"
        "<column name='[Calc_1]' caption='ADA'><calculation class='tableau' "
        "formula='SUM([is_present]) / SUM([membershipvalue])' /></column>"
        "<column name='[region]' /></datasource></datasources></workbook>"
    )
    assert workbook.formulas(twb) == {"ADA": "SUM([is_present]) / SUM([membershipvalue])"}
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/scripts/cube_validate/test_workbook.py -v` Expected:
PASS (11 tests). A failure here is a porting slip: compare the function against
`68c59490a5`, do not change the test.

- [ ] **Step 4: Commit**

```bash
git add scripts/cube_validate/workbook.py tests/scripts/cube_validate/test_workbook.py
git commit -m "feat(cube): port the workbook parser and review-copy builder"
```

---

### Task 5: Rows layer

**Files:**

- Create: `scripts/cube_validate/rows.py`
- Test: `tests/scripts/cube_validate/test_rows.py`

**Interfaces:**

- Consumes: `hyper.Workspace`, `hyper.write_table`, `config.Checks`,
  `config.side_sql`, `config.lit`.
- Produces:
  - `TAB = '"tab"."Extract"."Extract"'`, `CUB = '"cub"."cube"."rows"'`
  - `class RowsError(RuntimeError)`
  - `@dataclass RowsResult(totals: dict[str, int], buckets: list[dict], differing_columns: dict[str, int], invariants: dict[str, bool])`
    — each bucket dict has the label names, `month`, `base`, `cause`, `rows`,
    `students`.
  - `build(ws: Workspace, checks: Checks, scope: list[str]) -> RowsResult` —
    creates table `rows` in the workspace's scratch database.
  - Columns of `rows` that later tasks read: `in_t`, `in_c`, `k_<key>`,
    `l_<label>`, `d_<compare>`, `base`, `cause`, `t_<extract column>`,
    `c_<cube column>`, `t__dup`, `c__dup`, `t__v_<compare>`, `c__v_<compare>`.

- [ ] **Step 1: Write the failing tests (planted gaps A1)**

`tests/scripts/cube_validate/test_rows.py`:

```python
"""Rows layer with planted gaps: each plant has an exact expected bucket count."""

import dataclasses
import datetime as dt

import pytest

pytest.importorskip("tableauhyperapi")

from cube_validate import config, hyper, rows  # noqa: E402

D = [dt.date(2026, 10, 5), dt.date(2026, 10, 6), dt.date(2026, 10, 7)]
STUDENTS = {101: "Rise", 102: "Rise", 103: "TEAM", 104: "TEAM"}
TAB_COLS = [("student_number", "bigint"), ("calendardate", "date"),
            ("school_abbreviation", "text"), ("region", "text"), ("is_absent", "double")]
CUB_COLS = [("lea_student_identifier", "double"), ("attendance_date", "date"),
            ("locations_abbreviation", "text"), ("regions_region_name", "text"),
            ("is_absent", "double"), ("membership_value", "double")]


def _tab_rows():
    return [(s, d, sc, "Newark", 0.0) for s, sc in STUDENTS.items() for d in D]


def _cub_rows():
    return [(float(s), d, sc, "Newark", 0.0, 1.0) for s, sc in STUDENTS.items() for d in D]


def _checks(causes=()):
    return config.Checks(
        dashboard="d", workbook="w", workbook_luid="l", review_project_luid="p",
        dashboards=("Overview",), datasource="ds", dashboard_table="p.d.t",
        period_start=D[0],
        window=config.Window(dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York"),
        cost_cap_gb=50, quiet_minutes=(0, 10),
        cube=config.CubeRows("v", "attendance_date", ()),
        key=(config.Expr("student", "student_number", "cast(\"{p}lea_student_identifier\" as bigint)"),
             config.Expr("day", "calendardate", "attendance_date"),
             config.Expr("school", "school_abbreviation", "locations_abbreviation")),
        compare=(config.Expr("is_absent", "is_absent", "is_absent"),),
        labels=(config.Expr("region", "region", "regions_region_name"),),
        student_key="student", date_key="day", scope_key="school",
        causes=tuple(causes), filters={}, params={}, sheets={},
        cuts=(config.Cut("default"),), excluded_sheets={},
    )


def _run(tmp_path, tab, cub, checks=None, scope=("Rise", "TEAM")):
    hyper.write_table(tmp_path / "e.hyper", "Extract", "Extract", TAB_COLS, tab)
    hyper.write_table(tmp_path / "c.hyper", "cube", "rows", CUB_COLS, cub)
    with hyper.Workspace(tmp_path / "a.hyper", {"tab": tmp_path / "e.hyper", "cub": tmp_path / "c.hyper"}) as ws:
        res = rows.build(ws, checks or _checks(), list(scope))
        by = {}
        for b in res.buckets:
            by[(b["base"], b["cause"])] = by.get((b["base"], b["cause"]), 0) + b["rows"]
        return res, by


def test_clean_sides_all_match(tmp_path):
    res, by = _run(tmp_path, _tab_rows(), _cub_rows())
    assert by == {("match", None): 12}
    assert all(res.invariants.values())


def test_school_day_deleted_from_cube_is_dashboard_only(tmp_path):
    cub = [r for r in _cub_rows() if not (r[2] == "Rise" and r[1] == D[1])]
    res, by = _run(tmp_path, _tab_rows(), cub)
    assert by == {("match", None): 10, ("dashboard_only", "unexplained"): 2}
    assert all(res.invariants.values())


def test_flipped_absences_are_value_differs_on_that_column(tmp_path):
    cub = [(*r[:4], 1.0 if r[0] == 101.0 else r[4], r[5]) for r in _cub_rows()]
    res, by = _run(tmp_path, _tab_rows(), cub)
    assert by[("value_differs", "unexplained")] == 3
    assert res.differing_columns == {"is_absent": 3}


def test_moved_school_is_one_dashboard_only_and_one_cube_only(tmp_path):
    cub = [(r[0], r[1], "TEAM" if (r[0] == 101.0 and r[1] == D[0]) else r[2], *r[3:]) for r in _cub_rows()]
    _, by = _run(tmp_path, _tab_rows(), cub)
    assert by[("dashboard_only", "unexplained")] == 1 and by[("cube_only", "unexplained")] == 1


def test_duplicate_dashboard_row_is_dashboard_only_and_claimable(tmp_path):
    tab = _tab_rows() + [(101, D[0], "Rise", "Newark", 0.0)]
    cause = config.Cause("dup", "duplicate dashboard row", "t__dup > 1", "dashboard")
    res, by = _run(tmp_path, tab, _cub_rows(), _checks([cause]))
    assert by[("dashboard_only", "dup")] == 1 and res.totals["tableau"] == 13
    assert all(res.invariants.values())


def test_school_outside_cube_scope(tmp_path):
    tab = _tab_rows() + [(105, D[0], "Hatch", "Newark", 0.0)]
    _, by = _run(tmp_path, tab, _cub_rows())
    assert by[("outside_scope", "outside_scope")] == 1


def test_cause_claims_only_its_rows(tmp_path):
    cub = _cub_rows() + [(101.0, dt.date(2026, 10, 10), "Rise", "Newark", None, 0.0)]
    cause = config.Cause("break", "break day", "base = 'cube_only' and c_membership_value = 0", "dashboard")
    _, by = _run(tmp_path, _tab_rows(), cub, _checks([cause]))
    assert by[("cube_only", "break")] == 1 and by[("match", None)] == 12


def test_overlapping_causes_are_a_tool_error(tmp_path):
    cub = [r for r in _cub_rows() if r[1] != D[2]]
    a = config.Cause("a", "a", "base = 'dashboard_only'", "cube")
    b = config.Cause("b", "b", "k_day = '2026-10-07'", "cube")
    with pytest.raises(rows.RowsError, match="a, b"):
        _run(tmp_path, _tab_rows(), cub, _checks([a, b]))


def test_buckets_carry_labels_month_and_students(tmp_path):
    res, _ = _run(tmp_path, _tab_rows(), _cub_rows())
    (b,) = res.buckets
    assert b["region"] == "Newark" and b["month"] == dt.date(2026, 10, 1)
    assert b["students"] == 4 and res.totals == {"tableau": 12, "cube": 12, "joined": 12}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_rows.py -v`
Expected: FAIL with `ImportError: cannot import name 'rows'`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/rows.py`:

```python
"""Rows layer: join the extract's rows to Cube's, and give each exactly 1 bucket."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Checks, lit, side_sql

TAB = '"tab"."Extract"."Extract"'
CUB = '"cub"."cube"."rows"'
CAUSED = ("value_differs", "dashboard_only", "cube_only")
T_BUCKETS = ("match", "value_differs", "dashboard_only", "outside_scope")
C_BUCKETS = ("match", "value_differs", "cube_only")


class RowsError(RuntimeError):
    """The tool's own cause list or join broke a rule. Data never raises this."""


@dataclass
class RowsResult:
    totals: dict[str, int]
    buckets: list[dict]
    differing_columns: dict[str, int]
    invariants: dict[str, bool]


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _side(ws, checks: Checks, alias: str, schema: str, table: str, p: str) -> str:
    """One side's rows: raw columns prefixed, plus key, compare and label values."""
    side = "tableau" if p == "t" else "cube"
    src = f'"{alias}"."{schema}"."{table}"'
    cols = [f"{_q(c)} as {_q(f'{p}_{c}')}" for c in ws.columns(alias, schema, table)]
    keys = [f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__k_{e.name}')}" for e in checks.key]
    vals = [f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__v_{e.name}')}" for e in checks.compare]
    labs = [f"({side_sql(getattr(e, side), '')}) as {_q(f'{p}__l_{e.name}')}" for e in checks.labels]
    part = ", ".join(f"({side_sql(getattr(e, side), '')})" for e in checks.key)
    dup = f"row_number() over (partition by {part} order by {part}) as {_q(f'{p}__dup')}"
    sel = ", ".join([*cols, *keys, *vals, *labs, dup, f"true as {_q(f'{p}__in')}"])
    return f"select {sel} from {src}"


def build(ws, checks: Checks, scope: list[str]) -> RowsResult:
    """Join both sides into table `rows` with a base bucket and a cause per row.

    Args:
        ws: A hyper.Workspace with the extract attached as "tab" and Cube's rows
            as "cub".
        checks: The checks file.
        scope: The scope key's values Cube can see; dashboard-only rows outside
            it are "outside_scope".

    Returns:
        Totals, bucket counts, differing-column counts and the 2 balance
        invariants.

    Raises:
        RowsError: 2 causes claim the same row.
    """
    t = _side(ws, checks, "tab", "Extract", "Extract", "t")
    c = _side(ws, checks, "cub", "cube", "rows", "c")
    on = " and ".join(
        [f"t.{_q(f't__k_{e.name}')} = c.{_q(f'c__k_{e.name}')}" for e in checks.key]
        + ['t."t__dup" = c."c__dup"']
    )
    keys = [f"coalesce(t.{_q(f't__k_{e.name}')}, c.{_q(f'c__k_{e.name}')}) as {_q(f'k_{e.name}')}" for e in checks.key]
    labels = [f"coalesce(t.{_q(f't__l_{e.name}')}, c.{_q(f'c__l_{e.name}')}) as {_q(f'l_{e.name}')}" for e in checks.labels]
    diffs = [
        f"not (t.{_q(f't__v_{e.name}')} is not distinct from c.{_q(f'c__v_{e.name}')}) as {_q(f'd_{e.name}')}"
        for e in checks.compare
    ]
    joined = (
        "select t.*, c.*, coalesce(t.\"t__in\", false) as in_t, coalesce(c.\"c__in\", false) as in_c, "
        + ", ".join([*keys, *labels, *diffs])
        + f" from ({t}) t full outer join ({c}) c on {on}"
    )
    any_diff = " or ".join(f"j.{_q(f'd_{e.name}')}" for e in checks.compare) or "false"
    if checks.scope_key and scope:
        k = f"j.{_q(f'k_{checks.scope_key}')}"
        outside = f"{k} is null or {k} not in ({', '.join(lit(s) for s in scope)})"
    else:
        outside = "false"
    base = (
        f"case when j.in_t and j.in_c then case when {any_diff} then 'value_differs' else 'match' end "
        f"when j.in_t then case when {outside} then 'outside_scope' else 'dashboard_only' end "
        "else 'cube_only' end"
    )
    ws.execute(f"create temporary table rows_base as select j.*, {base} as base from ({joined}) j")

    caused = ", ".join(lit(b) for b in CAUSED)
    if checks.causes:
        flags = ", ".join(
            f"case when base in ({caused}) and ({x.where}) then 1 else 0 end as {_q(f'z_{i}')}"
            for i, x in enumerate(checks.causes)
        )
        total = " + ".join(_q(f"z_{i}") for i in range(len(checks.causes)))
        cols = ", ".join(_q(f"z_{i}") for i in range(len(checks.causes)))
        over = ws.query(f"select {cols}, count(*) from (select {flags} from rows_base) z where {total} > 1 group by {cols}")
        if over:
            msgs = []
            for r in over:
                ids = ", ".join(x.id for x, f in zip(checks.causes, r[:-1], strict=True) if f)
                msgs.append(f"{ids} ({r[-1]} rows)")
            raise RowsError("causes overlap, so a row would get 2 causes: " + "; ".join(msgs))
    whens = " ".join(f"when ({x.where}) then {lit(x.id)}" for x in checks.causes)
    cause = (
        "case when base = 'match' then null when base = 'outside_scope' then 'outside_scope' "
        f"{whens} else 'unexplained' end"
    )
    ws.execute(f"create temporary table rows as select *, {cause} as cause from rows_base")
    ws.execute("drop table rows_base")
    return _summarize(ws, checks)


def _summarize(ws, checks: Checks) -> RowsResult:
    labels = [f"l_{e.name}" for e in checks.labels]
    month = f'cast(date_trunc(\'month\', {_q(f"k_{checks.date_key}")}) as date)'
    group = [*(_q(n) for n in labels), month, "base", "cause"]
    sel = ", ".join([*(f"{_q(n)} as {_q(n[2:])}" for n in labels), f"{month} as month", "base", "cause"])
    buckets = ws.dicts(
        f"select {sel}, count(*) as rows, count(distinct {_q(f'k_{checks.student_key}')}) as students "
        f"from rows group by {', '.join(group)} order by {', '.join(group)}"
    )
    n_tab, n_cub = ws.count(TAB), ws.count(CUB)
    n_join = ws.count("rows")
    in_t, in_c = ws.count("rows where in_t"), ws.count("rows where in_c")
    t_sum = ws.count(f"rows where base in ({', '.join(lit(b) for b in T_BUCKETS)})")
    c_sum = ws.count(f"rows where base in ({', '.join(lit(b) for b in C_BUCKETS)})")
    differing = {}
    for e in checks.compare:
        differing[e.name] = ws.count(f"rows where base = 'value_differs' and {_q(f'd_{e.name}')}")
    return RowsResult(
        totals={"tableau": n_tab, "cube": n_cub, "joined": n_join},
        buckets=buckets,
        differing_columns={k: v for k, v in differing.items() if v},
        invariants={
            "dashboard rows balance": n_tab == in_t == t_sum,
            "Cube rows balance": n_cub == in_c == c_sum,
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_rows.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/rows.py tests/scripts/cube_validate/test_rows.py
git commit -m "feat(cube): rows layer joins both sides into one bucket per row"
```

---

### Task 6: Cut drafting

**Files:**

- Create: `scripts/cube_validate/cuts.py`
- Test: `tests/scripts/cube_validate/test_cuts.py`

**Interfaces:**

- Consumes: `workbook.Workbook`, `workbook.FilterCard`, `workbook.Param`,
  `workbook.Action`.
- Produces:
  `draft_cuts(wb: Workbook, dashboards: list[str], values: dict[str, list[str]]) -> list[dict]`
  (cut dicts in the checks-file shape, `default` first) and
  `plan_yaml(wb, dashboards, columns: list[str], values) -> str` (the draft the
  analyst edits into the checks file).

Rules (spec, _Cuts_): default; each filter card at 1 non-default value; each
list parameter's non-default values; each filter action once (largest mark).
Group bins are covered by the card that filters on the group; a group not on any
card gets no cut (the report lists it under excluded logic).

- [ ] **Step 1: Write the failing test**

`tests/scripts/cube_validate/test_cuts.py`:

```python
"""Cut drafting from the workbook."""

import yaml

from cube_validate import cuts, workbook


def _wb():
    return workbook.Workbook(
        dashboards={"Overview": ["ADA by School", "Trend"]},
        filters=[
            workbook.FilterCard("Overview", "region", "Region", "ds", False, True),
            workbook.FilterCard("Overview", "academic_year", "Year", "ds", False, False,
                                default_values=("2026",)),
        ],
        params=[workbook.Param("Overview", "Metric", ("ADA", "Tardy"), "ADA")],
        actions=[workbook.Action("Overview", "Click school", "ADA by School", "filter", "Overview", ())],
    )


def test_draft_cuts_one_per_piece_of_logic():
    got = cuts.draft_cuts(_wb(), ["Overview"], {"Region": ["Camden", "Newark"], "Year": ["2025", "2026"]})
    assert got == [
        {"id": "default"},
        {"id": "filter-region", "filters": {"Region": "Camden"}},
        {"id": "filter-year", "filters": {"Year": "2025"}},
        {"id": "param-metric-tardy", "params": {"Metric": "Tardy"}},
        {"id": "click-ada-by-school", "click": {"source_sheet": "ADA by School", "mark": "largest"}},
    ]


def test_plan_yaml_lists_sheets_columns_and_cuts():
    text = cuts.plan_yaml(_wb(), ["Overview"], ["student_number", "region"], {"Region": ["Camden"]})
    d = yaml.safe_load(text)
    assert d["sheets"] == {"ADA by School": {}, "Trend": {}}
    assert d["extract_columns"] == ["student_number", "region"]
    assert d["cuts"][0] == {"id": "default"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/cube_validate/test_cuts.py -v` Expected: FAIL
with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/cuts.py`:

```python
"""Draft a dashboard's cut list: 1 cut per piece of dashboard logic."""

from __future__ import annotations

import yaml

from .snapshot import slug
from .workbook import Workbook


def _non_default(values: list[str], defaults: tuple[str, ...]) -> str | None:
    return next((v for v in values if v not in defaults), None)


def draft_cuts(wb: Workbook, dashboards: list[str], values: dict[str, list[str]]) -> list[dict]:
    """The default view, each card at 1 other value, each parameter value, each click.

    Args:
        wb: The parsed workbook.
        dashboards: The dashboard tabs in scope.
        values: Each card caption's distinct extract values, sorted.

    Returns:
        Cut dicts in the checks-file shape, default first.
    """
    out: list[dict] = [{"id": "default"}]
    seen: set[str] = set()
    for f in wb.filters:
        if f.dashboard not in dashboards or f.caption in seen:
            continue
        seen.add(f.caption)
        pool = list(f.values) or values.get(f.caption, [])
        v = _non_default(pool, f.default_values)
        if v is not None:
            out.append({"id": f"filter-{slug(f.caption)}", "filters": {f.caption: v}})
    for p in wb.params:
        if p.dashboard not in dashboards:
            continue
        for v in p.values:
            if v != p.default:
                out.append({"id": f"param-{slug(p.caption)}-{slug(v)}", "params": {p.caption: v}})
    for a in wb.actions:
        if a.dashboard in dashboards and a.kind == "filter":
            out.append({"id": f"click-{slug(a.source_sheet)}",
                        "click": {"source_sheet": a.source_sheet, "mark": "largest"}})
    return out


def plan_yaml(wb: Workbook, dashboards: list[str], columns: list[str], values: dict[str, list[str]]) -> str:
    """The draft the analyst edits into the checks file: sheets, columns, cuts."""
    sheets = {s: {} for d in dashboards for s in wb.dashboards.get(d, [])}
    draft = {
        "sheets": sheets,
        "extract_columns": columns,
        "filter_cards": sorted({f.caption for f in wb.filters if f.dashboard in dashboards}),
        "params": sorted({p.caption for p in wb.params if p.dashboard in dashboards}),
        "cuts": draft_cuts(wb, dashboards, values),
    }
    return yaml.safe_dump(draft, sort_keys=False, allow_unicode=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/cube_validate/test_cuts.py -v` Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/cuts.py tests/scripts/cube_validate/test_cuts.py
git commit -m "feat(cube): draft one cut per piece of dashboard logic"
```

---

### Task 7: Cells layer

**Files:**

- Create: `scripts/cube_validate/cells.py`
- Test: `tests/scripts/cube_validate/test_cells.py`

**Interfaces:**

- Consumes: `config.Checks`, `config.Cut`, `config.FieldMap`, `config.side_sql`,
  `config.lit`; table `rows` from Task 5.
- Produces:
  - verdict constants `PASS`, `COINCIDENTAL`, `ROW_GAP`, `FORMULA_GAP`,
    `FILTER_IGNORED`, `UNPROVEN`, `NO_COUNTERPART`, `NO_ROWS`; `NEVER_CUBE` (the
    4 that are never Cube findings).
  - `class MappingGap(KeyError)` — a caption, header or param with no mapping.
  - `norm_value(v) -> str | None`, `parse_display(s) -> Display | None`,
    `display_equal(tableau: str | None, cube: float | None, scale: float = 1.0) -> bool`,
    `parse_export(data: bytes) -> list[dict[str, str]]`.
  - `cube_query(checks, sheet: str, cut: Cut, click_filters: dict[str, str]) -> dict`
    — used by capture (Task 10) and preflight (Task 11).
  - `answer_key(cut_id: str, sheet: str) -> str` → `"<cut>|<sheet>"`.
  - `verdict(equal: bool, buckets: list) -> str`.
  - `@dataclass Cell(cut, sheet, dims: dict[str, str], measure, tableau: str | None, cube: float | None, verdict, reason="", buckets: list[tuple] = [], students: tuple[int, int] = (0, 0))`.
  - `judge(ws, checks, manifest: dict, answers: dict, export: Callable[[str, str], bytes | None]) -> list[Cell]`.
- Manifest keys read: `manifest["cuts"][cut_id]["click_filters"]` (dict) and
  `["click_targets"]` (list of sheets).
- Answers shape:
  `answers[answer_key(cut, sheet)] = {"query", "data": [row dicts], "last_refresh", "sql", "error"}`.

- [ ] **Step 1: Write the failing tests (planted gaps A2)**

`tests/scripts/cube_validate/test_cells.py`:

```python
"""Cells layer: display precision, verdicts, predicates, and planted cell gaps."""

import datetime as dt

import pytest

from cube_validate import cells, config


def test_display_equal_reads_precision_from_the_export():
    assert cells.display_equal("94.2%", 0.94213)
    assert not cells.display_equal("94.2%", 0.9436)
    assert cells.display_equal("1,204", 1204.0)
    assert cells.display_equal("0.94213", 0.942130000001)
    assert cells.display_equal("", None) and not cells.display_equal("", 0.5)


def test_display_equal_rounds_half_up():
    assert cells.display_equal("94.3%", 0.9425)


def test_parse_export_pivots_measure_names_and_drops_totals():
    data = (
        "School,Measure Names,Measure Values\n"
        "Rise,ADA,94.2%\nRise,Students,300\nGrand Total,ADA,93.0%\n"
    ).encode("utf-8-sig")
    assert cells.parse_export(data) == [{"School": "Rise", "ADA": "94.2%", "Students": "300"}]


def test_norm_value_reads_tableau_and_cube_formats():
    assert cells.norm_value("10/6/2026") == "2026-10-06"
    assert cells.norm_value("2026-10-06T00:00:00.000") == "2026-10-06"
    assert cells.norm_value("1,204") == "1204"
    assert cells.norm_value("Null") is None


@pytest.mark.parametrize(
    ("equal", "buckets", "want"),
    [
        (True, [("match", None, 5, 2)], cells.PASS),
        (True, [("match", None, 5, 2), ("cube_only", "x", 1, 1)], cells.COINCIDENTAL),
        (False, [("match", None, 5, 2), ("dashboard_only", None, 1, 1)], cells.ROW_GAP),
        (False, [("match", None, 5, 2)], cells.FORMULA_GAP),
        (False, [], cells.NO_ROWS),
    ],
)
def test_verdict(equal, buckets, want):
    assert cells.verdict(equal, buckets) == want


def _checks(**over):
    base = dict(
        dashboard="d", workbook="w", workbook_luid="l", review_project_luid="p",
        dashboards=("Overview",), datasource="ds", dashboard_table="p.d.t",
        period_start=dt.date(2026, 7, 1),
        window=config.Window(dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York"),
        cost_cap_gb=50, quiet_minutes=(0, 10),
        cube=config.CubeRows("v", "attendance_date", ()),
        key=(config.Expr("student", "student_number", "lea_student_identifier"),
             config.Expr("day", "calendardate", "attendance_date")),
        compare=(), labels=(), student_key="student", date_key="day", scope_key=None,
        causes=(),
        filters={"Region": config.FieldMap("Region", "region", "regions_region_name", "regions_region_name")},
        params={},
        sheets={"ADA": config.SheetMap(
            "ADA", "v",
            dims={"School": config.FieldMap("School", "school_abbreviation", "locations_abbreviation",
                                            "locations_abbreviation")},
            measures={"ADA": config.MeasureMap("ADA", "avg_daily_attendance")},
            students="Students",
        )},
        cuts=(config.Cut("default"), config.Cut("filter-region", {"Region": "Camden"})),
        excluded_sheets={},
    )
    base.update(over)
    return config.Checks(**base)


def test_cube_query_maps_filters_dims_and_adds_count_students():
    q = cells.cube_query(_checks(), "ADA", config.Cut("filter-region", {"Region": "Camden"}), {})
    assert q["measures"] == ["v.avg_daily_attendance", "v.count_students"]
    assert q["dimensions"] == ["v.locations_abbreviation"]
    assert q["filters"] == [{"member": "v.regions_region_name", "operator": "equals", "values": ["Camden"]}]


def test_cube_query_refuses_an_unmapped_filter():
    with pytest.raises(cells.MappingGap, match="Grade"):
        cells.cube_query(_checks(), "ADA", config.Cut("x", {"Grade": "9"}), {})


def _rows_table(ws, extra=()):
    """A minimal rows table as Task 5 builds it."""
    ws.execute(
        "create temporary table rows (in_t bool, in_c bool, k_student bigint, k_day date, base text, cause text, "
        "t_region text, t_school_abbreviation text, c_regions_region_name text, c_locations_abbreviation text)"
    )
    vals = [
        "(true, true, 1, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', 'Rise')",
        "(true, true, 2, '2026-10-06', 'match', null, 'Newark', 'Rise', 'Newark', 'Rise')",
        "(true, true, 3, '2026-10-06', 'match', null, 'Camden', 'LSP', 'Camden', 'LSP')",
        *extra,
    ]
    ws.execute("insert into rows values " + ", ".join(vals))


def _judge(tmp_path, exports, answers, checks=None, extra=(), manifest=None):
    pytest.importorskip("tableauhyperapi")
    from cube_validate import hyper

    with hyper.Workspace(tmp_path / "a.hyper", {}) as ws:
        _rows_table(ws, extra)
        return cells.judge(ws, checks or _checks(), manifest or {"cuts": {}}, answers,
                           lambda cut, sheet: exports.get((cut, sheet)))


def _ans(cut, rows):
    return {cells.answer_key(cut, "ADA"): {"data": rows, "last_refresh": "x", "sql": "s", "query": {}}}


def test_matching_cells_pass(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n",
               ("filter-region", "ADA"): b"School,ADA,Students\nLSP,90.0%,1\n"}
    answers = {
        **_ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
                           {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"}]),
        **_ans("filter-region", [{"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"}]),
    }
    got = _judge(tmp_path, exports, answers)
    assert [c.verdict for c in got] == [cells.PASS] * 3


def test_shifted_cube_value_is_a_formula_gap_on_that_cell_only(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.95"},
                               {"v.locations_abbreviation": "LSP", "v.avg_daily_attendance": "0.9"}])
    checks = _checks(cuts=(config.Cut("default"),))
    got = {c.dims["School"]: c.verdict for c in _judge(tmp_path, exports, answers, checks)}
    assert got == {"Rise": cells.FORMULA_GAP, "LSP": cells.PASS}


def test_row_gap_lists_its_buckets(tmp_path):
    extra = ["(true, false, 4, '2026-10-06', 'dashboard_only', 'unexplained', 'Newark', 'Rise', null, null)"]
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,3\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.95"}])
    checks = _checks(cuts=(config.Cut("default"),))
    (c,) = [x for x in _judge(tmp_path, exports, answers, checks, extra) if x.measure == "ADA"]
    assert c.verdict == cells.ROW_GAP
    assert ("dashboard_only", "unexplained", 1, 1) in c.buckets and c.students == (3, 2)


def test_ignored_filter_is_never_judged(tmp_path):
    same = b"School,ADA,Students\nRise,94.2%,2\nLSP,90.0%,1\n"
    exports = {("default", "ADA"): same, ("filter-region", "ADA"): same}
    answers = {**_ans("default", []), **_ans("filter-region", [])}
    got = [c for c in _judge(tmp_path, exports, answers) if c.cut == "filter-region"]
    assert got and all(c.verdict == cells.FILTER_IGNORED for c in got)


def test_wrong_student_count_makes_the_cut_unproven(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,7\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}])
    got = _judge(tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),)))
    assert {c.verdict for c in got} == {cells.UNPROVEN}


def test_cut_without_a_student_count_is_unproven_with_one_reason(tmp_path):
    sheet = _checks().sheets["ADA"]
    checks = _checks(cuts=(config.Cut("default"),),
                     sheets={"ADA": config.SheetMap("ADA", "v", sheet.dims, sheet.measures, None)})
    exports = {("default", "ADA"): b"School,ADA\nRise,94.2%\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}])
    got = _judge(tmp_path, exports, answers, checks)
    assert {(c.verdict, c.reason) for c in got} == {(cells.UNPROVEN, "no sheet in this cut shows a student count")}


def test_cell_outside_the_captured_rows_is_not_a_formula_gap(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students\nRise,94.2%,2\nHatch,88.0%,0\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"},
                               {"v.locations_abbreviation": "Hatch", "v.avg_daily_attendance": "0.87"}])
    got = {c.dims["School"]: c.verdict for c in _judge(tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),)))
           if c.measure == "ADA"}
    assert got["Hatch"] == cells.NO_ROWS


def test_unmapped_measure_has_no_cube_counterpart(tmp_path):
    exports = {("default", "ADA"): b"School,ADA,Students,Tardy\nRise,94.2%,2,3.0%\n"}
    answers = _ans("default", [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}])
    got = {c.measure: c.verdict for c in _judge(tmp_path, exports, answers, _checks(cuts=(config.Cut("default"),)))}
    assert got["Tardy"] == cells.NO_COUNTERPART and got["ADA"] == cells.PASS
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_cells.py -v`
Expected: FAIL with `ImportError: cannot import name 'cells'`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/cells.py`:

```python
"""Cells layer: compare each exported Tableau number with Cube's, explain by rows."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .config import Checks, Cut, FieldMap, lit, side_sql

PASS = "pass"
COINCIDENTAL = "coincidental match"
ROW_GAP = "row gap"
FORMULA_GAP = "formula gap"
FILTER_IGNORED = "filter ignored"
UNPROVEN = "mapping unproven"
NO_COUNTERPART = "no Cube counterpart"
NO_ROWS = "no captured rows"
NEVER_CUBE = (FILTER_IGNORED, UNPROVEN, NO_COUNTERPART, NO_ROWS)
ORDER = (ROW_GAP, FORMULA_GAP, COINCIDENTAL, PASS, *NEVER_CUBE)

ALL = "(All)"
NULLS = ("", "Null", "(Blank)", "%null%")
TOTALS = ("Total", "Grand Total")
_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_ISO_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})T00:00:00(\.0+)?Z?$")
_GROUPED_INT = re.compile(r"^-?\d{1,3}(,\d{3})+$")


class MappingGap(KeyError):
    """A filter caption, sheet header or parameter value has no mapping."""


def norm_value(v) -> str | None:
    """A value as both sides store it: ISO dates, plain integers, None for blank."""
    if v is None:
        return None
    s = str(v).strip()
    if s in NULLS:
        return None
    if m := _US_DATE.match(s):
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if m := _ISO_TS.match(s):
        return m.group(1)
    if _GROUPED_INT.match(s):
        return s.replace(",", "")
    return s


@dataclass(frozen=True)
class Display:
    value: float
    decimals: int
    percent: bool


def parse_display(s: str | None) -> Display | None:
    """A number as Tableau exported it, with its decimals and percent sign."""
    if s is None:
        return None
    t = s.strip().replace(",", "")
    if t in NULLS:
        return None
    percent = t.endswith("%")
    t = t.rstrip("%").strip()
    try:
        value = float(t)
    except ValueError:
        return None
    return Display(value, len(t.split(".", 1)[1]) if "." in t else 0, percent)


def display_equal(tableau: str | None, cube: float | None, scale: float = 1.0) -> bool:
    """Cube's value rounded the way Tableau displayed its own (half up)."""
    d = parse_display(tableau)
    if d is None or cube is None:
        return d is None and cube is None
    v = Decimal(repr(cube * scale * (100 if d.percent else 1)))
    shown = float(v.quantize(Decimal(1).scaleb(-d.decimals), rounding=ROUND_HALF_UP))
    return math.isclose(shown, d.value, rel_tol=1e-9, abs_tol=1e-9)


def parse_export(data: bytes) -> list[dict[str, str]]:
    """Rows of a sheet's CSV export, wide, without total rows."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    if rows and "Measure Names" in rows[0] and "Measure Values" in rows[0]:
        dims = [c for c in rows[0] if c not in ("Measure Names", "Measure Values")]
        wide: dict[tuple, dict] = {}
        for r in rows:
            k = tuple(r[d] for d in dims)
            wide.setdefault(k, {d: r[d] for d in dims})[r["Measure Names"]] = r["Measure Values"]
        rows = list(wide.values())
    return [r for r in rows if not any((v or "").strip() in TOTALS for v in r.values())]


def answer_key(cut_id: str, sheet: str) -> str:
    return f"{cut_id}|{sheet}"


def _stored(fm: FieldMap, label: str | None, side: str) -> str | None:
    n = norm_value(label)
    if label is None or n is None:
        return None
    if side == "c" and label in fm.cube_values:
        return fm.cube_values[label]
    return fm.values.get(label, n)


def _pred(fm: FieldMap, label: str | None, side: str) -> str | None:
    """SQL over table `rows` for field = label on one side; None for (All)."""
    if label == ALL:
        return None
    expr = fm.tableau if side == "t" else fm.cube_column
    if not expr:
        raise MappingGap(f"{fm.caption}: no {'extract' if side == 't' else 'Cube'} column")
    col = side_sql(expr, f"{side}_")
    v = _stored(fm, label, side)
    return f"({col} is null)" if v is None else f"({col} = {lit(v)})"


def cube_query(checks: Checks, sheet: str, cut: Cut, click_filters: dict[str, str]) -> dict:
    """The aggregate Cube query for one sheet under one cut.

    Raises:
        MappingGap: A filter, click field or parameter value is not mapped.
    """
    sm = checks.sheets[sheet]
    v = sm.view
    measures = sorted({f"{v}.{m.cube}" for m in sm.measures.values() if m.cube} | {f"{v}.count_students"})
    dimensions = [f"{v}.{d.cube}" for d in sm.dims.values() if d.cube]
    filters: list[dict] = []
    for caption, label in {**cut.filters, **click_filters}.items():
        if label == ALL:
            continue
        fm = checks.filters.get(caption)
        if fm is None or not fm.cube:
            raise MappingGap(caption)
        stored = _stored(fm, label, "c")
        member = f"{v}.{fm.cube}"
        filters.append(
            {"member": member, "operator": "notSet"}
            if stored is None
            else {"member": member, "operator": "equals", "values": [stored]}
        )
    for caption, value in cut.params.items():
        pv = checks.params.get(caption, {}).get(value)
        if pv is None:
            raise MappingGap(f"{caption} = {value}")
        filters.extend(pv.cube_filters)
    return {"measures": measures, "dimensions": dimensions, "filters": filters, "limit": 50000}


def verdict(equal: bool, buckets: list) -> str:
    """The spec's verdict table for a cell whose cut is judgeable."""
    if not buckets:
        return NO_ROWS
    all_match = all(b[0] == "match" for b in buckets)
    if equal:
        return PASS if all_match else COINCIDENTAL
    return FORMULA_GAP if all_match else ROW_GAP


@dataclass
class Cell:
    cut: str
    sheet: str
    dims: dict[str, str]
    measure: str
    tableau: str | None
    cube: float | None
    verdict: str
    reason: str = ""
    buckets: list[tuple] = field(default_factory=list)
    students: tuple[int, int] = (0, 0)


def _cut_preds(checks: Checks, cut: Cut, click: dict[str, str], side: str) -> list[str]:
    out = []
    for caption, label in {**cut.filters, **click}.items():
        fm = checks.filters.get(caption)
        if fm is None:
            raise MappingGap(caption)
        p = _pred(fm, label, side)
        if p:
            out.append(p)
    for caption, value in cut.params.items():
        pv = checks.params.get(caption, {}).get(value)
        if pv is None:
            raise MappingGap(f"{caption} = {value}")
        expr = pv.tableau if side == "t" else pv.cube_column
        if expr:
            out.append(f"({side_sql(expr, f'{side}_')})")
    return out


def _where(preds_t: list[str], preds_c: list[str]) -> str:
    t = " and ".join(["in_t", *preds_t])
    c = " and ".join(["in_c", *preds_c])
    return f"(({t}) or ({c}))"


def judge(
    ws,
    checks: Checks,
    manifest: dict,
    answers: dict,
    export: Callable[[str, str], bytes | None],
) -> list[Cell]:
    """Every exported number's verdict.

    Args:
        ws: A hyper.Workspace holding table `rows` (Task 5).
        checks: The checks file.
        manifest: The snapshot manifest (click filters per cut).
        answers: Cube answers by answer_key.
        export: Reads a cut's sheet export, or None when it was not exported.

    Returns:
        One Cell per exported number, plus one per Cube mark Tableau did not show.
    """
    student = f'"k_{checks.student_key}"'
    default = checks.cuts[0]
    out: list[Cell] = []
    for cut in checks.cuts:
        meta = (manifest.get("cuts") or {}).get(cut.id, {})
        click = meta.get("click_filters") or {}
        targets = set(meta.get("click_targets") or [])
        exports = {s: export(cut.id, s) for s in checks.sheets}
        try:
            base_t = {s: _cut_preds(checks, cut, click if s in targets else {}, "t") for s in checks.sheets}
            base_c = {s: _cut_preds(checks, cut, click if s in targets else {}, "c") for s in checks.sheets}
            gap = ""
        except MappingGap as e:
            base_t = base_c = {}
            gap = f"not mapped: {e.args[0]}"
        ignored = set()
        if cut.id != default.id and not gap:
            for s, data in exports.items():
                if data is not None and data == export(default.id, s):
                    n_cut = ws.count("rows where " + " and ".join(["in_t", *base_t[s]]))
                    n_def = ws.count("rows where in_t")
                    if n_cut != n_def:
                        ignored.add(s)
        proof = gap or _proof(ws, checks, exports, base_t, student)
        for sheet, data in exports.items():
            if data is None:
                continue
            sm = checks.sheets[sheet]
            ans = answers.get(answer_key(cut.id, sheet)) or {}
            cube_rows = {
                tuple(norm_value(r.get(f"{sm.view}.{d.cube}")) for d in sm.dims.values() if d.cube): r
                for r in ans.get("data") or []
            }
            seen = set()
            for row in parse_export(data):
                dims = {h: v for h, v in row.items() if h in sm.dims}
                unmapped = [h for h, v in row.items() if h not in sm.dims and h not in sm.measures
                            and h != sm.students and parse_display(v) is None and v not in NULLS]
                key = tuple(_stored(sm.dims[h], dims.get(h), "c") for h, d in sm.dims.items() if d.cube)
                key = tuple(norm_value(k) for k in key)
                seen.add(key)
                crow = cube_rows.get(key)
                status, reason, buckets, studs = _status(
                    ws, checks, sheet, row, dims, unmapped, ignored, proof, base_t, base_c, ans, student
                )
                for h, v in row.items():
                    if h in sm.dims or h == sm.students or (h not in sm.measures and parse_display(v) is None):
                        continue
                    m = sm.measures.get(h)
                    cube_v = float(crow[f"{sm.view}.{m.cube}"]) if (m and m.cube and crow and crow.get(f"{sm.view}.{m.cube}") is not None) else None
                    if m is None or not m.cube:
                        vd, rs = NO_COUNTERPART, "measure not mapped"
                    elif status:
                        vd, rs = status, reason
                    else:
                        vd, rs = verdict(display_equal(v, cube_v, m.scale), buckets), ""
                    out.append(Cell(cut.id, sheet, dims, h, v, cube_v, vd, rs, buckets, studs))
            for key, crow in cube_rows.items():
                if key in seen:
                    continue
                for m in sm.measures.values():
                    raw = crow.get(f"{sm.view}.{m.cube}") if m.cube else None
                    if raw is None:
                        continue
                    labels = dict(zip([h for h, d in sm.dims.items() if d.cube], key, strict=True))
                    out.append(Cell(cut.id, sheet, {k: v or "" for k, v in labels.items()}, m.column, None,
                                    float(raw), ROW_GAP if not proof else UNPROVEN,
                                    "Cube shows a mark Tableau does not" if not proof else proof))
    return out


def _proof(ws, checks: Checks, exports: dict, base_t: dict, student: str) -> str:
    """'' when every student count in the cut matches the extract, else why not."""
    checked = 0
    for sheet, data in exports.items():
        sm = checks.sheets[sheet]
        if data is None or not sm.students:
            continue
        for row in parse_export(data):
            want = parse_display(row.get(sm.students))
            if want is None:
                continue
            preds = list(base_t[sheet])
            for h, label in row.items():
                if h in sm.dims:
                    p = _pred(sm.dims[h], label, "t")
                    if p:
                        preds.append(p)
            got = int(ws.query(f"select count(distinct {student}) from rows where " + " and ".join(["in_t", *preds]))[0][0])
            checked += 1
            if got != int(want.value):
                return f"{sheet}: extract has {got} students where Tableau shows {int(want.value)}"
    return "" if checked else "no sheet in this cut shows a student count"


def _status(ws, checks, sheet, row, dims, unmapped, ignored, proof, base_t, base_c, ans, student):
    """(verdict override, reason, buckets, (students dashboard, students Cube))."""
    if sheet in ignored:
        return FILTER_IGNORED, "export equals the default view's", [], (0, 0)
    if proof:
        return UNPROVEN, proof, [], (0, 0)
    if unmapped:
        return NO_COUNTERPART, f"dimension not mapped: {', '.join(unmapped)}", [], (0, 0)
    if ans.get("error") or "data" not in ans:
        return UNPROVEN, f"no Cube answer: {ans.get('error') or 'not captured'}", [], (0, 0)
    sm = checks.sheets[sheet]
    pt, pc = list(base_t[sheet]), list(base_c[sheet])
    for h, label in dims.items():
        for side, acc in (("t", pt), ("c", pc)):
            p = _pred(sm.dims[h], label, side)
            if p:
                acc.append(p)
    where = _where(pt, pc)
    buckets = [tuple(r) for r in ws.query(
        f"select base, cause, count(*), count(distinct {student}) from rows where {where} "
        "group by base, cause order by base, cause"
    )]
    t_and = " and ".join(["in_t", *pt])
    c_and = " and ".join(["in_c", *pc])
    studs = ws.query(
        f"select count(distinct case when {t_and} then {student} end), "
        f"count(distinct case when {c_and} then {student} end) from rows where {where}"
    )[0]
    return "", "", buckets, (int(studs[0]), int(studs[1]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_cells.py -v`
Expected: PASS. If `test_row_gap_lists_its_buckets` fails on `students`, check
the `count(distinct case ...)` query reads `rows where {where}`, not all rows.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/cells.py tests/scripts/cube_validate/test_cells.py
git commit -m "feat(cube): cells layer judges each exported number against Cube by rows"
```

---

### Task 8: Hand checks

**Files:**

- Create: `scripts/cube_validate/handchecks.py`
- Test: `tests/scripts/cube_validate/test_handchecks.py`

**Interfaces:**

- Consumes: `cells.Cell`, verdict constants, table `rows`.
- Produces:
  - `@dataclass HandCheck(id: str, kind: str, title: str, steps: list[str])`
  - `pick(cells: list[Cell], row_samples: list[dict], seed: str, limit: int = 15, passes: int = 3) -> list[HandCheck]`
  - `row_samples(ws, checks) -> list[dict]` — 1 row per non-match
    `(base, cause)`.
  - `write(dir: Path, checks_list: list[HandCheck], review_copy: str, answers: dict) -> tuple[Path, Path]`
    — writes `hand_checks.md` and `hand_checks.yml`, keeping results already
    entered for an id that is still listed.
  - `read_results(path: Path) -> dict[str, str]` — id → `agree`, `disagree` or
    `pending`.

- [ ] **Step 1: Write the failing test**

`tests/scripts/cube_validate/test_handchecks.py`:

```python
"""Hand-check selection and results."""

import yaml

from cube_validate import cells, handchecks


def _cell(v, sheet="ADA", school="Rise"):
    return cells.Cell("default", sheet, {"School": school}, "ADA", "94.2%", 0.95, v)


def test_pick_covers_every_verdict_and_bucket_then_passes():
    cs = [_cell(cells.ROW_GAP), _cell(cells.FORMULA_GAP), *[_cell(cells.PASS, school=f"S{i}") for i in range(10)]]
    rows = [{"base": "cube_only", "cause": "unexplained", "k_student": 1, "k_day": "2026-10-06"}]
    got = handchecks.pick(cs, rows, seed="snap")
    kinds = [(h.kind, h.title) for h in got]
    assert [k for k, _ in kinds].count("cell") == 5 and [k for k, _ in kinds].count("row") == 1
    assert any(cells.ROW_GAP in t for _, t in kinds) and any(cells.FORMULA_GAP in t for _, t in kinds)
    assert handchecks.pick(cs, rows, seed="snap") == got  # deterministic


def test_write_keeps_entered_results(tmp_path):
    hc = [handchecks.HandCheck("C1", "cell", "t", ["s"])]
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {})
    y = tmp_path / "hand_checks.yml"
    data = yaml.safe_load(y.read_text())
    data[0]["result"] = "agree"
    y.write_text(yaml.safe_dump(data))
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {})
    assert handchecks.read_results(y) == {"C1": "agree"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/cube_validate/test_handchecks.py -v` Expected:
FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/handchecks.py`:

````python
"""Hand checks: a short list a person reproduces in Tableau, Cube and the SIS."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cells import NEVER_CUBE, ORDER, PASS, Cell, answer_key


@dataclass
class HandCheck:
    id: str
    kind: str
    title: str
    steps: list[str]
    answer: str = ""  # answer_key of a cell check's Cube query


def row_samples(ws, checks) -> list[dict]:
    """1 row per non-match (base, cause), the first by student and day."""
    s, d = f'"k_{checks.student_key}"', f'"k_{checks.date_key}"'
    pairs = ws.query("select distinct base, cause from rows where base <> 'match' order by 1, 2")
    out = []
    for base, cause in pairs:
        cond = "cause is null" if cause is None else f"cause = '{cause}'"
        r = ws.dicts(f"select * from rows where base = '{base}' and {cond} order by {s}, {d} limit 1")
        out.extend(r)
    return out


def _cell_check(i: int, c: Cell) -> HandCheck:
    where = ", ".join(f"{k} = {v}" for k, v in c.dims.items()) or "the only mark"
    return HandCheck(
        f"C{i}", "cell", f"{c.verdict}: {c.sheet} / {c.measure} ({where}, cut {c.cut})",
        [
            f"In the review copy, open sheet `{c.sheet}` and set cut `{c.cut}` (see manifest.json).",
            f"Find the mark {where}. Tableau should show `{c.tableau}` for {c.measure}.",
            f"Run the Cube query for `{answer_key(c.cut, c.sheet)}` (below). The captured value was `{c.cube}`.",
            f"The tool says **{c.verdict}**{f' ({c.reason})' if c.reason else ''}. Agree?",
        ],
        answer_key(c.cut, c.sheet),
    )


def _row_check(i: int, r: dict) -> HandCheck:
    keys = {k: v for k, v in r.items() if k.startswith("k_")}
    return HandCheck(
        f"R{i}", "row", f"{r['base']} / {r['cause']}: {keys}",
        [
            f"Row key {keys}. Dashboard side present: {r.get('in_t')}; Cube side present: {r.get('in_c')}.",
            "Look the day up in PowerSchool (Newark, Camden, Paterson) or Focus (Miami).",
            f"The tool files it as **{r['base']}**, cause **{r['cause']}**. Does the source agree?",
        ],
    )


def pick(cells: list[Cell], row_samples: list[dict], seed: str, limit: int = 15, passes: int = 3) -> list[HandCheck]:
    """Every verdict and bucket the run produced, then random passes, capped."""
    rng = random.Random(seed)
    firsts: dict[str, Cell] = {}
    for c in sorted(cells, key=lambda c: (c.cut, c.sheet, c.measure, sorted(c.dims.items()))):
        if c.verdict != PASS and c.verdict not in NEVER_CUBE:
            firsts.setdefault(c.verdict, c)
    for c in cells:
        if c.verdict in NEVER_CUBE:
            firsts.setdefault(c.verdict, c)
    head = [firsts[v] for v in ORDER if v in firsts]
    budget = max(limit - passes, 0)
    picked_cells = head[:budget]
    picked_rows = row_samples[: max(budget - len(picked_cells), 0)]
    pool = [c for c in cells if c.verdict == PASS]
    room = min(passes, limit - len(picked_cells) - len(picked_rows))
    picked_cells += rng.sample(pool, min(room, len(pool)))
    out = [_cell_check(i + 1, c) for i, c in enumerate(picked_cells)]
    out += [_row_check(i + 1, r) for i, r in enumerate(picked_rows)]
    return out


def read_results(path: Path) -> dict[str, str]:
    if not Path(path).exists():
        return {}
    return {e["id"]: e.get("result") or "pending" for e in yaml.safe_load(Path(path).read_text()) or []}


def write(dir: Path, checks_list: list[HandCheck], review_copy: str, answers: dict) -> tuple[Path, Path]:
    """Write hand_checks.md (steps) and hand_checks.yml (results to fill in)."""
    dir = Path(dir)
    md, yml = dir / "hand_checks.md", dir / "hand_checks.yml"
    old = read_results(yml)
    lines = ["# Hand checks", "", f"Review copy: `{review_copy}`. Local only: this file names students.", ""]
    for h in checks_list:
        lines += [f"## {h.id}: {h.title}", "", *[f"{n}. {s}" for n, s in enumerate(h.steps, 1)], ""]
        if h.answer:
            q = (answers.get(h.answer) or {}).get("query")
            if q:
                lines += ["```json", json.dumps(q, indent=2), "```", ""]
    md.write_text("\n".join(lines))
    yml.write_text(yaml.safe_dump(
        [{"id": h.id, "result": old.get(h.id, "pending"), "note": ""} for h in checks_list],
        sort_keys=False,
    ))
    return md, yml
````

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/cube_validate/test_handchecks.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/handchecks.py tests/scripts/cube_validate/test_handchecks.py
git commit -m "feat(cube): pick hand checks that cover every verdict and bucket"
```

---

### Task 9: Report

**Files:**

- Create: `scripts/cube_validate/report.py`
- Test: `tests/scripts/cube_validate/test_report.py`

**Interfaces:**

- Consumes: `rows.RowsResult`, `cells.Cell`, verdict constants,
  `handchecks.read_results`.
- Produces:
  - `small(n: int) -> str`
  - `trust(invariants: dict[str, bool], results: dict[str, str]) -> str`
  - `render(checks, manifest: dict, rows_result, cells: list, results: dict, formulas: dict[str, str], answers: dict) -> str`

- [ ] **Step 1: Write the failing test**

`tests/scripts/cube_validate/test_report.py`:

```python
"""Report rendering: small cells, trust verdict, held findings."""

import datetime as dt

from cube_validate import cells, config, report, rows


def test_small_hides_counts_under_ten():
    assert report.small(0) == "0" and report.small(7) == "<10" and report.small(1204) == "1,204"


def test_trust_reads_invariants_then_hand_checks():
    ok = {"a": True}
    assert report.trust({"a": False}, {}).startswith("Not trusted: invariant broken: a")
    assert report.trust(ok, {}).startswith("Pending: no hand checks")
    assert report.trust(ok, {"C1": "pending", "C2": "agree"}).startswith("Pending: 1 of 2")
    assert report.trust(ok, {"C1": "disagree"}).startswith("Not trusted: 1 hand check")
    assert report.trust(ok, {"C1": "agree"}).startswith("Trusted for this run")


def test_render_holds_findings_and_suppresses_small_cells():
    rr = rows.RowsResult(
        totals={"tableau": 12, "cube": 13, "joined": 13},
        buckets=[{"region": "Newark", "month": dt.date(2026, 10, 1), "base": "cube_only",
                  "cause": "unexplained", "rows": 3, "students": 1}],
        differing_columns={}, invariants={"dashboard rows balance": True},
    )
    cs = [cells.Cell("default", "ADA", {"School": "Rise"}, "ADA", "94.2%", 0.95, cells.FORMULA_GAP)]
    checks = config.Checks.__new__(config.Checks)
    object.__setattr__(checks, "dashboard", "attendance_dashboard")
    object.__setattr__(checks, "excluded_sheets", {"Comm Log": "no Cube counterpart"})
    object.__setattr__(checks, "sheets", {"ADA": config.SheetMap("ADA", "v", {}, {"ADA": config.MeasureMap("ADA", "avg_daily_attendance")})})
    text = report.render(checks, {"period": "2026-07-01:2026-10-15"}, rr, cs, {}, {"ADA": "SUM([x])"},
                         {cells.answer_key("default", "ADA"): {"sql": "SELECT 1"}})
    assert "Findings (held until the tool is trusted)" in text
    assert "<10" in text and "| 3 |" not in text
    assert "SUM([x])" in text and "SELECT 1" in text
    assert "Comm Log" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/cube_validate/test_report.py -v` Expected:
FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/report.py`:

````python
"""report.md: trust verdict first, held findings second. Aggregates only."""

from __future__ import annotations

from collections import Counter

from .cells import FORMULA_GAP, ORDER, ROW_GAP, answer_key

SMALL = 10


def small(n: int) -> str:
    """Counts 1 to 9 show as <10, so the report can go to #data_team."""
    return "<10" if 0 < n < SMALL else f"{n:,}"


def trust(invariants: dict[str, bool], results: dict[str, str]) -> str:
    broken = [k for k, v in invariants.items() if not v]
    if broken:
        return f"Not trusted: invariant broken: {', '.join(broken)}."
    if not results:
        return "Pending: no hand checks recorded yet."
    pending = sum(1 for v in results.values() if v == "pending")
    if pending:
        return f"Pending: {pending} of {len(results)} hand checks still open."
    bad = sum(1 for v in results.values() if v == "disagree")
    if bad:
        return f"Not trusted: {bad} hand check{'s' if bad > 1 else ''} disagree."
    return "Trusted for this run: invariants hold and every hand check agrees."


def render(checks, manifest: dict, rows_result, cells: list, results: dict,
           formulas: dict[str, str], answers: dict) -> str:
    inv = {**(manifest.get("invariants") or {}), **rows_result.invariants}
    out = [f"# {checks.dashboard}: Cube validation", ""]
    out += ["## Trust verdict", "", trust(inv, results), "",
            "Unit tests are part of trust: `uv run --with tableauhyperapi pytest tests/scripts/cube_validate`.", ""]
    out += ["## Invariants", "", "| Invariant | Holds |", "| --- | --- |"]
    out += [f"| {k} | {'yes' if v else '**no**'} |" for k, v in inv.items()]
    out += ["", "## Capture", ""]
    for k in ("period", "extract_refreshed", "cube_refresh", "cost", "scope_size", "clock_risk"):
        if k in manifest:
            out.append(f"- {k.replace('_', ' ')}: {manifest[k]}")
    out += ["", "## Findings (held until the tool is trusted)", "", "### Row buckets", ""]
    t = rows_result.totals
    out.append(f"Dashboard rows {small(t['tableau'])}, Cube rows {small(t['cube'])}, joined {small(t['joined'])}.")
    out.append("")
    if rows_result.buckets:
        keys = [k for k in rows_result.buckets[0] if k not in ("rows", "students")]
        out += ["| " + " | ".join(keys) + " | rows | students |", "| " + " | ".join("---" for _ in keys) + " | --- | --- |"]
        for b in rows_result.buckets:
            out.append("| " + " | ".join(str(b[k]) for k in keys) + f" | {small(b['rows'])} | {small(b['students'])} |")
    if rows_result.differing_columns:
        out += ["", "Value differences by column: "
                + ", ".join(f"{k} {small(v)}" for k, v in rows_result.differing_columns.items())]
    out += ["", "### Cell verdicts", "", "| Verdict | Cells |", "| --- | --- |"]
    counts = Counter(c.verdict for c in cells)
    out += [f"| {v} | {small(counts[v])} |" for v in ORDER if counts[v]]
    gaps = [c for c in cells if c.verdict in (ROW_GAP, FORMULA_GAP)]
    if gaps:
        out += ["", "| Cut | Sheet | Measure | Marks | Verdict | Tableau | Cube |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for c in gaps:
            marks = ", ".join(f"{k}={v}" for k, v in c.dims.items())
            out.append(f"| {c.cut} | {c.sheet} | {c.measure} | {marks} | {c.verdict} | {c.tableau} | {c.cube} |")
    shown = set()
    for c in cells:
        if c.verdict != FORMULA_GAP or (c.sheet, c.measure) in shown:
            continue
        shown.add((c.sheet, c.measure))
        out += ["", f"#### Formula gap: {c.sheet} / {c.measure}", "",
                "Workbook formula:", "", "```text", formulas.get(c.measure, "(no calculation found)"), "```", "",
                "Cube SQL:", "", "```sql", (answers.get(answer_key(c.cut, c.sheet)) or {}).get("sql", ""), "```"]
    out += ["", "## Not checked", ""]
    out += [f"- {s}: {why}" for s, why in checks.excluded_sheets.items()] or ["- (none)"]
    return "\n".join(out) + "\n"
````

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/cube_validate/test_report.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/report.py tests/scripts/cube_validate/test_report.py
git commit -m "feat(cube): report puts the trust verdict first and holds findings"
```

---

### Task 10: Cube capture

**Files:**

- Create: `scripts/cube_validate/capture_cube.py`
- Test: `tests/scripts/cube_validate/test_capture_cube.py`

**Interfaces:**

- Consumes: `config.Checks`, `cells.cube_query`, `cells.answer_key`,
  `cells.MappingGap`, `hyper.write_table`, `snapshot.Snapshot`.
- Produces:
  - `CUBE_LIMIT = 50_000`, `DEFAULT_CUBE_URL`, `class CubeError(RuntimeError)`,
    `class CaptureError(RuntimeError)`
  - `@dataclass LoadResult(data: list[dict], last_refresh: str | None, total: int | None)`
  - `class CubeClient(url, secret, email, http=None, sleep=time.sleep, http_factory=None)`
    with `.load(query, renew=False) -> LoadResult`,
    `.sql(query) -> tuple[str, list]`, `.member_types(view) -> dict[str, str]`
    (short name → Cube type).
  - `row_queries(checks, start: date, end: date) -> list[tuple[str, dict]]` —
    `(part_id, query)`, 1 per day.
  - `pull_rows(client, snap, parts, built_at: datetime, workers=8) -> dict[str, dict]`
    — writes `cube_parts/<id>.json`, skips parts already on disk, returns a part
    report; raises `CaptureError` naming every failed part.
  - `write_cube_hyper(snap, checks, types: dict[str, str]) -> tuple[int, list[str]]`
    — rows written and the scope (distinct scope-key values).
  - `capture_answers(client, snap, checks, manifest, built_at, workers=8) -> dict`
    — writes `answers.json`.
  - `client_from_env() -> CubeClient`.

Reused deliberately: the old `CubeClient` (`68c59490a5`,
`scripts/cube_validate.py:144-233`), changed to return `LoadResult` with the
answer's own `lastRefreshTime` and `total`, to accept `renew`, and to compile
via `/sql`.

- [ ] **Step 1: Write the failing tests**

`tests/scripts/cube_validate/test_capture_cube.py`:

```python
"""Cube capture with a fake HTTP client. No live calls."""

import datetime as dt
import json
from types import SimpleNamespace

import pytest

from cube_validate import capture_cube, config, snapshot

BUILT = dt.datetime(2026, 10, 15, 19, 5, tzinfo=dt.UTC)


class FakeHttp:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def post(self, url, json, headers):
        self.calls.append((url, json))
        return SimpleNamespace(status_code=200, json=lambda: self.answer(url, json))

    def get(self, url, headers):
        return SimpleNamespace(status_code=200, json=lambda: self.answer(url, None))


def _client(answer):
    return capture_cube.CubeClient("https://cube/x", "s", "me@x", http=FakeHttp(answer), sleep=lambda s: None)


def _checks():
    return SimpleNamespace(
        cube=config.CubeRows("v", "attendance_date", ("lea_student_identifier", "attendance_date")),
        period_start=dt.date(2026, 10, 5),
    )


def test_row_queries_one_per_day_with_total():
    parts = capture_cube.row_queries(_checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 6))
    assert [p for p, _ in parts] == ["2026-10-05", "2026-10-06"]
    q = parts[0][1]
    assert q["ungrouped"] and q["total"] and q["limit"] == 50000
    assert q["filters"][0] == {"member": "v.attendance_date", "operator": "inDateRange",
                               "values": ["2026-10-05", "2026-10-05"]}


def test_load_returns_the_answers_own_refresh_and_total():
    c = _client(lambda u, q: {"data": [{"a": 1}], "lastRefreshTime": "2026-10-15T20:00:00.000Z", "total": 1})
    r = c.load({"dimensions": []})
    assert r.data == [{"a": 1}] and r.total == 1 and r.last_refresh.startswith("2026-10-15T20")


def test_short_part_fails_capture_naming_the_day(tmp_path):
    snap = snapshot.Snapshot(tmp_path)
    c = _client(lambda u, q: {"data": [{"a": 1}], "lastRefreshTime": "2026-10-15T20:00:00.000Z", "total": 2})
    parts = capture_cube.row_queries(_checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5))
    with pytest.raises(capture_cube.CaptureError, match="2026-10-05: 1 of 2 rows"):
        capture_cube.pull_rows(c, snap, parts, BUILT)
    assert not list(snap.cube_parts.iterdir())


def test_stale_answer_is_renewed_once_then_fails(tmp_path):
    seen = []

    def answer(u, q):
        seen.append(q.get("renewQuery"))
        return {"data": [], "lastRefreshTime": "2026-10-15T10:00:00.000Z", "total": 0}

    snap = snapshot.Snapshot(tmp_path)
    parts = capture_cube.row_queries(_checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5))
    with pytest.raises(capture_cube.CaptureError, match="older than"):
        capture_cube.pull_rows(_client(answer), snap, parts, BUILT)
    assert seen == [None, True]


def test_finished_parts_are_kept_and_skipped(tmp_path):
    snap = snapshot.Snapshot(tmp_path)
    (snap.cube_parts / "2026-10-05.json").write_text(json.dumps({"rows": [], "total": 0, "last_refresh": "x"}))
    c = _client(lambda u, q: pytest.fail("should not ask Cube again"))
    parts = capture_cube.row_queries(_checks(), dt.date(2026, 10, 5), dt.date(2026, 10, 5))
    assert capture_cube.pull_rows(c, snap, parts, BUILT)["2026-10-05"]["status"] == "kept"


def test_sql_returns_the_compiled_query_and_params():
    c = _client(lambda u, q: {"sql": {"sql": ["SELECT ?", ["x"]]}})
    assert c.sql({"measures": []}) == ("SELECT ?", ["x"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scripts/cube_validate/test_capture_cube.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write the implementation**

First port the client body:

```bash
git show 68c59490a5:scripts/cube_validate.py | sed -n '144,233p' > /tmp/old_cube_client.py
```

Then write `scripts/cube_validate/capture_cube.py`, keeping the ported
`_httpx_client`, per-thread `_http`, `_token` and the retry loop of `load`
verbatim except where marked:

```python
"""Cube side of a capture: rows by day, aggregate answers, each stamped."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import cells
from .hyper import write_table

CUBE_LIMIT = 50_000
DEFAULT_CUBE_URL = "https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1"
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
HYPER_TYPES = {"number": "double", "time": "date", "boolean": "bool", "string": "text"}


class CubeError(RuntimeError):
    """Cube returned an error."""


class CaptureError(RuntimeError):
    """Capture could not freeze a complete, current answer; names the parts."""


@dataclass
class LoadResult:
    data: list[dict]
    last_refresh: str | None
    total: int | None


def _httpx_client():
    import httpx

    return httpx.Client(timeout=120)


class CubeClient:
    def __init__(self, url, secret, email, http=None, sleep=time.sleep, http_factory=None):
        self.url, self.secret, self.email = url.rstrip("/"), secret, email
        self._shared = http
        self._factory = http_factory or _httpx_client
        self._local = threading.local()
        self.sleep = sleep

    def _http(self):
        """One HTTP client per thread, so parallel runs never share a connection pool."""
        if self._shared is not None:
            return self._shared
        if getattr(self._local, "client", None) is None:
            self._local.client = self._factory()
        return self._local.client

    def _token(self) -> str:
        import jwt

        now = int(time.time())
        # cube.js checks maxAge from `iat`, so it must be present.
        return jwt.encode({"email": self.email, "iat": now, "exp": now + 300}, self.secret, algorithm="HS256")

    def _post(self, path: str, query: dict) -> dict:
        import httpx

        overloaded = 0
        for _ in range(120):
            try:
                r = self._http().post(f"{self.url}/{path}", json={"query": query},
                                      headers={"Authorization": self._token()})
            except httpx.TransportError as err:
                if overloaded >= 5:
                    raise CubeError(f"Cube connection failed: {err}") from err
                overloaded += 1
                self.sleep(2**overloaded)
                continue
            if r.status_code in (429, 502, 503, 504) and overloaded < 5:
                overloaded += 1
                self.sleep(2**overloaded)
                continue
            try:
                body = r.json()
            except ValueError as e:
                raise CubeError(f"HTTP {r.status_code}: response is not JSON") from e
            if body.get("error") == "Continue wait":
                self.sleep(1)
                continue
            if r.status_code >= 400 or "error" in body:
                raise CubeError(str(body.get("error") or f"HTTP {r.status_code}")[:300])
            return body
        raise CubeError("gave up after 120 'Continue wait' responses")

    def load(self, query: dict, renew: bool = False) -> LoadResult:
        """Rows with this answer's own lastRefreshTime and total."""
        q = {**query, "renewQuery": True} if renew else query
        body = self._post("load", q)
        return LoadResult(body.get("data", []), body.get("lastRefreshTime"), body.get("total"))

    def sql(self, query: dict) -> tuple[str, list]:
        """The BigQuery SQL and parameters Cube compiles; touches no data."""
        body = self._post("sql", query)
        sql, params = body["sql"]["sql"]
        return sql, list(params)

    def member_types(self, view: str) -> dict[str, str]:
        r = self._http().get(f"{self.url}/meta", headers={"Authorization": self._token()})
        for c in r.json().get("cubes", []):
            if c["name"] == view:
                return {m["name"].split(".", 1)[1]: m["type"] for kind in ("measures", "dimensions")
                        for m in c.get(kind, [])}
        raise CubeError(f"view {view} is not visible to {self.email}")


def client_from_env() -> CubeClient:
    email = os.environ.get("CUBE_USER_EMAIL", "").strip()
    if not email and USER_EMAIL_CACHE.exists():
        email = USER_EMAIL_CACHE.read_text().strip()
    if not email:
        raise CubeError("no Cube identity: set CUBE_USER_EMAIL")
    return CubeClient(os.environ.get("CUBE_API_URL", DEFAULT_CUBE_URL), os.environ["CUBE_API_SECRET"], email)


def row_queries(checks, start: dt.date, end: dt.date) -> list[tuple[str, dict]]:
    """1 ungrouped query per day, so each prunes to 1 date partition."""
    v = checks.cube.view
    out = []
    d = start
    while d <= end:
        day = d.isoformat()
        out.append((day, {
            "dimensions": [f"{v}.{m}" for m in checks.cube.members],
            "filters": [{"member": f"{v}.{checks.cube.date}", "operator": "inDateRange", "values": [day, day]},
                        *checks.cube.filters],
            "ungrouped": True, "limit": CUBE_LIMIT, "total": True,
        }))
        d += dt.timedelta(days=1)
    return out


def _ts(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _current(client, query: dict, built_at: dt.datetime) -> tuple[LoadResult, str]:
    """An answer no older than built_at, asking once more if needed."""
    r = client.load(query)
    if (_ts(r.last_refresh) or built_at) < built_at:
        r = client.load(query, renew=True)
        if (_ts(r.last_refresh) or built_at) < built_at:
            return r, f"answer from {r.last_refresh} is older than the build at {built_at.isoformat()}"
    return r, ""


def pull_rows(client, snap, parts: list[tuple[str, dict]], built_at: dt.datetime, workers: int = 8) -> dict[str, dict]:
    """Capture every part; a part is written only when complete and current.

    Raises:
        CaptureError: Any part was short, hit the row limit, or stayed stale.
    """
    report: dict[str, dict] = {}

    def one(part: tuple[str, dict]) -> tuple[str, dict]:
        pid, q = part
        path = snap.cube_parts / f"{pid}.json"
        if path.exists():
            return pid, {"status": "kept"}
        try:
            r, stale = _current(client, q, built_at)
        except CubeError as e:
            return pid, {"status": "failed", "why": str(e)}
        if stale:
            return pid, {"status": "failed", "why": stale}
        if r.total is None or len(r.data) != r.total:
            return pid, {"status": "failed", "why": f"{len(r.data)} of {r.total} rows"}
        if len(r.data) >= CUBE_LIMIT:
            return pid, {"status": "failed", "why": f"hit the {CUBE_LIMIT}-row limit"}
        path.write_text(json.dumps({"rows": r.data, "total": r.total, "last_refresh": r.last_refresh}))
        return pid, {"status": "captured", "rows": len(r.data), "last_refresh": r.last_refresh}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pid, rep in pool.map(one, parts):
            report[pid] = rep
    failed = {p: r["why"] for p, r in report.items() if r["status"] == "failed"}
    if failed:
        raise CaptureError("Cube parts failed: " + "; ".join(f"{p}: {w}" for p, w in sorted(failed.items())))
    return report


def _cast(value, cube_type: str):
    if value is None:
        return None
    if cube_type == "number":
        return float(value)
    if cube_type == "time":
        return dt.date.fromisoformat(str(value)[:10])
    if cube_type == "boolean":
        return value if isinstance(value, bool) else str(value).lower() == "true"
    return str(value)


def write_cube_hyper(snap, checks, types: dict[str, str]) -> tuple[int, list[str]]:
    """cube.hyper from every part file; returns rows written and the scope."""
    v, members = checks.cube.view, list(checks.cube.members)
    columns = [(m, HYPER_TYPES[types[m]]) for m in members]
    scope_member = next((e.cube for e in checks.key if e.name == checks.scope_key), None)
    scope: set[str] = set()

    def rows():
        for f in sorted(snap.cube_parts.glob("*.json")):
            for r in json.loads(f.read_text())["rows"]:
                if scope_member and r.get(f"{v}.{scope_member}") is not None:
                    scope.add(str(r[f"{v}.{scope_member}"]))
                yield [_cast(r.get(f"{v}.{m}"), types[m]) for m in members]

    n = write_table(snap.cube, "cube", "rows", columns, rows())
    return n, sorted(scope)


def capture_answers(client, snap, checks, manifest: dict, built_at: dt.datetime, workers: int = 8) -> dict:
    """1 aggregate answer per (cut, sheet), with its query, SQL and refresh time."""
    jobs = []
    for cut in checks.cuts:
        meta = (manifest.get("cuts") or {}).get(cut.id, {})
        targets = set(meta.get("click_targets") or [])
        for sheet in checks.sheets:
            click = (meta.get("click_filters") or {}) if sheet in targets else {}
            jobs.append((cut, sheet, click))

    def one(job):
        cut, sheet, click = job
        key = cells.answer_key(cut.id, sheet)
        try:
            q = cells.cube_query(checks, sheet, cut, click)
        except cells.MappingGap as e:
            return key, {"error": f"not mapped: {e.args[0]}"}
        try:
            r, stale = _current(client, q, built_at)
            sql, _ = client.sql(q)
        except CubeError as e:
            return key, {"query": q, "error": str(e)}
        if stale:
            return key, {"query": q, "error": stale}
        return key, {"query": q, "data": r.data, "last_refresh": r.last_refresh, "sql": sql}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        answers = dict(pool.map(one, jobs))
    snap.answers.write_text(json.dumps(answers, indent=2))
    return answers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scripts/cube_validate/test_capture_cube.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/capture_cube.py tests/scripts/cube_validate/test_capture_cube.py
git commit -m "feat(cube): capture Cube rows by day and answers, each stamped and complete"
```

---

### Task 11: Preflight

**Files:**

- Create: `scripts/cube_validate/preflight.py`
- Test: `tests/scripts/cube_validate/test_preflight.py`

**Interfaces:**

- Consumes: `config.Window`, `config.Checks`, `capture_cube.row_queries`,
  `cells.cube_query`, `cells.MappingGap`.
- Produces:
  - `class PreflightError(RuntimeError)`
  - `check_window(now: datetime, extract_at: datetime, w: Window) -> str` — `""`
    when fine, else the reason.
  - `class BigQuery(client=None)` with
    `.dry_run(sql, params) -> tuple[int, set[str]]` (bytes, referenced base
    tables) and `.modified(table) -> str` (ISO UTC).
  - `planned_queries(checks, start, end) -> list[tuple[str, dict]]` — row parts
    plus 1 aggregate per (cut, sheet) without click filters; unmapped ones
    skipped.
  - `estimate(cube, bq, queries) -> dict` →
    `{"bytes": int, "tables": sorted list, "sql": {id: sql}, "skipped": [ids]}`.
  - `clock_map(bq, tables) -> dict[str, str]`,
    `changed(before, after) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

`tests/scripts/cube_validate/test_preflight.py`:

```python
"""Preflight: window, cost, clock map. Fakes only."""

import datetime as dt
from zoneinfo import ZoneInfo

from cube_validate import config, preflight

NY = ZoneInfo("America/New_York")
W = config.Window(dt.time(15, 30), dt.time(6), dt.time(15), "America/New_York")


def _ny(d, h, m=0):
    return dt.datetime(2026, 10, d, h, m, tzinfo=NY)


def test_window_accepts_evening_and_overnight_after_todays_refresh():
    assert preflight.check_window(_ny(15, 22), _ny(15, 15, 2), W) == ""
    assert preflight.check_window(_ny(16, 2), _ny(15, 15, 2), W) == ""


def test_window_refuses_daytime_and_a_stale_extract():
    assert "outside" in preflight.check_window(_ny(15, 10), _ny(15, 6, 1), W)
    assert "before" in preflight.check_window(_ny(15, 22), _ny(15, 6, 1), W)


class FakeCube:
    def sql(self, q):
        return f"SELECT /*{len(q.get('dimensions', []))}*/ 1", ["2026-10-05"]


class FakeBQ:
    def dry_run(self, sql, params):
        return 1_000_000, {"p.marts.fct", "p.marts.dim"}

    def modified(self, t):
        return {"p.marts.fct": "2026-10-15T19:05:00+00:00"}.get(t, "2026-10-01T00:00:00+00:00")


def test_estimate_sums_bytes_and_collects_tables():
    got = preflight.estimate(FakeCube(), FakeBQ(), [("a", {}), ("b", {"dimensions": ["x"]})])
    assert got["bytes"] == 2_000_000 and got["tables"] == ["p.marts.dim", "p.marts.fct"]
    assert set(got["sql"]) == {"a", "b"}


def test_clock_map_and_changes():
    before = preflight.clock_map(FakeBQ(), ["p.marts.fct", "p.marts.dim"])
    after = {**before, "p.marts.dim": "2026-10-15T23:00:00+00:00"}
    assert preflight.changed(before, after) == ["p.marts.dim"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scripts/cube_validate/test_preflight.py -v` Expected:
FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`scripts/cube_validate/preflight.py`:

```python
"""Preflight: free checks before anything costs money or touches Tableau."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

from . import cells
from .capture_cube import row_queries

BQ_PROJECT = "teamster-332318"
_INT = re.compile(r"^-?\d+$")


class PreflightError(RuntimeError):
    """A preflight check failed; nothing was spent."""


def _in_window(t: dt.time, w) -> bool:
    if w.start <= w.end:
        return w.start <= t < w.end
    return t >= w.start or t < w.end


def check_window(now: dt.datetime, extract_at: dt.datetime, w) -> str:
    """'' when now is inside the window and the extract is this window's refresh."""
    tz = ZoneInfo(w.tz)
    local = now.astimezone(tz)
    if not _in_window(local.time(), w):
        return f"{local:%H:%M} is outside the capture window {w.start:%H:%M}-{w.end:%H:%M} {w.tz}"
    anchor_day = local.date() if local.time() >= w.extract_after else local.date() - dt.timedelta(days=1)
    anchor = dt.datetime.combine(anchor_day, w.extract_after, tzinfo=tz)
    if extract_at.astimezone(tz) < anchor:
        return f"the extract refreshed at {extract_at.astimezone(tz):%Y-%m-%d %H:%M}, before this window's {anchor:%Y-%m-%d %H:%M} refresh"
    return ""


class BigQuery:
    """Dry runs and table metadata. Dry runs read nothing and cost nothing."""

    def __init__(self, client=None):
        if client is None:
            from google.cloud import bigquery

            client = bigquery.Client(project=BQ_PROJECT)
        self.client = client

    def _params(self, params: list, typed: bool) -> list:
        from google.cloud import bigquery

        out = []
        for p in params:
            kind = "INT64" if typed and _INT.match(str(p)) else "STRING"
            out.append(bigquery.ScalarQueryParameter(None, kind, int(p) if kind == "INT64" else str(p)))
        return out

    def dry_run(self, sql: str, params: list) -> tuple[int, set[str]]:
        from google.cloud import bigquery

        last = None
        for typed in (True, False):
            cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                          query_parameters=self._params(params, typed))
            try:
                job = self.client.query(sql, job_config=cfg)
            except Exception as e:  # noqa: BLE001 - retried untyped, then reported
                last = e
                continue
            tables = {f"{t.project}.{t.dataset_id}.{t.table_id}" for t in (job.referenced_tables or [])}
            return int(job.total_bytes_processed or 0), tables
        raise PreflightError(f"dry run failed: {last}")

    def modified(self, table: str) -> str:
        return self.client.get_table(table).modified.isoformat()


def planned_queries(checks, start: dt.date, end: dt.date) -> list[tuple[str, dict]]:
    """Every query capture will send, clicks left unfiltered (an upper bound)."""
    out = [(f"rows:{p}", q) for p, q in row_queries(checks, start, end)]
    for cut in checks.cuts:
        base = cut.__class__(cut.id, cut.filters, cut.params, None)
        for sheet in checks.sheets:
            try:
                out.append((f"answer:{cells.answer_key(cut.id, sheet)}", cells.cube_query(checks, sheet, base, {})))
            except cells.MappingGap:
                continue
    return out


def estimate(cube, bq, queries: list[tuple[str, dict]]) -> dict:
    """Compile each query through Cube's /sql and dry-run it on BigQuery."""
    total, tables, sqls = 0, set(), {}
    for qid, q in queries:
        sql, params = cube.sql(q)
        n, refs = bq.dry_run(sql, params)
        total += n
        tables |= refs
        sqls[qid] = sql
    return {"bytes": total, "tables": sorted(tables), "sql": sqls}


def clock_map(bq, tables) -> dict[str, str]:
    """Each base table's last-modified time (UTC)."""
    return {t: bq.modified(t) for t in sorted(tables)}


def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(t for t in after if before.get(t) != after[t])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scripts/cube_validate/test_preflight.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate/preflight.py tests/scripts/cube_validate/test_preflight.py
git commit -m "feat(cube): preflight checks the window, prices every query, maps clocks"
```

---

### Task 12: Tableau capture

**Files:**

- Create: `scripts/cube_validate/capture_tableau.py`
- Test: `tests/scripts/cube_validate/test_capture_tableau.py`

**Interfaces:**

- Consumes: `workbook.*`, `snapshot.*`, `config.Checks`, `cells.parse_export`.
- Produces (ported unless marked new): `SessionError`, `retry`, `vf_value`,
  `pick_click_row`, `signed_in`, `Session` (with `export_view`,
  `wait_out_refreshes`, `review_copies`, `publish`, `call`), `open_guard`,
  `server_from_env()` (old `_server`),
  `download(luid, out_dir) -> tuple[Path, str]` (old `_download`), and new:
  - `review_name(now: datetime, workbook: str) -> str`
  - `capture(checks, snap, session, now) -> dict` — unpacks the extract,
    publishes the review copy, exports every cut (resuming cuts already in the
    manifest), and returns manifest additions:
    `{"extract_refreshed", "review_copy", "cuts": {id: {"sheets": {sheet: file}, "vf": [...], "params": {...}, "click_filters": {...}, "click_targets": [...]}}}`.
  - `click_targets(wb, dashboards, source_sheet) -> list[str]`.

Reused deliberately: the old Tableau session handling and download
(`68c59490a5`, `scripts/cube_validate_snapshot.py:915-1153` and `1403-1428`).

- [ ] **Step 1: Port the session code verbatim**

```bash
src=scripts/cube_validate_snapshot.py
{
  printf '"""Tableau side of a capture: download, review copy, exports.\n\nSession handling and download ported from 68c59490a5 (proven on the DDI run).\n"""\n\nfrom __future__ import annotations\n\n'
  printf 'import contextlib\nimport csv\nimport datetime as dt\nimport io\nimport os\nimport re\nimport time\nfrom pathlib import Path\n\n'
  printf 'from . import cells, snapshot, workbook\n\nALL = "(All)"\nBLANK = "(Blank)"\n\n'
  git show 68c59490a5:$src | sed -n '915,918p'   # TEMP_CB, NON_PRODUCTION_PROJECTS, REVIEW_PREFIX
  echo
  git show 68c59490a5:$src | sed -n '923,955p'   # SessionError, RefreshedError, retry, vf_value
  git show 68c59490a5:$src | sed -n '964,1153p'  # pick_click_row .. open_guard (skip _is_number: use workbook._is_number)
  echo
  git show 68c59490a5:$src | sed -n '1403,1428p' # _server, _download
} > scripts/cube_validate/capture_tableau.py
```

Edits: in `pick_click_row` replace `_is_number` with `workbook._is_number`;
rename `_server` to `server_from_env` and `_download` to `download` (update the
call inside `download`); remove `quiet_minutes` (the checks file's
`quiet_minutes` is passed to `Session(quiet=...)` directly); drop
`check_refresh` and `RefreshedError` (the review copy never refreshes). Run
`uv run ruff check scripts/cube_validate/capture_tableau.py` and fix only
unused-import findings.

- [ ] **Step 2: Port the session tests, add capture tests**

Create `tests/scripts/cube_validate/test_capture_tableau.py` from these test
functions of `git show 68c59490a5:tests/scripts/test_cube_validate_snapshot.py`
(alias `snap` → `capture_tableau`, copy the fakes they use):
`test_session_refuses_a_production_project`,
`test_vf_value_escapes_commas_and_expands_all_and_blank`,
`test_pick_click_row_takes_the_largest_or_smallest_mark`,
`test_retry_recovers_then_gives_up`,
`test_a_lost_session_waits_signs_in_again_and_retries`,
`test_exports_wait_out_the_dashboards_quiet_minutes`,
`test_a_failed_sign_out_after_a_lost_session_is_not_an_error`,
`test_export_signs_in_again_when_tableau_drops_the_session`.

Add:

```python
import datetime as dt

from cube_validate import capture_tableau, workbook


def test_review_name():
    assert capture_tableau.review_name(dt.datetime(2026, 10, 15, 16, 5), "Attendance Dashboard") == \
        "ZZ-REVIEW 2026-10-15 1605 Attendance Dashboard"


def test_click_targets_follow_the_action_and_its_exclusions():
    wb = workbook.Workbook(
        dashboards={"Overview": ["ADA by School", "Trend", "Roster"]}, filters=[], params=[],
        actions=[workbook.Action("Overview", "c", "ADA by School", "filter", "Overview", ("Roster",))],
    )
    assert capture_tableau.click_targets(wb, ["Overview"], "ADA by School") == ["Trend"]
```

- [ ] **Step 3: Run tests to verify the new ones fail**

Run: `uv run pytest tests/scripts/cube_validate/test_capture_tableau.py -v`
Expected: the ported tests PASS; `test_review_name` and
`test_click_targets_follow_the_action_and_its_exclusions` FAIL with
`AttributeError`.

- [ ] **Step 4: Add `review_name`, `click_targets` and `capture`**

Append to `capture_tableau.py`:

```python
def review_name(now: dt.datetime, workbook_name: str) -> str:
    return f"{REVIEW_PREFIX}{now:%Y-%m-%d %H%M} {workbook_name}"


def click_targets(wb, dashboards: list[str], source_sheet: str) -> list[str]:
    """The sheets a filter action from source_sheet filters."""
    out: list[str] = []
    for a in wb.actions:
        if a.kind != "filter" or a.source_sheet != source_sheet or a.dashboard not in dashboards:
            continue
        for s in wb.dashboards.get(a.target, []):
            if s != source_sheet and s not in a.exclude and s not in out:
                out.append(s)
    return out


def capture(checks, snap, session, now: dt.datetime) -> dict:
    """Freeze the Tableau side: extract, review copy, every cut's exports.

    Args:
        checks: The checks file.
        snap: The snapshot; snap.twbx must already be downloaded.
        session: A signed-in Session on the review project.
        now: Used for the review copy's name.

    Returns:
        Manifest additions (see the task's interface list).

    Raises:
        SessionError: The data source has no embedded extract, or an earlier
            review copy is still in TEMP-CB.
    """
    m = snapshot.read_manifest(snap)
    extracts = workbook.unpack_extracts(snap.twbx, snap.dir)
    if checks.datasource not in extracts:
        raise SessionError(
            f"{checks.datasource} has no embedded extract in the workbook; a published "
            "data source would refresh under the review copy, so the snapshot would not hold"
        )
    (snap.dir / extracts[checks.datasource]["file"]).rename(snap.extract)
    text = workbook.twb_text(snap.twbx)
    wb = workbook.read_workbook(text)
    if "review_copy" not in m:
        open_guard(session, checks.workbook)
        listed = set(checks.sheets) | {c.click.source_sheet for c in checks.cuts if c.click}
        twbx, hidden = workbook.build_review_twbx(snap.twbx, snap.dir, list(checks.dashboards), listed)
        name = review_name(now, checks.workbook)
        session.publish(twbx, name, hidden)
        m["review_copy"] = {"name": name, "url": getattr(session.copy, "webpage_url", "")}
        snapshot.write_manifest(snap, m)
    m["extract_refreshed"] = extracts[checks.datasource]["refreshed"]
    cuts = m.setdefault("cuts", {})
    for cut in checks.cuts:
        if cut.id in cuts:
            continue
        vf = [(k, vf_value(v, [])) for k, v in cut.filters.items() if v != ALL]
        params = list(cut.params.items())
        entry = {"vf": vf, "params": dict(params), "click_filters": {}, "click_targets": [], "sheets": {}}
        if cut.click:
            session.wait_out_refreshes()
            src = session.export_view(cut.click.source_sheet, vf, params)
            entry["click_filters"] = pick_click_row(src, cut.click.mark, None)
            entry["click_targets"] = click_targets(wb, list(checks.dashboards), cut.click.source_sheet)
        for sheet in checks.sheets:
            extra = [(k, vf_value(v, [])) for k, v in entry["click_filters"].items()] if sheet in entry["click_targets"] else []
            session.wait_out_refreshes()
            data = session.export_view(sheet, vf + extra, params)
            path = snap.export_path(cut.id, sheet)
            path.write_bytes(data)
            entry["sheets"][sheet] = str(path.relative_to(snap.dir))
        cuts[cut.id] = entry
        snapshot.write_manifest(snap, m)
    return m
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/scripts/cube_validate/test_capture_tableau.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate/capture_tableau.py tests/scripts/cube_validate/test_capture_tableau.py
git commit -m "feat(cube): freeze the Tableau side from a review copy of the downloaded extract"
```

---

### Task 13: Commands

**Files:**

- Modify: `scripts/cube_validate/cli.py`
- Test: `tests/scripts/cube_validate/test_cli.py`

**Interfaces:**

- Consumes: every module above.
- Produces: `main(argv) -> int` with:
  - `plan <checks>` (Tableau creds): download into `<root>/<dashboard>/plan/`,
    unpack, write `plan.yml` via `cuts.plan_yaml`, print its path.
  - `run <checks> [--period A:B]` (Tableau, Cube, BigQuery): preflight → Tableau
    capture → Cube rows → Cube answers → clock recheck → `analyze`. `--snapshot`
    resumes that snapshot.
  - `answers <checks> --snapshot S`: re-capture Cube answers into S after a
    mapping change, only if inside the window and the clock map is unchanged.
  - `analyze <checks> [--snapshot S]` (no creds): rows → cells → hand checks →
    report; prints the report path and trust verdict.
  - `close <checks>`: list this workbook's review copies still in TEMP-CB.
  - `analyze_snapshot(checks, snap) -> tuple[Path, str]` (report path, trust
    line) — the offline core, tested directly.

- [ ] **Step 1: Write the failing test (end to end, offline)**

`tests/scripts/cube_validate/test_cli.py`:

```python
"""analyze end to end on a synthetic snapshot. No live calls."""

import datetime as dt
import json

import pytest
import yaml

pytest.importorskip("tableauhyperapi")

from cube_validate import cells, cli, hyper, snapshot  # noqa: E402

CHECKS = {
    "dashboard": "d", "workbook": "W", "workbook_luid": "l",
    "review_project_luid": "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc", "dashboards": ["Overview"],
    "datasource": "ds", "dashboard_table": "p.d.t", "period_start": "2026-10-05",
    "window": {"start": "15:30", "end": "06:00", "extract_after": "15:00", "tz": "America/New_York"},
    "cost_cap_gb": 50,
    "cube": {"view": "v", "date": "attendance_date",
             "members": ["lea_student_identifier", "attendance_date", "locations_abbreviation"]},
    "rows": {"student_key": "student", "date_key": "day", "scope_key": "school",
             "key": {"student": {"tableau": "student_number", "cube": 'cast("{p}lea_student_identifier" as bigint)'},
                     "day": {"tableau": "calendardate", "cube": "attendance_date"},
                     "school": {"tableau": "school_abbreviation", "cube": "locations_abbreviation"}}},
    "sheets": {"ADA": {"students": "Students",
                       "dims": {"School": {"tableau": "school_abbreviation", "cube": "locations_abbreviation",
                                           "cube_column": "locations_abbreviation"}},
                       "measures": {"ADA": {"cube": "avg_daily_attendance"}}}},
    "cuts": [{"id": "default"}],
}


def test_analyze_writes_report_and_hand_checks(tmp_path):
    checks_path = tmp_path / "c.yml"
    checks_path.write_text(yaml.safe_dump(CHECKS))
    snap = snapshot.new_snapshot("d", dt.datetime(2026, 10, 15, 16, 0), root=tmp_path)
    d = dt.date(2026, 10, 6)
    hyper.write_table(snap.extract, "Extract", "Extract",
                      [("student_number", "bigint"), ("calendardate", "date"), ("school_abbreviation", "text")],
                      [(1, d, "Rise"), (2, d, "Rise")])
    hyper.write_table(snap.cube, "cube", "rows",
                      [("lea_student_identifier", "double"), ("attendance_date", "date"), ("locations_abbreviation", "text")],
                      [(1.0, d, "Rise"), (2.0, d, "Rise")])
    snap.export_path("default", "ADA").write_bytes(b"School,ADA,Students\nRise,94.2%,2\n")
    snap.answers.write_text(json.dumps({cells.answer_key("default", "ADA"): {
        "query": {}, "sql": "SELECT", "last_refresh": "x",
        "data": [{"v.locations_abbreviation": "Rise", "v.avg_daily_attendance": "0.942"}]}}))
    snapshot.write_manifest(snap, {"scope": ["Rise"], "invariants": {"capture completeness": True},
                                   "review_copy": {"name": "ZZ-REVIEW x"}, "cuts": {"default": {}}})
    report, trust = cli.analyze_snapshot(cli.config.load_checks(checks_path), snap)
    text = report.read_text()
    assert "| pass | <10 |" in text and trust.startswith("Pending")
    assert (snap.analysis / "hand_checks.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_cli.py -v`
Expected: FAIL with
`AttributeError: module 'cube_validate.cli' has no attribute 'analyze_snapshot'`.

- [ ] **Step 3: Write the implementation**

Replace `scripts/cube_validate/cli.py`:

```python
"""Command line: plan, run, answers, analyze, close.

plan, run, answers and close need the Tableau PAT and CUBE_API_SECRET, which
only the pytest secrets fixture provides; run them inside a throwaway
tests/test_zz_*.py (see the cube-dashboard skill). analyze needs nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from . import (
    capture_cube,
    capture_tableau,
    cells,
    config,
    cuts,
    handchecks,
    hyper,
    preflight,
    report,
    rows,
    snapshot,
    workbook,
)

COMMANDS = ("plan", "run", "answers", "analyze", "close")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        s = sub.add_parser(name)
        s.add_argument("checks", help="path to checks/<dashboard>.yml")
        s.add_argument("--snapshot", help="snapshot folder (default: newest)")
        s.add_argument("--period", help="START:END dates to capture, e.g. 2025-07-01:2026-06-30")
    return p


def _period(checks, arg: str | None, today: dt.date) -> tuple[dt.date, dt.date, str]:
    if not arg:
        return checks.period_start, today, ""
    a, b = arg.split(":")
    return dt.date.fromisoformat(a), dt.date.fromisoformat(b), f"{a[:4]}-{b[2:4]}"


def analyze_snapshot(checks, snap) -> tuple[Path, str]:
    """Phases 3 and 4 on a frozen snapshot. Calls nothing outside the snapshot."""
    m = snapshot.read_manifest(snap)
    answers = json.loads(snap.answers.read_text()) if snap.answers.exists() else {}
    with hyper.Workspace(snap.analysis / "analysis.hyper", {"tab": snap.extract, "cub": snap.cube}) as ws:
        rr = rows.build(ws, checks, m.get("scope") or [])
        cs = cells.judge(ws, checks, m, answers, lambda cut, sheet: _export(snap, cut, sheet))
        picked = handchecks.pick(cs, handchecks.row_samples(ws, checks), seed=snap.dir.name)
    handchecks.write(snap.analysis, picked, (m.get("review_copy") or {}).get("name", ""), answers)
    results = handchecks.read_results(snap.analysis / "hand_checks.yml")
    forms = workbook.formulas(workbook.twb_text(snap.twbx)) if snap.twbx.exists() else {}
    text = report.render(checks, m, rr, cs, results, forms, answers)
    path = snap.analysis / "report.md"
    path.write_text(text)
    return path, report.trust({**(m.get("invariants") or {}), **rr.invariants}, results)


def _export(snap, cut: str, sheet: str) -> bytes | None:
    p = snap.export_path(cut, sheet)
    return p.read_bytes() if p.exists() and p.stat().st_size else None


def _plan(checks) -> int:
    root = snapshot.SNAPSHOT_ROOT / checks.dashboard / "plan"
    root.mkdir(parents=True, exist_ok=True)
    twbx, _ = capture_tableau.download(checks.workbook_luid, root)
    text = workbook.twb_text(twbx)
    wb = workbook.read_workbook(text)
    extracts = workbook.unpack_extracts(twbx, root)
    values: dict[str, list[str]] = {}
    columns: list[str] = []
    if checks.datasource in extracts:
        path = root / extracts[checks.datasource]["file"]
        with hyper.Workspace(root / "scratch.hyper", {"tab": path}) as ws:
            columns = ws.columns("tab", "Extract", "Extract")
            for f in wb.filters:
                if f.field in columns and f.caption not in values:
                    got = ws.query(f'select distinct "{f.field}" from "tab"."Extract"."Extract" order by 1 limit 50')
                    values[f.caption] = [str(r[0]) for r in got if r[0] is not None]
    out = root / "plan.yml"
    out.write_text(cuts.plan_yaml(wb, list(checks.dashboards), columns, values))
    print(f"Draft written to {out}. Edit sheets, mappings and cuts into the checks file.")
    return 0


def _built_at(clock: dict[str, str], tables: list[str]) -> dt.datetime:
    cube_tables = [t for t in tables if ".kipptaf_marts." in t] or tables
    return max(dt.datetime.fromisoformat(clock[t]) for t in cube_tables)


def _run(checks, args) -> int:
    now = dt.datetime.now(dt.UTC)
    start, end, tag = _period(checks, args.period, now.date())
    snap = snapshot.Snapshot(Path(args.snapshot)) if args.snapshot else snapshot.new_snapshot(checks.dashboard, now, tag)
    m = snapshot.read_manifest(snap)
    m["period"] = f"{start}:{end}"

    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        live = server.workbooks.get_by_id(checks.workbook_luid)
        why = preflight.check_window(now, live.updated_at, checks.window)
        if why:
            raise preflight.PreflightError(why)
        cube = capture_cube.client_from_env()
        bq = preflight.BigQuery()
        est = preflight.estimate(cube, bq, preflight.planned_queries(checks, start, end))
        _, dash_tables = bq.dry_run(f"select * from `{checks.dashboard_table}`", [])
        tables = sorted(set(est["tables"]) | dash_tables)
        before = m.get("clock_before") or preflight.clock_map(bq, tables)
        gb = est["bytes"] / 1e9
        m.update(cost=f"{gb:.2f} GB planned, cap {checks.cost_cap_gb} GB", clock_before=before, clock_tables=tables)
        snapshot.write_manifest(snap, m)
        if gb > checks.cost_cap_gb:
            raise preflight.PreflightError(f"planned {gb:.2f} GB is over the cap of {checks.cost_cap_gb} GB")

        if not snap.twbx.exists():
            twbx, _ = capture_tableau.download(checks.workbook_luid, snap.dir)
            Path(twbx).rename(snap.twbx)
        session = capture_tableau.Session(server, checks.review_project_luid, auth=auth, quiet=checks.quiet_minutes)
        m.update(capture_tableau.capture(checks, snap, session, now))
        snapshot.write_manifest(snap, m)

    built = _built_at(before, tables)
    parts = capture_cube.pull_rows(cube, snap, capture_cube.row_queries(checks, start, end), built)
    n, scope = capture_cube.write_cube_hyper(snap, checks, cube.member_types(checks.cube.view))
    capture_cube.capture_answers(cube, snap, checks, m, built)
    after = preflight.clock_map(bq, tables)
    moved = preflight.changed(before, after)
    m.update(scope=scope, scope_size=len(scope), clock_after=after,
             clock_risk=", ".join(moved) or "none",
             cube_refresh=f"{len(parts)} parts, {n} rows",
             invariants={**(m.get("invariants") or {}), "capture completeness": True})
    snapshot.write_manifest(snap, m)
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0


def _answers(checks, args) -> int:
    snap = snapshot.Snapshot(Path(args.snapshot))
    m = snapshot.read_manifest(snap)
    now = dt.datetime.now(dt.UTC)
    extract_at = dt.datetime.fromisoformat(m["extract_refreshed"])
    why = preflight.check_window(now, extract_at, checks.window)
    if why:
        raise preflight.PreflightError(why)
    bq = preflight.BigQuery()
    after = preflight.clock_map(bq, m["clock_tables"])
    moved = preflight.changed(m["clock_before"], after)
    if moved:
        raise preflight.PreflightError(f"tables changed since capture: {', '.join(moved)}; run a new capture")
    capture_cube.capture_answers(capture_cube.client_from_env(), snap, checks, m, _built_at(m["clock_before"], m["clock_tables"]))
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0


def _close(checks) -> int:
    server, auth = capture_tableau.server_from_env()
    with capture_tableau.signed_in(server, auth):
        session = capture_tableau.Session(server, checks.review_project_luid)
        left = session.review_copies(checks.workbook)
    if not left:
        print("No review copies left in TEMP-CB.")
        return 0
    for w in left:
        print(f"Delete in Tableau: {w.name}: {w.webpage_url}")
    print(capture_tableau.FIND_BY_NAME)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    checks = config.load_checks(args.checks)
    if args.command == "plan":
        return _plan(checks)
    if args.command == "run":
        return _run(checks, args)
    if args.command == "answers":
        return _answers(checks, args)
    if args.command == "close":
        return _close(checks)
    snap = snapshot.Snapshot(Path(args.snapshot)) if args.snapshot else snapshot.latest_snapshot(checks.dashboard)
    path, trust = analyze_snapshot(checks, snap)
    print(f"{trust}\nReport: {path}")
    return 0
```

In `tests/scripts/cube_validate/test_package.py`, the existing test still holds
(argparse rejects `nope` before loading checks).

- [ ] **Step 4: Run the whole suite**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/cube_validate -v 2>&1 | tail -n 30`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check scripts/cube_validate tests/scripts/cube_validate
git add scripts/cube_validate/cli.py tests/scripts/cube_validate/test_cli.py
git commit -m "feat(cube): plan, run, answers, analyze and close commands"
```

---

### Task 14: Runbook and the Attendance checks file

**Files:**

- Modify: `.claude/skills/cube-dashboard/SKILL.md` (full rewrite)
- Create: `.claude/skills/cube-dashboard/checks/attendance_dashboard.yml`

**Interfaces:**

- Consumes: the commands from Task 13.

- [ ] **Step 1: Write the Attendance checks file**

`.claude/skills/cube-dashboard/checks/attendance_dashboard.yml`:

```yaml
# Attendance Dashboard: what `cube_validate` compares. Committed, so it never
# holds a person's name. `plan` drafts sheets, filters and cuts; the analyst
# approves each mapping and cause.
dashboard: attendance_dashboard
workbook: Attendance Dashboard # confirm against `plan`'s download
workbook_luid: 87c13e78-a912-40a4-95dd-33248fc1cbd3
review_project_luid: ddc817c2-6bc7-4bca-8be9-e385f95b9ebc
dashboards: [] # tabs in scope, from plan.yml
datasource: "" # the extract's caption, from plan.yml
dashboard_table: teamster-332318.kipptaf_tableau.rpt_tableau__attendance_dashboard
period_start: 2026-07-01
# Extract refreshes 6:00 AM and 3:00 PM; Cube's facts rebuild ~6:15 AM and
# ~3:05 PM. Only the evening pairs like for like.
window:
  start: "15:30"
  end: "06:00"
  extract_after: "15:00"
  tz: America/New_York
cost_cap_gb: 50
tableau_quiet_minutes: [0, 10]
cube:
  view: student_attendance_enrollment_daily_view
  date: attendance_date
  members:
    - lea_student_identifier
    - attendance_date
    - locations_abbreviation
    - regions_region_name
    - grade_level
    - attendance_value
    - membership_value
    - attendance_code
    - is_absent
    - is_tardy
    - is_iss
    - is_oss
    - is_in_session_day
  filters: []
rows:
  student_key: student
  date_key: day
  scope_key: school
  key:
    student:
      tableau: student_number
      cube: cast("{p}lea_student_identifier" as bigint)
    day: { tableau: calendardate, cube: attendance_date }
    school: { tableau: school_abbreviation, cube: locations_abbreviation }
  compare:
    attendance_value: { tableau: is_present, cube: attendance_value }
    is_absent: { tableau: is_absent, cube: is_absent }
    is_tardy: { tableau: is_tardy, cube: is_tardy }
    is_iss: { tableau: is_iss, cube: is_iss }
    is_oss: { tableau: is_oss, cube: is_oss }
    grade_level: { tableau: grade_level, cube: grade_level }
  labels:
    region: { tableau: region, cube: regions_region_name }
causes: []
filters: {}
params: {}
sheets: {}
cuts:
  - id: default
excluded_sheets: {}
```

- [ ] **Step 2: Rewrite the runbook**

Replace `.claude/skills/cube-dashboard/SKILL.md` with:

````markdown
---
name: cube-dashboard
description:
  Use when validating Cube against a Tableau dashboard, re-checking one after a
  Cube or workbook fix, mapping a dashboard's sheets to Cube members, adding a
  cause to a dashboard's rows layer, or reading a validation report. Triggers:
  "validate <dashboard> against Cube", "does Cube match Tableau", cube_validate,
  ZZ-REVIEW copies in TEMP-CB, or any file under
  .claude/skills/cube-dashboard/checks/.
---

# cube-dashboard

Both sides are captured once, inside the dashboard's evening window, into a
snapshot. Analysis reconciles rows first, then compares each exported number
with Cube's and explains gaps by the rows. Design:
`docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md`.

## Running a step that needs credentials

`plan`, `run`, `answers` and `close` need the Tableau PAT and `CUBE_API_SECRET`;
only the pytest secrets fixture provides them. Write this throwaway file, set
`ARGS`, run it, delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

ARGS = ["run", ".claude/skills/cube-dashboard/checks/<dashboard>.yml"]
PKG = Path(__file__).parents[1] / "scripts" / "cube_validate"


def test_step():
    spec = importlib.util.spec_from_file_location(
        "cube_validate", PKG / "__init__.py", submodule_search_locations=[str(PKG)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    from cube_validate import cli

    assert cli.main(ARGS) == 0
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback. `analyze` needs no secrets:
`uv run --with tableauhyperapi python -m scripts.cube_validate analyze <checks>`.

## When to run

The window is in the checks file and differs per dashboard. Attendance: 3:30 PM
to 6:00 AM New York time, after the 3:00 PM extract refresh and Cube's ~3:05 PM
rebuild. Re-check both times in Dagster before relying on them. `run` refuses
outside the window or when the extract predates this window's refresh.

- No Tableau MCP calls during a run: they sign in with the same token.
- A capture costs money; analysis is free and can be repeated.

## First validation of a dashboard

1. `plan <checks>`: downloads the workbook, writes `plan.yml` (sheets, extract
   columns, filter cards, parameters, drafted cuts). Fill `dashboards`,
   `datasource`, `sheets` (stubs) and `cuts`; list under `excluded_sheets`, with
   the reason, every sheet with no Cube counterpart, every sheet on another data
   source ("separate run"), and every sheet that blends 2 data sources
   ("blended, not checked"). Never list a sheet with a name column.
2. Evening 1: `run <checks>`. Rows layer and exports are now frozen. Cells are
   mostly "mapping unproven" or "no Cube counterpart" until mapping.
3. Map from the exports in `<snapshot>/exports/`: each header to a dim or
   measure, each filter caption under `filters`. Each sheet showing a student
   count names it under `students`; without one, its cuts stay unproven.
4. Same evening, still in the window: `answers <checks> --snapshot <dir>`. It
   refuses if any base table changed since capture.
5. Build causes from the first report's raw buckets (below), then `analyze`.
6. Work the hand checks (below). Then `close <checks>`; the analyst deletes the
   review copy in Tableau and runs `close` again until it reports none left.

## Causes

The run starts with none. For each candidate, measure on this snapshot how many
rows it claims and what stays unexplained (`analyze` after adding it), then the
analyst approves it. Causes are SQL over table `rows`: `base`, `k_<key>`,
`t_<extract column>`, `c_<Cube column>`, `t__dup`, `c__dup`. Two causes claiming
one row stop the report; never order them to make it pass.

## Reading the report

- **Trust verdict first.** Trusted only when every invariant holds and every
  hand check agrees. Findings stay held until then.
- **Row buckets:** match, value differs, dashboard only, Cube only, outside
  scope; each split by cause or "unexplained".
- **Cells:** pass, coincidental match, row gap, formula gap. Filter ignored,
  mapping unproven, no Cube counterpart and no captured rows are the tool's
  limits, never Cube findings.
- Counts under 10 show as `<10`, so the report can go to `#data_team`.

## Hand checks

`<snapshot>/analysis/hand_checks.md` lists 10 to 15 checks: one per verdict and
bucket, plus random passes. Tableau side in the review copy (same frozen
extract), Cube side against the captured value, rows against PowerSchool or
Focus. Mark each `agree` or `disagree` in `hand_checks.yml`, then `analyze`.

## Last year

Once per year, after its logic last changed:
`run <checks> --period 2025-07-01:2026-06-30`. Its snapshot is tagged with the
year and kept until July.

## Rules

- Snapshots hold student-level rows: they stay in `~/.cache/cube-validate/`.
  `hand_checks.md` names students; keep it local.
- The checks file is committed, so it never holds a person's name.
- Review copies go to TEMP-CB only. The tool deletes nothing on Tableau.
````

- [ ] **Step 3: Lint the markdown and YAML**

Run (cwd `/workspaces/teamster`):
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md .claude/skills/cube-dashboard/checks/attendance_dashboard.yml </dev/null 2>&1 | tail -n 15`
Expected: no issues (fix any reported; formatting is the commit hook's).

- [ ] **Step 4: Confirm the checks file loads**

Run:
`uv run python -c "import importlib.util,sys;from pathlib import Path;p=Path('scripts/cube_validate');s=importlib.util.spec_from_file_location('cube_validate',p/'__init__.py',submodule_search_locations=[str(p)]);m=importlib.util.module_from_spec(s);sys.modules['cube_validate']=m;s.loader.exec_module(m);from cube_validate import config;print(config.load_checks('.claude/skills/cube-dashboard/checks/attendance_dashboard.yml').cube.view)"`
Expected: `ConfigError: checks file: missing datasource` — `datasource` and
`dashboards` are filled by the analyst after `plan`. This proves the file is
read and the gate works.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/cube-dashboard/SKILL.md .claude/skills/cube-dashboard/checks/attendance_dashboard.yml
git commit -m "docs(cube): runbook and Attendance checks file for the redesigned validator"
```

---

### Task 15: First Attendance run (operational, analyst-gated)

No code. Each step needs the analyst; stop and ask at each gate.

- [ ] **Step 1:** Run `plan` (throwaway pytest). Show the analyst `plan.yml`:
      dashboards, sheets, filter cards, parameters, drafted cuts. Fill
      `dashboards`, `datasource`, sheet stubs, `excluded_sheets` and `cuts` from
      their edits. Commit the checks file.
- [ ] **Step 2:** After 3:30 PM New York time: `run`. Report the trust line,
      capture timing, cost, row totals and bucket counts (aggregates only).
- [ ] **Step 3:** Draft the mapping from the exports with the analyst; then
      `answers --snapshot <dir>` the same evening.
- [ ] **Step 4:** Measure candidate causes on this snapshot (Miami tardy and
      suspension nulls, inclusive `exitdate` duplicates, Cube break days), one
      at a time; the analyst approves each. Re-run `analyze`.
- [ ] **Step 5:** The analyst works `hand_checks.md` and fills
      `hand_checks.yml`; `analyze` again. Record whether the tool is trusted.
- [ ] **Step 6:** `close` until no review copy remains.
