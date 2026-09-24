# Cube Sandbox Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Cube Cloud deployment that answers real queries against a
fabricated warehouse, so MasterBorn can develop a kit against KTAF's semantic
layer without ever holding a credential that reads real data.

**Architecture:** A committed schema snapshot is the only thing read from
production. Everything downstream — the coverage manifest, the fabricated data,
the checks — derives from committed files, so most of the toolchain runs in CI
with no cloud access. A single pinned revision covers the model, the snapshot
and the catalog together.

**Tech Stack:** Python 3.13, `google-cloud-bigquery`, `fastavro`, `pyyaml`,
pytest. Cube 1.7.x. BigQuery. Dagster for the production-side refresh.

**Spec:**
[docs/superpowers/specs/2026-09-11-cube-sandbox-build-design.md](../specs/2026-09-11-cube-sandbox-build-design.md)

## Global Constraints

- **Python `>=3.13`**, matching the repo's existing scripts.
- **The toolchain lives in `src/teamster/cube_sandbox/`**, a package, because
  several modules share the model-introspection code and the refresh step
  becomes a Dagster asset. Entry points run as
  `uv run python -m teamster.cube_sandbox.<module>`.
- **Never `cat` a file under `src/cube/`** — use the Read tool. Those paths
  carry rules that load on a path match.
- **No production data read, ever.** Only `INFORMATION_SCHEMA`. If a task needs
  a value, it comes from `access.js`, the cube YAML, or `personas.yml`.
- **Every count is asserted, never hard-coded.** The table count has already
  moved from 20 to 21 and the column count from 230 to 243.
- **Fabricated addresses use a domain under `.invalid`.** RFC 2606 guarantees it
  never resolves.
- **`uv run` everything.** Never bare `python` or `pytest`.
- **Before pushing markdown, SQL or YAML:**
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.

## Review Focus

Five failure modes the spec implies but no task's happy path exercises. Each
line's test is added to the task that owns the code.

1. **A cube YAML references a column absent from the snapshot.** The CI check
   must fail with the column named, not raise a `KeyError`. Task 9.
2. **A table in the union generates zero rows.** Coverage must fail, not pass
   vacuously because no cell was ever evaluated. Task 8.
3. **An Avro logical type does not match the declared BigQuery type.** The load
   must fail loudly rather than letting BigQuery coerce it. Task 10.
4. **`personas.yml` declares a scope value `access.js` does not handle.** The
   manifest must reject it, because a persona nothing branches on tests nothing.
   Task 4.
5. **The spine cycle leaves every homeroom key null.** Coverage must catch a
   wholly-null column where the manifest wanted a mix. Task 5.

---

## Status — updated 2026-09-24

**Resuming? Read this section, then the execution order below, then start at the
first task not marked complete.** Trust this block and `git log` over any
recollection. The SDD ledger under `.superpowers/` carries more detail but is
gitignored, so it may not exist in your checkout.

| Task  | State                  | Commits             |
| ----- | ---------------------- | ------------------- |
| 1     | Complete, review clean | `82c68d9..3c080e0`  |
| 2     | Complete, review clean | `3c080e0..e5eadca`  |
| 3     | Complete, review clean | `e5eadca..09272d8`  |
| 7     | Complete, review clean | `09272d8..7d76082`  |
| 10    | Complete, review clean | `7d76082..84f7dd8`  |
| 4     | Complete, review clean | `84f7dd8..ad3de7e5` |
| 5     | Complete               | `ad3de7e5..2a12dc9` |
| 6     | Complete               | `2a12dc9..a723c57`  |
| 8     | Complete               | `a723c57..de23dd7`  |
| 9     | Complete               | `de23dd7..aef1b79`  |
| 11–15 | Complete, not run live | `bf0f8b8..f4f2db7`  |
| 16    | Complete               | `f4f2db7..740c09b`  |

Every task in the plan is implemented. Two follow-up commits sit between them,
both from the Task 4 review: `f2815bd1` narrows the key and policy exemptions,
and `4790bc4f` adds the join-path orphan cells the spec requires and `build()`
never emitted.

### Whole-branch review and two fix waves — 2026-09-24

The final review found 3 Critical, 6 Important and 3 Minor, and judged all six
of the overnight run's rulings correct. Everything it raised is closed.

**Wave A — `1876473..b48232e`.** Three Criticals, all the same failure class: a
check that passes without verifying. `exit_code` failed on the 8 cells
row-counting cannot score, so the generator's only gate was permanently red.
`referenced_columns` read only cube YAML, so `dim_staff_reporting_chain` had
**zero** cells — an empty table passed coverage in full — and
`dim_staff_cube_access` covered 4 of 15 columns, missing `google_email`, the key
`resolveAccess` matches. Also: an unsatisfiable `is_current_homeroom` null cell,
no assertion of the spec's two-distinct-values rule for the sensitive tiers, a
staleness check its own workflow never triggered, ~30 tests outside CI, a
`/meta` diff blind to retypes.

**Wave B — `66ce187..6b4342a`.** The pipeline had parts and no way to run. Added
`generate()`, a `coverage` entry point reading real Avro, and entry points for
divergence, mutation and `/meta`. **BigQuery ignores a load job's schema for
AVRO** — confirmed against Google's documentation — so the spec's
explicit-schema guarantee was not happening. `load.py` now creates the table
from `bq_schema` first, loads with `WRITE_TRUNCATE_DATA` + `CREATE_NEVER`, and
`assert_complete` compares types as well as names.

**Verified independently on 2026-09-24**, not taken from a subagent report: a
`tiny` generate from scratch, scored against the committed manifest, gives **421
covered, 0 uncovered, 8 unproven** — 21 Avro files, 8,320 rows. 219 tests pass.
Coverage against an empty directory exits 1, so it cannot pass vacuously.

**Still not done:** nothing has ever been loaded and no query has been served
from the sandbox dataset. `WRITE_TRUNCATE_DATA` is documented but unexercised
live. The `full` profile has never been generated or timed.
`cube-catalog-meta.json` is still absent from `main`. Mutation testing perturbs
the model only — a persona-scope perturbation needs a regenerate, reload and
midnight-ET cache expiry.

**Gotcha when running it by hand:** `generate --out DIR` writes to
`DIR/<scale>/`, while `coverage --avro-dir` wants the directory holding the
Avro. Pass `build/cube_sandbox/tiny`, not `build/cube_sandbox`. The runbook in
`docs/reference/cube-sandbox.md` has it right.

**Decisions taken during execution that the task text does not carry:**

- Task 1's `scope_values` returns `{region, school, network}` for
  `student_location_scope` as a documented literal. The regex in the task text
  returns an empty set against the real `access.js`.
- Task 1's `policy_columns` recurses into nested `or`/`and` filter blocks.
  Without it `job_function_level` is missed and the
  `reporting_chain_or_below_rank` persona silently resolves to nothing.
- Task 1's `scope_values["staff_pii_scope"]` is bounded to the
  `switch (row.staff_pii_scope)` body. The bare `case` regex in the task text
  sweeps five spurious labels from unrelated switches.
- Task 3 has a sixth persona, `shaquille.oneal@ktaf-sandbox.invalid`, with
  `reporting_chain` and an empty chain. It exercises the no-group default-deny
  path that exists because Cube errors on an `equals []` row filter.
- Task 4's `dbt_not_null` matches the test name exactly. A substring match also
  catches `not_null_proportion`, which asserts a proportion rather than absence.
- Task 7 implements all three of `avro_schema`, `bq_schema` and `write`. The
  task's numbered steps cover only the first; Task 10 calls the other two.
- Task 4's key exemption is `model.key_columns`, derived from
  `primary_key: true` dimensions and the operands of an EQUALITY in a join's
  `sql:`. Not every column named in a predicate: a bare boolean term
  (`is_current_homeroom`) and a `BETWEEN` range bound (`effective_start_date`)
  are ordinary attributes, and exempting them repeats the over-exemption the
  name-suffix rule was deleted for.
- Task 4's `policy_columns` returns `(table, column)`, resolved through each
  view's `includes:` blocks and its `prefix:` rule. As bare names, `staff_key`
  exempted that column on three unrelated tables and `locations_abbreviation`
  matched no warehouse column at all.
- Task 4 emits the spec's "one orphan on each side of every join path" cells,
  which the task text omits. 24 paths, 48 cells. Without them nothing requires
  an unmatched key, and `location_key` / `work_location_key` are documented NULL
  in production.
- Task 5 breaks the spine cycle at HEAD → TAIL, not TAIL → HEAD as the task's
  Step 3 code does. The plan contradicts itself here: its own Step 1 test
  asserts `dim_student_enrollments` comes first, and that test is right. The
  homeroom join is declared from the enrollment side but its foreign key lives
  on the section table.
- Task 5's `resolve_spine` fills `is_current_homeroom` on the SECTION rows.
  There is no `homeroom_section_key` on `dim_student_enrollments` — that column
  does not exist in the pinned snapshot, and the relationship runs the other
  way.
