# cube-dashboard skill, validate mode: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `cube-dashboard` skill whose validate mode compares Cube with what a
Tableau dashboard shows, at every grain the dashboard's sheets use, and reports
each Asana measure row as pass, fail, or incomplete.

**Architecture:** One script, `scripts/cube_validate.py`, with two subcommands.
`grains` reads a downloaded `.twb` and proposes the grains for a measure. `run`
reads a reviewed checks file, runs one Cube `/load` and one BigQuery query per
(view, table, grain), compares cell by cell, and writes a report plus
`latest.json` under `~/asana-sync/validation/`. The skill runbook wraps it:
author checks, run, render spot checks, post Asana comments; the user's
`sync.py` turns `latest.json` into the `mismatch` tag.

**Tech Stack:** Python 3.13 via `uv run`, `httpx`, `pyjwt`, `pyyaml`,
`google-cloud-bigquery`, `tableauserverclient`, `defusedxml` (all already in the
project environment), pytest. Cube Cloud REST API, Tableau MCP, Asana MCP.

**Spec:**
[docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md](../specs/2026-10-08-cube-validate-skill-design.md)

## Global Constraints

- Run everything with `uv run`; never bare `python` or `pytest`.
- Tolerance: counts match exactly; rates match within 0.001 (0.1 percentage
  point). Every gap is reported with its size.
- Window on both sides: July 1 of the current academic year through yesterday.
- A row passes only if every comparable cell passes. A grain error makes the row
  `incomplete`, never `pass`.
- Aggregates only. No student names or ids in any output. In Asana comments, a
  cell under 10 students (or of unknown size) shows as "small cell" with no
  values.
- Cube auth: HS256 JWT `{email, iat, exp}` signed with `CUBE_API_SECRET`, sent
  as the raw `Authorization` header (no `Bearer`). The secret comes only from
  the environment, which only the pytest secrets fixture provides; `run`
  executes inside a throwaway `tests/test_zz_*.py` that is deleted after.
- Default Cube REST URL:
  `https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`.
- Tags change only through `~/asana-sync/sync.py`, which the user runs. The
  skill never touches Anthony's six checklist subtasks.
- Durable outputs: checks files in the repo; run outputs in
  `~/asana-sync/validation/`; downloaded workbooks in
  `.claude/scratch/cube-dashboard/`.

## Review Focus

- Cube returns every value as a string (`"5"`, `"0.92"`,
  `"2026-09-01T00:00:00.000"`) while BigQuery returns ints, floats and dates:
  keys must normalize so the same cell joins. Pinned in Task 3
  (`test_norm_key_*`).
- A fine grain that returns 50,000 rows from Cube is silently truncated: the
  grain must error, not compare a partial result. Pinned in Task 4
  (`test_cube_client_row_limit_errors`).
- Running on July 1 must not produce an empty or inverted window. Pinned in Task
  2 (`test_academic_window_*`).
- A rate whose denominator is 0 or null on one side: both null is a match, one
  null is a mismatch, never a crash. Pinned in Task 3 (`test_rate_nulls`).
- A hard-filter value with no data (a region with no rows yet) must not abort
  the scope guard; only "warehouse has students, Cube has none" does. Pinned in
  Task 4 (`test_scope_guard_*`).

## Prerequisite (user, one time)

Add one line to the secrets template that `tests/conftest.py` loads (the
hook-protected file under `.devcontainer/tpl/`), in the same form as its other
lines: `CUBE_API_SECRET=` followed by the same 1Password reference that
`scripts/cube-rest-mcp-launch.sh` passes to `op read`. Needed before Task 7;
Tasks 1 to 6 do not need it.

---

### Task 1: Grain derivation from a `.twb`

**Files:**

- Create: `scripts/cube_validate.py`
- Create: `tests/scripts/fixtures/cube_validate/mini.twb`
- Create: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `Sheet` dataclass (`name: str`, `dashboards: list[str]`,
  `datasource: str`, `measures: dict[str, str]` caption to formula,
  `shelf_dims: list[str]`, `filter_dims: list[str]`,
  `other_filters: list[str]`); `parse_twb(path, dashboards) -> list[Sheet]`;
  `propose_grains(sheets, measure) -> list[list[str]]`;
  `main(argv: list[str] | None = None) -> int` with subcommand `grains`. Date
  parts are labelled `<field>@<part>`, for example `calendardate@month`.

- [ ] **Step 1: Write the fixture workbook**

`tests/scripts/fixtures/cube_validate/mini.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook>
  <datasources>
    <datasource caption='rpt_demo (kipptaf_tableau)' name='federated.abc'>
      <column caption='# Tardy' datatype='integer' name='[Calculation_1]' role='measure' type='quantitative'>
        <calculation class='tableau' formula="IIF([att_code] = 'T', 1, 0)" />
      </column>
      <column caption='School' datatype='string' name='[school_abbreviation]' role='dimension' type='nominal' />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Tardy by School'>
      <table>
        <view>
          <filter class='categorical' column='[federated.abc].[none:gender:nk]' />
          <filter class='categorical' column='[federated.abc].[Region User Filter]' />
          <filter class='categorical' column='[federated.abc].[none:region:nk]' />
        </view>
        <panes>
          <pane>
            <encodings>
              <text column='[federated.abc].[sum:Calculation_1:qk]' />
            </encodings>
          </pane>
        </panes>
        <rows>([federated.abc].[none:region:nk] / [federated.abc].[none:school_abbreviation:nk])</rows>
        <cols>[federated.abc].[mn:calendardate:ok]</cols>
      </table>
    </worksheet>
    <worksheet name='Scratch Sheet'>
      <table>
        <rows>[federated.abc].[sum:Calculation_1:qk]</rows>
        <cols>[federated.abc].[none:grade_level:ok]</cols>
      </table>
    </worksheet>
    <worksheet name='Headcount'>
      <table>
        <rows>[federated.abc].[ctd:student_number:qk]</rows>
        <cols />
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Live'>
      <zones><zone name='Tardy by School' /><zone name='Headcount' /></zones>
    </dashboard>
    <dashboard name='Retired'>
      <zones><zone name='Scratch Sheet' /></zones>
    </dashboard>
  </dashboards>
</workbook>
```

- [ ] **Step 2: Write the failing tests**

