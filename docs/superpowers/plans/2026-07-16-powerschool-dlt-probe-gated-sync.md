# PowerSchool dlt probe-gated sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse kipppaterson's 48 per-table dlt PowerSchool assets into one
probe-gated `@dlt_assets` multi-asset that full-replaces only tables whose
`COUNT(*)`/`MAX(cursor)` signature drifted.

**Architecture:** One `@dlt.source` of 48 custom `@dlt.resource`s (gate inside
each resource, signature in `dlt.current.resource_state()`), one `dlt.pipeline`,
one `@dlt_assets`. Two schedules subset the multi-asset by tier. Spec:
`docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md`.

**Tech Stack:** dagster 1.13.13, dagster-dlt 0.29.13, dlt 1.28.1, SQLAlchemy +
oracledb (probe), BigQuery destination.

## Global Constraints

- Tracked in issue #3807; branch `cbini/feat/claude-powerschool-dlt-paterson`;
  ALL file edits target the worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson`
  (editing `/workspaces/teamster/<path>` silently dirties `main`).
- Every git command:
  `git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson ...`
  or run Bash with that cwd.
- Python via `uv run` only; execute from inside the worktree
  (`cd <worktree> && uv run ...`). Python ≥3.13 style: built-in generics,
  `X | None`, return-type annotations on library functions.
- Asset keys stay `kipppaterson/powerschool/{table}`; BQ dataset stays
  `dagster_kipppaterson_dlt_powerschool`; schedule names stay
  `kipppaterson__powerschool__dlt__intraday_asset_job_schedule` /
  `..__nightly_asset_job_schedule` (regenerated docs depend on names).
- `write_disposition="replace"` everywhere; no BigQuery `MERGE`; no
  partitioning.
- Commit messages: conventional commits, footer
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do not run `trunk fmt` manually; pre-commit formats. Suppress lint with
  `# trunk-ignore(linter/rule): reason` on the line immediately above.

---

### Task 1: Spike — verify dlt zero-yield + state-commit assumptions

The design assumes (a) a `replace` resource that yields zero rows produces no
load job and leaves the destination table untouched, and (b) whether a
state-only change commits without any data load. Verify locally against duckdb
before building anything. If (a) is FALSE (the table gets truncated), STOP — the
gate cannot live inside the resource and the design needs revision. (b) may be
either way: if state-only changes do NOT commit, the empty-table edge just
re-truncates each tick (idempotent, acceptable) — record the result.

**Files:**

- Create (throwaway, gitignored): `.claude/scratch/dlt_spike.py` under the
  worktree
- Modify:
  `docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md`
  (record spike results in the Spike section)

**Interfaces:** none (evidence only).

- [ ] **Step 1: Write the spike script**

```python
"""Spike: zero-yield replace semantics + state-only commit in dlt 1.28.1."""

import dlt


def build_source(rows: list[dict], state_marker: str | None):
    @dlt.resource(name="probe_target", write_disposition="replace")
    def probe_target():
        if state_marker is not None:
            dlt.current.resource_state()["signature"] = state_marker
        yield from rows

    @dlt.source(name="spike")
    def spike_source():
        yield probe_target

    return spike_source()


pipeline = dlt.pipeline(
    pipeline_name="spike_pipeline",
    destination="duckdb",
    dataset_name="spike",
    dev_mode=False,
)

# Run 1: load 3 rows, write state marker "v1"
info1 = pipeline.run(build_source([{"id": 1}, {"id": 2}, {"id": 3}], "v1"))
with pipeline.sql_client() as c:
    count1 = c.execute_sql("select count(*) from probe_target")[0][0]
print(f"run1 jobs={len(info1.load_packages[0].jobs['completed_jobs'])} rows={count1}")

# Run 2: yield NOTHING, no state change -> expect no load job, table untouched
info2 = pipeline.run(build_source([], None))
with pipeline.sql_client() as c:
    count2 = c.execute_sql("select count(*) from probe_target")[0][0]
packages2 = len(info2.load_packages)
print(f"run2 packages={packages2} rows_after={count2}")
assert count2 == 3, f"ZERO-YIELD TRUNCATED THE TABLE (rows={count2}) - design broken"

# Run 3: yield nothing but CHANGE state -> does state-only commit?
info3 = pipeline.run(build_source([], "v2"))
state3 = pipeline.state["sources"]["spike"]["resources"]["probe_target"]["signature"]
print(f"run3 packages={len(info3.load_packages)} state_after={state3}")

# Run 4: fresh pipeline instance (simulates new pod) - is "v2" restorable?
pipeline2 = dlt.pipeline(
    pipeline_name="spike_pipeline", destination="duckdb", dataset_name="spike"
)
pipeline2.sync_destination()
restored = (
    pipeline2.state.get("sources", {})
    .get("spike", {})
    .get("resources", {})
    .get("probe_target", {})
    .get("signature")
)
print(f"run4 restored_state={restored}")
print("SPIKE OK: zero-yield preserved table; state-only commit =", restored == "v2")
```