- Task 5's `_PRODUCTION_ROWS` carries the spec's 2026-09-24 figures unverified.
  Re-measuring needs a production `INFORMATION_SCHEMA` read.
- Task 9 required fixing `referenced_columns`: sweeping every bare identifier
  out of a member's `sql:` attributed measure names and cube names to tables as
  columns, so the check reported 30 phantom missing columns and could never
  pass. `member_columns` now resolves `{CUBE}.col`, `{member}` and
  `{other_cube.member}` separately.
- Task 9 also asserts the committed `coverage_manifest.yml` matches a fresh
  `build()`. A drifted generated file makes every later coverage result an
  assertion against a stale contract.
- Task 12's `BLOCKED` matches the real SQL API denial shape, not a bare "not
  found", and `load_canaries` refuses a BLOCKED-only file — every view reports
  "not found" for everyone against an empty compiled schema.
- Task 13's `divergences.yml` carries all three cells including
  `attendance_view_weighting`, which the task text omits.

### If you are a scheduled cloud agent

You have **no Google Cloud credentials and no sandbox service-account key**.
Never authenticate to GCP, never run a live load, and never run the snapshot
refresh — the snapshot is already committed at
`src/cube/sandbox/schema_snapshot.json`. Tasks 4, 5, 6, 8 and 9 need only
committed files, so all of them are yours to do.

**Task 11 copies a script from `.claude/scratch/`, which is gitignored and
absent from your clone.** Write `scripts/cube_sandbox_isolation.py` fresh from
the spec's Piece 1 section instead. It must run the positive leg first and skip
the negative leg when the positive fails, tell a real permission denial from a
missing table, and refuse to impersonate from production credentials.

**Task 10's `main` and Task 11's scripts cannot be run here**, only written and
unit-tested against fakes. Say so plainly in your report rather than implying a
live run happened.

Run everything with `uv run`. Push after each task. Leave this Status section
updated for whoever picks it up next, and end with a list of every ruling you
made and what it costs if wrong.

**Two Minors deferred for the final review to triage:** both were real, and both
are closed in `bf0f8b8d`. Task 7's NUMERIC precision/scale is now asserted
whole, with the two numbers as named constants. Task 10's B608 suppression now
cites an identifier guard rather than the caller's good intentions.

### Two things a cloud agent cannot do, discovered 2026-09-24

- **`uv run` cannot sync this project in the cloud container.** `dbt-core` pulls
  `dbt-core-experimental-parser`, whose build backend downloads a wheel from
  GitHub with `urllib`. Python 3.13 enables `ssl.VERIFY_X509_STRICT` by default
  and the agent proxy's CA carries no `keyUsage` extension, so the build fails
  TLS verification where Python 3.11 succeeds. Tests were run with
  `PYTHONPATH=src uv run --no-project --python 3.13 --with pytest --with pyyaml --with fastavro --with google-cloud-bigquery --with 'psycopg[binary]' python -m pytest`.
  Dependency versions there are not the lockfile's.
- **`trunk` is unavailable**: no `.trunk/tools/`, not on `PATH`, and
  `get.trunk.io` is refused by the egress policy (403). Linting was done with
  the underlying tools at the versions `.trunk/trunk.yaml` pins — `ruff 0.16.8`
  (check and format), `prettier 3.9.8`, `markdownlint-cli2` against a copy of
  the repo's config, `yamllint 1.38.0`, `bandit 1.9.4`. Run `trunk check` before
  merging.

## Execution order

The task numbers below are stable — dependencies, reviews and the ledger all
reference them. **Execute in this order**, which front-loads the shortest path
to a queryable table:

| Order | Tasks          | Why                                                   |
| ----- | -------------- | ----------------------------------------------------- |
| 1st   | 1, 2, 3, 7, 10 | First load: `dim_staff_cube_access` becomes queryable |
| 2nd   | 4, 5, 6, 8, 9  | The contract and the full dataset                     |
| 3rd   | 11 – 16        | Checks, canaries, deploy                              |

**Why `dim_staff_cube_access` first.** Until it holds rows, `resolveAccess`
finds no match, every persona default-denies, and every query returns nothing.
It is also the one table the generator is not needed for — personas are
declared, so its rows come straight from `personas.yml`. Five tasks and roughly
six rows give MasterBorn something that authenticates.

That first load is not a pinned revision and is not covered by the manifest. It
is a smoke test, and nothing downstream should treat it as the sandbox being
built.

## Phase 1 — no cloud resources

Tasks 1 to 9 run in CI and on any laptop. None needs the sandbox project, a
credential, or a warehouse write.

### Task 1: Model introspection

Every later task needs to know which tables and columns the Cube model touches.
This is that module, and nothing else parses the model.

**Files:**

- Create: `src/teamster/cube_sandbox/__init__.py`
- Create: `src/teamster/cube_sandbox/model.py`
- Test: `tests/cube_sandbox/test_model.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `table_set(cube_root: Path) -> set[str]`,
  `referenced_columns(cube_root: Path) -> dict[str, set[str]]`,
  `policy_columns(cube_root: Path) -> set[str]`,
  `scope_values(access_js: Path) -> dict[str, set[str]]`.

- [ ] **Step 1: Write the failing test for the table set**

```python
# tests/cube_sandbox/test_model.py
from __future__ import annotations

from pathlib import Path

from teamster.cube_sandbox import model

CUBE_ROOT = Path(__file__).parents[2] / "src" / "cube"


def test_table_set_includes_the_cube_js_only_table() -> None:
    tables = model.table_set(CUBE_ROOT)
    # dim_staff_reporting_chain appears in no cube YAML; cube.js reads it
    # directly. Missing it fails identity resolution for reporting_chain
    # personas only, which is silent.
    assert "dim_staff_reporting_chain" in tables
    # Every entry is a bare table name, not a qualified path.
    assert all("." not in t for t in tables)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_model.py -v` Expected: FAIL with
`ModuleNotFoundError: No module named 'teamster.cube_sandbox'`

- [ ] **Step 3: Write the minimal implementation**

```python
# src/teamster/cube_sandbox/model.py
"""Parse the Cube model for the facts the sandbox toolchain needs.

Nothing else in this package parses `src/cube/`. The table set in particular
is the union of two sources, and using either alone is wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_SQL_TABLE = re.compile(r"sql_table:\s*(?:['\"])?kipptaf_marts\.(\w+)")
_CUBE_JS_REF = re.compile(r"`kipptaf_marts\.(\w+)`")


def table_set(cube_root: Path) -> set[str]:
    """Every kipptaf_marts table the model reads, from both sources."""
    tables: set[str] = set()
    for path in (cube_root / "model").rglob("*.yml"):
        tables |= set(_SQL_TABLE.findall(path.read_text()))
    tables |= set(_CUBE_JS_REF.findall((cube_root / "cube.js").read_text()))
    return tables
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_model.py -v` Expected: PASS

- [ ] **Step 5: Add the referenced-columns test**

```python
def test_referenced_columns_are_keyed_by_table() -> None:
    columns = model.referenced_columns(CUBE_ROOT)
    assert "dim_students" in columns
    assert columns["dim_students"], "a cube with dimensions yields columns"
    # Keys are a subset of the table set: a column cannot be referenced on a
    # table the model never reads.
    assert set(columns) <= model.table_set(CUBE_ROOT)
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_model.py -v` Expected: FAIL with
`AttributeError: module ... has no attribute 'referenced_columns'`

- [ ] **Step 7: Implement referenced columns**

```python
def referenced_columns(cube_root: Path) -> dict[str, set[str]]:
    """Columns each table must carry, from every cube's dimensions and measures.

    A dimension's `sql:` may be an expression, so take every bare identifier in
    it. Over-collecting is safe here: a column named that does not exist fails
    the Task 9 check loudly, which is the outcome we want.
    """
    out: dict[str, set[str]] = {}
    for path in (cube_root / "model" / "cubes").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []):
            table = str(cube.get("sql_table", "")).split(".")[-1]
            if not table:
                continue
            names: set[str] = set()
            for member in (*cube.get("dimensions", []), *cube.get("measures", [])):
                names |= set(re.findall(r"\b[a-z_][a-z0-9_]*\b", str(member.get("sql", ""))))
            out.setdefault(table, set()).update(names)
    return out
```

- [ ] **Step 8: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_model.py -v` Expected: PASS

- [ ] **Step 9: Add policy columns and scope values**

```python
def test_policy_columns_are_flat_names() -> None:
    cols = model.policy_columns(CUBE_ROOT)
    # row_level filters name a flat view member, never a cube-qualified path.
    assert cols and all("." not in c for c in cols)


def test_scope_values_come_from_access_js() -> None:
    values = model.scope_values(CUBE_ROOT / "access.js")
    assert "staff_pii_scope" in values
    assert "all_in_scope" in values["staff_pii_scope"]
    assert "none" not in values["staff_pii_scope"], "none is the absence of a group"
```

- [ ] **Step 10: Implement both**

```python
_SCOPE_CASE = re.compile(r"case\s+[\"'](\w+)[\"']")


def policy_columns(cube_root: Path) -> set[str]:
    """Every view member an access_policy row_level filter interpolates."""
    out: set[str] = set()
    for path in (cube_root / "model" / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            for policy in view.get("access_policy", []):
                for f in policy.get("row_level", {}).get("filters", []):
                    if member := f.get("member"):
                        out.add(str(member))
    return out


def scope_values(access_js: Path) -> dict[str, set[str]]:
    """Scope enum values the code branches on, by scope column.

    Sourced from access.js because production is a subset of the domain the
    code handles — several policy branches have no production row.
    """
    text = access_js.read_text()
    tiers = set(re.findall(r"scope:\s*[\"'](\w+_scope)[\"']", text))
    branched = set(_SCOPE_CASE.findall(text))
    out = {t: {"__non_none__"} for t in tiers}
    out["staff_pii_scope"] = branched - {"none"}
    out["student_location_scope"] = set(
        re.findall(r"student-\$\{row\.student_location_scope\}|[\"'](region|school|network)[\"']", text)
    ) - {""}
    return {k: v for k, v in out.items() if v}
```

- [ ] **Step 11: Run the full test file**

Run: `uv run pytest tests/cube_sandbox/test_model.py -v` Expected: PASS, 4 tests

- [ ] **Step 12: Commit**

```bash
git add src/teamster/cube_sandbox/ tests/cube_sandbox/
git commit -m "feat(cube): parse the Cube model for the sandbox toolchain"
```

---

### Task 2: Schema snapshot refresh

The only step that reads production. It writes what it read into the repo, so
everything downstream reads a committed file.

**Files:**

- Create: `src/teamster/cube_sandbox/snapshot.py`
- Create: `src/cube/sandbox/schema_snapshot.json` (generated, committed)
- Test: `tests/cube_sandbox/test_snapshot.py`

**Interfaces:**

- Consumes: `model.table_set`.
- Produces: `render(rows: list[dict]) -> dict`, `load(path: Path) -> dict`, and
  a `__main__` entry point. Snapshot shape:
  `{"tables": {"<table>": {"<column>": {"type": str, "nullable": bool}}}}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_snapshot.py
from __future__ import annotations

from teamster.cube_sandbox import snapshot


def test_render_is_sorted_and_stable() -> None:
    rows = [
        {"table_name": "dim_b", "column_name": "z", "data_type": "STRING", "is_nullable": "YES"},
        {"table_name": "dim_a", "column_name": "a", "data_type": "INT64", "is_nullable": "NO"},
    ]
    out = snapshot.render(rows)
    # Sorted output is what makes the committed diff readable, which is the
    # whole point of committing it.
    assert list(out["tables"]) == ["dim_a", "dim_b"]
    assert out["tables"]["dim_a"]["a"] == {"type": "INT64", "nullable": False}
    assert out["tables"]["dim_b"]["z"]["nullable"] is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_snapshot.py -v` Expected: FAIL with
`ImportError: cannot import name 'snapshot'`

- [ ] **Step 3: Implement render and load**

```python
# src/teamster/cube_sandbox/snapshot.py
"""Read production schema once, into a committed file.