`tests/scripts/test_cube_validate.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: errors, because `scripts/cube_validate.py` does not exist.

- [ ] **Step 4: Write the implementation**

`scripts/cube_validate.py`:

```python
"""Compare Cube with what a Tableau dashboard shows, at every grain its sheets use.

    uv run scripts/cube_validate.py grains <workbook.twb> --dashboard "<name>" [...] [--measure "<caption>"]
    uv run scripts/cube_validate.py run <checks.yml> [--rows <gid,...>] [--scope-only]

`grains` reads a downloaded .twb and proposes the grains for one measure's check entry.
`run` needs CUBE_API_SECRET, which only the pytest secrets fixture provides, so it runs
inside a throwaway tests/test_zz_*.py. Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

import defusedxml.ElementTree as SafeET

# [federated.<datasource>].[<derivation>:<field>:<type>], or [federated.<ds>].[<named filter>]
_TOKEN = re.compile(r"\[(federated\.[^\]]+)\]\.\[([^\]]+)\]")
_INSTANCE = re.compile(r"^([a-z]+):(.+):([a-z]+)$")
_DATE_PARTS = {
    "yr": "year",
    "tyr": "year",
    "qr": "quarter",
    "tqr": "quarter",
    "mn": "month",
    "tmn": "month",
    "wk": "week",
    "twk": "week",
    "dy": "day",
    "tdy": "day",
}
_MEASURE_DERIVATIONS = {"sum", "avg", "cnt", "ctd", "min", "max", "med", "usr", "agg"}


@dataclass
class Sheet:
    name: str
    dashboards: list[str]
    datasource: str = ""
    measures: dict[str, str] = field(default_factory=dict)  # caption -> formula
    shelf_dims: list[str] = field(default_factory=list)
    filter_dims: list[str] = field(default_factory=list)
    other_filters: list[str] = field(default_factory=list)


def _columns(root: ET.Element) -> dict[tuple[str, str], tuple[str, str]]:
    """(datasource name, '[field]') -> (caption, formula)."""
    out = {}
    for ds in root.find("datasources").findall("datasource"):
        for col in ds.findall("column"):
            calc = col.find("calculation")
            out[(ds.get("name"), col.get("name"))] = (
                col.get("caption") or col.get("name").strip("[]"),
                calc.get("formula", "") if calc is not None else "",
            )
    return out


def _classify(ds: str, inner: str, columns) -> tuple[str, str, str]:
    """Return (kind, label, formula); kind is 'dim', 'measure' or 'other'."""
    m = _INSTANCE.match(inner)
    if not m:
        return "other", inner, ""
    deriv, fld, _ = m.groups()
    caption, formula = columns.get((ds, f"[{fld}]"), (fld, ""))
    if deriv == "none":
        return "dim", caption, formula
    if deriv in _DATE_PARTS:
        return "dim", f"{caption}@{_DATE_PARTS[deriv]}", formula
    if deriv in _MEASURE_DERIVATIONS:
        return "measure", caption, formula
    return "other", caption, formula


def parse_twb(path, dashboards: list[str]) -> list[Sheet]:
    """Every worksheet placed on one of `dashboards`, with its shelves and filters."""
    root = SafeET.parse(path).getroot()  # defusedxml: no entity expansion
    columns = _columns(root)
    ds_caption = {
        d.get("name"): d.get("caption") or d.get("name")
        for d in root.find("datasources").findall("datasource")
    }
    placed: dict[str, list[str]] = {}
    for d in root.find("dashboards").findall("dashboard"):
        if d.get("name") in dashboards:
            for z in d.iter("zone"):
                if z.get("name") and d.get("name") not in placed.get(z.get("name"), []):
                    placed.setdefault(z.get("name"), []).append(d.get("name"))
    sheets = []
    for w in root.find("worksheets").findall("worksheet"):
        if w.get("name") not in placed:
            continue
        s = Sheet(w.get("name"), placed[w.get("name")])
        tab = w.find("table")
        shelves = " ".join(tab.findtext(t) or "" for t in ("rows", "cols"))
        encodings = " ".join(e.get("column", "") for e in w.findall(".//encodings/*"))
        for ds, inner in _TOKEN.findall(f"{shelves} {encodings}"):
            s.datasource = s.datasource or ds_caption.get(ds, ds)
            kind, label, formula = _classify(ds, inner, columns)
            if kind == "dim" and label not in s.shelf_dims:
                s.shelf_dims.append(label)
            elif kind == "measure":
                s.measures.setdefault(label, formula)
        for f in w.iter("filter"):
            for ds, inner in _TOKEN.findall(f.get("column", "")):
                kind, label, _ = _classify(ds, inner, columns)
                target = s.filter_dims if kind == "dim" else s.other_filters
                if label not in target and label not in s.shelf_dims:
                    target.append(label)
        sheets.append(s)
    return sheets


def propose_grains(sheets: list[Sheet], measure: str) -> list[list[str]]:
    """The total, each sheet's shelf grain, and each filter added to it one at a time."""
    grains: list[list[str]] = [[]]
    for s in sheets:
        if measure not in s.measures:
            continue
        for g in [s.shelf_dims] + [s.shelf_dims + [f] for f in s.filter_dims]:
            if g not in grains:
                grains.append(list(g))
    return grains


def _grains_command(a) -> int:
    sheets = parse_twb(a.twb, a.dashboard)
    if a.measure:
        using = [s for s in sheets if a.measure in s.measures]
        out = {
            "measure": a.measure,
            "sheets": [asdict(s) for s in using],
            "grains": propose_grains(sheets, a.measure),
        }
    else:
        out = {"sheets": [asdict(s) for s in sheets]}
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grains", help="propose grains from a downloaded .twb")
    g.add_argument("twb")
    g.add_argument("--dashboard", action="append", required=True)
    g.add_argument("--measure")
    a = p.parse_args(argv)
    return _grains_command(a)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py tests/scripts/fixtures/cube_validate/mini.twb
git commit -F - <<'MSG'
feat(cube): propose validation grains from a Tableau workbook

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

### Task 2: Checks file loading and query building

**Files:**

- Modify: `scripts/cube_validate.py`
- Create: `tests/scripts/fixtures/cube_validate/checks.yml`
- Modify: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces: `CheckError(ValueError)`; `Dim` frozen dataclass (`name`,
  `cube: str | None`, `sql: str`, `granularity: str | None`);
  `load_checks(path) -> dict` (returns the YAML with `dimensions` replaced by
  `dict[str, Dim]` and defaults `hard_filters=[]`,
  `scope_measure="count_students"`,
  `students_sql="count(distinct student_number)"`);
  `academic_window(today: date) -> tuple[date, date]`;
  `cube_query(view, measures: list[str], grain: list[str], dims, hard_filters, window) -> dict`;
  `cube_key(view, dim: Dim) -> str`;
  `truth_sql(table, metrics: list[dict], grain: list[str], dims, hard_filters, window, students_sql) -> str`;
  constant `CUBE_LIMIT = 50_000`. Column aliases in `truth_sql`: `g<i>` per
  grain dimension, `m<i>` for a count metric, `m<i>_num`/`m<i>_den` for a rate,
  and `n_students`.

- [ ] **Step 1: Write the fixture checks file**

`tests/scripts/fixtures/cube_validate/checks.yml`:

```yaml
dashboard: demo_dashboard
task_gid: "100"
table: proj.ds.rpt_demo
view: demo_view
dimensions:
  date: { cube: attendance_date, sql: calendardate }
  month:
    {
      cube: attendance_date,
      granularity: month,
      sql: "date_trunc(calendardate, month)",
    }
  region: { cube: regions_region_name, sql: region }
  school: { cube: locations_abbreviation, sql: school_abbreviation }
  team: { cube: null, sql: team }
hard_filters:
  - { dim: region, values: [Camden, Newark] }
rows:
  - row_gid: "1"
    name: "# Tardy"
    metrics:
      - { cube: count_tardy_days, kind: count, sql: "sum(is_tardy)" }
    grains: [[], [region], [region, school], [region, team]]
  - row_gid: "2"
    name: ADA
    metrics:
      - {
          cube: avg_daily_attendance,
          kind: rate,
          num: "sum(is_present)",
          den: "sum(membershipvalue)",
        }
    grains: [[], [region, month]]
```

- [ ] **Step 2: Write the failing tests** (append to
      `tests/scripts/test_cube_validate.py`)

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: the Task 2 tests fail with `AttributeError` (no `load_checks`).

- [ ] **Step 4: Write the implementation** (add to `scripts/cube_validate.py`
      below `propose_grains`; add `import datetime as dt` and `import yaml` to
      the imports)