- [ ] **Step 2: Run the spike**

Run (from the worktree):
`uv run --with duckdb python .claude/scratch/dlt_spike.py`

Expected: `run2 rows_after=3` (assertion passes). Record whether
`restored_state` is `v2` (state-only commits) or `v1` (it doesn't).

- [ ] **Step 3: Record results in the spec**

Edit the spec's `## Spike` section: mark items 1-2 with results, e.g. append
`— verified 2026-07-16 (duckdb spike): zero-yield produces no load job and does not truncate; state-only changes do/do not commit (re-truncate each tick is acceptable if not).`
Item 3 (timing) stays open until Task 6.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md
git commit -m "docs(powerschool): record dlt spike results in spec"
```

---

### Task 2: Library — `PowerSchoolTable` + `probe_signature`

**Files:**

- Modify: `src/teamster/libraries/dlt/powerschool/assets.py` (add to top, keep
  existing content for now)
- Test: `tests/test_dlt_powerschool.py` (create)

**Interfaces:**

- Produces: `PowerSchoolTable(name: str, cursor_column: str | None)` frozen
  dataclass;
  `probe_signature(connection, table_name: str, cursor_column: str) -> dict[str, int | str | None]`
  returning `{"count": int, "max_cursor": str | None}` (ISO string, tz-naive).
  Task 3's resource compares this dict by equality against
  `dlt.current.resource_state()["signature"]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dlt_powerschool.py`:

```python
"""Unit tests for the probe-gated PowerSchool dlt factory (no external deps)."""

from datetime import datetime
from types import SimpleNamespace

from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
    probe_signature,
)


class FakeResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, clause):
        self.queries.append(str(clause))
        return FakeResult(self.row)


def test_probe_signature_shapes_datetime_cursor():
    conn = FakeConnection((42, datetime(2026, 7, 15, 13, 30, 0)))

    sig = probe_signature(conn, "students", "transaction_date")

    assert sig == {"count": 42, "max_cursor": "2026-07-15T13:30:00"}
    assert "COUNT(*)" in conn.queries[0]
    assert "MAX(transaction_date)" in conn.queries[0]
    assert "FROM students" in conn.queries[0]


def test_probe_signature_empty_table_none_cursor():
    conn = FakeConnection((0, None))

    sig = probe_signature(conn, "cc", "transaction_date")

    assert sig == {"count": 0, "max_cursor": None}


def test_powerschool_table_dataclass():
    t = PowerSchoolTable(name="students", cursor_column="transaction_date")
    n = PowerSchoolTable(name="test", cursor_column=None)

    assert t.cursor_column == "transaction_date"
    assert n.cursor_column is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && uv run pytest tests/test_dlt_powerschool.py -v` Expected:
FAIL — `ImportError: cannot import name 'PowerSchoolTable'`.

- [ ] **Step 3: Implement**

Add to `src/teamster/libraries/dlt/powerschool/assets.py` (below the existing
imports; add `from dataclasses import dataclass` and `import sqlalchemy as sa`
to the imports):

```python
@dataclass(frozen=True)
class PowerSchoolTable:
    """One PowerSchool table's sync config.

    cursor_column None means the table has no change-tracking column and is
    always fully replaced when selected (nightly tier only).
    """

    name: str
    cursor_column: str | None


def probe_signature(
    connection, table_name: str, cursor_column: str
) -> dict[str, int | str | None]:
    """Fetch the change signature for a table: total count + max cursor.

    Equality-compared against the stored signature; drift in either value
    (including a cursor regression) triggers a full replace. Values are
    JSON-serializable for dlt resource state.
    """
    count, max_cursor = connection.execute(
        # trunk-ignore(bandit/B608): table/column names from static YAML config
        sa.text(
            f"SELECT COUNT(*), MAX({cursor_column}) FROM {table_name}"  # noqa: S608
        )
    ).one()

    return {
        "count": count,
        "max_cursor": max_cursor.isoformat() if max_cursor is not None else None,
    }
