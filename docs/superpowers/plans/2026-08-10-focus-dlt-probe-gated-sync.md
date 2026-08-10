# Focus dlt Probe-Gated Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Focus's 77 per-table dlt assets with one probe-gated
multi-asset plus an intraday sensor, so an unchanged table is probed but never
reloaded.

**Architecture:** Extract the PowerSchool probe/signature helpers into a shared
`libraries/dlt/probe.py`, then rebuild the Focus factory as one two-mode
`@dlt_assets` (sensor-gated selection vs. unconditional full refresh) and add a
sensor that probes every table each tick and requests only the drifted ones. All
Focus-specific behavior — empty-table materialization, the interval adapter, the
nullability adapter, `autodetect_schema=True`, parquet load files, the
`_dlt_id`/`_dlt_load_id` knobs — is preserved exactly.

**Tech Stack:** Python 3.13, Dagster + `dagster-dlt`, dlt 1.29.x, SQLAlchemy,
PostgreSQL source, BigQuery destination, pytest, `uv`.

**Design spec:**
`docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md` — read
it before starting. It carries the reasoning; this plan carries the steps.

**Issue:** [#4447](https://github.com/TEAMSchools/teamster/issues/4447)

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt`
  on branch `cbini/refactor/claude-focus-probe-gated-dlt`. `cd` into it in the
  SAME command as any `pytest` / `trunk` call, or use `git -C <worktree>`.
  Editing `/workspaces/teamster/<path>` instead silently dirties `main`.
- **Python:** `requires-python = ">=3.13"`. Built-in generics (`list[str]`,
  `dict[str, int]`), `X | None` for nullable. Google-style docstrings. Always
  `uv run`, never bare `python` / `pytest`.
- **No new dependencies.** Everything needed is already in `pyproject.toml`.
- **Asset keys are frozen:** `[kippmiami, dlt, focus, <table_name>]`. Changing
  the shape breaks every downstream dbt staging model.
- **Destination is frozen:** dataset `dagster_kippmiami_dlt_focus`, pipeline
  name `focus`, dlt source name `focus`, `bigquery(autodetect_schema=True)`.
- **Schedule name is frozen:**
  `kippmiami__dlt__focus__daily_asset_job_schedule`. Renaming mints a new
  Dagster+ schedule object and abandons its status and tick history.
- **These must survive untouched** in the Focus factory:
  `dlt.mark.materialize_table_schema()` on an empty table,
  `interval_to_microseconds_adapter`, `remove_nullability_adapter`,
  `reflection_level="full_with_precision"`, `backend="pyarrow"`,
  `loader_file_format="parquet"`, `write_disposition="replace"`, and both
  `normalize.parquet_normalizer.add_dlt_id` / `add_dlt_load_id` knobs.
- **Out of scope — do not add:** `.fetch_row_count()` on the run iterator, a
  `max_extract_workers` parameter, an `intraday` / `nightly` tiering flag in the
  Focus YAML, or any change to `autodetect_schema`.
- **Commits:** conventional commits, one per task, body ends with `Refs #4447`.
  If a commit message is hook-blocked, write it to
  `.claude/scratch/commit-msg.txt` with the `Write` tool and use
  `git commit -F`.
- **Linting:** never run `trunk fmt` manually — the pre-commit hook formats.
  Before the final push run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd set to the worktree. Fall back to `~/.cache/trunk/launcher/trunk` if
  `.trunk/tools/trunk` is absent.
- **`kippmiami.definitions` cannot be imported in the codespace** — it resolves
  `FOCUS_DB` credentials eagerly at module load. Verify with
  `uv run python -m py_compile <files>` plus importing the affected submodule
  alone. This is expected, not a failure you introduced.
- **Focus is unreachable from the codespace** (IP allowlist). Every test in this
  plan uses sqlite or fakes. Live verification is Task 6, on a branch
  deployment.

---

## File Structure

| File                                                                             | Responsibility                                                                                                                                                                          |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/teamster/libraries/dlt/probe.py`                                            | **new** — source-agnostic probe/gate primitives: `ProbeTable`, `ProbeSignatureConfig`, `probe_signature`, `compute_changed`, `stored_signatures`, `IN_FLIGHT_STATUSES`, `in_flight_run` |
| `src/teamster/libraries/dlt/powerschool/assets.py`                               | PowerSchool factory; imports the primitives instead of defining them                                                                                                                    |
| `src/teamster/libraries/dlt/powerschool/sensors.py`                              | PowerSchool sensor; imports `in_flight_run`                                                                                                                                             |
| `src/teamster/libraries/dlt/focus/assets.py`                                     | Focus two-mode multi-asset factory + pipeline builder + asset-key helper                                                                                                                |
| `src/teamster/libraries/dlt/focus/sensors.py`                                    | **new** — Focus intraday probe-gated sensor                                                                                                                                             |
| `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`                      | one factory call over the YAML table list                                                                                                                                               |
| `src/teamster/code_locations/kippmiami/dlt/focus/sensors.py`                     | **new** — one sensor-factory call                                                                                                                                                       |
| `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`                   | cron trimmed to `0 4 * * *`                                                                                                                                                             |
| `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`              | `cursor_column` per table                                                                                                                                                               |
| `src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`, `dlt/__init__.py` | export `sensors`                                                                                                                                                                        |
| `src/teamster/code_locations/kippmiami/definitions.py`                           | register `dlt.sensors`                                                                                                                                                                  |
| `tests/libraries/test_dlt_probe.py`                                              | **new** — the moved helper tests                                                                                                                                                        |
| `tests/libraries/test_dlt_focus_sensors.py`                                      | **new** — Focus sensor tests                                                                                                                                                            |
| `tests/libraries/test_dlt_focus_signature_state.py`                              | **new** — the signature reaches `resource_state`                                                                                                                                        |
| 6 PowerSchool code-location files, 2 PowerSchool test files, 4 Focus test files  | `ProbeTable` rename / new factory signature                                                                                                                                             |

---

## Task 1: Shared probe module

Pure refactor — **no behavior change**. The move and the rename land together
because splitting them leaves the tree broken between commits.

**Files:**

- Create: `src/teamster/libraries/dlt/probe.py`
- Modify: `src/teamster/libraries/dlt/powerschool/assets.py`
- Modify: `src/teamster/libraries/dlt/powerschool/sensors.py`
- Modify: `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/assets.py`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/sensors.py`
- Modify: `src/teamster/code_locations/kippcamden/powerschool/sis/dlt/assets.py`
- Modify:
  `src/teamster/code_locations/kippcamden/powerschool/sis/dlt/sensors.py`
- Modify:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/assets.py`
- Modify:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/sensors.py`
- Create: `tests/libraries/test_dlt_probe.py`
- Modify: `tests/libraries/test_dlt_powerschool_assets.py`
- Modify: `tests/libraries/test_dlt_powerschool_sensors.py`

**Interfaces:**

- Consumes: nothing (first task).
- Produces, all importable from `teamster.libraries.dlt.probe`:
  - `ProbeTable(name: str, cursor_column: str | None)` — frozen dataclass
  - `ProbeSignatureConfig` — Dagster `Config` with `count: int`,
    `max_cursor: str | None = None`
  - `probe_signature(connection, table_name: str, cursor_column: str | None) -> dict[str, int | str | None]`
  - `compute_changed(selected: list[ProbeTable], current: dict[str, dict], stored: dict[str, dict]) -> list[ProbeTable]`
  - `stored_signatures(dlt_pipeline, source_name: str) -> dict[str, dict]`
  - `IN_FLIGHT_STATUSES: list[DagsterRunStatus]`
  - `in_flight_run(instance: DagsterInstance, sensor_name: str, nightly_schedule_name: str) -> RunRecord | None`

- [ ] **Step 1: Create the shared module**

Create `src/teamster/libraries/dlt/probe.py` with exactly this content. The
bodies are moved verbatim from `powerschool/assets.py` and
`powerschool/sensors.py`; only the names and the source-specific wording in
docstrings change.

```python
"""Source-agnostic probe-and-gate primitives for dlt full-replace pipelines.

A probe reads a cheap change signature for a table — `COUNT(*)` plus
`MAX(cursor_column)` — and compares it to the signature stored in dlt
`resource_state` by the last successful load. Drift selects the table for a full
`replace`; equality skips it.

Shared by `powerschool/` and `focus/`. Each library keeps its own sensor: the
connection lifecycles differ (an SSH tunnel plus an Oracle resource vs. a plain
Postgres URL), so a common sensor factory would be indirection without a payer.
"""

from dataclasses import dataclass
from datetime import date, datetime

import sqlalchemy as sa
from dagster import (
    Config,
    DagsterInstance,
    DagsterRunStatus,
    RunRecord,
    RunsFilter,
)

IN_FLIGHT_STATUSES = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


@dataclass(frozen=True)
class ProbeTable:
    """One source table's sync config.

    cursor_column None means the table has no change-tracking column. Its
    signature is then count-only, so a net row add or remove still selects it,
    but an in-place edit is caught only by the unconditional full refresh.
    """

    name: str
    cursor_column: str | None


class ProbeSignatureConfig(Config):
    """One table's probed change signature, passed by a gating sensor."""

    count: int
    max_cursor: str | None = None


def probe_signature(
    connection, table_name: str, cursor_column: str | None
) -> dict[str, int | str | None]:
    """Fetch the change signature for a table: total count + max cursor.

    Equality-compared against the stored signature; drift in either value
    (including a cursor regression) triggers a full replace. Tables without a
    cursor column are count-only — the signature still carries
    ``max_cursor: None`` so it compares equal to the run-config round-trip
    shape (which defaults the key to None). Values are JSON-serializable for
    dlt resource state.
    """
    if cursor_column is None:
        (count,) = connection.execute(
            # trunk-ignore(bandit/B608): table name from static YAML config
            sa.text(f"SELECT COUNT(*) FROM {table_name}")
        ).one()

        return {"count": int(count), "max_cursor": None}

    count, max_cursor = connection.execute(
        # trunk-ignore(bandit/B608): table/column names from static YAML config
        sa.text(f"SELECT COUNT(*), MAX({cursor_column}) FROM {table_name}")
    ).one()

    if max_cursor is None:
        max_cursor_value = None
    elif isinstance(max_cursor, (datetime, date)):
        max_cursor_value = max_cursor.isoformat()
    else:
        # Non-temporal cursor (e.g. a numeric change column); store its string
        # form so the signature stays JSON-serializable.
        max_cursor_value = str(max_cursor)

    # int(count): mirror the JSON-safe-scalar normalization done for max_cursor
    # above (the driver returns int today, but keep the state doc
    # driver-agnostic).
    return {"count": int(count), "max_cursor": max_cursor_value}


def compute_changed(
    selected: list[ProbeTable],
    current: dict[str, dict],
    stored: dict[str, dict],
) -> list[ProbeTable]:
    """Select tables whose just-probed signature differs from the stored one.

    Drift in count or max cursor — or a missing stored entry (first tick, or a
    table new to the config) — selects the table. No-cursor tables carry a
    count-only signature (``max_cursor: None``), so a net row add/remove
    selects them; in-place edits are caught by the unconditional full refresh.
    """
    return [
        table for table in selected if current.get(table.name) != stored.get(table.name)
    ]


def stored_signatures(dlt_pipeline, source_name: str) -> dict[str, dict]:
    """Read last-run per-resource signatures from dlt pipeline state."""
    resources = (
        dlt_pipeline.state.get("sources", {}).get(source_name, {}).get("resources", {})
    )
    return {
        name: res_state["signature"]
        for name, res_state in resources.items()
        if isinstance(res_state, dict) and "signature" in res_state
    }


def in_flight_run(
    instance: DagsterInstance, sensor_name: str, nightly_schedule_name: str
) -> RunRecord | None:
    """Return the first in-flight run launched by this sensor or the nightly
    schedule, or None.

    The baseline advances only on load success, so while a run launched by
    either trigger is still committing, re-selecting its tables would
    double-launch. Checked over the non-terminal status set
    (``IN_FLIGHT_STATUSES``) against the auto-applied ``dagster/sensor_name``
    and ``dagster/schedule_name`` run tags.
    """
    for tag, value in (
        ("dagster/sensor_name", sensor_name),
        ("dagster/schedule_name", nightly_schedule_name),
    ):
        records = instance.get_run_records(
            filters=RunsFilter(tags={tag: value}, statuses=IN_FLIGHT_STATUSES),
            limit=1,
        )
        if records:
            return records[0]
    return None
```

- [ ] **Step 2: Strip the moved code out of `powerschool/assets.py`**

Delete these from `src/teamster/libraries/dlt/powerschool/assets.py`:

- the `PowerSchoolTable` dataclass
- `probe_signature`
- `_compute_changed`
- `ProbeSignatureConfig`
- `_stored_signatures`

Keep everything else, including `_resolve_extract_workers` and
`oracle_number_adapter` (PowerSchool-specific).

Add the import, and replace every `PowerSchoolTable` annotation in the file with
`ProbeTable`:

```python
from teamster.libraries.dlt.probe import (
    ProbeSignatureConfig,
    ProbeTable,
    probe_signature,
)
```

`PowerSchoolDltConfig.probe` keeps its type — it now refers to the imported
`ProbeSignatureConfig`:

```python
class PowerSchoolDltConfig(Config):
    """Run config selecting the op's mode.

    probe present (intraday sensor): the sensor already probed and gated —
    load exactly the run's asset selection, persisting the passed signatures.
    probe absent (nightly schedule / manual launch): full refresh — probe the
    selection once, then load it all unconditionally with fresh baselines.
    """

    probe: dict[str, ProbeSignatureConfig] | None = None
```

Remove the now-unused `dataclass`, `date`, `datetime`, and `Config` imports only
if nothing else in the file uses them — `Config` is still used by the two config
classes, so it stays.

- [ ] **Step 3: Repoint `powerschool/sensors.py`**

Delete `_IN_FLIGHT_STATUSES` and `_in_flight_run` from
`src/teamster/libraries/dlt/powerschool/sensors.py`. Replace the imports with:

```python
from dagster import (
    RunRequest,
    SensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)

from teamster.libraries.dlt.powerschool.assets import (
    _SOURCE_NAME,
    _asset_key,
    build_powerschool_dlt_pipeline,
)
from teamster.libraries.dlt.powerschool.resources import OracleResource
from teamster.libraries.dlt.probe import (
    ProbeTable,
    compute_changed,
    in_flight_run,
    probe_signature,
    stored_signatures,
)
from teamster.libraries.ssh.resources import SSHResource
```

Then in the file body rename the three call sites and the two annotations:

- `_in_flight_run(` → `in_flight_run(`
- `_stored_signatures(` → `stored_signatures(`
- `_compute_changed(` → `compute_changed(`
- `list[PowerSchoolTable]` → `list[ProbeTable]` (both occurrences)

- [ ] **Step 4: Rename in the three PowerSchool code locations**

Six files, same two edits each. Run from the worktree root:

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
for loc in kippnewark kippcamden kipppaterson; do
  sed -i \
    -e 's/^    PowerSchoolTable,$/    ProbeTable,/' \
    -e 's/^from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable$/from teamster.libraries.dlt.probe import ProbeTable/' \
    -e 's/PowerSchoolTable(/ProbeTable(/' \
    "src/teamster/code_locations/${loc}/powerschool/sis/dlt/assets.py" \
    "src/teamster/code_locations/${loc}/powerschool/sis/dlt/sensors.py"
done
```

The first `sed` expression rewrites the name inside the multi-line
`from ... import (` block in `assets.py`; that block still imports
`build_powerschool_dlt_assets` from `powerschool.assets`, so `ProbeTable` must
move to its own import line. Fix each `assets.py` by hand afterward so it reads:

```python
from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import build_powerschool_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable
```

(substituting the right `CODE_LOCATION` import per location).

- [ ] **Step 5: Move the helper tests**

Create `tests/libraries/test_dlt_probe.py`. Move into it, unchanged except for
the import line and the renames:

- from `tests/libraries/test_dlt_powerschool_assets.py`: `FakeResult`,
  `FakeConnection`, the four `test_probe_signature_*` tests, the
  `test_powerschool_table_dataclass` test (rename it
  `test_probe_table_dataclass`), the seven `test_compute_changed_*` tests, and
  the two `test_stored_signatures_*` tests
- from `tests/libraries/test_dlt_powerschool_sensors.py`: `_FakeInstance`,
  `_fake_record`, and the three `test_in_flight_run_*` tests

Header and imports for the new file:

```python
"""Unit tests for the shared dlt probe/gate primitives (no external deps)."""

import types
from datetime import datetime

from teamster.libraries.dlt.probe import (
    IN_FLIGHT_STATUSES,
    ProbeTable,
    compute_changed,
    in_flight_run,
    probe_signature,
    stored_signatures,
)
```

Inside the moved tests, rewrite `PowerSchoolTable(` → `ProbeTable(`,
`_compute_changed(` → `compute_changed(`, `_stored_signatures(` →
`stored_signatures(`, `_in_flight_run(` → `in_flight_run(`, and
`_IN_FLIGHT_STATUSES` → `IN_FLIGHT_STATUSES`.

Delete the moved tests and their now-unused imports/helpers from the two
PowerSchool test files. In `test_dlt_powerschool_sensors.py` the remaining tests
still need `ProbeTable`, so its import becomes:

```python
from teamster.libraries.dlt.powerschool.sensors import (
    _build_run_request,
    build_powerschool_dlt_intraday_sensor,
)
from teamster.libraries.dlt.probe import ProbeTable
```

- [ ] **Step 6: Run the affected tests**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/test_dlt_probe.py \
  tests/libraries/test_dlt_powerschool_assets.py \
  tests/libraries/test_dlt_powerschool_sensors.py \
  tests/libraries/test_powerschool_dlt_extract_workers.py -v
```

Expected: all pass. A failure naming `PowerSchoolTable` means a rename site was
missed — `grep -rn PowerSchoolTable src/ tests/` must return nothing.

- [ ] **Step 7: Confirm no import regressions in the PowerSchool locations**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run python -c "
import teamster.code_locations.kippnewark.powerschool.sis.dlt.assets as a
import teamster.code_locations.kippnewark.powerschool.sis.dlt.sensors as s
print(len(a.assets), len(s.sensors))
"
```

Expected: `1 1`. If it fails on a missing dbt manifest, run
`uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kippnewark/__init__.py`
first.

- [ ] **Step 8: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git add -u && git add src/teamster/libraries/dlt/probe.py tests/libraries/test_dlt_probe.py &&
git commit -m "refactor(dagster): extract shared dlt probe helpers

Moves the probe/signature/gate primitives out of the powerschool library
into libraries/dlt/probe.py so focus and illuminate can share them.
PowerSchoolTable becomes ProbeTable. No behavior change.

Refs #4447"
```

---

## Task 2: Focus two-mode multi-asset

**Files:**

- Modify: `src/teamster/libraries/dlt/focus/assets.py`
- Create: `tests/libraries/test_dlt_focus_signature_state.py`
- Modify: `tests/libraries/test_dlt_focus_op_config.py`
- Modify: `tests/libraries/test_dlt_replace_loader_file_format.py`
- Modify: `tests/libraries/test_dlt_focus_type_adapter.py`
- Modify: `tests/libraries/test_dlt_focus_empty_load_package.py`

**Interfaces:**

- Consumes: `ProbeTable`, `ProbeSignatureConfig`, `probe_signature` from
  `teamster.libraries.dlt.probe` (Task 1).
- Produces, from `teamster.libraries.dlt.focus.assets`:
  - `_asset_key(code_location: str, table_name: str) -> AssetKey`
  - `build_focus_dlt_pipeline(code_location: str) -> dlt.Pipeline`
  - `FOCUS_SOURCE_NAME: str` (`"focus"`)
  - `FocusDltConfig` with `refresh: str | None` and
    `probe: dict[str, ProbeSignatureConfig] | None`
  - `build_focus_source(sql_database_credentials, tables: list[ProbeTable], signatures: dict[str, dict] | None = None, db_schema: str | None = FOCUS_DB_SCHEMA)`
  - `build_focus_dlt_assets(sql_database_credentials, code_location: str, tables: list[ProbeTable], op_tags: dict[str, object] | None = None)`
  - unchanged: `_focus_table_items`, `interval_to_microseconds_adapter`,
    `REFRESH_MODES`, `FOCUS_DB_SCHEMA`, `FOCUS_CHUNK_SIZE`

- [ ] **Step 1: Write the failing test for the signature write**

Create `tests/libraries/test_dlt_focus_signature_state.py`:

```python
"""The Focus resource persists its probed signature to dlt resource state.

The signature must be written from INSIDE the extracted resource: dlt commits
state only from resources that actually reached the load package, so a write
from the source function body or after the load never round-trips. sqlite stands
in for Focus Postgres — the Codespace cannot reach Focus (IP allowlist).
"""

import shutil
import tempfile
from pathlib import Path

import dlt
import sqlalchemy as sa
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.destinations import bigquery

from teamster.libraries.dlt.focus.assets import build_focus_source
from teamster.libraries.dlt.probe import ProbeTable, stored_signatures

SIGNATURE = {"count": 3, "max_cursor": "2026-08-09T12:00:00"}


def _seed(url: str, rows: int) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("create table referrals (referral_id integer not null, note text)")
        )
        for i in range(rows):
            conn.execute(sa.text("insert into referrals values (:i, 'n')"), {"i": i})
    engine.dispose()


def _extract(url: str, rows: int, signature: dict) -> dict[str, dict]:
    """Extract one table through the real source and return the stored state."""
    _seed(url, rows)

    dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
    dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

    pipelines_dir = tempfile.mkdtemp(prefix="focus-signature-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_signature_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )
        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(url),
                tables=[ProbeTable(name="referrals", cursor_column="note")],
                signatures={"referrals": signature},
                db_schema=None,
            ),
            loader_file_format="parquet",
        )
        return stored_signatures(pipeline, "focus")
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)


def test_populated_table_persists_its_signature(tmp_path: Path) -> None:
    stored = _extract(f"sqlite:///{tmp_path / 'focus.db'}", rows=3, signature=SIGNATURE)

    assert stored == {"referrals": SIGNATURE}


def test_empty_table_persists_its_signature(tmp_path: Path) -> None:
    """The 0-row path yields only hints plus the materialize marker.

    Whether dlt commits resource state for that shape is the design's one open
    risk. If this test fails, do NOT weaken it — apply the spec's contingency
    (attach the signature via `dlt.mark.with_hints`) and record the finding.
    """
    empty_signature = {"count": 0, "max_cursor": None}

    stored = _extract(
        f"sqlite:///{tmp_path / 'empty.db'}", rows=0, signature=empty_signature
    )

    assert stored == {"referrals": empty_signature}


def test_no_signature_writes_no_state(tmp_path: Path) -> None:
    """A None signature must not create a state key."""
    _seed(f"sqlite:///{tmp_path / 'none.db'}", rows=1)

    pipelines_dir = tempfile.mkdtemp(prefix="focus-nosig-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_nosig_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )
        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(
                    f"sqlite:///{tmp_path / 'none.db'}"
                ),
                tables=[ProbeTable(name="referrals", cursor_column=None)],
                signatures=None,
                db_schema=None,
            ),
            loader_file_format="parquet",
        )

        assert stored_signatures(pipeline, "focus") == {}
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/test_dlt_focus_signature_state.py -v
```

Expected: FAIL at collection or in `build_focus_source` —
`TypeError: got an unexpected keyword argument 'tables'`, because the source
still takes `table_name`.

- [ ] **Step 3: Rewrite `libraries/dlt/focus/assets.py`**

Replace the import block and everything from `FocusDltConfig` onward. Keep
`REFRESH_MODES`, `interval_to_microseconds_adapter`, and `_focus_table_items`
byte-for-byte as they are — three Focus test files pin their behavior.

New imports:

```python
from collections.abc import Iterator
from typing import Any, get_args

import dlt
import sqlalchemy as sa
from dagster import AssetExecutionContext, AssetKey, AssetSpec, Config
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import config as dlt_config
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.common.typing import TRefreshMode
from dlt.destinations import bigquery
from dlt.extract.items import DataItemWithMeta
from dlt.extract.resource import DltResource
from dlt.sources.sql_database import remove_nullability_adapter
from dlt.sources.sql_database.helpers import table_rows
from sqlalchemy import BigInteger
from sqlalchemy.sql.sqltypes import _AbstractInterval
from sqlalchemy.types import TypeEngine

from teamster.libraries.dlt.probe import (
    ProbeSignatureConfig,
    ProbeTable,
    probe_signature,
)
```

`DltSource` is no longer imported — the factory builds the source inline.

Asset-key helper and pipeline builder, placed just after the module constants:

```python
def _asset_key(code_location: str, table_name: str) -> AssetKey:
    """The asset key for one Focus table (single source of truth).

    The translator, the sensor's asset selection, and the sensor's RunRequest all
    route through this. The dbt `focus_dlt` source's `asset_key` meta must match
    this shape or the dbt-source -> dlt-asset lineage breaks.
    """
    return AssetKey([code_location, "dlt", FOCUS_SOURCE_NAME, table_name])


def build_focus_dlt_pipeline(code_location: str) -> Any:
    """The shared BigQuery pipeline for one district's Focus source.

    Used by the assets factory (loads) and by the intraday sensor (baseline
    reads via sync_destination + resource state).

    `autodetect_schema=True` is load-bearing: paired with
    `loader_file_format="parquet"` it is what lets a `replace` table whose source
    went to 0 rows truncate successfully (#4733).
    """
    return pipeline(
        pipeline_name=FOCUS_SOURCE_NAME,
        destination=bigquery(autodetect_schema=True),
        dataset_name=f"dagster_{code_location}_dlt_{FOCUS_SOURCE_NAME}",
        progress=LogCollector(dump_system_stats=False),
    )
```

Config class:

```python
class FocusDltConfig(Config):
    """Run config for the Focus dlt op.

    `probe` present (intraday sensor): the sensor already probed and gated —
    load exactly the run's asset selection, persisting the passed signatures.
    `probe` absent (04:00 schedule / manual launch): full refresh — probe the
    selection once, then load it all unconditionally with fresh baselines.

    `refresh` is unset on every scheduled run. It exists for the one-time
    migration that recreates already-populated tables so they gain the
    `_dlt_id` / `_dlt_load_id` columns — BigQuery refuses to add REQUIRED
    columns to an existing table, so they must be dropped and reloaded
    (`drop_resources`, #4740).
    """

    probe: dict[str, ProbeSignatureConfig] | None = None
    refresh: str | None = None
```

Translator — now delegating the key to `_asset_key`:

```python
class FocusDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=_asset_key(self.code_location, data.resource.name),
            deps=[],
        )

        return asset_spec.merge_attributes(kinds={"postgresql"})
```

Resource builder — the existing parameters keep their names and positions so the
two `test_dlt_focus_type_adapter.py` tests that call it still pass; `signature`
is appended as an optional keyword:

```python
def _build_focus_resource(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None = FOCUS_DB_SCHEMA,
    signature: dict | None = None,
) -> DltResource:
    """Build one full-replace dlt resource for a Focus table.

    Drives the exported ``table_rows`` generator (via `_focus_table_items`)
    rather than wrapping ``sql_table``, so the resource can append
    ``dlt.mark.materialize_table_schema()`` when the source yielded no data. A
    table with 0 rows otherwise produces nothing dlt can act on, normalize drops
    the package, and BigQuery never gets a table — leaving no target for a dbt
    staging model (#4740). Same ``table_rows`` pattern as
    ``libraries/dlt/powerschool/``.

    When `signature` is given it is written to the resource's dlt state WITH the
    load, becoming the baseline the next sensor tick compares against. It is
    written here, inside the extracted resource, because dlt commits state only
    from resources that reached the load package — a write from the source body
    or after the load never round-trips. `parallelized=True` is compatible with
    `resource_state` writes; what breaks is nesting a DltResource inside a
    parallelized resource, which this does not do.
    """

    @dlt.resource(name=table_name, write_disposition="replace", parallelized=True)
    def _focus_table() -> Iterator:
        if signature is not None:
            dlt.current.resource_state()["signature"] = signature

        yield from _focus_table_items(
            sql_database_credentials=sql_database_credentials,
            table_name=table_name,
            db_schema=db_schema,
        )

    return _focus_table
```

Source — now multi-table:

```python
@dlt.source(name=FOCUS_SOURCE_NAME)
def build_focus_source(
    sql_database_credentials: ConnectionStringCredentials,
    tables: list[ProbeTable],
    signatures: dict[str, dict] | None = None,
    db_schema: str | None = FOCUS_DB_SCHEMA,
) -> Iterator:
    """One resource per table. The source name must stay `focus` — it is the dlt
    schema name the destination's stored schema and state are keyed on."""
    signatures = signatures or {}

    for table in tables:
        yield _build_focus_resource(
            sql_database_credentials=sql_database_credentials,
            table_name=table.name,
            db_schema=db_schema,
            signature=signatures.get(table.name),
        )
```

Factory:

```python
def build_focus_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    code_location: str,
    tables: list[ProbeTable],
    op_tags: dict[str, object] | None = None,
):
    """Build ONE two-mode @dlt_assets over all Focus tables.

    The selection decision belongs to the caller: the intraday sensor probes,
    gates, and passes per-table signatures via run config (`probe`); the 04:00
    schedule and manual launches pass no config and get an unconditional full
    refresh. In both modes the op runs the pipeline over a source narrowed to the
    run's asset selection — a full `replace` per table — persisting each table's
    signature to dlt resource_state WITH the load, so failures self-heal: the old
    baseline survives and the table re-selects next tick. See
    docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md.
    """
    if op_tags is None:
        op_tags = {}

    dlt_pipeline = build_focus_dlt_pipeline(code_location)
    translator = FocusDagsterDltTranslator(code_location)
    tables_by_key = {_asset_key(code_location, t.name): t for t in tables}

    @dlt_assets(
        # The full source only defines the asset specs; the op runs a narrowed
        # one.
        dlt_source=build_focus_source(
            sql_database_credentials=sql_database_credentials, tables=tables
        ),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__{FOCUS_SOURCE_NAME}",
        dagster_dlt_translator=translator,
        group_name=FOCUS_SOURCE_NAME,
        pool=f"dlt_{FOCUS_SOURCE_NAME}_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        config: FocusDltConfig,
        dlt: DagsterDltResource,
    ) -> Iterator:
        # Both knobs make the arrow data path carry `_dlt_id` / `_dlt_load_id`,
        # which dlt's object path injects as REQUIRED when
        # `materialize_table_schema()` creates an empty table. Without them the
        # first real load into such a table fails with
        # `Field _dlt_load_id is missing in new schema` (#4740). Set here, not at
        # import: each step runs in its own pod, so it cannot leak to another
        # pipeline. NOT `dlt.config` — `dlt` is the resource parameter here.
        dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
        dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

        selected = [
            tables_by_key[key]
            for key in context.selected_asset_keys
            if key in tables_by_key
        ]

        if config.probe is not None:
            # Sensor mode: the sensor probed and gated already — persist its
            # signatures with the load, no re-probe.
            signatures: dict[str, dict] = {
                name: {"count": sig.count, "max_cursor": sig.max_cursor}
                for name, sig in config.probe.items()
            }
            context.log.info(f"focus sensor-selected load: {sorted(signatures)}")
        else:
            # Full-refresh mode (04:00 schedule / manual launch): load the whole
            # selection unconditionally. Probe FIRST so fresh baseline signatures
            # persist WITH the load — dlt commits state only from extracted
            # resources, so a post-load write would not round-trip.
            engine = sa.create_engine(
                sql_database_credentials.to_native_representation()
            )
            try:
                with engine.connect() as connection:
                    signatures = {
                        table.name: probe_signature(
                            connection, table.name, table.cursor_column
                        )
                        for table in selected
                    }
            finally:
                engine.dispose()

            context.log.info(f"focus full-refresh load: {sorted(signatures)}")

        # Stream dlt's periodic extract/normalize/load progress into the Dagster
        # event log. The factory-built collector defaults to logger="stdout"
        # (step-pod compute logs only), which went dark for one table at a time
        # before and would now go dark for the whole multi-table load.
        dlt_pipeline.collector = LogCollector(
            logger=context.log, log_period=30.0, dump_system_stats=False
        )

        # loader_file_format="parquet": BigQuery schema autodetection rejects the
        # empty jsonl file dlt writes to truncate a `replace` table whose source
        # went to 0 rows. See `replace` write-disposition in ../CLAUDE.md (#4733).
        run_kwargs: dict[str, Any] = {
            "write_disposition": "replace",
            "loader_file_format": "parquet",
        }

        if config.refresh is not None:
            if config.refresh not in REFRESH_MODES:
                raise ValueError(
                    f"refresh must be one of {sorted(REFRESH_MODES)}, got"
                    f" {config.refresh!r} — dlt would silently treat that as"
                    " drop_resources and recreate every table in this run"
                )

            context.log.info(f"dlt refresh mode: {config.refresh}")
            run_kwargs["refresh"] = config.refresh

        yield from dlt.run(
            context=context,
            dlt_source=build_focus_source(
                sql_database_credentials=sql_database_credentials,
                tables=selected,
                signatures=signatures,
            ),
            dlt_pipeline=dlt_pipeline,
            dagster_dlt_translator=translator,
            **run_kwargs,
        )

    return _assets
```

- [ ] **Step 4: Run the new test**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/test_dlt_focus_signature_state.py -v
```

Expected: `test_populated_table_persists_its_signature` and
`test_no_signature_writes_no_state` PASS.

`test_empty_table_persists_its_signature` is the design's open risk. If it
FAILS, stop and report it — do not edit the assertion. The contingency is in the
spec under _Open risk_: attach the signature via `dlt.mark.with_hints` alongside
the materialize marker.

- [ ] **Step 5: Update the four existing Focus test files for the new
      signature**

`tests/libraries/test_dlt_focus_empty_load_package.py` — one call site:

```python
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(url),
                tables=[ProbeTable(name="referrals", cursor_column=None)],
                db_schema=None,
            ),
```

Add `from teamster.libraries.dlt.probe import ProbeTable` to its imports.

`tests/libraries/test_dlt_focus_type_adapter.py` — the factory call in
`test_factory_builds_a_source_with_the_table_named_resource`:

```python
    assets = build_focus_dlt_assets(
        sql_database_credentials=ConnectionStringCredentials(
            "postgresql+psycopg://localhost:5432/focus"
        ),
        code_location="kippmiami",
        tables=[ProbeTable(name="gradebook_assignments", cursor_column="updated_at")],
    )
```

Add the `ProbeTable` import. The two `_build_focus_resource` tests need no
change — the new `signature` parameter defaults to `None`.

`tests/libraries/test_dlt_focus_op_config.py` — three edits:

```python
@pytest.fixture(name="focus_assets")
def fixture_focus_assets() -> Any:
    return build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=[ProbeTable(name="discipline_referrals", cursor_column="updated_at")],
    )
```

```python
class _StubContext:
    """The op logs its mode and reads the run's asset selection.

    `selected_asset_keys` drives which tables the narrowed source carries, and
    every test here runs in sensor mode (`probe` set) so the op never opens a
    connection to probe.
    """

    def __init__(self) -> None:
        self.log = _StubLog()
        self.selected_asset_keys = {
            AssetKey(["kippmiami", "dlt", "focus", "discipline_referrals"])
        }
```

```python
PROBE = {"discipline_referrals": ProbeSignatureConfig(count=1, max_cursor=None)}


def _config(**kwargs: Any) -> FocusDltConfig:
    """Sensor-mode config: `probe` set, so the op does not open a connection."""
    return FocusDltConfig(probe=PROBE, **kwargs)
```

Then replace each `FocusDltConfig()` with `_config()` and
`FocusDltConfig(refresh="drop_resources")` with
`_config(refresh="drop_resources")`, and
`FocusDltConfig(refresh="drop_resource")` with
`_config(refresh="drop_resource")`. Add to that file's imports:

```python
from dagster import AssetKey

from teamster.libraries.dlt.probe import ProbeSignatureConfig, ProbeTable
```

`tests/libraries/test_dlt_replace_loader_file_format.py` — the Focus fixture
takes `tables`, and `_run_kwargs` must pass a real context plus a sensor-mode
config, since `context=None` no longer works:

```python
class _StubLog:
    def info(self, message: str) -> None:
        pass


class _StubContext:
    def __init__(self, keys: set[Any]) -> None:
        self.log = _StubLog()
        self.selected_asset_keys = keys


FOCUS_KEY = AssetKey(["kippmiami", "dlt", "focus", "discipline_referrals"])


@pytest.fixture(name="focus_assets")
def fixture_focus_assets() -> Any:
    return build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=[ProbeTable(name="discipline_referrals", cursor_column="updated_at")],
    )
```

In `_run_kwargs`, replace the `{"context": None, ...}` line and the focus
branch:

```python
    kwargs: dict[str, Any] = {"context": None, "dlt": dlt_resource}

    # the focus op takes run config and reads the context; the illuminate op does
    # neither
    if "config" in assets.op.compute_fn.decorated_fn.__annotations__:
        from teamster.libraries.dlt.focus.assets import FocusDltConfig
        from teamster.libraries.dlt.probe import ProbeSignatureConfig

        kwargs["context"] = _StubContext({FOCUS_KEY})
        kwargs["config"] = config or FocusDltConfig(
            probe={
                "discipline_referrals": ProbeSignatureConfig(count=1, max_cursor=None)
            }
        )
```

Add `from dagster import AssetKey` and
`from teamster.libraries.dlt.probe import ProbeTable` to its imports.

- [ ] **Step 6: Run the whole Focus + PowerSchool dlt suite**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/ -k "dlt" -v
```

Expected: all pass. The `test_dlt_focus_materialize_empty.py` tests must pass
**unmodified** — if they fail, `_focus_table_items` was changed and must be
restored.

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git add -u && git add tests/libraries/test_dlt_focus_signature_state.py &&
git commit -m "refactor(dagster): make the Focus dlt factory a probe-gated multi-asset

One two-mode @dlt_assets over all Focus tables replaces the per-table
factory: sensor-gated selection with passed signatures, or an
unconditional full refresh that probes first. Asset keys, dataset,
adapters, parquet load files and the row-id knobs are unchanged.

Refs #4447"
```

---

## Task 3: Focus intraday sensor

**Files:**

- Create: `src/teamster/libraries/dlt/focus/sensors.py`
- Create: `tests/libraries/test_dlt_focus_sensors.py`

**Interfaces:**

- Consumes: `_asset_key`, `build_focus_dlt_pipeline`, `FOCUS_SOURCE_NAME` from
  `focus.assets` (Task 2); `ProbeTable`, `compute_changed`, `in_flight_run`,
  `probe_signature`, `stored_signatures` from `probe` (Task 1).
- Produces, from `teamster.libraries.dlt.focus.sensors`:
  - `_build_run_request(code_location: str, changed: list[ProbeTable], current: dict[str, dict]) -> RunRequest`
  - `build_focus_dlt_intraday_sensor(code_location: str, tables: list[ProbeTable], sql_database_credentials, nightly_schedule_name: str, minimum_interval_seconds: int = 900) -> SensorDefinition`

- [ ] **Step 1: Write the failing tests**

Create `tests/libraries/test_dlt_focus_sensors.py`:

```python
"""Unit tests for the Focus dlt intraday sensor factory (no external deps)."""

from typing import Any

from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.sensors import (
    _build_run_request,
    build_focus_dlt_intraday_sensor,
)
from teamster.libraries.dlt.probe import ProbeTable

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/focus")


def test_sensor_factory_shape() -> None:
    sensor_def = build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=[ProbeTable(name="students", cursor_column="updated_at")],
        sql_database_credentials=CREDENTIALS,
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )

    assert sensor_def.name == "kippmiami__dlt__focus__intraday_sensor"
    assert sensor_def.minimum_interval_seconds == 900
    # credentials are closure-captured, not a Dagster resource
    assert sensor_def.required_resource_keys == set()


def test_sensor_selects_every_configured_table() -> None:
    tables = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="login_history", cursor_column=None),
    ]

    sensor_def = build_focus_dlt_intraday_sensor(
        code_location="kippmiami",
        tables=tables,
        sql_database_credentials=CREDENTIALS,
        nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
    )

    selection: Any = sensor_def.asset_selection

    assert sorted(k.to_user_string() for k in selection.resolve([])) == [
        "kippmiami/dlt/focus/login_history",
        "kippmiami/dlt/focus/students",
    ]


def test_build_run_request_selects_changed_and_passes_signatures() -> None:
    changed = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="login_history", cursor_column=None),
    ]
    current = {
        "students": {"count": 43, "max_cursor": "2026-08-09T00:00:00"},
        "login_history": {"count": 10, "max_cursor": None},
        # unchanged table present in the probe but not in `changed`:
        "districts": {"count": 1, "max_cursor": "2026-07-01T00:00:00"},
    }

    run_request = _build_run_request("kippmiami", changed, current)

    # trunk-ignore(pyright): asset_selection is always set in our RunRequests
    assert [k.to_user_string() for k in run_request.asset_selection] == [
        "kippmiami/dlt/focus/students",
        "kippmiami/dlt/focus/login_history",
    ]
    assert run_request.run_config == {
        "ops": {
            "kippmiami__dlt__focus": {
                "config": {
                    "probe": {
                        "students": {
                            "count": 43,
                            "max_cursor": "2026-08-09T00:00:00",
                        },
                        "login_history": {"count": 10, "max_cursor": None},
                    }
                }
            }
        }
    }
    assert run_request.tags["dagster/max_runtime"] == "3600"
```

If `selection.resolve([])` raises on your Dagster version, replace that
assertion with
`assert sorted(k.to_user_string() for k in selection.asset_keys) == [...]` — the
point is that all configured tables are in the selection, not the accessor.

- [ ] **Step 2: Run to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/test_dlt_focus_sensors.py -v
```

Expected: FAIL at collection —
`ModuleNotFoundError: teamster.libraries.dlt.focus.sensors`.

- [ ] **Step 3: Write the sensor**

Create `src/teamster/libraries/dlt/focus/sensors.py`:

```python
import sqlalchemy as sa
from dagster import (
    RunRequest,
    SensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import (
    FOCUS_SOURCE_NAME,
    _asset_key,
    build_focus_dlt_pipeline,
)
from teamster.libraries.dlt.probe import (
    ProbeTable,
    compute_changed,
    in_flight_run,
    probe_signature,
    stored_signatures,
)


def _build_run_request(
    code_location: str, changed: list[ProbeTable], current: dict[str, dict]
) -> RunRequest:
    """RunRequest for the changed tables, passing their probed signatures.

    The probe payload rides run config (the op's `FocusDltConfig.probe` field):
    the op loads exactly this selection and persists these signatures with the
    load — no re-probe, no gate.
    """
    return RunRequest(
        asset_selection=[_asset_key(code_location, table.name) for table in changed],
        run_config={
            "ops": {
                f"{code_location}__dlt__{FOCUS_SOURCE_NAME}": {
                    "config": {
                        "probe": {table.name: current[table.name] for table in changed}
                    }
                }
            }
        },
        tags={"dagster/max_runtime": "3600"},
    )


def build_focus_dlt_intraday_sensor(
    code_location: str,
    tables: list[ProbeTable],
    sql_database_credentials: ConnectionStringCredentials,
    nightly_schedule_name: str,
    minimum_interval_seconds: int = 900,
) -> SensorDefinition:
    """Build the intraday change-detection sensor for one district's Focus DB.

    Each tick probes every table (COUNT(*) + MAX(cursor); count-only for
    no-cursor tables) over one engine, compares against the baseline stored in
    dlt resource state, and requests a run for only the changed tables —
    unchanged tables are never planned, and an idle tick launches nothing. Skips
    while a run launched by this sensor or by the nightly full-refresh schedule
    is in flight (the baseline advances only on load success, so an in-flight
    table would re-select and double-launch).

    Credentials are closure-captured rather than taken as a Dagster resource,
    matching how the Focus code location already resolves them at import.

    See docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md.
    """
    sensor_name = f"{code_location}__dlt__{FOCUS_SOURCE_NAME}__intraday_sensor"

    @sensor(
        name=sensor_name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=[_asset_key(code_location, table.name) for table in tables],
    )
    def _sensor(context: SensorEvaluationContext) -> RunRequest | SkipReason:
        in_flight = in_flight_run(context.instance, sensor_name, nightly_schedule_name)
        if in_flight is not None:
            return SkipReason(f"run {in_flight.dagster_run.run_id} in flight")

        dlt_pipeline = build_focus_dlt_pipeline(code_location)

        # Restore prior signatures from the destination state table. On a truly
        # first run (no dataset) this raises; treat as no prior state.
        try:
            dlt_pipeline.sync_destination()
        except Exception as e:
            # Expected only on the first tick / a brand-new dataset. A persistent
            # failure here (bad perms, wrong dataset) would full-reload every
            # table every tick, so surface it at warning.
            context.log.warning(
                f"dlt sync_destination failed ({e}); treating all tables as "
                "changed (expected only on first run / new dataset)"
            )

        stored = stored_signatures(dlt_pipeline, FOCUS_SOURCE_NAME)

        # One shared engine for the whole probe, like the op's full-refresh probe.
        engine = sa.create_engine(sql_database_credentials.to_native_representation())
        try:
            with engine.connect() as connection:
                current: dict[str, dict] = {
                    table.name: probe_signature(
                        connection, table.name, table.cursor_column
                    )
                    for table in tables
                }
        finally:
            engine.dispose()

        changed = compute_changed(tables, current, stored)

        context.log.info(
            f"focus probe: {len(changed)}/{len(tables)} changed; "
            f"changed={sorted(table.name for table in changed)}"
        )

        if not changed:
            return SkipReason(f"no change across {len(tables)} probed tables")

        return _build_run_request(code_location, changed, current)

    return _sensor
```

- [ ] **Step 4: Run the tests**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/test_dlt_focus_sensors.py -v
```

Expected: 3 passed. The op name in the run config (`kippmiami__dlt__focus`) must
match the `name=` given to `@dlt_assets` in Task 2 — a mismatch makes every
sensor-launched run fail with an invalid-run-config error at launch, and this
test is what catches it.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git add src/teamster/libraries/dlt/focus/sensors.py tests/libraries/test_dlt_focus_sensors.py &&
git commit -m "feat(dagster): add the Focus dlt intraday probe-gated sensor

Probes every Focus table each tick, compares to the dlt-state baseline,
and requests a run for only the drifted tables. Skips while a
sensor-launched or nightly-schedule run is in flight.

Refs #4447"
```

---

## Task 4: Wire up the kippmiami code location

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`
- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`
- Create: `src/teamster/code_locations/kippmiami/dlt/focus/sensors.py`
- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`
- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`
- Modify: `src/teamster/code_locations/kippmiami/dlt/__init__.py`
- Modify: `src/teamster/code_locations/kippmiami/definitions.py`

**Interfaces:**

- Consumes: `build_focus_dlt_assets` (Task 2), `build_focus_dlt_intraday_sensor`
  (Task 3), `ProbeTable` (Task 1).
- Produces: `kippmiami.dlt.sensors` — a list with one `SensorDefinition`.

- [ ] **Step 1: Add `cursor_column` to all 77 YAML entries**

`updated_at` for every table except `co_teachers` and `login_history`, which
have no such column in the source. Verified against
`dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS` on 2026-08-10: 75 of 77
tables carry `updated_at` as a TIMESTAMP.

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run python - <<'PY'
import pathlib

path = pathlib.Path(
    "src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml"
)
no_cursor = {"co_teachers", "login_history"}
out = []

for line in path.read_text().splitlines():
    out.append(line)
    if line.startswith("  - table_name: "):
        name = line.split(": ", 1)[1].strip()
        cursor = "null" if name in no_cursor else "updated_at"
        out.append(f"    cursor_column: {cursor}")

path.write_text("\n".join(out) + "\n")
PY
```

- [ ] **Step 2: Verify the YAML transform**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run python - <<'PY'
import pathlib

import yaml

path = pathlib.Path(
    "src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml"
)
assets = yaml.safe_load(path.read_text())["assets"]

print("entries:", len(assets))
print("missing cursor_column:", [a for a in assets if "cursor_column" not in a])
print("null cursor:", sorted(a["table_name"] for a in assets if a["cursor_column"] is None))
PY
```

Expected exactly:

```text
entries: 77
missing cursor_column: []
null cursor: ['co_teachers', 'login_history']
```

- [ ] **Step 3: Rewrite the code-location assets module**

`src/teamster/code_locations/kippmiami/dlt/focus/assets.py`:

```python
import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        tables=[
            # a["cursor_column"], not .get(): a new table added without a
            # declared cursor must fail loudly at module load, not silently
            # become count-only.
            ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
    )
]
```

- [ ] **Step 4: Add the code-location sensors module**

Create `src/teamster/code_locations/kippmiami/dlt/focus/sensors.py`:

```python
import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.sensors import build_focus_dlt_intraday_sensor
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

sensors = [
    build_focus_dlt_intraday_sensor(
        code_location=CODE_LOCATION,
        tables=[
            ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
        sql_database_credentials=sql_database_credentials,
        # Must match the schedule's `name` exactly — the in-flight guard reads
        # the `dagster/schedule_name` run tag.
        nightly_schedule_name=(
            f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule"
        ),
    )
]
```

- [ ] **Step 5: Trim the schedule to the 04:00 full refresh**

In `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`, keep the
`name=` line and its comment exactly as they are. Replace the `cron_schedule`
line and the comment block above it with:

```python
    # 04:00 keeps the pre-dawn pull that every Focus-derived model depends on --
    # Miami enrollment, attendance, and the FRESH scaffold's Miami rows all read
    # it, and FRESH's Tableau extract refreshes at 05:00.
    #
    # This is now the UNCONDITIONAL full-refresh tier. The 12:00 and 14:00 crons
    # were replaced by `<CODE_LOCATION>__dlt__focus__intraday_sensor`, which
    # probes every table every 15 minutes and loads only the drifted ones -- so
    # the live-Focus snapshot the rpt_focus__* import-once anti-joins read is
    # refreshed within 15 minutes of a change instead of at two fixed times. The
    # safe rule for ops is unchanged and is a dependency, not a clock time: do
    # not re-run the delivery unless a Focus sync has run SINCE the last import.
    #
    # Keep this tier unconditional. It is the backstop for any table whose
    # `updated_at` the Focus app does not bump on an in-place edit, which the
    # count+cursor probe cannot see.
    cron_schedule="0 4 * * *",
```

Substitute the real code location for `<CODE_LOCATION>` in that comment.

- [ ] **Step 6: Export the sensors**

`src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`:

```python
from teamster.code_locations.kippmiami.dlt.focus.assets import assets
from teamster.code_locations.kippmiami.dlt.focus.schedules import schedules
from teamster.code_locations.kippmiami.dlt.focus.sensors import sensors

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
```

`src/teamster/code_locations/kippmiami/dlt/__init__.py`:

```python
from teamster.code_locations.kippmiami.dlt import focus

assets = [
    *focus.assets,
]

schedules = [
    *focus.schedules,
]

sensors = [
    *focus.sensors,
]

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
```

- [ ] **Step 7: Register the sensor in the definitions**

In `src/teamster/code_locations/kippmiami/definitions.py`, add `*dlt.sensors` as
the first entry of the `sensors=[` list:

```python
    sensors=[
        *dlt.sensors,
        *couchdrop.sensors,
        *iready.sensors,
        *renlearn.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
```

- [ ] **Step 8: Compile-check every edited module**

`kippmiami.definitions` cannot be imported here — it resolves `FOCUS_DB`
credentials at module load, which are unset in the codespace. Compile instead:

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run python -m py_compile \
  src/teamster/code_locations/kippmiami/definitions.py \
  src/teamster/code_locations/kippmiami/dlt/__init__.py \
  src/teamster/code_locations/kippmiami/dlt/focus/__init__.py \
  src/teamster/code_locations/kippmiami/dlt/focus/assets.py \
  src/teamster/code_locations/kippmiami/dlt/focus/sensors.py \
  src/teamster/code_locations/kippmiami/dlt/focus/schedules.py &&
echo COMPILED
```

Expected: `COMPILED`.

- [ ] **Step 9: Prove the wiring builds, with fake credentials**

This bypasses the `FOCUS_DB` resolution by building the same objects the code
location builds, so the asset keys, the op name, and the sensor name are all
verified together:

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run python - <<'PY'
import pathlib

import yaml
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.focus.sensors import build_focus_dlt_intraday_sensor
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(
    "src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml"
)
tables = [
    ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
credentials = ConnectionStringCredentials(
    "postgresql+psycopg://user:pw@localhost:5432/focus"
)

assets = build_focus_dlt_assets(
    sql_database_credentials=credentials,
    code_location="kippmiami",
    tables=tables,
)
sensor_def = build_focus_dlt_intraday_sensor(
    code_location="kippmiami",
    tables=tables,
    sql_database_credentials=credentials,
    nightly_schedule_name="kippmiami__dlt__focus__daily_asset_job_schedule",
)

keys = sorted(spec.key.to_user_string() for spec in assets.specs)

print("tables:", len(tables))
print("specs:", len(keys))
print("first key:", keys[0])
print("op name:", assets.op.name)
print("sensor:", sensor_def.name)
assert len(keys) == 77, keys
assert all(k.startswith("kippmiami/dlt/focus/") for k in keys)
assert assets.op.name == "kippmiami__dlt__focus"
assert sensor_def.name == "kippmiami__dlt__focus__intraday_sensor"
print("OK")
PY
```

Expected: `tables: 77`, `specs: 77`, `op name: kippmiami__dlt__focus`, and `OK`.

- [ ] **Step 10: Confirm the schedule still targets all 77 assets under its old
      name**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
grep -n "name=\|cron_schedule" src/teamster/code_locations/kippmiami/dlt/focus/schedules.py
```

Expected: the name line still reads
`f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule"`, and
`cron_schedule="0 4 * * *"` with no list.

- [ ] **Step 11: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git add -u && git add src/teamster/code_locations/kippmiami/dlt/focus/sensors.py &&
git commit -m "feat(dagster): gate the Focus sync with the intraday sensor

Declares a cursor_column per table (updated_at, except co_teachers and
login_history), collapses the 77 asset factory calls into one, trims the
schedule to the 04:00 unconditional refresh, and registers the intraday
sensor. The schedule keeps its name so its Dagster+ identity survives.

Refs #4447"
```

---

## Task 5: Documentation

**Files:**

- Modify: `src/teamster/libraries/dlt/CLAUDE.md`
- Modify: `src/teamster/libraries/dlt/focus/CLAUDE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update the dlt library CLAUDE.md**

In `src/teamster/libraries/dlt/CLAUDE.md`, replace the `### focus/` sub-library
section with:

```markdown
### `focus/`

Loads tables from the **Focus SIS** (student information system) PostgreSQL
database directly to BigQuery using `dlt`'s `table_rows` generator with the
PyArrow backend. Probe-gated, same style as `powerschool/`.

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Factories:
  `build_focus_dlt_assets(sql_database_credentials, code_location, tables, op_tags=None)`
  and
  `build_focus_dlt_intraday_sensor(code_location, tables, sql_database_credentials, nightly_schedule_name, minimum_interval_seconds=900)`
  (`sensors.py`)
- **Op run-config contract** (`FocusDltConfig`): `probe` present (intraday
  sensor) → load exactly the run's asset selection with the passed signatures.
  `probe` absent (04:00 schedule / manual launch) → probe the selection once
  BEFORE the load, then load it all unconditionally. `refresh` is the separate
  #4740 migration knob and is orthogonal to gating.
- Tiering: `0 4 * * *` is the unconditional full refresh — the backstop for a
  table whose `updated_at` the Focus app does not bump on an in-place edit. The
  sensor covers everything between.
- `cursor_column` is `updated_at` for every Focus table except `co_teachers` and
  `login_history`, which are count-only. A new table must declare one in
  `config/focus.yaml`; the code location reads `a["cursor_column"]`, so omitting
  it fails at module load.
- Uses `reflection_level="full_with_precision"` + `remove_nullability_adapter`
  (forces all columns `NULLABLE` so upstream `NOT NULL` changes don't break the
  `replace` load — see `focus/CLAUDE.md`)
- `interval_to_microseconds_adapter` maps Postgres `interval` to INT64
  microseconds; without it dlt rejects the inferred `duration[us]` (see
  `focus/CLAUDE.md`)
```

Then add a bullet to the `## Notes` section's shared-helpers area:

```markdown
### Shared probe helpers (`probe.py`)

`ProbeTable`, `ProbeSignatureConfig`, `probe_signature`, `compute_changed`,
`stored_signatures`, `IN_FLIGHT_STATUSES`, and `in_flight_run` live in
`libraries/dlt/probe.py` and are shared by `powerschool/` and `focus/`. Each
library keeps its OWN sensor — powerschool needs an SSH tunnel plus an Oracle
resource, focus a plain Postgres URL. Do not merge them into a generic sensor
factory; `illuminate/` (#4446) is the third intended consumer of the helpers,
not of a shared sensor.
```

- [ ] **Step 2: Update the Focus library CLAUDE.md**

In `src/teamster/libraries/dlt/focus/CLAUDE.md`, add this section directly after
the `## Empty source tables` section:

```markdown
## Probe gating

One `@dlt_assets` op covers every Focus table; the intraday sensor decides which
of them a run carries. A table is loaded only when its probed signature
(`COUNT(*)` + `MAX(updated_at)`) differs from the one the last successful load
wrote to dlt `resource_state`.

- **Gating cannot move into the op.** A `replace` resource that yields zero rows
  truncates its table, so a skip has to be an exclusion from the run. Probing in
  the op would also plan all 77 assets every tick and emit
  `ASSET_FAILED_TO_MATERIALIZE` for the skipped ones.
- **The signature is written inside the extracted resource.** dlt commits state
  only from resources that reached the load package, so a failed load keeps the
  old baseline and the table re-selects on the next tick — failures self-heal.
- **A 0-row table** carries `{count: 0, max_cursor: null}` and gates out after
  its first load, so the empty-table materialization runs once, not every tick.
- **Enable order matters.** The sensor selects any table with no stored
  signature, so enabling it before an 04:00 full refresh has seeded baselines
  makes the first tick select all 77 tables at once. Seed first, then enable.
```

- [ ] **Step 3: Lint both files**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/libraries/dlt/CLAUDE.md \
  src/teamster/libraries/dlt/focus/CLAUDE.md </dev/null 2>&1 | tail -20
```

Expected: `✔ No issues`.

- [ ] **Step 4: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git add -u &&
git commit -m "docs(dagster): document Focus probe gating and the shared helpers

Refs #4447"
```

**Not in this task:** `docs/reference/automations.md` is generated by
`uv run scripts/gen-automations-doc.py`, which silently SKIPS code locations
that fail to import — and `kippmiami` cannot import in the codespace.
Regenerating here would drop locations from the catalog. Note it in the PR body
as a follow-up for a full environment; do not fake it.

---

## Task 6: Full verification and PR

**Files:** none — verification and handoff.

- [ ] **Step 1: Full local test sweep**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
uv run pytest tests/libraries/ -v 2>&1 | tail -30
```

Expected: all pass. Anything failing outside `tests/libraries/` that references
`dlt`, `focus`, or `powerschool` must be investigated, not waved off — check
whether your own change caused it before calling it pre-existing.

- [ ] **Step 2: Confirm no stale references remain**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
grep -rn "PowerSchoolTable" src/ tests/ docs/ ; \
grep -rn "table_name=" src/teamster/code_locations/kippmiami/dlt/ ; \
echo "--- exit: expect no output above ---"
```

Expected: no output before the marker line.

- [ ] **Step 3: Lint every changed file**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
files=$(git diff --name-only origin/main...HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) &&
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix ${files} </dev/null > /tmp/trunk-focus.log 2>&1 ;
tail -30 /tmp/trunk-focus.log
```

Run this in the background if it exceeds two minutes — its progress spinner
prints no result lines, so interim output reads as a false clean. Only interpret
the output after the run exits.

- [ ] **Step 4: Push and open the PR**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-focus-probe-gated-dlt &&
git push
```

Open the PR with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, including:

- `Refs #4447`
- the local test results
- the branch-deployment validation checklist from Step 5, unticked
- the `docs/reference/automations.md` regeneration follow-up
- an explicit statement that the sensor ships `defaultStatus` STOPPED and must
  be enabled by hand only AFTER one 04:00 full refresh has seeded baselines

- [ ] **Step 5: Branch-deployment validation (requires the deployment to be
      live)**

The codespace cannot reach Focus. Branch-deployment dlt runs write to the
**prod** dataset — dlt has no branch redirect — so this order minimizes prod
writes.

- [ ] Sensor left stopped. Evaluate one tick from the Dagster UI's sensor test
      view. Expect a log line `focus probe: N/77 changed` and a skip or a run
      request. Zero writes. A `sync_destination failed` warning on the first
      evaluation is expected only if the dlt state row is unreadable — with 77
      tables already landed it should NOT appear.
- [ ] Launch the consolidated asset job manually for `districts`, `schools`, and
      one 0-row table (identify one with `select table_id, row_count from ` +
      backtick + `teamster-332318.dagster_kippmiami_dlt_focus.__TABLES__` +
      backtick + `where row_count = 0`; confirm with `count(*)`, since
      `__TABLES__.row_count` lags). Confirm success and unchanged row counts.
- [ ] Re-evaluate the sensor tick. Those three tables must now be absent from
      `changed`. **This is the step that answers the design's open risk** — if
      the 0-row table still appears, apply the spec's contingency.
- [ ] Confirm a changed table still fully replaces: pick one, note its
      `count(*)`, re-run, confirm the count and a fresh `_dlt_load_id`.
- [ ] Run the full 77-table refresh to seed every baseline.
- [ ] Re-evaluate the tick: expect `0/77 changed` or only genuinely-churning
      tables.

- [ ] **Step 6: Post-merge cutover**

- [ ] Confirm the `kippmiami` code location deployed
      (`mcp__dagster__get_location_load_history`).
- [ ] Let one `0 4 * * *` run complete. Confirm 77 materializations.
- [ ] Enable `kippmiami__dlt__focus__intraday_sensor`
      (`mcp__dagster__start_sensor`, `confirm=False` first).
- [ ] Watch the first three ticks (`mcp__dagster__get_tick_history`). Expect
      skips or small selections, never all 77.
- [ ] Regenerate `docs/reference/automations.md` in a full environment.

---

## Self-Review

**Spec coverage:**

| Spec section                              | Task                            |
| ----------------------------------------- | ------------------------------- |
| `libraries/dlt/probe.py` contract         | 1                               |
| PowerSchool rename, 8 call sites          | 1                               |
| Focus two-mode multi-asset                | 2                               |
| Preserved Focus behavior                  | 2 (Global Constraints + Step 6) |
| Signature write in the resource           | 2                               |
| `LogCollector` repointed at `context.log` | 2                               |
| Focus sensor + in-flight guard            | 3                               |
| Cursor config, 75 + 2                     | 4                               |
| Schedule trimmed, name preserved          | 4                               |
| Sensor ships STOPPED                      | 6                               |
| Open risk: 0-row `resource_state`         | 2 Step 4, 6 Step 5              |
| Unit testing                              | 1, 2, 3                         |
| Branch-deployment validation              | 6                               |
| Cutover and rollback                      | 6                               |
| Docs                                      | 5                               |

**Placeholder scan:** none. Every code step carries the real content; the only
deliberately open item is the 0-row `resource_state` question, which is a test
with a named contingency rather than a TBD.

**Type consistency:** `ProbeTable`, `ProbeSignatureConfig`, `probe_signature`,
`compute_changed`, `stored_signatures`, `in_flight_run`, `IN_FLIGHT_STATUSES`,
`_asset_key`, `build_focus_dlt_pipeline`, `build_focus_source`,
`build_focus_dlt_assets`, `build_focus_dlt_intraday_sensor`, and
`_build_run_request` are spelled identically everywhere they appear. The op name
`kippmiami__dlt__focus` appears in Task 2 (`@dlt_assets name=`), Task 3 (the run
config key), and Task 4 Step 9 (the assertion) — all three must agree, and Task
3 Step 4 says so explicitly.