```python
# ---------------------------------------------------------------- checks files and queries
CUBE_LIMIT = 50_000
KINDS = {"count", "rate"}


class CheckError(ValueError):
    """A checks file that cannot be run as written."""


@dataclass(frozen=True)
class Dim:
    name: str
    cube: str | None  # None: no Cube member, so grains using it are not comparable
    sql: str
    granularity: str | None = None


def load_checks(path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    for key in ("dashboard", "table", "view", "dimensions", "rows"):
        if key not in data:
            raise CheckError(f"{path}: missing '{key}'")
    dims = {
        n: Dim(n, d.get("cube"), d["sql"], d.get("granularity"))
        for n, d in data["dimensions"].items()
    }
    if "date" not in dims or not dims["date"].cube:
        raise CheckError(f"{path}: 'dimensions.date' needs a cube member and a sql column")
    for d in dims.values():
        if d.granularity and d.cube != dims["date"].cube:
            raise CheckError(
                f"{path}: dimension '{d.name}' has a granularity but is not on the "
                f"date member '{dims['date'].cube}'"
            )
    data.setdefault("hard_filters", [])
    for f in data["hard_filters"]:
        if f["dim"] not in dims:
            raise CheckError(f"{path}: hard filter on unknown dimension '{f['dim']}'")
    for row in data["rows"]:
        where = f"{path}: row {row.get('row_gid')} ({row.get('name')})"
        for key in ("row_gid", "name", "metrics", "grains"):
            if key not in row:
                raise CheckError(f"{where}: missing '{key}'")
        for m in row["metrics"]:
            if m.get("kind") not in KINDS:
                raise CheckError(f"{where}: metric {m.get('cube')}: kind must be count or rate")
            need = ("cube", "sql") if m["kind"] == "count" else ("cube", "num", "den")
            missing = [k for k in need if not m.get(k)]
            if missing:
                raise CheckError(f"{where}: metric {m.get('cube')} is missing {missing}")
        for g in row["grains"]:
            unknown = [n for n in g if n not in dims]
            if unknown:
                raise CheckError(f"{where}: grain {g} uses unknown dimension(s) {unknown}")
            if sum(1 for n in g if dims[n].granularity) > 1:
                raise CheckError(f"{where}: grain {g} has more than one date part")
    data["dimensions"] = dims
    data.setdefault("scope_measure", "count_students")
    data.setdefault("students_sql", "count(distinct student_number)")
    return data


def academic_window(today: dt.date) -> tuple[dt.date, dt.date]:
    """July 1 of the academic year that contains yesterday, through yesterday."""
    end = today - dt.timedelta(days=1)
    return dt.date(end.year if end.month >= 7 else end.year - 1, 7, 1), end


def cube_key(view: str, dim: Dim) -> str:
    return f"{view}.{dim.cube}.{dim.granularity}" if dim.granularity else f"{view}.{dim.cube}"


def cube_query(view, measures, grain, dims, hard_filters, window) -> dict:
    td = {
        "dimension": f"{view}.{dims['date'].cube}",
        "dateRange": [window[0].isoformat(), window[1].isoformat()],
    }
    plain = []
    for name in grain:
        d = dims[name]
        if d.granularity:
            td["granularity"] = d.granularity
        else:
            plain.append(f"{view}.{d.cube}")
    return {
        "measures": [f"{view}.{m}" for m in measures],
        "dimensions": plain,
        "timeDimensions": [td],
        "filters": [
            {
                "member": f"{view}.{dims[f['dim']].cube}",
                "operator": "equals",
                "values": [str(v) for v in f["values"]],
            }
            for f in hard_filters
        ],
        "limit": CUBE_LIMIT,
        "timezone": "UTC",
    }


def _sql_literal(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return "'" + str(v).replace("'", "\\'") + "'"


def truth_sql(table, metrics, grain, dims, hard_filters, window, students_sql) -> str:
    select = [f"{dims[n].sql} as g{i}" for i, n in enumerate(grain)]
    for i, m in enumerate(metrics):
        if m["kind"] == "count":
            select.append(f"{m['sql']} as m{i}")
        else:
            select += [f"{m['num']} as m{i}_num", f"{m['den']} as m{i}_den"]
    select.append(f"{students_sql} as n_students")
    where = [f"{dims['date'].sql} between '{window[0]}' and '{window[1]}'"]
    for f in hard_filters:
        values = ", ".join(_sql_literal(v) for v in f["values"])
        where.append(f"{dims[f['dim']].sql} in ({values})")
    sql = f"select {', '.join(select)} from `{table}` where {' and '.join(where)}"
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: all pass (5 from Task 1, 11 from Task 2).

- [ ] **Step 6: Commit**

```bash
git add -u && git add tests/scripts/fixtures/cube_validate/checks.yml
git commit -F - <<'MSG'
feat(cube): load validation checks and build Cube and BigQuery queries

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

### Task 3: Cell comparison

**Files:**

- Modify: `scripts/cube_validate.py`
- Modify: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `cube_key`, `Dim` (Task 2).
- Produces: constants `SMALL_CELL = 10`, `RATE_TOLERANCE = 0.001`; `Cell`
  dataclass (`key: tuple[str, ...]`, `cube: float | None`,
  `truth: float | None`, `n_students: int | None`, `ok: bool`, property
  `delta: float`); `norm_key(v) -> str`;
  `cube_cells(rows, view, grain_dims: list[Dim], metric: str) -> dict[tuple, float | None]`;
  `truth_cells(rows, n_grain: int, i: int, kind: str) -> dict[tuple, tuple[float | None, int | None]]`;
  `compare(kind, cube, truth) -> list[Cell]`; `summarize(cells, kind) -> dict`
  with keys `cells`, `bad`, `worst` (up to 5 dicts with `key`, `cube`, `truth`,
  `n_students`, `kind`); `row_verdict(grains: list[dict]) -> str` (`pass` /
  `fail` / `incomplete`).

- [ ] **Step 1: Write the failing tests** (append)

```python
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
        [{"g0": "Newark", "g1": dt.date(2026, 9, 1), "m0_num": 9, "m0_den": 10, "n_students": 12}],
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
    region = cv.summarize(cv.compare("count", {("N",): 20.0}, {("N",): (20.0, 200)}), "count")
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: the Task 3 tests fail with `AttributeError`.

- [ ] **Step 3: Write the implementation** (add below `truth_sql`)

```python
# ---------------------------------------------------------------- comparison
SMALL_CELL = 10
RATE_TOLERANCE = 0.001
_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]")
_WHOLE_FLOAT = re.compile(r"^-?\d+\.0+$")


def norm_key(v) -> str:
    """One spelling per dimension value, so Cube strings join BigQuery types."""
    if v is None:
        return "∅"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, dt.date):
        return v.isoformat()[:10]
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if m := _ISO_DATE.match(s):
        return m.group(1)
    if _WHOLE_FLOAT.match(s):
        return s.split(".")[0]
    if s in ("True", "False"):
        return s.lower()
    return s


def _num(v) -> float | None:
    return None if v is None or v == "" else float(v)


@dataclass
class Cell:
    key: tuple[str, ...]
    cube: float | None
    truth: float | None
    n_students: int | None
    ok: bool

    @property
    def delta(self) -> float:
        if self.cube is None or self.truth is None:
            return float("inf")
        return abs(self.cube - self.truth)


def cube_cells(rows, view, grain_dims, metric) -> dict:
    keys = [cube_key(view, d) for d in grain_dims]
    return {
        tuple(norm_key(r.get(k)) for k in keys): _num(r.get(f"{view}.{metric}"))
        for r in rows
    }


def truth_cells(rows, n_grain, i, kind) -> dict:
    out = {}
    for r in rows:
        key = tuple(norm_key(r[f"g{j}"]) for j in range(n_grain))
        if kind == "count":
            v = _num(r[f"m{i}"])
        else:
            num, den = _num(r[f"m{i}_num"]), _num(r[f"m{i}_den"])
            v = None if not den else num / den
        n = r.get("n_students")
        out[key] = (v, None if n is None else int(n))
    return out