This is the only module that touches production. Everything downstream reads
the committed snapshot at the pinned revision, so no build depends on what
production looks like right now.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path("src/cube/sandbox/schema_snapshot.json")


def render(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, dict[str, Any]] = {}
    for row in rows:
        tables.setdefault(row["table_name"], {})[row["column_name"]] = {
            "type": row["data_type"],
            "nullable": row["is_nullable"] == "YES",
        }
    return {"tables": {t: dict(sorted(c.items())) for t, c in sorted(tables.items())}}


def load(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_snapshot.py -v` Expected: PASS

- [ ] **Step 5: Add the entry point**

```python
def main() -> int:
    from google.cloud import bigquery

    from teamster.cube_sandbox import model

    tables = sorted(model.table_set(Path("src/cube")))
    client = bigquery.Client(project="teamster-332318")
    rows = [
        dict(r)
        for r in client.query(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM `teamster-332318.kipptaf_marts.INFORMATION_SCHEMA.COLUMNS` "
            "WHERE table_name IN UNNEST(@tables)",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("tables", "STRING", tables)
                ]
            ),
        ).result()
    ]
    out = render(rows)
    found = set(out["tables"])
    missing = set(tables) - found
    if missing:
        raise SystemExit(f"model references tables absent from production: {sorted(missing)}")
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {SNAPSHOT_PATH}: {len(found)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Generate the snapshot**

Run: `uv run python -m teamster.cube_sandbox.snapshot` Expected:
`wrote src/cube/sandbox/schema_snapshot.json: 21 tables`

- [ ] **Step 7: Commit**

```bash
git add src/teamster/cube_sandbox/snapshot.py tests/cube_sandbox/test_snapshot.py src/cube/sandbox/schema_snapshot.json
git commit -m "feat(cube): refresh the sandbox schema snapshot from production"
```

---

### Task 3: Persona declarations

Personas are declared, never generated. `canaries.yml` names them, so they must
survive a seed change.

**Files:**

- Create: `src/cube/sandbox/personas.yml`
- Create: `src/teamster/cube_sandbox/personas.py`
- Test: `tests/cube_sandbox/test_personas.py`

**Interfaces:**

- Consumes: `model.scope_values`.
- Produces: `load(path: Path) -> list[Persona]` where `Persona` is a dataclass
  with `email: str`, `given_name: str`, `surname: str`,
  `scopes: dict[str, str]`, `reportees: list[str]`, `purpose: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_personas.py
from __future__ import annotations

from pathlib import Path

from teamster.cube_sandbox import personas

PERSONAS = Path(__file__).parents[2] / "src" / "cube" / "sandbox" / "personas.yml"


def test_every_persona_uses_an_invalid_domain() -> None:
    for p in personas.load(PERSONAS):
        # RFC 2606 reserves .invalid, so no fabricated address can collide
        # with a real account or receive mail.
        assert p.email.endswith(".invalid"), p.email


def test_emails_are_ascii() -> None:
    for p in personas.load(PERSONAS):
        # google_email is the key resolveAccess matches exactly. A non-ASCII
        # address is a realistic-looking identity that resolves to nobody.
        assert p.email.isascii(), p.email
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_personas.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Write the declarations**

```yaml
# src/cube/sandbox/personas.yml
# Declared, not generated. canaries.yml references these by email, so they must
# survive a seed change and a generator refactor.
personas:
  - email: diana.taurasi@ktaf-sandbox.invalid
    given_name: Diana
    surname: Taurasi
    purpose: Network-wide student access, full staff PII remit.
    scopes:
      student_location_scope: network
      staff_pii_scope: all_in_scope
      staff_compensation_scope: all_in_scope
      staff_observations_scope: none
      staff_benefits_scope: all_in_scope
    reportees: []

  - email: ororo.munroe@ktaf-sandbox.invalid
    given_name: Ororo
    surname: Munroe
    purpose: School-scoped students; chain-scoped PII with a non-empty chain.
    scopes:
      student_location_scope: school
      staff_pii_scope: reporting_chain
      staff_compensation_scope: none
      staff_observations_scope: reporting_chain
      staff_benefits_scope: reporting_chain
    reportees:
      - zydrunas.ilgauskas@ktaf-sandbox.invalid

  - email: zydrunas.ilgauskas@ktaf-sandbox.invalid
    given_name: Žydrūnas
    surname: Ilgauskas
    purpose: Region-scoped students; teaching-staff PII. Empty chain.
    scopes:
      student_location_scope: region
      staff_pii_scope: teaching_staff
      staff_compensation_scope: none
      staff_observations_scope: none
      staff_benefits_scope: none
    reportees: []

  - email: aja.ogwumike@ktaf-sandbox.invalid
    given_name: A'ja
    surname: Ogwumike
    purpose: Default-deny on every axis. Resolves to a row with no groups.
    scopes:
      student_location_scope: none
      staff_pii_scope: none
      staff_compensation_scope: none
      staff_observations_scope: none
      staff_benefits_scope: none
    reportees: []

  - email: karl-anthony.maximoff@ktaf-sandbox.invalid
    given_name: Karl-Anthony
    surname: Maximoff
    purpose: Rank-scoped PII with both a remit and a chain.
    scopes:
      student_location_scope: network
      staff_pii_scope: reporting_chain_or_below_rank
      staff_compensation_scope: reporting_chain
      staff_observations_scope: all_in_scope
      staff_benefits_scope: none
    reportees:
      - aja.ogwumike@ktaf-sandbox.invalid
```

Note: `unresolvable@ktaf-sandbox.invalid` is deliberately **absent** from this
file. Task 4 asserts it has no `dim_staff_cube_access` row, which exercises
clean default-deny for an identity the warehouse has never heard of.

- [ ] **Step 4: Implement the loader**

```python
# src/teamster/cube_sandbox/personas.py
"""Load the declared persona set.

Personas are hand-written because canaries.yml names them. The manifest
asserts the declared set covers every scope value access.js handles, so this
file cannot quietly fall behind the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

UNRESOLVABLE = "unresolvable@ktaf-sandbox.invalid"


@dataclass(frozen=True)
class Persona:
    email: str
    given_name: str
    surname: str
    purpose: str
    scopes: dict[str, str]
    reportees: list[str] = field(default_factory=list)


def load(path: Path) -> list[Persona]:
    doc = yaml.safe_load(path.read_text()) or {}
    return [Persona(**p) for p in doc.get("personas", [])]
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/cube_sandbox/test_personas.py -v` Expected: PASS, 2
tests

- [ ] **Step 6: Commit**

```bash
git add src/cube/sandbox/personas.yml src/teamster/cube_sandbox/personas.py tests/cube_sandbox/test_personas.py
git commit -m "feat(cube): declare the sandbox persona set"
```

---

### Task 4: Coverage manifest

The generator's specification. Generated, so a new column or scope value becomes
a loud uncovered cell.

**Files:**

- Create: `src/teamster/cube_sandbox/manifest.py`
- Create: `src/cube/sandbox/coverage_manifest.yml` (generated, committed)
- Test: `tests/cube_sandbox/test_manifest.py`

**Interfaces:**

- Consumes: `snapshot.load`, `model.*`, `personas.load`.
- Produces:
  `build(snap, referenced, policy_columns, not_null, scopes, people) -> dict`
  shaped
  `{"cells": [{"kind": str, "table": str|None, "column": str|None, "detail": str, "status": "uncovered"}]}`,
  and `dbt_not_null(marts_root: Path) -> set[tuple[str, str]]`. Every parameter
  is passed by keyword in the tests, so the names are part of the interface.

- [ ] **Step 1: Write the failing test for null-cell exemptions**

```python
# tests/cube_sandbox/test_manifest.py
from __future__ import annotations

from teamster.cube_sandbox import manifest

SNAP = {"tables": {"dim_x": {
    "student_key": {"type": "STRING", "nullable": True},
    "nickname": {"type": "STRING", "nullable": True},
    "abbreviation": {"type": "STRING", "nullable": True},
}}}


def _null_columns(cells) -> set[str]:
    return {c["column"] for c in cells if c["kind"] == "null"}


def test_keys_and_policy_columns_are_exempt_from_the_null_rule() -> None:
    cells = manifest.build(
        snap=SNAP,
        referenced={"dim_x": {"student_key", "nickname", "abbreviation"}},
        policy_columns={"abbreviation"},
        not_null=set(),
        scopes={},
        people=[],
    )["cells"]
    # A null join key breaks the fixtures; a null policy column makes the
    # persona resolve to nothing.
    assert _null_columns(cells) == {"nickname"}


def test_dbt_not_null_columns_are_exempt() -> None:
    cells = manifest.build(
        snap=SNAP,
        referenced={"dim_x": {"nickname"}},
        policy_columns=set(),
        not_null={("dim_x", "nickname")},
        scopes={},
        people=[],
    )["cells"]
    # INFORMATION_SCHEMA reports every column NULLABLE, so dbt's not_null
    # tests carry the real contract.
    assert _null_columns(cells) == set()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_manifest.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement build**

```python
# src/teamster/cube_sandbox/manifest.py
"""Generate the coverage contract.

Hand-writing this list would let it go stale silently. Generating it turns a
new column, view or scope value into an uncovered cell instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from teamster.cube_sandbox.personas import Persona

_KEY_SUFFIXES = ("_key", "_id", "_identifier", "_number")


def _is_key(column: str) -> bool:
    return column.endswith(_KEY_SUFFIXES)


def build(
    snap: dict[str, Any],
    referenced: dict[str, set[str]],
    policy_columns: set[str],
    not_null: set[tuple[str, str]],
    scopes: dict[str, set[str]],
    people: list[Persona],
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []

    for table, columns in sorted(snap["tables"].items()):
        for column in sorted(columns):
            if column not in referenced.get(table, set()):
                continue
            cells.append({"kind": "non_null", "table": table, "column": column,
                          "detail": "at least one non-null row", "status": "uncovered"})
            exempt = (
                _is_key(column)
                or column in policy_columns
                or (table, column) in not_null
            )
            if not exempt:
                cells.append({"kind": "null", "table": table, "column": column,
                              "detail": "at least one null row", "status": "uncovered"})

    declared = {
        (name, value)
        for p in people
        for name, value in p.scopes.items()
        if value != "none"
    }
    for name, values in sorted(scopes.items()):
        for value in sorted(values):
            if value == "__non_none__":
                continue
            cells.append({"kind": "scope", "table": "dim_staff_cube_access",
                          "column": name, "detail": value, "status": "uncovered"})

    undeclared = {(n, v) for n, v in declared if v not in scopes.get(n, set())
                  and "__non_none__" not in scopes.get(n, set())}
    if undeclared:
        raise ValueError(
            f"personas.yml declares scope values access.js does not handle: {sorted(undeclared)}"
        )

    for state in ("hasRemit", "hasChain"):
        for value in ("true", "false"):
            cells.append({"kind": "derived", "table": None, "column": state,
                          "detail": value, "status": "uncovered"})

    cells.append({"kind": "identity", "table": None, "column": None,
                  "detail": "one email with no dim_staff_cube_access row",
                  "status": "uncovered"})

    for name in ("unpinned_cumulative", "attendance_view_weighting", "school_week_vs_iso"):
        cells.append({"kind": "divergence", "table": None, "column": None,
                      "detail": name, "status": "uncovered"})

    return {"cells": cells}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_manifest.py -v` Expected: PASS, 2
tests

- [ ] **Step 5: Add the Review Focus test — an undeclared scope value**

```python
from teamster.cube_sandbox.personas import Persona

import pytest


def test_persona_with_an_unhandled_scope_value_is_rejected() -> None:
    rogue = Persona(
        email="x@ktaf-sandbox.invalid", given_name="X", surname="Y",
        purpose="invalid", scopes={"staff_pii_scope": "made_up"}, reportees=[],
    )
    # A persona nothing branches on tests nothing, so the manifest must
    # refuse rather than emit a cell no policy can reach.
    with pytest.raises(ValueError, match="access.js does not handle"):
        manifest.build(
            snap={"tables": {}}, referenced={}, policy_columns=set(),
            not_null=set(), scopes={"staff_pii_scope": {"all_in_scope"}},
            people=[rogue],
        )
```

- [ ] **Step 6: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_manifest.py -v` Expected: PASS, 3
tests

- [ ] **Step 7: Add the dbt not_null reader and the entry point**

```python
def dbt_not_null(marts_root: Path) -> set[tuple[str, str]]:
    """Columns dbt asserts are never null, as (table, column).

    INFORMATION_SCHEMA reports every kipptaf_marts column NULLABLE, so it
    exempts nothing. These tests carry the real contract, and they are
    committed, so reading them needs no production access.
    """
    out: set[tuple[str, str]] = set()
    for path in marts_root.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for m in doc.get("models", []):
            for col in m.get("columns", []):
                tests = col.get("data_tests", col.get("tests", []))
                if any("not_null" in str(t) for t in tests):
                    out.add((m["name"], col["name"]))
    return out
```

- [ ] **Step 8: Generate and commit the manifest**

Run: `uv run python -m teamster.cube_sandbox.manifest` Expected: a written path
and a cell count

```bash
git add src/teamster/cube_sandbox/manifest.py tests/cube_sandbox/test_manifest.py src/cube/sandbox/coverage_manifest.yml
git commit -m "feat(cube): generate the sandbox coverage manifest"
```

---

### Task 5: Generator — order, the spine cycle, foreign keys

**Files:**

- Create: `src/teamster/cube_sandbox/generate.py`
- Test: `tests/cube_sandbox/test_generate.py`

**Interfaces:**

- Consumes: `snapshot.load`, `model.table_set`, `personas.load`.
- Produces: `generation_order(tables, edges) -> list[str]`,
  `generate(snap, people, scale, seed) -> dict[str, list[dict]]`.

- [ ] **Step 1: Write the failing test for ordering**

```python
# tests/cube_sandbox/test_generate.py
from __future__ import annotations

import pytest

from teamster.cube_sandbox import generate


def test_dependencies_are_generated_first() -> None:
    order = generate.generation_order(
        tables={"fct_a", "dim_b", "dim_c"},
        edges={("fct_a", "dim_b"), ("dim_b", "dim_c")},
    )
    assert order.index("dim_c") < order.index("dim_b") < order.index("fct_a")


def test_the_spine_cycle_is_reported_not_raised() -> None:
    # dim_student_enrollments and dim_student_section_enrollments reference
    # each other. No order satisfies both, so the cycle is broken deliberately
    # in three passes rather than treated as an error.
    order = generate.generation_order(
        tables={"dim_student_enrollments", "dim_student_section_enrollments"},
        edges={
            ("dim_student_enrollments", "dim_student_section_enrollments"),
            ("dim_student_section_enrollments", "dim_student_enrollments"),
        },
    )
    assert set(order) == {"dim_student_enrollments", "dim_student_section_enrollments"}
    assert order[0] == "dim_student_enrollments"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_generate.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement ordering**

```python
# src/teamster/cube_sandbox/generate.py
"""Fabricate the sandbox dataset.

Facts never invent a key: every foreign key is sampled from rows already
generated, which makes referential integrity hold by construction rather than
by a check afterwards.
"""

from __future__ import annotations

import random
from typing import Any

SPINE_HEAD = "dim_student_enrollments"
SPINE_TAIL = "dim_student_section_enrollments"


def generation_order(tables: set[str], edges: set[tuple[str, str]]) -> list[str]:
    """Topological order, with the spine cycle broken at a known edge."""
    edges = {(a, b) for a, b in edges if not (a == SPINE_TAIL and b == SPINE_HEAD)}
    remaining, order = set(tables), []
    while remaining:
        ready = sorted(
            t for t in remaining
            if not any(a == t and b in remaining for a, b in edges)
        )
        if not ready:
            raise ValueError(f"unbroken dependency cycle among {sorted(remaining)}")
        order.extend(ready)
        remaining -= set(ready)
    return order
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_generate.py -v` Expected: PASS, 2
tests

- [ ] **Step 5: Add the Review Focus test — a wholly-null spine column**

```python
def test_homeroom_keys_are_a_mix_not_all_null() -> None:
    rows = generate.resolve_spine(
        enrollments=[{"enrollment_key": f"e{i}", "homeroom_section_key": None} for i in range(20)],
        sections=[{"section_key": f"s{i}"} for i in range(5)],
        rng=random.Random(0),
    )
    keys = [r["homeroom_section_key"] for r in rows]
    # A deliberate slice stays null; all-null would mean the second pass never
    # ran, which loads cleanly and fails at query time.
    assert any(k is None for k in keys), "the null slice is a required cell"
    assert any(k is not None for k in keys), "all-null means the cycle never closed"
```

- [ ] **Step 6: Implement the spine resolution**

```python
def resolve_spine(
    enrollments: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    rng: random.Random,
    null_share: float = 0.05,
) -> list[dict[str, Any]]:
    """Third pass of the cycle: fill homeroom keys from the sections written.

    Leaving a slice null is one of the manifest's required cells, not
    sloppiness.
    """
    keys = [s["section_key"] for s in sections]
    for row in enrollments:
        row["homeroom_section_key"] = None if rng.random() < null_share else rng.choice(keys)
    return enrollments
```

- [ ] **Step 7: Add the scale-profile test**

```python
def test_tiny_and_full_differ_only_in_row_count() -> None:
    tiny = generate.row_target("dim_students", scale="tiny")
    full = generate.row_target("dim_students", scale="full")
    # Same generator, same seed, same manifest coverage. Only the multiplier
    # differs, so a tiny run that satisfies the manifest proves the generator
    # correct without waiting on a full build.
    assert tiny < full
    assert tiny >= generate.MANIFEST_FLOOR


def test_dim_dates_is_bounded_in_both_profiles() -> None:
    # Production's calendar spine runs to the year 9999, and an unbounded date
    # dimension is what drove the partitioned pre-aggregation incident (#4460).
    for scale in ("tiny", "full"):
        assert generate.row_target("dim_dates", scale=scale) <= generate.DATE_SPINE_MAX
```

- [ ] **Step 8: Implement the profiles**

```python
MANIFEST_FLOOR = 50
DATE_SPINE_MAX = 20 * 366  # the real academic-year range, never to year 9999

_PRODUCTION_ROWS = {
    "fct_student_attendance_enrollment_daily": 29_791_485,
    "fct_assessment_scores_enrollment_scoped": 15_080_518,
    "fct_student_attendance_enrollment_periods": 4_402_039,
    "dim_students": 31_297,
    "dim_staff_work_history": 30_116,
    "dim_staff_reporting_chain": 9_310,
}


def row_target(table: str, scale: str) -> int:
    """Rows to generate for one table under a named profile."""
    if table == "dim_dates":
        return DATE_SPINE_MAX
    if scale == "tiny":
        return MANIFEST_FLOOR
    if scale == "full":
        return _PRODUCTION_ROWS.get(table, MANIFEST_FLOOR * 100)
    raise ValueError(f"unknown scale {scale!r}")
```

Re-measure `_PRODUCTION_ROWS` rather than trusting it. These counts have already
moved once — the daily attendance fact was 12.6M in an earlier draft.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest tests/cube_sandbox/test_generate.py -v` Expected: PASS, 5
tests

- [ ] **Step 10: Commit**

```bash
git add src/teamster/cube_sandbox/generate.py tests/cube_sandbox/test_generate.py
git commit -m "feat(cube): order sandbox generation and close the spine cycle"
```

---

### Task 6: Generator — invented values

**Files:**

- Modify: `src/teamster/cube_sandbox/generate.py`
- Create: `src/cube/sandbox/reserved_names.yml` (restore from `aaa57b7222`)
- Test: `tests/cube_sandbox/test_values.py`

**Interfaces:**

- Consumes: `reserved_names.yml`.
- Produces: `fabricate_name(rng) -> tuple[str, str]`,
  `birth_date_for_grade(grade, academic_year, rng) -> date`,
  `to_ascii_email(given, surname) -> str`.

- [ ] **Step 1: Restore the reserved names file**

```bash
git show aaa57b7222:src/cube/sandbox/reserved_names.yml > src/cube/sandbox/reserved_names.yml
```

The names are already written and reviewed once. Re-inventing 40 surnames would
produce a different list with no more authority.

- [ ] **Step 2: Write the failing tests**

```python
# tests/cube_sandbox/test_values.py
from __future__ import annotations

import datetime as dt
import random

from teamster.cube_sandbox import generate


def test_emails_fold_to_ascii() -> None:
    # google_email is matched exactly by resolveAccess, and a non-ASCII local
    # part needs SMTPUTF8 and is not what any real directory holds.
    email = generate.to_ascii_email("Ororo", "Munroe")
    assert email.isascii()
    assert email.endswith("@ktaf-sandbox.invalid")


def test_birth_date_follows_grade() -> None:
    # A 3rd grader born in 1998 breaks every age calculation downstream.
    born = generate.birth_date_for_grade(3, 2026, random.Random(0))
    age = 2026 - born.year
    assert 7 <= age <= 11, f"implausible age {age} for grade 3"


def test_surnames_come_from_the_reserved_set() -> None:
    rng = random.Random(0)
    _, surname = generate.fabricate_name(rng)
    assert surname in generate.reserved_surnames()
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/cube_sandbox/test_values.py -v` Expected: FAIL with
`AttributeError`

- [ ] **Step 4: Implement the value rules**

```python
import datetime as dt
import unicodedata
from functools import cache
from pathlib import Path

import yaml

SANDBOX_DOMAIN = "ktaf-sandbox.invalid"
NAMES_PATH = Path("src/cube/sandbox/reserved_names.yml")


@cache
def _names() -> dict[str, list[str]]:
    return yaml.safe_load(NAMES_PATH.read_text())


def reserved_surnames() -> list[str]:
    return _names()["surnames"]


def fabricate_name(rng: random.Random) -> tuple[str, str]:
    """A realistic given name beside a coined surname.

    The surname carries the proof: nothing else uses these words, so the
    appearance of the name identifies the row as synthetic.
    """
    given = rng.choice([g["name"] if isinstance(g, dict) else g for g in _names()["given_names"]])
    return given, rng.choice(reserved_surnames())


def to_ascii_email(given: str, surname: str) -> str:
    def fold(part: str) -> str:
        decomposed = unicodedata.normalize("NFKD", part)
        return "".join(c for c in decomposed if c.isascii() and (c.isalnum())).lower()

    return f"{fold(given)}.{fold(surname)}@{SANDBOX_DOMAIN}"


def birth_date_for_grade(grade: int, academic_year: int, rng: random.Random) -> dt.date:
    """Grade first, then a birth date inside that grade's plausible window.

    A deliberate minority falls off-cohort — retained, accelerated, late entry
    — because those students are real and are what a kit gets wrong.
    """
    typical_age = grade + 5
    offset = rng.choices([0, -1, 1], weights=[85, 8, 7])[0]
    year = academic_year - typical_age - offset
    return dt.date(year, rng.randint(1, 12), rng.randint(1, 28))
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/cube_sandbox/test_values.py -v` Expected: PASS, 3
tests

- [ ] **Step 6: Commit**

```bash
git add src/cube/sandbox/reserved_names.yml src/teamster/cube_sandbox/generate.py tests/cube_sandbox/test_values.py
git commit -m "feat(cube): fabricate names, birth dates and addresses"
```

---

### Task 7: Avro output and explicit BigQuery schemas

**Files:**

- Create: `src/teamster/cube_sandbox/avro.py`
- Test: `tests/cube_sandbox/test_avro.py`

**Interfaces:**

- Consumes: `snapshot.load`.
- Produces: `avro_schema(table, columns) -> dict`,
  `bq_schema(table, columns) -> list[SchemaField]`,
  `write(path, schema, rows) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_avro.py
from __future__ import annotations

from teamster.cube_sandbox import avro


def test_nullable_columns_become_unions() -> None:
    schema = avro.avro_schema("dim_x", {"a": {"type": "STRING", "nullable": True}})
    field = schema["fields"][0]
    # Avro encodes null in the type, which is why this is not CSV: the
    # manifest's central assertion is about nulls.
    assert field["type"] == ["null", "string"]


def test_logical_types_map_exactly() -> None:
    schema = avro.avro_schema("dim_x", {
        "d": {"type": "DATE", "nullable": False},
        "t": {"type": "TIMESTAMP", "nullable": False},
        "n": {"type": "NUMERIC", "nullable": False},
    })
    by_name = {f["name"]: f["type"] for f in schema["fields"]}
    assert by_name["d"] == {"type": "int", "logicalType": "date"}
    assert by_name["t"] == {"type": "long", "logicalType": "timestamp-micros"}
    assert by_name["n"]["logicalType"] == "decimal"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/cube_sandbox/test_avro.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement the mapping**

```python
# src/teamster/cube_sandbox/avro.py
"""Avro output and the matching explicit BigQuery schema.

Creating the table from the snapshot rather than letting BigQuery infer types
from the Avro is what makes the two match by construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_LOGICAL: dict[str, Any] = {
    "STRING": "string",
    "INT64": "long",
    "FLOAT64": "double",
    "BOOL": "boolean",
    "DATE": {"type": "int", "logicalType": "date"},
    "DATETIME": {"type": "long", "logicalType": "timestamp-micros"},
    "TIMESTAMP": {"type": "long", "logicalType": "timestamp-micros"},
    "NUMERIC": {"type": "bytes", "logicalType": "decimal", "precision": 38, "scale": 9},
}


def avro_schema(table: str, columns: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = []
    for name, meta in columns.items():
        base = _LOGICAL.get(meta["type"])
        if base is None:
            raise ValueError(f"{table}.{name}: no Avro mapping for {meta['type']}")
        fields.append({"name": name, "type": ["null", base] if meta["nullable"] else base})
    return {"type": "record", "name": table, "fields": fields}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/cube_sandbox/test_avro.py -v` Expected: PASS, 2 tests

- [ ] **Step 5: Add the Review Focus test — an unmappable type**

```python
import pytest


def test_an_unmapped_type_fails_loudly() -> None:
    # Letting this through would have BigQuery coerce at load time, and the
    # mismatch would surface as wrong data rather than a failed build.
    with pytest.raises(ValueError, match="no Avro mapping for GEOGRAPHY"):
        avro.avro_schema("dim_x", {"g": {"type": "GEOGRAPHY", "nullable": True}})
```

- [ ] **Step 6: Run it, then commit**

Run: `uv run pytest tests/cube_sandbox/test_avro.py -v` Expected: PASS, 3 tests

```bash
git add src/teamster/cube_sandbox/avro.py tests/cube_sandbox/test_avro.py
git commit -m "feat(cube): map the snapshot onto Avro and BigQuery schemas"
```

---

### Task 8: Coverage assertion

**Files:**

- Create: `src/teamster/cube_sandbox/coverage.py`
- Test: `tests/cube_sandbox/test_coverage.py`

**Interfaces:**

- Consumes: the manifest, generated rows.
- Produces: `assess(manifest, tables) -> list[dict]` returning cells with
  `observed` counts, and a non-zero exit on any zero.

- [ ] **Step 1: Write the failing tests**

```python
# tests/cube_sandbox/test_coverage.py
from __future__ import annotations

from teamster.cube_sandbox import coverage

MANIFEST = {"cells": [
    {"kind": "null", "table": "dim_x", "column": "a", "detail": "", "status": "uncovered"},
    {"kind": "non_null", "table": "dim_x", "column": "a", "detail": "", "status": "uncovered"},
]}


def test_a_covered_cell_reports_its_count() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": None}, {"a": "v"}]})
    assert all(c["observed"] > 0 for c in result)


def test_an_empty_table_fails_rather_than_passing_vacuously() -> None:
    # Zero rows means no cell was ever evaluated. Reporting that as covered is
    # the silent failure the manifest exists to prevent.
    result = coverage.assess(MANIFEST, {"dim_x": []})
    assert all(c["observed"] == 0 for c in result)
    assert coverage.exit_code(result) == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/cube_sandbox/test_coverage.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement**

```python
# src/teamster/cube_sandbox/coverage.py
"""Assert the generated rows satisfy the coverage contract."""

from __future__ import annotations

from typing import Any


def assess(manifest: dict[str, Any], tables: dict[str, list[dict]]) -> list[dict]:
    out = []
    for cell in manifest["cells"]:
        rows = tables.get(cell["table"], []) if cell["table"] else []
        column = cell["column"]
        if cell["kind"] == "null":
            observed = sum(1 for r in rows if r.get(column) is None)
        elif cell["kind"] == "non_null":
            observed = sum(1 for r in rows if r.get(column) is not None)
        else:
            observed = sum(1 for r in rows if str(r.get(column)) == cell["detail"])
        out.append({**cell, "observed": observed})
    return out


def exit_code(assessed: list[dict]) -> int:
    return 1 if any(c["observed"] == 0 for c in assessed) else 0
```

- [ ] **Step 4: Run the tests, then commit**

Run: `uv run pytest tests/cube_sandbox/test_coverage.py -v` Expected: PASS, 2
tests

```bash
git add src/teamster/cube_sandbox/coverage.py tests/cube_sandbox/test_coverage.py
git commit -m "feat(cube): assert generated rows against the coverage manifest"
```

---

### Task 9: The CI consistency check

**Files:**

- Create: `src/teamster/cube_sandbox/checks.py`
- Create: `.github/workflows/cube-sandbox-contract.yaml`
- Test: `tests/cube_sandbox/test_checks.py`

**Interfaces:**

- Consumes: `model.referenced_columns`, `snapshot.load`.
- Produces: `missing_columns(referenced, snap) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/cube_sandbox/test_checks.py
from __future__ import annotations

from teamster.cube_sandbox import checks

SNAP = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}


def test_a_consistent_pair_reports_nothing() -> None:
    assert checks.missing_columns({"dim_x": {"a"}}, SNAP) == []


def test_a_model_column_absent_from_the_snapshot_is_named() -> None:
    # The check compares model and snapshot at the SAME commit, so this is
    # what a model change outrunning the snapshot looks like.
    missing = checks.missing_columns({"dim_x": {"a", "b"}}, SNAP)
    assert missing == ["dim_x.b"]


def test_a_model_table_absent_from_the_snapshot_does_not_raise() -> None:
    # A KeyError here would report a crash instead of the real problem.
    assert checks.missing_columns({"dim_y": {"z"}}, SNAP) == ["dim_y.z"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/cube_sandbox/test_checks.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement**

```python
# src/teamster/cube_sandbox/checks.py
"""Repo-level consistency, with no credentials and no warehouse read.

Comparing model and snapshot within one commit is what makes this work on a
refresh pull request: the snapshot was computed from the model as it stood
when the refresh ran, so a model change landing meanwhile would otherwise
merge a commit whose halves disagree.
"""

from __future__ import annotations

from typing import Any


def missing_columns(referenced: dict[str, set[str]], snap: dict[str, Any]) -> list[str]:
    tables = snap["tables"]
    return sorted(
        f"{table}.{column}"
        for table, columns in referenced.items()
        for column in columns
        if column not in tables.get(table, {})
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/cube_sandbox/test_checks.py -v` Expected: PASS, 3
tests

- [ ] **Step 5: Add the workflow**

```yaml
# .github/workflows/cube-sandbox-contract.yaml
name: cube sandbox contract

on:
  pull_request:
    paths:
      - src/cube/**
      - src/teamster/cube_sandbox/**

jobs:
  contract:
    if: github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
      - uses: astral-sh/setup-uv@d9e0f98d3fc6adb07d1e3d37f3043649ddad06a1 # v6.5.0
      - run: uv run python -m teamster.cube_sandbox.checks
      - run: uv run pytest tests/cube_sandbox -v
```

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .github/workflows/cube-sandbox-contract.yaml </dev/null
git add src/teamster/cube_sandbox/checks.py tests/cube_sandbox/test_checks.py .github/workflows/cube-sandbox-contract.yaml
git commit -m "feat(cube): gate the model and snapshot on every pull request"
```

---

## Phase 2 — needs the sandbox project

### Task 10: The load step

**Files:**

- Create: `src/teamster/cube_sandbox/load.py`
- Test: `tests/cube_sandbox/test_load.py`

**Interfaces:**

- Consumes: `avro.bq_schema`, generated Avro files.
- Produces: `loaded_columns(client, dataset) -> dict[str, set[str]]`,
  `assert_complete(snap, loaded) -> None`.

- [ ] **Step 1: Write the failing test for post-load completeness**

```python
# tests/cube_sandbox/test_load.py
from __future__ import annotations

import pytest

from teamster.cube_sandbox import load

SNAP = {"tables": {"dim_x": {"a": {"type": "STRING", "nullable": True}}}}


def test_a_complete_load_passes() -> None:
    load.assert_complete(SNAP, {"dim_x": {"a"}})


def test_a_partial_load_is_caught() -> None:
    # The generator writes table by table. A failure partway leaves the
    # sandbox short of the snapshot it was built from, and nothing else
    # notices.
    with pytest.raises(ValueError, match="dim_x.a"):
        load.assert_complete(SNAP, {"dim_x": set()})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/cube_sandbox/test_load.py -v` Expected: FAIL with
`ImportError`

- [ ] **Step 3: Implement**

```python
# src/teamster/cube_sandbox/load.py
"""Stage Avro to GCS and create native tables from the snapshot's schema."""

from __future__ import annotations

from typing import Any

SANDBOX_PROJECT = "teamster-cube-sandbox"
SANDBOX_DATASET = "kipptaf_marts"


def assert_complete(snap: dict[str, Any], loaded: dict[str, set[str]]) -> None:
    missing = sorted(
        f"{table}.{column}"
        for table, columns in snap["tables"].items()
        for column in columns
        if column not in loaded.get(table, set())
    )
    if missing:
        raise ValueError(f"load incomplete, sandbox is short of the snapshot: {missing}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/cube_sandbox/test_load.py -v` Expected: PASS, 2 tests

- [ ] **Step 5: Implement the load itself**

```python
def loaded_columns(client: Any, project: str, dataset: str) -> dict[str, set[str]]:
    rows = client.query(
        f"SELECT table_name, column_name "
        f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`"
    ).result()
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row.table_name, set()).add(row.column_name)
    return out


def load_table(client: Any, table: str, gcs_uri: str, schema: list[Any]) -> None:
    """Create the table from the snapshot's schema, then load the Avro.

    The explicit schema is what makes the deployed types match the snapshot by
    construction. Letting BigQuery infer them from the Avro would make it match
    by luck.
    """
    from google.cloud import bigquery

    client.load_table_from_uri(
        gcs_uri,
        f"{SANDBOX_PROJECT}.{SANDBOX_DATASET}.{table}",
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.AVRO,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=schema,
            use_avro_logical_types=True,
        ),
    ).result()