```

(If trunk flags the `noqa`, drop it — the `trunk-ignore` line is the
authoritative suppression.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/test_dlt_powerschool.py -v` Expected:
3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/teamster/libraries/dlt/powerschool/assets.py tests/test_dlt_powerschool.py
git commit -m "feat(powerschool): add dlt probe signature helpers"
```

---

### Task 3: Library — gated source + single `@dlt_assets` factory

Replaces the per-table factory wholesale. The only caller is
`code_locations/kipppaterson/powerschool/sis/dlt/assets.py` (updated in Task 4 —
the tree will not import cleanly between Task 3 and Task 4 commits; that is
fine, they land in sequence).

**Files:**

- Modify: `src/teamster/libraries/dlt/powerschool/assets.py` (replace
  `LOAD_STRATEGIES` and `build_powerschool_dlt_assets`; keep `ORACLE_SCHEMA`,
  `oracle_number_adapter`, `_oracle_connection_url`,
  `PowerSchoolDagsterDltTranslator`, Task 2's additions)
- Test: `tests/test_dlt_powerschool.py` (extend)

**Interfaces:**

- Consumes: `PowerSchoolTable`, `probe_signature` (Task 2).
- Produces:
  `build_powerschool_dlt_assets(code_location: str, tables: list[PowerSchoolTable], op_tags: dict[str, object] | None = None) -> AssetsDefinition`
  — ONE multi-asset (`can_subset=True`) with keys
  `{code_location}/powerschool/{table.name}`, op name
  `{code_location}__powerschool`, pool `dlt_powerschool_{code_location}`,
  pipeline name `powerschool`, dataset
  `dagster_{code_location}_dlt_powerschool`. Task 4 calls it once with all 48
  tables.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dlt_powerschool.py`:

```python
from teamster.libraries.dlt.powerschool.assets import build_powerschool_dlt_assets


def test_factory_builds_single_subsettable_multiasset():
    tables = [
        PowerSchoolTable(name="students", cursor_column="transaction_date"),
        PowerSchoolTable(name="users", cursor_column="whenmodified"),
        PowerSchoolTable(name="test", cursor_column=None),
    ]

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", tables=tables
    )

    assert {k.to_user_string() for k in assets_def.keys} == {
        "kipppaterson/powerschool/students",
        "kipppaterson/powerschool/users",
        "kipppaterson/powerschool/test",
    }
    assert assets_def.can_subset is True
    assert assets_def.op.name == "kipppaterson__powerschool"
    assert assets_def.op.pool == "dlt_powerschool_kipppaterson"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`cd <worktree> && uv run pytest tests/test_dlt_powerschool.py::test_factory_builds_single_subsettable_multiasset -v`
Expected: FAIL — `TypeError` (old signature takes `table_name`, not `tables`).

- [ ] **Step 3: Replace the factory**

In `src/teamster/libraries/dlt/powerschool/assets.py`: delete `LOAD_STRATEGIES`
and the entire existing `build_powerschool_dlt_assets`; add
`from dagster import MaterializeResult` alongside the existing dagster imports
(keep `AssetExecutionContext`, `AssetKey`, `AssetSpec`) and
`from sqlalchemy.engine import Engine` if annotating; then add:

```python
def build_powerschool_dlt_assets(
    code_location: str,
    tables: list[PowerSchoolTable],
    op_tags: dict[str, object] | None = None,
):
    """Build ONE probe-gated @dlt_assets over all PowerSchool tables.

    Each table is a custom dlt resource: tables with a cursor_column probe
    COUNT(*)/MAX(cursor) and full-replace only on signature drift (signature
    stored in dlt resource state, restored from the destination); tables
    without a cursor always full-replace when selected. Schedules subset the
    multi-asset per tier. See
    docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md.
    """
    # Per-run report written by resources during extract, read by the op after
    # dlt.run() completes (same process; each Dagster run is a fresh pod).
    loaded_tables: set[str] = set()
    emptied_tables: set[str] = set()
    engine_holder: dict[str, object] = {}

    def _get_engine():
        # Lazy singleton: env vars exist only in the run pod, and the probe
        # engine is shared by all gated resources over the one SSH tunnel.
        if "engine" not in engine_holder:
            engine_holder["engine"] = sa.create_engine(_oracle_connection_url())
        return engine_holder["engine"]

    def _build_resource(table: PowerSchoolTable):
        @dlt.resource(name=table.name, write_disposition="replace")
        def _table_rows() -> Iterator:
            if table.cursor_column is not None:
                state = dlt.current.resource_state()
                with _get_engine().connect() as connection:
                    signature = probe_signature(
                        connection, table.name, table.cursor_column
                    )
                if signature == state.get("signature"):
                    return  # unchanged: no rows -> no load job -> table untouched
                state["signature"] = signature
                if signature["count"] == 0:
                    # replace can't land zero rows; op truncates explicitly
                    emptied_tables.add(table.name)
                    return
            loaded_tables.add(table.name)
            yield from sql_table(
                credentials=_oracle_connection_url(),
                schema=ORACLE_SCHEMA,
                table=table.name,
                backend="pyarrow",
                reflection_level="full_with_precision",
                defer_table_reflect=True,
                table_adapter_callback=remove_nullability_adapter,
                type_adapter_callback=oracle_number_adapter,
            )

        return _table_rows

    @dlt.source(name="powerschool")
    def dlt_source():
        for table in tables:
            yield _build_resource(table)

    dlt_pipeline = dlt.pipeline(
        pipeline_name="powerschool",
        # No `autodetect_schema=True`: oracle_number_adapter +
        # full_with_precision reflection are the authoritative decimal schema
        # (see oracle_number_adapter docstring).
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_powerschool",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source(),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__powerschool",
        dagster_dlt_translator=PowerSchoolDagsterDltTranslator(code_location),
        group_name="powerschool",
        pool=f"dlt_powerschool_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        loaded_tables.clear()
        emptied_tables.clear()

        with ssh_powerschool.open_ssh_tunnel_paramiko():
            try:
                # dlt.run() executes the full pipeline before yielding events,
                # so loaded_tables/emptied_tables are complete by iteration.
                for event in dlt.run(context=context):
                    table_name = check_asset_key(event).path[-1]

                    if table_name in loaded_tables:
                        yield event
                    elif table_name in emptied_tables:
                        with dlt_pipeline.sql_client() as client:
                            qualified = client.make_qualified_table_name(table_name)
                            client.execute_sql(f"TRUNCATE TABLE {qualified}")
                        context.log.info(f"{table_name}: emptied at source, truncated")
                        yield event
                    else:
                        context.log.info(f"{table_name}: unchanged, skipped")
            finally:
                if "engine" in engine_holder:
                    engine_holder.pop("engine").dispose()

    return _assets


def check_asset_key(event) -> AssetKey:
    """Narrow a dlt event's asset key (MaterializeResult.asset_key is optional)."""
    from dagster_shared import check

    return check.not_none(event.asset_key)
```

Module-level import note: move `from dagster_shared import check` to the top
imports and drop the local import; `Iterator` is already imported from
`collections.abc`. The `dlt` op parameter shadows the module import inside
`_assets` — same pattern as the previous implementation; the op body only needs
`dlt.run` (the resource) and closures.

- [ ] **Step 4: Run the test suite**

Run: `cd <worktree> && uv run pytest tests/test_dlt_powerschool.py -v` Expected:
all PASS (factory test + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/teamster/libraries/dlt/powerschool/assets.py tests/test_dlt_powerschool.py
git commit -m "feat(powerschool): probe-gated single multi-asset dlt factory"
```

---

### Task 4: Code location — config, assets, schedules

**Files:**

- Rewrite:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml`
- Rewrite:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/assets.py`
- Rewrite:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/schedules.py`
- Test: `tests/test_dlt_powerschool.py` (extend)

**Interfaces:**

- Consumes: `build_powerschool_dlt_assets`, `PowerSchoolTable` (Task 3).
- Produces: module attribute `assets: list` containing the ONE assets def;
  `schedules: list[ScheduleDefinition]` with the two existing schedule names.
  `definitions.py` needs no changes (already loads the module and wires `dlt`
  - `ssh_powerschool`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dlt_powerschool.py`:

```python
import pathlib

import yaml

CONFIG = pathlib.Path(
    "src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml"
)

INTRADAY_TRANSACTION_DATE = {
    "attendance", "storedgrades", "pgfinalgrades", "cc", "students", "courses",
    "schools", "sections", "termbins", "terms",
}
INTRADAY_WHENMODIFIED = {
    "gradescaleitem", "roledef", "s_nj_crs_x", "s_nj_ren_x", "s_nj_stu_x",
    "s_stu_x", "schoolstaff", "sectionteacher", "studentcorefields",
    "studentrace", "u_studentsuserfields", "users", "userscorefields",
}
NIGHTLY_WHENMODIFIED = {
    "assignmentcategoryassoc", "assignmentscore", "assignmentsection",
    "districtteachercategory", "gradecalcformulaweight", "gradecalcschoolassoc",
    "gradecalculationtype", "gradeformulaset", "gradeschoolconfig",
    "gradeschoolformulaassoc", "teachercategory",
}
NIGHTLY_NO_CURSOR = {
    "attendance_code", "attendance_conversion_items", "bell_schedule",
    "calendar_day", "cycle_day", "fte", "gen", "log", "reenrollments",
    "spenrollments", "studenttest", "studenttestscore", "test", "testscore",
}


def test_config_matches_spec_cursor_map():
    entries = yaml.safe_load(CONFIG.read_text())["assets"]
    by_name = {e["table_name"]: e for e in entries}

    assert len(entries) == 48

    for name in INTRADAY_TRANSACTION_DATE:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "transaction_date",
            "schedule_tier": "intraday",
        }
    for name in INTRADAY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "schedule_tier": "intraday",
        }
    for name in NIGHTLY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "schedule_tier": "nightly",
        }
    for name in NIGHTLY_NO_CURSOR:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": None,
            "schedule_tier": "nightly",
        }


def test_schedules_subset_by_tier():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        powerschool_dlt_intraday_asset_job_schedule as intraday,
        powerschool_dlt_nightly_asset_job_schedule as nightly,
    )

    assert intraday.cron_schedule == "*/15 * * * *"
    assert nightly.cron_schedule == "0 2 * * *"
    assert intraday.tags == {"dagster/max_runtime": "3600"}
    assert nightly.tags == {"dagster/max_runtime": "3600"}


def test_assets_module_exposes_single_def():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        assets,
    )

    assert len(assets) == 1
    assert len(list(assets[0].keys)) == 48
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`cd <worktree> && uv run pytest tests/test_dlt_powerschool.py -v -k "config or schedules or single_def"`
Expected: FAIL (yaml lacks `cursor_column`; assets module has 48 defs; old
schedules have no tags).

- [ ] **Step 3: Rewrite `config/assets.yaml`**

Full contents — 48 entries. Cursor map verified against kippnewark 2026-07-16
(spec "Cursor map" section):

```yaml
assets:
  # intraday, cursor transaction_date
  - table_name: attendance
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: cc
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: courses
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: pgfinalgrades
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: schools
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: sections
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: storedgrades
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: students
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: termbins
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: terms
    cursor_column: transaction_date
    schedule_tier: intraday
  # intraday, cursor whenmodified
  - table_name: gradescaleitem
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: roledef
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_crs_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_ren_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_stu_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_stu_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: schoolstaff
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: sectionteacher
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: studentcorefields
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: studentrace
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_studentsuserfields
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: users
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: userscorefields
    cursor_column: whenmodified
    schedule_tier: intraday
  # nightly gradebook, cursor whenmodified
  - table_name: assignmentcategoryassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: assignmentscore
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: assignmentsection
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: districtteachercategory
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalcformulaweight
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalcschoolassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalculationtype
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeformulaset
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeschoolconfig
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeschoolformulaassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: teachercategory
    cursor_column: whenmodified
    schedule_tier: nightly
  # nightly, no cursor -> unconditional replace
  - table_name: attendance_code
    cursor_column: null
    schedule_tier: nightly
  - table_name: attendance_conversion_items
    cursor_column: null
    schedule_tier: nightly
  - table_name: bell_schedule
    cursor_column: null
    schedule_tier: nightly
  - table_name: calendar_day
    cursor_column: null
    schedule_tier: nightly
  - table_name: cycle_day
    cursor_column: null
    schedule_tier: nightly
  - table_name: fte
    cursor_column: null
    schedule_tier: nightly
  - table_name: gen
    cursor_column: null
    schedule_tier: nightly
  - table_name: log
    cursor_column: null
    schedule_tier: nightly
  - table_name: reenrollments
    cursor_column: null
    schedule_tier: nightly
  - table_name: spenrollments
    cursor_column: null
    schedule_tier: nightly
  - table_name: studenttest
    cursor_column: null
    schedule_tier: nightly
  - table_name: studenttestscore
    cursor_column: null
    schedule_tier: nightly
  - table_name: test
    cursor_column: null
    schedule_tier: nightly
  - table_name: testscore
    cursor_column: null
    schedule_tier: nightly
```

- [ ] **Step 4: Rewrite `assets.py`**

```python
import pathlib

import yaml

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
    build_powerschool_dlt_assets,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

assets = [
    build_powerschool_dlt_assets(
        code_location=CODE_LOCATION,
        tables=[
            PowerSchoolTable(
                name=a["table_name"], cursor_column=a["cursor_column"]
            )
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
    )
]
```

- [ ] **Step 5: Rewrite `schedules.py`**

Keep the existing tier validation; add intraday-requires-cursor validation and
run tags:

```python
import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())

_VALID_SCHEDULE_TIERS = {"intraday", "nightly"}

_invalid_tier_assets = [
    a for a in config["assets"] if a["schedule_tier"] not in _VALID_SCHEDULE_TIERS
]
if _invalid_tier_assets:
    raise ValueError(
        "Invalid schedule_tier for table(s): "
        + ", ".join(
            f"{a['table_name']!r} ({a['schedule_tier']!r})"
            for a in _invalid_tier_assets
        )
        + f"; expected one of {sorted(_VALID_SCHEDULE_TIERS)}"
    )

# no-cursor tables cannot be probe-gated, so they must not run intraday
_ungated_intraday = [
    a
    for a in config["assets"]
    if a["schedule_tier"] == "intraday" and a["cursor_column"] is None
]
if _ungated_intraday:
    raise ValueError(
        "intraday tables require a cursor_column: "
        + ", ".join(a["table_name"] for a in _ungated_intraday)
    )


def _tier_targets(tier: str) -> list[str]:
    return [
        f"{CODE_LOCATION}/powerschool/{a['table_name']}"
        for a in config["assets"]
        if a["schedule_tier"] == tier
    ]


powerschool_dlt_intraday_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__intraday_asset_job_schedule",
    cron_schedule="*/15 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("intraday"),
    tags={"dagster/max_runtime": "3600"},
)

powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("nightly"),
    tags={"dagster/max_runtime": "3600"},
)

schedules = [
    powerschool_dlt_intraday_asset_job_schedule,
    powerschool_dlt_nightly_asset_job_schedule,
]
```

- [ ] **Step 6: Run the full test file**

Run: `cd <worktree> && uv run pytest tests/test_dlt_powerschool.py -v` Expected:
all PASS. Also sanity-check tier sizes inline:
`uv run python -c "from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import _tier_targets; print(len(_tier_targets('intraday')), len(_tier_targets('nightly')))"`
Expected: `23 25`.

- [ ] **Step 7: Commit**

```bash
git add src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/ tests/test_dlt_powerschool.py
git commit -m "feat(kipppaterson): probe-gated single multi-asset powerschool dlt config"
```

---

### Task 5: Validation + docs

**Files:**

- Modify: `src/teamster/code_locations/kipppaterson/CLAUDE.md` (PowerSchool via
  dlt section)

**Interfaces:** none.

- [ ] **Step 1: Validate definitions and run the broader test suite**

```bash
cd <worktree>
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipppaterson/__init__.py
uv run dagster definitions validate -m teamster.code_locations.kipppaterson.definitions
uv run pytest tests/test_dlt_powerschool.py tests/test_dagster_definitions.py -v
```

Expected: validate succeeds; tests pass. (If validate fails on missing env vars
unrelated to this change, fall back to
`uv run python -c "import teamster.code_locations.kipppaterson.definitions"`.)

- [ ] **Step 2: Update `code_locations/kipppaterson/CLAUDE.md`**

Rewrite the "PowerSchool via dlt" bullet list items that describe per-table
assets and the go-live pool note. Replace the paragraph beginning "Assets are
defined in `powerschool/sis/dlt/`" so the section reads (keep surrounding
content):

```markdown
Paterson ingests PowerSchool with **dlt**, syncing directly from its Oracle
database through an in-process paramiko SSH tunnel (`ssh_powerschool` resource,
`enable_legacy_rsa=True`) and landing to BigQuery via keyless ADC (issue #3807).
This is the pilot/template for migrating the ODBC districts (`kippnewark`,
`kippcamden`, `kippmiami`) off `sshpass`. ONE probe-gated `@dlt_assets`
multi-asset covers all 48 tables (`powerschool/sis/dlt/`): each table's dlt
resource probes `COUNT(*)`/`MAX(cursor_column)` and full-replaces only on
signature drift (signature in dlt resource state, restored from BigQuery);
`cursor_column: null` tables always replace. Config in
`powerschool/sis/dlt/config/assets.yaml`; two schedules in `schedules.py` subset
the multi-asset (intraday 15-min = 23 cursor tables; nightly = 25). Design:
`docs/superpowers/specs/2026-07-16-powerschool-dlt-probe-gated-sync-design.md`.
```

And replace the go-live bullet ("set a low concurrency limit...") with:

```markdown
- The `dlt_powerschool_kipppaterson` pool stays at limit 1 (Dagster+ deployment
  settings, UI) so an overrunning tick serializes with the next instead of
  racing it
```

- [ ] **Step 3: Trunk-check changed markdown, commit**

```bash
cd <worktree>
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/teamster/code_locations/kipppaterson/CLAUDE.md </dev/null
git add -u
git commit -m "docs(kipppaterson): describe probe-gated powerschool dlt sync"
```

---

### Task 6: Branch-deployment end-to-end + timing (spike item 3)

Requires push + CI deploy; coordinate with the user before pushing (dbt Cloud CI
on PR #4415 restarts on push — confirm it is in a terminal state first).

**Files:** none (operational validation; results recorded in the spec's
Baseline/Spike sections + PR comment).

- [ ] **Step 1: Push the branch** (after confirming dbt Cloud CI is idle)

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson push
```

- [ ] **Step 2: Wait for the branch deployment**

Watch the PR's `deploy` Actions job; recover the branch-deployment hash from the
log line `Deploying to branch deployment {hash}`. First MCP call against a
dormant deployment may throw `DagsterUserCodeUnreachableError` — retry after
~90s.

- [ ] **Step 3: Full-load run (timing baseline)**

Launch one run selecting ALL 48 asset keys via
`mcp__dagster__launch_run(deployment={hash}, confirm=False first)`. Fresh
pipeline state → every table full-loads. Record wall-clock (run
`startTime`→`endTime`) in the spec's Baseline section (spike item 3). Expect
under ~10 min.

- [ ] **Step 4: Idle re-run (gate verification)**

Immediately launch the same selection again. Expected: run SUCCEEDS, zero or
near-zero materializations (only tables that genuinely changed between runs),
per-table `unchanged, skipped` log lines in compute logs
(`get_run_compute_logs`), runtime ~1-2 min.

- [ ] **Step 5: Data verification (BigQuery MCP)**

- `SELECT count(*) FROM dagster_kipppaterson_dlt_powerschool.students` matches
  the run's `rows_loaded` metadata (`mcp__dagster__get_asset_materializations`).
- `_dlt_pipeline_state` has a row for pipeline `powerschool`.

- [ ] **Step 6: Record results + update spec, commit, comment on PR #4415**

Update the spec's Spike item 3 and Baseline with measured numbers; commit
(`docs(powerschool): record collapsed-run timing`); summarize the E2E evidence
in a PR #4415 comment (no PII — counts and durations only).

---

## Self-review notes

- Spec coverage: gating/state (Task 3), event filtering incl. emptied-table
  truncate (Task 3), config/cursor map (Task 4), schedules subsetting + tiers
  (Task 4), pool limit 1 + max_runtime (Task 4 tags + CLAUDE.md, pool limit is a
  UI setting that already exists), ODBC resource elimination (Paterson never
  wired `db_powerschool` for dlt — no change needed), spike items 1-2 (Task 1),
  spike item 3 + E2E (Task 6), migration first-run full load (Task 6 step 3),
  docs (Task 5).
- `select_columns` parity (`cc`, `u_studentsuserfields`, `log`) is explicitly
  out of scope per spec.
- Types consistent: `PowerSchoolTable` / `probe_signature` signatures match
  between Tasks 2-4.