def compare(kind, cube, truth) -> list[Cell]:
    cells = []
    for key in sorted(set(cube) | set(truth)):
        c = cube.get(key)
        t, n = truth.get(key, (None, None))
        if kind == "count":
            # No row on a side means nothing to count there: compare as 0.
            c, t = c or 0.0, t or 0.0
            ok = abs(c - t) < 1e-9
        else:
            ok = (c is None and t is None) or (
                c is not None and t is not None and abs(c - t) <= RATE_TOLERANCE + 1e-12
            )
        cells.append(Cell(key, c, t, n, ok))
    return cells


def summarize(cells, kind) -> dict:
    bad = sorted((c for c in cells if not c.ok), key=lambda c: -c.delta)
    return {
        "cells": len(cells),
        "bad": len(bad),
        "worst": [
            {
                "key": list(c.key),
                "cube": c.cube,
                "truth": c.truth,
                "n_students": c.n_students,
                "kind": kind,
            }
            for c in bad[:5]
        ],
    }


def row_verdict(grains) -> str:
    statuses = [g["status"] for g in grains]
    if "fail" in statuses:
        return "fail"
    if "error" in statuses or "pass" not in statuses:
        return "incomplete"
    return "pass"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -F - <<'MSG'
feat(cube): compare Cube and warehouse cells with count and rate tolerance

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

### Task 4: Cube client, run orchestration, outputs, `run` CLI

**Files:**

- Modify: `scripts/cube_validate.py`
- Modify: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: everything from Tasks 2 and 3.
- Produces: `CubeError`, `ScopeError`; constants `DEFAULT_CUBE_URL`,
  `BQ_PROJECT = "teamster-332318"`, `DEFAULT_OUT`;
  `CubeClient(url, secret, email, http=None, sleep=time.sleep)` with
  `.load(query) -> tuple[list[dict], list[str]]` (rows, pre-aggregation names);
  `bigquery_rows(sql) -> list[dict]`;
  `scope_guard(checks, cube_load, bq, window) -> None`;
  `run_dashboard(checks, cube_load, bq, today, rows=None, scope_only=False) -> dict`;
  `comment_text(row, result, report_path) -> str`;
  `report_markdown(result) -> str`; `write_outputs(result, out_dir) -> Path`;
  `main` gains subcommand `run`. Result shape:
  `{"dashboard", "window": [start, end], "run_date", "rows": {gid: {"name", "verdict", "grains": [{"grain", "status", "cells", "bad", "metrics", "pre_aggregations", "error"}], "comment"}}}`.
  `latest.json`: `{"rows": {gid: {"verdict", "date", "dashboard", "name"}}}`.

- [ ] **Step 1: Write the failing tests** (append)

```python
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
            return [{f"{v}.regions_region_name": r, f"{v}.count_students": n} for r, n in self.scope.items()], []
        dims = q["dimensions"]
        gran = q["timeDimensions"][0].get("granularity")
        if not dims:
            return [{f"{v}.count_tardy_days": "30", f"{v}.avg_daily_attendance": "0.9"}], ["main_rollup"]
        if gran == "month":
            return [
                {
                    f"{v}.regions_region_name": "Camden",
                    f"{v}.attendance_date.month": "2026-09-01T00:00:00.000",
                    f"{v}.avg_daily_attendance": "0.9",
                }
            ], []
        if len(dims) == 1:
            return [
                {f"{v}.regions_region_name": "Camden", f"{v}.count_tardy_days": "10"},
                {f"{v}.regions_region_name": "Newark", f"{v}.count_tardy_days": "20"},
            ], []
        return [
            {f"{v}.regions_region_name": "Camden", f"{v}.locations_abbreviation": "A", f"{v}.count_tardy_days": "10"},
            {f"{v}.regions_region_name": "Newark", f"{v}.locations_abbreviation": "B", f"{v}.count_tardy_days": "15"},
            {f"{v}.regions_region_name": "Newark", f"{v}.locations_abbreviation": "C", f"{v}.count_tardy_days": "5"},
        ], []


class FakeBQ:
    def __init__(self, fail_on=None, scope=None):
        self.fail_on = fail_on
        self.scope = scope or [{"g0": "Camden", "n_students": 100}, {"g0": "Newark", "n_students": 200}]

    def __call__(self, sql):
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")
        if " as m0" not in sql and " as m0_num" not in sql:
            return self.scope
        if " as g0" not in sql:
            return [{"m0": 30, "m1_num": 90, "m1_den": 100, "n_students": 300}]
        if "date_trunc" in sql:
            return [{"g0": "Camden", "g1": dt.date(2026, 9, 1), "m0_num": 45, "m0_den": 50, "n_students": 100}]
        if " as g1" not in sql:
            return [{"g0": "Camden", "m0": 10, "n_students": 100}, {"g0": "Newark", "m0": 20, "n_students": 200}]
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
    assert [g["status"] for g in tardy["grains"]] == ["pass", "pass", "fail", "not_comparable"]
    assert ada["verdict"] == "pass"
    # scope guard + total (shared by both rows) + region + region x school + region x month
    assert len(cube.queries) == 5
    assert tardy["grains"][0]["pre_aggregations"] == ["main_rollup"]
    assert result["window"] == ["2026-07-01", "2026-10-07"]


def test_run_dashboard_grain_error_makes_row_incomplete():
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(fail_on="date_trunc"), TODAY)
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
        [{"error": "Continue wait"}, {"data": [{"a": "1"}], "usedPreAggregations": {"r1": {}}}]
    )
    client = cv.CubeClient("https://cube/api/", SECRET, "me@example.org", http=http, sleep=lambda _: None)
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
    client = cv.CubeClient("u", SECRET, "e", http=FakeHttp([{"error": "bad member"}]), sleep=lambda _: None)
    with pytest.raises(cv.CubeError, match="bad member"):
        client.load({})


def test_write_outputs_comments_report_and_latest_merge(tmp_path):
    (tmp_path / "latest.json").write_text(
        json.dumps({"rows": {"999": {"verdict": "pass", "date": "2026-10-01", "dashboard": "other", "name": "x"}}})
    )
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY)
    report = cv.write_outputs(result, tmp_path)
    latest = json.loads((tmp_path / "latest.json").read_text())
    assert set(latest["rows"]) == {"999", "1", "2"}
    assert latest["rows"]["1"]["verdict"] == "fail"
    assert report == tmp_path / "2026-10-08-demo_dashboard.md"
    assert (tmp_path / "2026-10-08-demo_dashboard.json").exists()
    comment = result["rows"]["1"]["comment"]
    assert comment.splitlines()[0] == "Cube vs Tableau check, 2026-10-08: FAIL"
    assert "Window: 2026-07-01 to 2026-10-07. 3 grains, 6 cells, 2 out of tolerance." in comment
    assert "Worst: count_tardy_days at region x school, Newark / B: Cube 15, Tableau 12." in comment
    assert "Not comparable: region x team (no Cube member)." in comment


def test_comment_hides_small_cells():
    row = {
        "verdict": "fail",
        "grains": [
            {
                "grain": ["school"],
                "status": "fail",
                "cells": 1,
                "bad": 1,
                "metrics": {"count_tardy_days": {"worst": [{"key": ["A"], "cube": 3.0, "truth": 4.0, "n_students": 6, "kind": "count"}]}},
            }
        ],
    }
    text = cv.comment_text(row, {"run_date": "2026-10-08", "window": ["a", "b"]}, Path("r.md"))
    assert "small cell" in text and "Cube 3" not in text


def test_run_cli_requires_the_secret(monkeypatch):
    monkeypatch.delenv("CUBE_API_SECRET", raising=False)
    with pytest.raises(SystemExit, match="CUBE_API_SECRET"):
        cv.main(["run", str(FIX / "checks.yml")])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: the Task 4 tests fail with `AttributeError`.

- [ ] **Step 3: Write the implementation** (add below `row_verdict`; add
      `import os` and `import time` to the imports)

```python
# ---------------------------------------------------------------- clients
DEFAULT_CUBE_URL = "https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1"
USER_EMAIL_CACHE = Path.home() / ".config" / "teamster" / "cube-user-email"
DEFAULT_OUT = Path.home() / "asana-sync" / "validation"
BQ_PROJECT = "teamster-332318"