def main() -> int:
    from google.cloud import bigquery

    from teamster.cube_sandbox import avro, snapshot

    snap = snapshot.load()
    client = bigquery.Client(project=SANDBOX_PROJECT)
    for table, columns in snap["tables"].items():
        load_table(
            client,
            table,
            f"gs://{SANDBOX_PROJECT}-staging/{table}.avro",
            avro.bq_schema(table, columns),
        )
    assert_complete(snap, loaded_columns(client, SANDBOX_PROJECT, SANDBOX_DATASET))
    print(f"loaded {len(snap['tables'])} tables and verified against the snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`use_avro_logical_types=True` is load-bearing: without it BigQuery reads a
`date` logical type as an integer, and the column lands as `INT64` against a
snapshot that says `DATE`.

- [ ] **Step 6: Commit**

```bash
git add src/teamster/cube_sandbox/load.py tests/cube_sandbox/test_load.py
git commit -m "feat(cube): load the sandbox and assert it matches the snapshot"
```

---

### Task 11: The isolation checks

Two checks, because two identities. Promote
`.claude/scratch/cube-sandbox-isolation-test.py`, which already works.

**Files:**

- Create: `scripts/cube_sandbox_isolation.py`
- Create: `scripts/cube_sandbox_deny_policy.py`
- Test: `tests/scripts/test_cube_sandbox_isolation.py`

**Interfaces:**

- Produces: exit 0 on pass, 1 on fail, 2 on unproven.

- [ ] **Step 1: Promote the working script**

```bash
cp /workspaces/teamster/.claude/scratch/cube-sandbox-isolation-test.py scripts/cube_sandbox_isolation.py
```

It already runs the positive leg first, skips the negative leg when the positive
fails, tells a 403 from a 404, and refuses to impersonate from production
credentials. Keep all four behaviours.

- [ ] **Step 2: Write the verdict test**

```python
# tests/scripts/test_cube_sandbox_isolation.py
"""Tests for scripts/cube_sandbox_isolation.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_sandbox_isolation.py"


def _load():
    spec = importlib.util.spec_from_file_location("cube_sandbox_isolation", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_sandbox_isolation"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_module_loads() -> None:
    assert _load() is not None


def test_the_target_account_is_the_sandbox_one() -> None:
    mod = _load()
    assert mod.SERVICE_ACCOUNT.endswith("@teamster-cube-sandbox.iam.gserviceaccount.com")
    assert mod.PRODUCTION_TABLE.startswith("teamster-332318.")
```

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/scripts/test_cube_sandbox_isolation.py -v` Expected:
PASS, 2 tests

- [ ] **Step 4: Write the deny-policy check**

```python
# scripts/cube_sandbox_deny_policy.py
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "google-auth>=2.0",
#   "requests>=2.32",
# ]
# ///

"""Assert deny-sandbox-bigquery still exists on the production project.

Separate from the isolation test because it needs a different identity: this
one reads production IAM, that one acts as the sandbox service account. One
account holding both would be a step toward the cross-project binding the
design exists to prevent.
"""

from __future__ import annotations

import sys

import google.auth
from google.auth.transport.requests import AuthorizedSession

POLICY = "deny-sandbox-bigquery"
ATTACHMENT = "cloudresourcemanager.googleapis.com%2Fprojects%2Fteamster-332318"


def main() -> int:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    response = AuthorizedSession(credentials).get(
        f"https://iam.googleapis.com/v2/policies/{ATTACHMENT}/denypolicies"
    )
    if response.status_code == 403:
        print("UNPROVEN - this identity lacks denypolicies.list on teamster-332318")
        return 2
    names = [p.get("name", "") for p in response.json().get("policies", [])]
    if any(name.endswith(POLICY) for name in names):
        print(f"PASS - {POLICY} exists")
        return 0
    print(f"FAILED - {POLICY} not found. Isolation rests on the absence of a grant alone.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_sandbox_isolation.py scripts/cube_sandbox_deny_policy.py tests/scripts/test_cube_sandbox_isolation.py
git commit -m "feat(cube): promote the isolation test and add the deny-policy check"
```

---

### Task 12: Canary assertions

**Files:**

- Modify: `scripts/cube_rls_matrix.py`
- Create: `src/cube/sandbox/canaries.yml`
- Test: `tests/test_cube_rls_matrix.py`

**Interfaces:**

- Produces: `--expect <path>` flag, non-zero exit on any mismatch.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_cube_rls_matrix.py
def test_zero_rows_does_not_satisfy_blocked() -> None:
    mod = _load_script()
    # This one distinction is what forces production-mode sign-off: a dev-mode
    # runner returns zero rows where production denies, and treating that as a
    # pass reports a falsely benign matrix.
    assert not mod.expectation_met("BLOCKED", rows=[], error=None)
    assert mod.expectation_met("BLOCKED", rows=[], error="Table or CTE with name 'x' not found")
    assert mod.expectation_met("ZERO", rows=[], error=None)
    assert not mod.expectation_met("ZERO", rows=[("a",)], error=None)
    assert mod.expectation_met("ROWS", rows=[("a",)], error=None)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_cube_rls_matrix.py -v` Expected: FAIL with
`AttributeError: ... has no attribute 'expectation_met'`

- [ ] **Step 3: Implement**

```python
def expectation_met(expect: str, rows: list[tuple], error: str | None) -> bool:
    """Whether one viewer's result matches its declared expectation.

    BLOCKED asserts a real denial. A quiet zero rows is a FAILURE, not a pass.
    """
    match expect:
        case "BLOCKED":
            return error is not None and "not found" in error
        case "ZERO":
            return error is None and not rows
        case "ROWS":
            return error is None and bool(rows)
        case _:
            raise ValueError(f"unknown expectation {expect!r}")
```

- [ ] **Step 4: Write the canaries**

```yaml
# src/cube/sandbox/canaries.yml
# Both tiers run this file. KTAF CI owns it, because KTAF owns the marts and
# the access_policy blocks and must break first when a policy changes.
canaries:
  - persona: aja.ogwumike@ktaf-sandbox.invalid
    query_shape: SELECT count(*) FROM student_attendance_enrollment_daily_view
    expect: BLOCKED
    why: none on every axis emits no group, so the view default-denies.

  - persona: unresolvable@ktaf-sandbox.invalid
    query_shape: SELECT count(*) FROM student_attendance_enrollment_daily_view
    expect: BLOCKED
    why: no dim_staff_cube_access row at all resolves to an empty context.

  - persona: diana.taurasi@ktaf-sandbox.invalid
    query_shape: SELECT count(*) FROM student_attendance_enrollment_daily_view
    expect: ROWS
    why: network student scope sees every location.

  - persona: zydrunas.ilgauskas@ktaf-sandbox.invalid
    query_shape: SELECT count(*) FROM staff_pii
    expect: ROWS
    why: teaching_staff PII scope resolves against a non-empty remit.
```

- [ ] **Step 5: Run the tests, then commit**

Run: `uv run pytest tests/test_cube_rls_matrix.py -v` Expected: PASS

```bash
git add scripts/cube_rls_matrix.py src/cube/sandbox/canaries.yml tests/test_cube_rls_matrix.py
git commit -m "feat(cube): turn the RLS matrix into an assertion runner"
```

---

### Task 13: Divergence assertions

**Files:**

- Create: `src/cube/sandbox/divergences.yml`
- Create: `src/teamster/cube_sandbox/divergence.py`
- Test: `tests/cube_sandbox/test_divergence.py`

**Interfaces:**

- Produces: `diverges(a: float, b: float, min_ratio: float) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_divergence.py
from __future__ import annotations

from teamster.cube_sandbox import divergence


def test_convergence_is_a_failure() -> None:
    # If the pair converges, the fabricated data has lost the property that
    # makes the sandbox teach this lesson, and the suite must say so.
    assert not divergence.diverges(100.0, 101.0, min_ratio=0.10)
    assert divergence.diverges(100.0, 140.0, min_ratio=0.10)


def test_a_zero_denominator_does_not_divide() -> None:
    assert not divergence.diverges(0.0, 0.0, min_ratio=0.10)
```

- [ ] **Step 2: Run it to verify it fails, then implement**

```python
# src/teamster/cube_sandbox/divergence.py
"""Assert that queries a careless kit treats as equivalent are not.

Separate from canaries.yml: a canary going red means the access model broke,
this going red means KTAF's generator regressed. MasterBorn runs the canaries
as their gate and cannot fix this one.
"""

from __future__ import annotations


def diverges(a: float, b: float, min_ratio: float) -> bool:
    if not a and not b:
        return False
    return abs(a - b) / max(abs(a), abs(b)) >= min_ratio
```

- [ ] **Step 3: Write the declarations**

```yaml
# src/cube/sandbox/divergences.yml
divergences:
  - name: unpinned_cumulative
    min_ratio: 0.10
    why:
      Cumulative position is re-stamped daily, so an open range counts students
      who crossed on any day.
    a:
      SELECT count_chronically_absent FROM
      student_attendance_enrollment_daily_view WHERE attendance_date =
      '2026-03-02'
    b:
      SELECT count_chronically_absent FROM
      student_attendance_enrollment_daily_view WHERE attendance_date BETWEEN
      '2025-07-01' AND '2026-03-02'

  - name: school_week_vs_iso
    min_ratio: 0.05
    why:
      period_type week is the PowerSchool school week, and ISO bucketing
      compiles, does not throw, and returns a meaningless breakdown.
    a:
      SELECT count(*) FROM student_attendance_enrollment_periods_view WHERE
      period_type = 'week'
    b:
      SELECT count(*) FROM student_attendance_enrollment_daily_view GROUP BY
      DATE_TRUNC(attendance_date, ISOWEEK)
```

- [ ] **Step 4: Run and commit**

Run: `uv run pytest tests/cube_sandbox/test_divergence.py -v` Expected: PASS, 2
tests

```bash
git add src/cube/sandbox/divergences.yml src/teamster/cube_sandbox/divergence.py tests/cube_sandbox/test_divergence.py
git commit -m "feat(cube): assert the sandbox still teaches its divergences"
```

---

### Task 14: Mutation testing

**Files:**

- Create: `src/teamster/cube_sandbox/mutate.py`
- Test: `tests/cube_sandbox/test_mutate.py`

**Interfaces:**

- Produces: `uncaught_ratio(results: list[bool]) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_mutate.py
from __future__ import annotations

from teamster.cube_sandbox import mutate


def test_every_mutation_caught_is_zero_uncaught() -> None:
    assert mutate.uncaught_ratio([True, True, True]) == 0.0


def test_an_uncaught_mutation_is_reported() -> None:
    # A canary that would still pass with the policy deleted proves nothing.
    assert mutate.uncaught_ratio([True, False]) == 0.5
```

- [ ] **Step 2: Implement, run, commit**

```python
# src/teamster/cube_sandbox/mutate.py
"""Measure whether the canaries are load-bearing.

Perturb one access_policy block or one persona's scope value and require at
least one canary to flip red. This is the only honest measure of the suite.
"""

from __future__ import annotations


def uncaught_ratio(results: list[bool]) -> float:
    return 0.0 if not results else sum(1 for r in results if not r) / len(results)
```

```bash
git add src/teamster/cube_sandbox/mutate.py tests/cube_sandbox/test_mutate.py
git commit -m "feat(cube): report uncaught mutations against the canaries"
```

---

### Task 15: The `/meta` check

**Files:**

- Create: `src/teamster/cube_sandbox/meta_check.py`
- Test: `tests/cube_sandbox/test_meta_check.py`

**Interfaces:**

- Produces: `member_diff(live: dict, catalog: dict) -> dict[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cube_sandbox/test_meta_check.py
from __future__ import annotations

from teamster.cube_sandbox import meta_check

CATALOG = {"cubes": [{"name": "v", "measures": [{"name": "v.a"}], "dimensions": []}]}


def test_an_identical_deployment_diffs_empty() -> None:
    assert meta_check.member_diff(CATALOG, CATALOG) == {"added": [], "removed": []}


def test_a_missing_member_is_reported() -> None:
    # This proves the deployed model is the pinned model. It proves nothing
    # about the data: /meta is compiled from the model and never reads the
    # warehouse.
    live = {"cubes": [{"name": "v", "measures": [], "dimensions": []}]}
    assert meta_check.member_diff(live, CATALOG) == {"added": [], "removed": ["v.a"]}
```

- [ ] **Step 2: Implement, run, commit**

```python
# src/teamster/cube_sandbox/meta_check.py
"""Compare the deployed model against the catalog at the PINNED revision.

Comparing against the newest catalog on main would turn this red on every
production change, and a gate that cries wolf gets overridden.
"""

from __future__ import annotations

from typing import Any


def _members(doc: dict[str, Any]) -> set[str]:
    return {
        m["name"]
        for cube in doc.get("cubes", [])
        for key in ("measures", "dimensions")
        for m in cube.get(key, [])
    }


def member_diff(live: dict[str, Any], catalog: dict[str, Any]) -> dict[str, list[str]]:
    a, b = _members(live), _members(catalog)
    return {"added": sorted(a - b), "removed": sorted(b - a)}
```

```bash
git add src/teamster/cube_sandbox/meta_check.py tests/cube_sandbox/test_meta_check.py
git commit -m "feat(cube): check the deployed model against the pinned catalog"
```

---

### Task 16: Deploy mechanics and documentation

**Files:**

- Modify: `src/cube/CLAUDE.md`
- Create: `docs/reference/cube-sandbox.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Scope the no-manual-deploy rule to production**

Read `src/cube/CLAUDE.md` with the Read tool, then change:

> **No manual deploy command.** Production redeploys are triggered by merges to
> `main` in Cube Cloud; do not propose a deploy step.

to:

> **No manual deploy command on the production deployment.** Production
> redeploys are triggered by merges to `main` in Cube Cloud; do not propose a
> deploy step there. The sandbox deployment is the deliberate exception: it runs
> in CLI mode and deploys only when someone runs `npx cubejs-cli deploy` from a
> tagged checkout. See `docs/reference/cube-sandbox.md`.

A rule with a silent exception stops being followed.

- [ ] **Step 2: Write the reference page**

Cover: what the sandbox is, the two persona emulation paths, the bump procedure
in the spec's seven steps, and the reserved namespace. Name the reserved
surnames explicitly — a namespace nobody published is not reserved.

- [ ] **Step 3: Add the nav entry**

```yaml
# mkdocs.yml, under nav: Reference:
- Cube sandbox: reference/cube-sandbox.md
```

- [ ] **Step 4: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/reference/cube-sandbox.md mkdocs.yml src/cube/CLAUDE.md </dev/null
git add src/cube/CLAUDE.md docs/reference/cube-sandbox.md mkdocs.yml
git commit -m "docs(cube): publish the sandbox reference and scope the deploy rule"
```

---

## Blocked on someone else

Neither blocks Phase 1.

- **`iam.googleapis.com/denypolicies.list` on `teamster-332318`** for whatever
  identity runs Task 11's second check. Nothing on the analytics side holds it
  today.
- **`cube-catalog-meta.json` landing on `main`.** It exists only on
  `cristinabaldor/feat/claude-cube-api-key-access` and in scratch, and both
  copies predate the query-rewrite changes. Task 15 needs a current one.