class CubeError(RuntimeError):
    """Cube returned an error, or a result that cannot be compared."""


class ScopeError(RuntimeError):
    """The Cube identity sees less than the dashboard does."""


class CubeClient:
    def __init__(self, url, secret, email, http=None, sleep=time.sleep):
        import httpx

        self.url, self.secret, self.email = url.rstrip("/"), secret, email
        self.http = http or httpx.Client(timeout=60)
        self.sleep = sleep

    def _token(self) -> str:
        import jwt

        now = int(time.time())
        # cube.js checks maxAge from `iat`, so it must be present.
        return jwt.encode(
            {"email": self.email, "iat": now, "exp": now + 300}, self.secret, algorithm="HS256"
        )

    def load(self, query) -> tuple[list[dict], list[str]]:
        for _ in range(120):
            r = self.http.post(
                f"{self.url}/load", json={"query": query}, headers={"Authorization": self._token()}
            )
            try:
                body = r.json()
            except ValueError as e:
                raise CubeError(f"HTTP {r.status_code}: response is not JSON") from e
            if body.get("error") == "Continue wait":
                self.sleep(1)
                continue
            if r.status_code >= 400 or "error" in body:
                raise CubeError(str(body.get("error") or f"HTTP {r.status_code}")[:300])
            rows = body.get("data", [])
            if len(rows) >= CUBE_LIMIT:
                raise CubeError(f"result hit the {CUBE_LIMIT}-row limit; this grain is too fine")
            return rows, sorted((body.get("usedPreAggregations") or {}).keys())
        raise CubeError("gave up after 120 'Continue wait' responses")


def bigquery_rows(sql: str) -> list[dict]:
    from google.cloud import bigquery

    return [dict(r.items()) for r in bigquery.Client(project=BQ_PROJECT).query(sql).result()]


# ---------------------------------------------------------------- run
def scope_guard(checks, cube_load, bq, window) -> None:
    """Stop when Cube sees none of a hard-filter value the warehouse has students for."""
    if not checks["hard_filters"]:
        return
    view, dims, hard = checks["view"], checks["dimensions"], checks["hard_filters"]
    name = hard[0]["dim"]
    rows, _ = cube_load(cube_query(view, [checks["scope_measure"]], [name], dims, hard, window))
    seen = {
        norm_key(r.get(cube_key(view, dims[name]))): _num(r.get(f"{view}.{checks['scope_measure']}")) or 0
        for r in rows
    }
    for r in bq(truth_sql(checks["table"], [], [name], dims, hard, window, checks["students_sql"])):
        value, n = norm_key(r["g0"]), r["n_students"]
        if n and not seen.get(value):
            raise ScopeError(
                f"Cube returned no {checks['scope_measure']} for {name}={value}, but the "
                f"warehouse has {n} students. The Cube identity's scope is narrower than "
                "the dashboard's; rerun as a network-scoped user."
            )


def run_dashboard(checks, cube_load, bq, today, rows=None, scope_only=False) -> dict:
    window = academic_window(today)
    dims, hard = checks["dimensions"], checks["hard_filters"]
    scope_guard(checks, cube_load, bq, window)
    result = {
        "dashboard": checks["dashboard"],
        "window": [window[0].isoformat(), window[1].isoformat()],
        "run_date": today.isoformat(),
        "rows": {},
    }
    if scope_only:
        return result
    selected = [r for r in checks["rows"] if rows is None or str(r["row_gid"]) in rows]

    # One Cube query and one SQL query per (view, table, grain), carrying every metric.
    jobs: dict[tuple, list[dict]] = {}
    for row in selected:
        where = (row.get("view", checks["view"]), row.get("table", checks["table"]))
        for g in row["grains"]:
            metrics = jobs.setdefault((*where, tuple(g)), [])
            for m in row["metrics"]:
                if m["cube"] not in [x["cube"] for x in metrics]:
                    metrics.append(m)

    outcomes = {}
    for (view, table, g), metrics in jobs.items():
        grain = [dims[n] for n in g]
        if any(d.cube is None for d in grain):
            outcomes[(view, table, g)] = {"status": "not_comparable"}
            continue
        try:
            crows, preaggs = cube_load(
                cube_query(view, [m["cube"] for m in metrics], list(g), dims, hard, window)
            )
            trows = bq(truth_sql(table, metrics, list(g), dims, hard, window, checks["students_sql"]))
        except Exception as e:  # noqa: BLE001 - any failure leaves this grain incomplete
            outcomes[(view, table, g)] = {"status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
            continue
        outcomes[(view, table, g)] = {
            "status": "ok",
            "pre_aggregations": preaggs,
            "metrics": {
                m["cube"]: summarize(
                    compare(
                        m["kind"],
                        cube_cells(crows, view, grain, m["cube"]),
                        truth_cells(trows, len(g), i, m["kind"]),
                    ),
                    m["kind"],
                )
                for i, m in enumerate(metrics)
            },
        }

    for row in selected:
        where = (row.get("view", checks["view"]), row.get("table", checks["table"]))
        grains = []
        for g in row["grains"]:
            o = outcomes[(*where, tuple(g))]
            entry = {"grain": list(g), "status": o["status"]}
            if o["status"] == "error":
                entry["error"] = o["error"]
            if o["status"] == "ok":
                ms = {m["cube"]: o["metrics"][m["cube"]] for m in row["metrics"]}
                bad = sum(s["bad"] for s in ms.values())
                entry.update(
                    status="fail" if bad else "pass",
                    cells=sum(s["cells"] for s in ms.values()),
                    bad=bad,
                    metrics=ms,
                    pre_aggregations=o["pre_aggregations"],
                )
            grains.append(entry)
        result["rows"][str(row["row_gid"])] = {
            "name": row["name"],
            "verdict": row_verdict(grains),
            "grains": grains,
        }
    return result


# ---------------------------------------------------------------- outputs
def _fmt(v, kind) -> str:
    if v is None:
        return "none"
    return f"{v * 100:.1f}%" if kind == "rate" else f"{v:,.0f}"


def _label(grain) -> str:
    return " x ".join(grain) or "total"


def _where(grain, key) -> str:
    return f"{_label(grain)}, {' / '.join(key) or 'all'}"


def comment_text(row, result, report_path) -> str:
    grains = row["grains"]
    compared = [g for g in grains if g["status"] in ("pass", "fail")]
    lines = [
        f"Cube vs Tableau check, {result['run_date']}: {row['verdict'].upper()}",
        f"Window: {result['window'][0]} to {result['window'][1]}. {len(compared)} grains, "
        f"{sum(g['cells'] for g in compared)} cells, "
        f"{sum(g['bad'] for g in compared)} out of tolerance.",
    ]
    worst = None
    for g in compared:
        for metric, s in g["metrics"].items():
            for c in s["worst"][:1]:
                d = float("inf") if c["cube"] is None or c["truth"] is None else abs(c["cube"] - c["truth"])
                if worst is None or d > worst[0]:
                    worst = (d, g["grain"], metric, c)
    if worst:
        _, grain, metric, c = worst
        if c["n_students"] is None or c["n_students"] < SMALL_CELL:
            lines.append(f"Worst: {metric} at {_where(grain, c['key'])}: small cell, values in the report.")
        else:
            lines.append(
                f"Worst: {metric} at {_where(grain, c['key'])}: "
                f"Cube {_fmt(c['cube'], c['kind'])}, Tableau {_fmt(c['truth'], c['kind'])}."
            )
    not_comparable = [_label(g["grain"]) for g in grains if g["status"] == "not_comparable"]
    if not_comparable:
        lines.append(f"Not comparable: {', '.join(not_comparable)} (no Cube member).")
    lines += [f"Error at {_label(g['grain'])}: {g['error']}" for g in grains if g["status"] == "error"]
    lines.append(f"Report: {report_path}")
    return "\n".join(lines)


def report_markdown(result) -> str:
    out = [
        f"# Cube vs Tableau: {result['dashboard']}",
        "",
        f"Run {result['run_date']}, window {result['window'][0]} to {result['window'][1]}.",
        "",
    ]
    for gid, row in result["rows"].items():
        out += [f"## {row['name']} ({gid}): {row['verdict']}", ""]
        for g in row["grains"]:
            line = f"- {_label(g['grain'])}: {g['status']}"
            if g["status"] in ("pass", "fail"):
                line += f", {g['bad']} of {g['cells']} cells out of tolerance"
                if g["pre_aggregations"]:
                    line += f" (pre-aggregations: {', '.join(g['pre_aggregations'])})"
            if g["status"] == "error":
                line += f": {g['error']}"
            out.append(line)
            for metric, s in g.get("metrics", {}).items():
                for c in s["worst"]:
                    n = c["n_students"] if c["n_students"] is not None else "n/a"
                    out.append(
                        f"  - {metric} {' / '.join(c['key']) or 'all'}: "
                        f"Cube {_fmt(c['cube'], c['kind'])}, Tableau {_fmt(c['truth'], c['kind'])}, "
                        f"students {n}"
                    )
        out.append("")
    return "\n".join(out)


def write_outputs(result, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result['run_date']}-{result['dashboard']}"
    report = out_dir / f"{stem}.md"
    for row in result["rows"].values():
        row["comment"] = comment_text(row, result, report)
    report.write_text(report_markdown(result))
    (out_dir / f"{stem}.json").write_text(json.dumps(result, indent=2, default=str))
    latest_path = out_dir / "latest.json"
    latest = json.loads(latest_path.read_text()) if latest_path.exists() else {"rows": {}}
    for gid, row in result["rows"].items():
        latest["rows"][gid] = {
            "verdict": row["verdict"],
            "date": result["run_date"],
            "dashboard": result["dashboard"],
            "name": row["name"],
        }
    latest_path.write_text(json.dumps(latest, indent=2))
    return report


def _user_email(given: str | None) -> str:
    email = (given or os.environ.get("CUBE_USER_EMAIL", "")).strip()
    if not email and USER_EMAIL_CACHE.exists():
        email = USER_EMAIL_CACHE.read_text().strip()
    if not email:
        sys.exit("No Cube identity: pass --as <email> or set CUBE_USER_EMAIL.")
    return email


def _run_command(a) -> int:
    secret = os.environ.get("CUBE_API_SECRET", "")
    if not secret:
        sys.exit(
            "CUBE_API_SECRET is not set: run this inside a throwaway pytest "
            "(see .claude/skills/cube-dashboard/SKILL.md)."
        )
    checks = load_checks(a.checks)
    cube = CubeClient(a.cube_url, secret, _user_email(a.email))
    result = run_dashboard(
        checks,
        cube.load,
        bigquery_rows,
        dt.date.today(),
        rows=set(a.rows.split(",")) if a.rows else None,
        scope_only=a.scope_only,
    )
    if a.scope_only:
        print("scope ok")
        return 0
    report = write_outputs(result, a.out)
    for gid, row in result["rows"].items():
        print(f"{row['verdict']:<10} {gid} {row['name']}")
    print(f"report: {report}")
    return 0 if all(r["verdict"] == "pass" for r in result["rows"].values()) else 1
```

Then extend `main` (replace the body after `g.add_argument("--measure")`):

```python
    r = sub.add_parser("run", help="compare Cube with the warehouse for a checks file")
    r.add_argument("checks")
    r.add_argument("--rows", help="comma-separated Asana row gids (default: all)")
    r.add_argument("--scope-only", action="store_true", help="run only the scope guard")
    r.add_argument("--as", dest="email", help="Cube identity (default: CUBE_USER_EMAIL)")
    r.add_argument("--cube-url", default=DEFAULT_CUBE_URL)
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = p.parse_args(argv)
    return _grains_command(a) if a.cmd == "grains" else _run_command(a)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 15`
Expected: all pass.

- [ ] **Step 5: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix scripts/cube_validate.py tests/scripts/test_cube_validate.py tests/scripts/fixtures/cube_validate/checks.yml </dev/null 2>&1 | tail -n 20`
Expected: no issues. Fix any ruff findings in place (long lines in the tests are
the likely ones; wrap them).

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -F - <<'MSG'
feat(cube): run Cube-versus-warehouse checks and write the report

Adds the Cube REST client, the scope guard, one query per view and
grain, the Markdown report, the per-row Asana comment text, and
latest.json for sync.py.

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

### Task 5: Attendance checks file

The judgment task: each Tableau formula becomes SQL on
`rpt_tableau__attendance_dashboard`, and each Cube member is confirmed against
its YAML. The user reviews the file before any run.

**Files:**

- Create: `.claude/skills/cube-dashboard/checks/attendance_dashboard.yml`

**Interfaces:**

- Consumes: `grains` CLI (Task 1), `load_checks` (Task 2).
- Produces: the checks file Task 7 runs.

- [ ] **Step 1: Confirm the done rows**

Call `mcp__claude_ai_Asana__get_task` on each subtask of the Attendance
Dashboard task `1213823788919470` with `opt_fields=name,completed,notes`. Keep
the rows with `completed: true`. Expected: 7 rows, `% On-Time (standalone)`
`1219087795895880`, `# Tardy` `1214703929266204`,
`ADA / Is Present (standalone)` `1214075610424640`, `Truancy flag / ...`
`1214073491303422`, `CountD Student Number (headcount)` `1219285655850612`,
`# Absences` `1219285941351457`, `Membershipvalue` `1219285583802448`. If the
set differs, use what Asana says and tell the user.

- [ ] **Step 2: Download the workbook**

Write `tests/test_zz_cube_dashboard_twb.py`:

```python
import os
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path(__file__).resolve().parents[1] / ".claude" / "scratch" / "cube-dashboard"
LUID = "87c13e78-a912-40a4-95dd-33248fc1cbd3"  # Attendance Dashboard
STEM = "attendance_dashboard"


def test_download() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        # tableauserverclient appends the extension: pass the stem.
        got = Path(server.workbooks.download(LUID, filepath=str(OUT / STEM), include_extract=False))
    if got.suffix == ".twbx":
        with zipfile.ZipFile(got) as z:
            name = next(n for n in z.namelist() if n.endswith(".twb"))
            (OUT / f"{STEM}.twb").write_bytes(z.read(name))
    elif got != OUT / f"{STEM}.twb":
        got.replace(OUT / f"{STEM}.twb")
    print("TWB bytes", (OUT / f"{STEM}.twb").stat().st_size)
```

Run:
`uv run pytest tests/test_zz_cube_dashboard_twb.py -s -q --tb=short 2>&1 | tail -n 5; rm tests/test_zz_cube_dashboard_twb.py`
Expected: `TWB bytes` about 1,000,000, then 1 passed.

- [ ] **Step 3: Propose grains for each row's Tableau measure**

The published dashboards are the 7 views `get-workbook` lists: Attendance
Rollup, Student Attendance Tracker, Trends, CA Intervention Tracker, Successful
Calls Tracking, Board Report, Miami - NSLP. First list every measure caption:

```bash
uv run scripts/cube_validate.py grains .claude/scratch/cube-dashboard/attendance_dashboard.twb \
  --dashboard "Attendance Rollup" --dashboard "Student Attendance Tracker" --dashboard "Trends" \
  --dashboard "CA Intervention Tracker" --dashboard "Successful Calls Tracking" \
  --dashboard "Board Report" --dashboard "Miami - NSLP" | uv run python -c \
  "import json,sys; [print(s['name'], '|', sorted(s['measures'])) for s in json.load(sys.stdin)['sheets']]"
```

Then, for each row's caption (for example `# Tardy`, `# Absences`,
`Attendance Metric`), rerun with `--measure "<caption>"` and keep the `grains`
and each sheet's `formula`. A row whose number appears through the
`Attendance Metric` parameter swap (ADA, % On-Time, Truancy) takes the grains of
`Attendance Metric` plus those of its standalone caption.

- [ ] **Step 4: Translate each formula to SQL**

For each row:

1. Read the Tableau `formula`. Resolve every field it references that is not a
   plain column: a group such as `[Att Code (group)]` is a
   `<column ... <calculation class='categorical-bin'>` in the `.twb`; grep
   `.claude/scratch/cube-dashboard/attendance_dashboard.twb` for its caption and
   rebuild its member list as a SQL `case` or `in`.
2. Read the Cube member's definition in
   `src/cube/model/cubes/students/student_attendance_enrollment_daily.yml` (or
   `..._periods.yml` for Truancy). Note its `filters:`: the SQL must count what
   the dashboard counts, not what Cube counts. If the two definitions differ on
   purpose, write the dashboard's version and add a YAML comment on the metric
   naming the difference.
3. Confirm every column used exists:
   `rg -n "<column>" src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__attendance_dashboard.sql`.
4. Pick `kind`: `count` for sums and distinct counts, `rate` for averages, with
   `num`/`den` as the sums the average divides.

- [ ] **Step 5: Write the file**

`.claude/skills/cube-dashboard/checks/attendance_dashboard.yml` starts with this
header (values verified against the view YAML and the `rpt_` SQL on 2026-10-08).
Add one `rows:` entry per done row from Steps 1 to 4, in the shape of the
`# Tardy` example in the spec, Section 2. Add a `dimensions:` entry for every
dimension in any grain; a dimension with no Cube member gets `cube: null`.

```yaml
# Validation checks for the Attendance Dashboard (Tableau workbook
# 87c13e78-a912-40a4-95dd-33248fc1cbd3). Run with the cube-dashboard skill.
# Every row's `sql` reproduces the Tableau formula on the dashboard's own table.
dashboard: attendance_dashboard
task_gid: "1213823788919470"
workbook_luid: 87c13e78-a912-40a4-95dd-33248fc1cbd3
table: teamster-332318.kipptaf_tableau.rpt_tableau__attendance_dashboard
view: student_attendance_enrollment_daily_view

dimensions:
  date: { cube: attendance_date, sql: calendardate }
  month:
    {
      cube: attendance_date,
      granularity: month,
      sql: "date_trunc(calendardate, month)",
    }
  academic_year: { cube: dates_academic_year, sql: academic_year }
  region: { cube: regions_region_name, sql: region }
  school: { cube: locations_abbreviation, sql: school_abbreviation }
  grade_level: { cube: grade_level, sql: grade_level }
  team: { cube: null, sql: team }

# Every NJ tab hard-codes these three regions; Miami - NSLP is Miami-only and
# is checked as its own rows if any of its measures are done.
hard_filters:
  - { dim: region, values: [Camden, Newark, Paterson] }
```

- [ ] **Step 6: Validate the file**

Run:
`uv run python -c "import importlib.util,sys; s=importlib.util.spec_from_file_location('cv','scripts/cube_validate.py'); m=importlib.util.module_from_spec(s); sys.modules['cv']=m; s.loader.exec_module(m); c=m.load_checks('.claude/skills/cube-dashboard/checks/attendance_dashboard.yml'); print(len(c['rows']), 'rows ok')"`
Expected: `7 rows ok`.

Then run each row's total-grain SQL once through
`mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly` (build it with
`truth_sql` and an empty grain) to confirm it compiles and returns one row.
Report only the aggregate.

- [ ] **Step 7: User review**

Show the user each row's Tableau formula next to its SQL and its grains, as a
table. Wait for approval; apply their changes.

- [ ] **Step 8: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/checks/attendance_dashboard.yml </dev/null 2>&1 | tail -n 10
git add .claude/skills/cube-dashboard/checks/attendance_dashboard.yml
git commit -F - <<'MSG'
feat(cube): add validation checks for the Attendance Dashboard

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

If gitleaks flags a gid line, rename the key (it matches keys containing "asana"
followed by 16 digits); the keys here are `task_gid` and `row_gid` for that
reason.

### Task 6: The skill runbook

**Files:**

- Create: `.claude/skills/cube-dashboard/SKILL.md`
- Modify: `scripts/CLAUDE.md` (Script Catalog table)

**Interfaces:**

- Consumes: the `grains` and `run` CLIs, the checks file format.
- Produces: the runbook Task 7 follows.

- [ ] **Step 1: Invoke `superpowers:writing-skills`** and follow it for the file
      below (its testing step is Task 7's pilot).

- [ ] **Step 2: Write `.claude/skills/cube-dashboard/SKILL.md`**

````markdown
---
name: cube-dashboard
description:
  "Use when checking that Cube matches a Tableau dashboard for the measure rows
  in the Asana project 'Data Marts + Semantic Layer': validating cube-covered
  rows against the live dashboard at every grain, authoring or updating a
  dashboard's checks file, reading a validation report, or posting results to
  Asana. Triggers: 'validate <dashboard> in Cube', 'does Cube match Tableau', a
  mismatch tag, ~/asana-sync/validation, checks/<dashboard>.yml."
---

# cube-dashboard

Validate mode compares Cube with what a Tableau dashboard shows, at every grain
the dashboard's sheets use, for the dashboard's done measure rows in Asana
("Data Marts + Semantic Layer", gid `1213735218595734`). Design:
`docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`.

A row passes only if every cell at every grain is within tolerance: counts
exactly, rates within 0.1 point. A total can match while a school is far off;
that is the case this exists to catch (#5692).

## Validate a dashboard

1. **Rows.** Read the dashboard task's subtasks from Asana; keep the completed
   ones whose notes have `Status:`. Never touch Anthony's six checklist
   subtasks.
2. **Checks.** Open `checks/<dashboard>.yml`. For any done row with no entry,
   author one (below). Show new or changed entries to the user and wait for
   approval before running.
3. **Run.** Write `tests/test_zz_cube_dashboard_run.py` (template below), run
   `uv run pytest tests/test_zz_cube_dashboard_run.py -s -q --tb=short`, then
   delete it. First run with `--scope-only`; a `ScopeError` means the Cube
   identity sees less than the dashboard, so stop and tell the user.
4. **Renders.** For each tab in the entries' `renders:`, call
   `mcp__tableau__get-view-image` once per region (`viewFilters` set to that
   region) and at the worst failing cells. Compare the visible numbers to the
   report. A render that disagrees with the warehouse SQL means the SQL is
   wrong: mark the row `incomplete` in your summary and fix the entry before
   posting anything.
5. **Review.** Summarize the verdicts for the user: rows that fail, the worst
   cell for each, any grain errors, any pre-aggregations on failed grains (a
   stale rollup is a different fix from a mart gap).
6. **Post.** After the user agrees, post each row's `comment` from
   `~/asana-sync/validation/<date>-<dashboard>.json` verbatim with
   `mcp__claude_ai_Asana__add_comment`.
7. **Tags.** Tell the user to run `~/asana-sync/sync.py` (preview, then
   `--apply`). It reads `latest.json` and adds or removes the `mismatch` tag;
   the skill never changes tags itself.

Run template:

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
EXTRA: list[str] = []  # e.g. ["--scope-only"] or ["--rows", "<gid>"]


def test_run() -> None:
    spec = importlib.util.spec_from_file_location("cube_validate", ROOT / "scripts/cube_validate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    print("exit", mod.main(["run", str(CHECKS), "--as", "<network-scoped email>", *EXTRA]))
```

## Author a check entry

1. Download the workbook to `.claude/scratch/cube-dashboard/<dashboard>.twb`
   with a throwaway pytest (`tableauserverclient`, `include_extract=False`; it
   appends the extension, so pass the stem).
2. Run `uv run scripts/cube_validate.py grains <twb> --dashboard "<view>" ...`
   with every published view name from `mcp__tableau__get-workbook`, then again
   with `--measure "<caption>"`. Keep its `grains` and each sheet's `formula`.
3. Translate the formula to SQL on the dashboard's `rpt_tableau__*` table.
   Resolve groups (`categorical-bin` columns in the `.twb`) and parameters.
   Match what the dashboard counts, not what the Cube measure counts; comment on
   any deliberate difference.
4. Map every grain dimension in `dimensions:`; one with no Cube member gets
   `cube: null` and is reported as not comparable, not as a mismatch.
5. `count` for sums and distinct counts, `rate` with `num`/`den` for averages.
6. Check the file loads (`load_checks`) and each total-grain SQL runs once in
   BigQuery.

## Rules

- Aggregates only. Never put student names or ids in a comment, the report, or
  chat. Comments already hide cells under 10 students.
- The scratchpad can be wiped: workbooks go in
  `.claude/scratch/cube-dashboard/`, results in `~/asana-sync/validation/`,
  checks in this folder.
- Build mode (work a dashboard's blocking table tasks) plugs in later through
  two things only: append the row's entry here, then
  `run <checks> --rows <gid>`; a built row is done when that returns `pass`.
````

- [ ] **Step 3: Add the script to the catalog**

In `scripts/CLAUDE.md`, add this row to the Script Catalog table after the
`cube_rls_matrix.py` row:

```markdown
| `cube_validate.py` | Compare Cube with a Tableau dashboard's warehouse table
at every grain the workbook's sheets use (`grains` proposes them from a `.twb`;
`run` compares and writes `~/asana-sync/validation/`). `run` needs
`CUBE_API_SECRET`, so it runs inside a throwaway pytest. Runbook: the
`cube-dashboard` skill (#4314). |
```

- [ ] **Step 4: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk fmt .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md </dev/null 2>&1 | tail -n 3
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md </dev/null 2>&1 | tail -n 10
git add -u && git add .claude/skills/cube-dashboard/SKILL.md
git commit -F - <<'MSG'
feat(cube): add the cube-dashboard skill runbook for validate mode

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
MSG
```

### Task 7: Attendance pilot

Follows the skill from Task 6 end to end; this is also the skill's test.

**Files:** none in the repo unless the pilot exposes a fix (then amend the
owning task's files and add a test that pins the fix).

- [ ] **Step 1: Confirm the prerequisite.** Ask the user whether the secrets
      template line is in. Probe with a throwaway test that prints only
      `set`/`MISSING` for `CUBE_API_SECRET`, then delete it. Stop here until it
      prints `set`.
- [ ] **Step 2: Scope guard.** Run the skill's template with
      `EXTRA = ["--scope-only"]`. Expected: `scope ok`.
- [ ] **Step 3: Full run.** Run the template with `EXTRA = []`. Expected: one
      verdict line per row and a `report:` path. Read the report.
- [ ] **Step 4: Renders.** Follow skill step 4 for the Attendance Rollup tab
      (`2995637c-c212-4909-a9e8-db3e6b533acc`) and the Student Attendance
      Tracker tab (`83fd1cce-1e00-413a-a889-b1c335099ac7`), once per region.
- [ ] **Step 5: Review with the user.** Present the verdicts and worst cells
      (aggregates only). Fix any check entry the renders contradict, rerun, and
      repeat until the user accepts the results.
- [ ] **Step 6: Post the comments** (skill step 6), after the user says so.
- [ ] **Step 7: Open the PR.** `git push`, then
      `mcp__github__create_pull_request` with the body from
      `.github/pull_request_template.md`, `Refs #4314`, the pilot's verdict
      counts, and the closing line
      `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Offer
      to watch CI and respond to `claude-review` (root CLAUDE.md).

### Task 8: `sync.py` respects the `mismatch` tag (outside the repo)

**Files:**

- Modify: `~/asana-sync/sync.py` (not in git; the user runs it)
- Modify: `~/asana-sync/RULES.md`

**Interfaces:**

- Consumes: `~/asana-sync/validation/latest.json` from Task 4.

- [ ] **Step 1: Edit `sync.py`**

Add `import json` to the imports. After the `STATUS = [...]` line add:

```python
MISMATCH = "mismatch"
LATEST = os.path.expanduser("~/asana-sync/validation/latest.json")
validation = json.load(open(LATEST))["rows"] if os.path.exists(LATEST) else {}
```

After the loop that fills `status_gid`, add:

```python
gids = tags.get(MISMATCH, [])
mismatch_gid = gids[0] if gids else call("POST", "/tags", {"data": {"name": MISMATCH, "workspace": WORKSPACE}})["data"]["gid"]
```

Change `report_untick, report_unverified = [], []` to
`report_untick, report_unverified, report_mismatch = [], [], []`.

In the row loop, directly after `named = members_named(r.get("notes"))`, add:

```python
        # 5. validation results from the cube-dashboard skill
        verdict = validation.get(rid, {}).get("verdict")
        tagged = mismatch_gid in have
        if verdict == "fail" and not tagged:
            write(f"{name}: validation failed -> add '{MISMATCH}'", "POST", f"/tasks/{rid}/addTag", {"tag": mismatch_gid})
            tagged = True
        elif verdict == "pass" and tagged:
            write(f"{name}: validation passed -> remove '{MISMATCH}'", "POST", f"/tasks/{rid}/removeTag", {"tag": mismatch_gid})
            tagged = False
        if tagged:
            report_mismatch.append(f"{name} ({rid}): {'done' if done else 'open'}, Cube does not match Tableau")
```

Change the auto-tick condition from
`if not done and blockers and all(d.get("completed") for _, d in blockers):` to
`if not done and not tagged and blockers and all(d.get("completed") for _, d in blockers):`.

Before `if not APPLY:` at the end, add:

```python
if report_mismatch:
    print(f"\nRows tagged '{MISMATCH}' (never auto-ticked; see ~/asana-sync/validation/):")
    print("\n".join("  " + x for x in report_mismatch))
```

Add a line to the module docstring's numbered list:
`5. Adds or removes the 'mismatch' tag from ~/asana-sync/validation/latest.json and never auto-ticks a tagged row.`

- [ ] **Step 2: Check it compiles**

Run: `uv run python -m py_compile ~/asana-sync/sync.py && echo ok` Expected:
`ok`.

- [ ] **Step 3: Update `RULES.md`**

Under "Done / tags", add: `- \`mismatch\`: the cube-dashboard skill found Cube
and Tableau disagree at some grain. sync.py sets it from
~/asana-sync/validation/latest.json and never auto-ticks a tagged row. Done rows
stay done but carry the tag until a passing run clears it.`

- [ ] **Step 4: Hand off.** Ask the user to run the preview
      (`uv run --with requests python ~/asana-sync/sync.py`) and check that the
      `would: ... add 'mismatch'` lines match the pilot's failing rows. They run
      `--apply` themselves.
