# PowerSchool dlt Intraday Sensor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PowerSchool dlt intraday `ScheduleDefinition` with a
probe-driven sensor in all three dlt districts (`kippnewark`, `kippcamden`,
`kipppaterson`) so unchanged tables are never planned and idle ticks launch
nothing.

**Architecture:** Change detection moves from the op into a new library sensor
factory that probes each intraday table, compares against the dlt-state
baseline, and emits `RunRequest(asset_selection=changed)` with the probe payload
in `run_config` — or a `SkipReason`. The op becomes two-mode: probe payload
present → load exactly the selection with the passed signatures; absent (nightly
schedule or manual launch) → probe-then-load all selected unconditionally (full
refresh + re-baseline). `config/assets.yaml` moves from a `schedule_tier` enum
to `intraday`/`nightly` membership booleans.

**Tech Stack:** Dagster 1.13 (sensors, pythonic run config), dlt 1.28.1
(`resource_state` baselines), SQLAlchemy + oracledb over an SSH tunnel.

**Spec:**
`docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md`
(Status: Approved, amended 2026-07-20). Read it before starting.

## Global Constraints

- **All file work happens in the worktree**
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor`
  — never the main checkout. Use `git -C <worktree>` for every git command.
- Run tests from inside the worktree:
  `cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor && uv run pytest ...`.
- Python via `uv run` only; `requires-python = ">=3.13"`; built-in generics and
  `X | None` unions; Google-style docstrings.
- Commit messages: conventional commits. One commit per task.
- Signature dict shape is ALWAYS `{"count": int, "max_cursor": str | None}` —
  both keys present, no-cursor tables carry `max_cursor: None`. A count-only
  dict would never compare equal to the run-config round-trip (which defaults
  `max_cursor` to `None`) and every no-cursor table would reload every tick.
- The probe in full-refresh mode runs BEFORE the load: dlt commits state only
  from a resource actually extracted into a successful load; post-load writes
  from the op body never round-trip.
- The intraday schedule and the sensor must never coexist in one deploy (double
  loads) — each district's migration removes the schedule and adds the sensor in
  the same commit.
- Trunk: do not run `trunk fmt`/`check` manually except the final doc check;
  binary is `/workspaces/teamster/.trunk/tools/trunk`, run with cwd set to the
  worktree.

---

### Task 1: `probe_signature` no-cursor support

**Files:**

- Modify: `src/teamster/libraries/dlt/powerschool/assets.py:52-77`
  (`probe_signature`)
- Test: `tests/libraries/test_dlt_powerschool_assets.py`

**Interfaces:**

- Consumes: existing `probe_signature(connection, table_name, cursor_column)`.
- Produces:
  `probe_signature(connection, table_name: str, cursor_column: str | None) -> dict[str, int | str | None]`
  — when `cursor_column is None`, issues `SELECT COUNT(*)` only and returns
  `{"count": n, "max_cursor": None}`. Tasks 3 and 4 call it with `None`.

- [ ] **Step 1: Write the failing test**

Append to `tests/libraries/test_dlt_powerschool_assets.py` (the `FakeConnection`
/ `FakeResult` fixtures at the top of the file already exist):

```python
def test_probe_signature_no_cursor_count_only():
    # No-cursor tables are count-gated: COUNT(*) only, and the signature keeps
    # the max_cursor key (None) so it compares equal to the run-config
    # round-trip shape.
    conn = FakeConnection((42,))

    sig = probe_signature(conn, "gen", None)

    assert sig == {"count": 42, "max_cursor": None}
    assert "COUNT(*)" in conn.queries[0]
    assert "MAX(" not in conn.queries[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`uv run pytest tests/libraries/test_dlt_powerschool_assets.py::test_probe_signature_no_cursor_count_only -v`

Expected: FAIL — `probe_signature` unpacks two columns from a one-column row
(`ValueError: not enough values to unpack`) or builds `MAX(None)` SQL.

- [ ] **Step 3: Implement**

In `src/teamster/libraries/dlt/powerschool/assets.py`, replace the
`probe_signature` function with:

```python
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
        # Non-temporal cursor (e.g. a numeric change column on a future table);
        # store its string form so the signature stays JSON-serializable.
        max_cursor_value = str(max_cursor)

    # int(count): mirror the JSON-safe-scalar normalization done for max_cursor
    # above (oracledb returns int today, but keep the state doc driver-agnostic).
    return {"count": int(count), "max_cursor": max_cursor_value}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_dlt_powerschool_assets.py -v`

Expected: all PASS (existing cursor-column tests unaffected).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/libraries/dlt/powerschool/assets.py tests/libraries/test_dlt_powerschool_assets.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "feat(dlt): count-only probe_signature for no-cursor powerschool tables"
```

---

### Task 2: `_compute_changed` gates every table on signature equality

**Files:**

- Modify: `src/teamster/libraries/dlt/powerschool/assets.py:80-96`
  (`_compute_changed`)
- Test: `tests/libraries/test_dlt_powerschool_assets.py`

**Interfaces:**

- Produces:
  `_compute_changed(selected: list[PowerSchoolTable], current: dict[str, dict], stored: dict[str, dict]) -> list[PowerSchoolTable]`
  — a table is changed iff `current.get(name) != stored.get(name)`. The
  no-cursor "always reload" special case is gone (the sensor probes no-cursor
  tables too, per Task 1; the op no longer calls this function after Task 3 — it
  becomes the sensor's gate).

- [ ] **Step 1: Rewrite the `_compute_changed` tests**

In `tests/libraries/test_dlt_powerschool_assets.py`, DELETE
`test_compute_changed_no_cursor_table_always_included` and replace it with:

```python
def test_compute_changed_no_cursor_count_drift_included():
    table = PowerSchoolTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 43, "max_cursor": None}}
    stored = {"gen": {"count": 42, "max_cursor": None}}

    changed = _compute_changed([table], current, stored)

    assert changed == [table]


def test_compute_changed_no_cursor_stable_count_excluded():
    table = PowerSchoolTable(name="gen", cursor_column=None)
    signature = {"count": 42, "max_cursor": None}
    current = {"gen": dict(signature)}
    stored = {"gen": dict(signature)}

    changed = _compute_changed([table], current, stored)

    assert changed == []


def test_compute_changed_no_stored_baseline_included():
    # Bootstrap: a table new to intraday (or first tick ever) has no stored
    # signature and must load once to establish one.
    table = PowerSchoolTable(name="gen", cursor_column=None)
    current = {"gen": {"count": 42, "max_cursor": None}}

    changed = _compute_changed([table], current, stored={})

    assert changed == [table]
```

Then update `test_compute_changed_mixed_set_order_preserved`: the `no_cursor`
table now needs a drifted signature to be included. Replace the body with:

```python
def test_compute_changed_mixed_set_order_preserved():
    no_cursor = PowerSchoolTable(name="test", cursor_column=None)
    drifted = PowerSchoolTable(name="students", cursor_column="transaction_date")
    unchanged = PowerSchoolTable(name="users", cursor_column="whenmodified")
    selected = [no_cursor, drifted, unchanged]

    unchanged_signature = {"count": 5, "max_cursor": "2026-07-14T00:00:00"}
    current = {
        "test": {"count": 9, "max_cursor": None},
        "students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"},
        "users": dict(unchanged_signature),
    }
    stored = {
        "test": {"count": 8, "max_cursor": None},
        "students": {"count": 42, "max_cursor": "2026-07-15T00:00:00"},
        "users": dict(unchanged_signature),
    }

    changed = _compute_changed(selected, current, stored)

    assert changed == [no_cursor, drifted]
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run:
`uv run pytest tests/libraries/test_dlt_powerschool_assets.py -v -k compute_changed`

Expected: `test_compute_changed_no_cursor_stable_count_excluded` FAILS (old code
always includes no-cursor tables); the drift/bootstrap tests pass incidentally.

- [ ] **Step 3: Implement**

Replace `_compute_changed` in `src/teamster/libraries/dlt/powerschool/assets.py`
with:

```python
def _compute_changed(
    selected: list[PowerSchoolTable],
    current: dict[str, dict],
    stored: dict[str, dict],
) -> list[PowerSchoolTable]:
    """Select tables whose just-probed signature differs from the stored one.

    Drift in count or max cursor — or a missing stored entry (first tick, or a
    table new to intraday) — selects the table. No-cursor tables carry a
    count-only signature (``max_cursor: None``), so a net row add/remove
    selects them; in-place edits are caught by the nightly full refresh.
    """
    return [
        table for table in selected if current.get(table.name) != stored.get(table.name)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_dlt_powerschool_assets.py -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/libraries/dlt/powerschool/assets.py tests/libraries/test_dlt_powerschool_assets.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "refactor(dlt): gate powerschool _compute_changed purely on signature equality"
```

---

### Task 3: Two-mode op (run-config probe payload / full-refresh)

**Files:**

- Modify: `src/teamster/libraries/dlt/powerschool/assets.py` (config classes,
  pipeline helper, `build_powerschool_dlt_assets` op body)
- Test: `tests/libraries/test_dlt_powerschool_assets.py`

**Interfaces:**

- Consumes: `probe_signature` with `cursor_column=None` (Task 1).
- Produces:
  - `class ProbeSignatureConfig(Config)` — fields `count: int`,
    `max_cursor: str | None = None`.
  - `class PowerSchoolDltConfig(Config)` — field
    `probe: dict[str, ProbeSignatureConfig] | None = None`.
  - `build_powerschool_dlt_pipeline(code_location: str) -> dlt.Pipeline` —
    module-level helper; Task 4's sensor calls it.
  - The op accepts run config
    `{"ops": {"<loc>__powerschool": {"config": {"probe": {<table>: {"count": n, "max_cursor": s|None}}}}}}`
    (sensor mode) or empty config (full-refresh mode).
  - `_stored_signatures(dlt_pipeline, source_name)` stays exported unchanged
    (the sensor uses it; the op no longer does).

- [ ] **Step 1: Write the failing tests**

Append to `tests/libraries/test_dlt_powerschool_assets.py`:

```python
def _resolved_probe_job(tables):
    from dagster import Definitions, define_asset_job
    from dagster_dlt import DagsterDltResource

    from teamster.libraries.dlt.powerschool.resources import OracleResource
    from teamster.libraries.ssh.resources import SSHResource

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", tables=tables
    )
    defs = Definitions(
        assets=[assets_def],
        jobs=[define_asset_job("probe_job", selection=list(assets_def.keys))],
        resources={
            "dlt": DagsterDltResource(),
            "ssh_powerschool": SSHResource(remote_host="localhost"),
            "db_powerschool": OracleResource(
                user="u", password="p", host="localhost", port="1521", service_name="s"
            ),
        },
    )
    return defs.resolve_job_def("probe_job")


def test_run_config_schema_accepts_probe_payload():
    job = _resolved_probe_job(
        [
            PowerSchoolTable(name="students", cursor_column="transaction_date"),
            PowerSchoolTable(name="gen", cursor_column=None),
        ]
    )

    from dagster import validate_run_config

    validated = validate_run_config(
        job,
        {
            "ops": {
                "kipppaterson__powerschool": {
                    "config": {
                        "probe": {
                            "students": {
                                "count": 43,
                                "max_cursor": "2026-07-16T00:00:00",
                            },
                            "gen": {"count": 10, "max_cursor": None},
                        }
                    }
                }
            }
        },
    )

    assert validated


def test_run_config_schema_accepts_empty_full_refresh():
    job = _resolved_probe_job(
        [PowerSchoolTable(name="students", cursor_column="transaction_date")]
    )

    from dagster import validate_run_config

    assert validate_run_config(job, {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run pytest tests/libraries/test_dlt_powerschool_assets.py -v -k run_config_schema`

Expected: `test_run_config_schema_accepts_probe_payload` FAILS —
`DagsterInvalidConfigError: ... received unexpected config entry "probe"` (the
op declares no config schema yet). The empty-config test passes incidentally.

- [ ] **Step 3: Implement**

In `src/teamster/libraries/dlt/powerschool/assets.py`:

1. Add `Config` to the dagster import:

```python
from dagster import AssetExecutionContext, AssetKey, AssetSpec, Config
```

1. Add the config classes and pipeline helper after `_resolve_extract_workers`:

```python
class ProbeSignatureConfig(Config):
    """One table's probed change signature, passed by the intraday sensor."""

    count: int
    max_cursor: str | None = None


class PowerSchoolDltConfig(Config):
    """Run config selecting the op's mode.

    probe present (intraday sensor): the sensor already probed and gated —
    load exactly the run's asset selection, persisting the passed signatures.
    probe absent (nightly schedule / manual launch): full refresh — probe the
    selection once, then load it all unconditionally with fresh baselines.
    """

    probe: dict[str, ProbeSignatureConfig] | None = None


def build_powerschool_dlt_pipeline(code_location: str) -> dlt.Pipeline:
    """The shared BigQuery pipeline for one district's PowerSchool source.

    Used by the assets factory (loads) and the intraday sensor (baseline
    reads via sync_destination + resource state).
    """
    return dlt.pipeline(
        pipeline_name=_SOURCE_NAME,
        # No `autodetect_schema=True`: oracle_number_adapter +
        # full_with_precision reflection are the authoritative decimal schema
        # (see oracle_number_adapter docstring).
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_{_SOURCE_NAME}",
        progress=LogCollector(dump_system_stats=False),
    )
```

1. In `build_powerschool_dlt_assets`, replace the inline `dlt.pipeline(...)`
   call with:

```python
    dlt_pipeline = build_powerschool_dlt_pipeline(code_location)
```

1. Replace the factory docstring's first two paragraphs with:

```python
    """Build ONE two-mode @dlt_assets over all PowerSchool tables.

    The selection decision belongs to the caller: the intraday sensor probes,
    gates, and passes per-table signatures via run config (`probe`); the
    nightly schedule and manual launches pass no config and get an
    unconditional full refresh. In both modes the op opens the SSH tunnel and
    runs the pipeline over a source narrowed to the run's asset selection — a
    full `replace` load per table — persisting each table's signature to dlt
    resource_state WITH the load (dlt commits state only from extracted
    resources, so failures self-heal: the old baseline survives and the table
    re-selects next tick). See
    docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md.
    """
```

    (keep the existing `max_extract_workers` paragraph as-is).

1. Replace the op body between the `selected = [...]` assignment and the
   `dlt_pipeline.collector = ...` line (i.e. delete the `sync_destination`
   try/except, the `_stored_signatures` call, the probe loop, the
   `_compute_changed` call, the probe log line, and the `if not changed`
   early-return) so the function reads:

```python
    def _assets(
        context: AssetExecutionContext,
        config: PowerSchoolDltConfig,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> Iterator:
        workers = _resolve_extract_workers(
            context.run.tags.get("dlt_extract_workers"), max_extract_workers
        )
        if workers is not None:
            # Set via dlt's config accessor (an in-memory provider that
            # pipeline.extract() resolves `workers=ConfigValue` from) rather than
            # os.environ — keeps the override inside dlt's config channel instead
            # of mutating the process environment.
            dlt.config["extract.workers"] = workers
            context.log.info(f"dlt extract workers capped at {workers}")

        # Diagnostic knob: Oracle cursor fetch size (rows/round-trip).
        arraysize = int(context.run.tags.get("dlt_arraysize") or 10_000)
        context.log.info(f"dlt oracle arraysize {arraysize}")

        selected = [
            tables_by_key[key]
            for key in context.selected_asset_keys
            if key in tables_by_key
        ]

        with ssh_powerschool.open_ssh_tunnel():
            connection_url = db_powerschool.connection_url()

            if config.probe is not None:
                # Intraday sensor mode: the sensor probed and gated already —
                # persist its signatures with the load, no re-probe.
                signatures: dict[str, dict] = {
                    name: {"count": sig.count, "max_cursor": sig.max_cursor}
                    for name, sig in config.probe.items()
                }
                context.log.info(
                    f"powerschool sensor-selected load: {sorted(signatures)}"
                )
            else:
                # Full-refresh mode (nightly schedule / manual launch): load the
                # whole selection unconditionally. Probe FIRST so fresh baseline
                # signatures persist WITH the load — dlt commits state only from
                # extracted resources, so a post-load write would not round-trip.
                engine = sa.create_engine(connection_url)
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
                context.log.info(
                    f"powerschool full-refresh load: {sorted(signatures)}"
                )

            # Stream dlt's periodic extract/normalize/load progress into the
            # Dagster event log. The factory-built collector defaults to
            # logger="stdout" (step-pod compute logs only); context.log is a
            # DagsterLogManager (a logging.Logger), so pointing the collector at
            # it surfaces progress as structured run events every log_period s.
            dlt_pipeline.collector = LogCollector(
                logger=context.log, log_period=30.0, dump_system_stats=False
            )

            try:
                # fetch_row_count() attaches an authoritative per-table row_count
                # to each materialization's metadata (surfaced in the asset
                # catalog) alongside dagster-dlt's default load metadata.
                yield from dlt.run(
                    context=context,
                    dlt_source=_powerschool_source(
                        selected, signatures, connection_url, arraysize
                    ),
                    dlt_pipeline=dlt_pipeline,
                    dagster_dlt_translator=translator,
                    write_disposition="replace",
                ).fetch_row_count()
            except Exception:
                # Surface dlt's per-table extracted row counts in the run log so a
                # load failure is legible without walking the exception chain.
                trace = dlt_pipeline.last_trace
                if trace is not None and trace.last_normalize_info is not None:
                    context.log.info(
                        "dlt normalize row counts before failure: "
                        f"{trace.last_normalize_info.row_counts}"
                    )
                raise
```

Keep `_stored_signatures` at the bottom of the module (the sensor imports it in
Task 4). `_compute_changed` also stays (the sensor imports it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_dlt_powerschool_assets.py -v`

Expected: all PASS. If `test_run_config_schema_accepts_probe_payload` fails with
a schema error about the `probe` field type, the
`dict[str, ProbeSignatureConfig]` mapping is the problem — fall back to
`probe: dict[str, dict] | None = None` is NOT acceptable (untyped dict isn't a
valid Dagster config leaf); instead nest via
`probe: dict[str, ProbeSignatureConfig] | None` debugging with
`build_powerschool_dlt_assets(...).op.config_schema` printed in a REPL, and if
genuinely unsupported, restructure to two parallel primitive maps
(`probe_counts: dict[str, int] | None`,
`probe_max_cursors: dict[str, str] | None`, with `None` cursor values encoded by
key absence) and update Task 4's `_build_run_request` payload to match.

- [ ] **Step 5: Verify the module still imports and existing factory tests
      pass**

Run:
`uv run pytest tests/libraries/test_dlt_powerschool_assets.py tests/libraries/test_powerschool_dlt_extract_workers.py -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/libraries/dlt/powerschool/assets.py tests/libraries/test_dlt_powerschool_assets.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "refactor(dlt): two-mode powerschool op driven by sensor probe run config"
```

---

### Task 4: Intraday sensor factory

**Files:**

- Create: `src/teamster/libraries/dlt/powerschool/sensors.py`
- Test: `tests/libraries/test_dlt_powerschool_sensors.py` (create)

**Interfaces:**

- Consumes (from `teamster.libraries.dlt.powerschool.assets`):
  `PowerSchoolTable`, `_SOURCE_NAME`, `_asset_key`, `_compute_changed`,
  `_stored_signatures`, `build_powerschool_dlt_pipeline`, `probe_signature`.
- Produces:
  `build_powerschool_dlt_intraday_sensor(code_location: str, tables: list[PowerSchoolTable], nightly_schedule_name: str, minimum_interval_seconds: int = 900) -> SensorDefinition`
  — sensor named `{code_location}__powerschool__dlt__intraday_sensor`, requiring
  resources `ssh_powerschool` + `db_powerschool`. Tasks 5-7 wire it per
  district.
- Also produces the module-level helper
  `_build_run_request(code_location, changed, current) -> RunRequest` (unit
  seam).

- [ ] **Step 1: Write the failing tests**

Create `tests/libraries/test_dlt_powerschool_sensors.py`:

```python
"""Unit tests for the PowerSchool dlt intraday sensor factory (no external deps)."""

from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
from teamster.libraries.dlt.powerschool.sensors import (
    _build_run_request,
    build_powerschool_dlt_intraday_sensor,
)


def test_sensor_factory_shape():
    sensor_def = build_powerschool_dlt_intraday_sensor(
        code_location="kipppaterson",
        tables=[PowerSchoolTable(name="students", cursor_column="transaction_date")],
        nightly_schedule_name=(
            "kipppaterson__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )

    assert sensor_def.name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensor_def.minimum_interval_seconds == 900
    assert sensor_def.required_resource_keys == {"ssh_powerschool", "db_powerschool"}


def test_build_run_request_selects_changed_and_passes_signatures():
    changed = [
        PowerSchoolTable(name="students", cursor_column="transaction_date"),
        PowerSchoolTable(name="gen", cursor_column=None),
    ]
    current = {
        "students": {"count": 43, "max_cursor": "2026-07-16T00:00:00"},
        "gen": {"count": 10, "max_cursor": None},
        # unchanged table present in the probe but not in `changed`:
        "users": {"count": 1, "max_cursor": "2026-07-01T00:00:00"},
    }

    run_request = _build_run_request("kipppaterson", changed, current)

    assert [k.to_user_string() for k in run_request.asset_selection] == [
        "kipppaterson/powerschool/sis/students",
        "kipppaterson/powerschool/sis/gen",
    ]
    assert run_request.run_config == {
        "ops": {
            "kipppaterson__powerschool": {
                "config": {
                    "probe": {
                        "students": {
                            "count": 43,
                            "max_cursor": "2026-07-16T00:00:00",
                        },
                        "gen": {"count": 10, "max_cursor": None},
                    }
                }
            }
        }
    }
    assert run_request.tags["dagster/max_runtime"] == "3600"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/libraries/test_dlt_powerschool_sensors.py -v`

Expected: FAIL — `ModuleNotFoundError: ... sensors`.

- [ ] **Step 3: Implement**

Create `src/teamster/libraries/dlt/powerschool/sensors.py`:

```python
import sqlalchemy as sa
from dagster import (
    DagsterRunStatus,
    RunRequest,
    RunsFilter,
    SensorDefinition,
    SensorEvaluationContext,
    SkipReason,
    sensor,
)

from teamster.libraries.dlt.powerschool.assets import (
    _SOURCE_NAME,
    PowerSchoolTable,
    _asset_key,
    _compute_changed,
    _stored_signatures,
    build_powerschool_dlt_pipeline,
    probe_signature,
)
from teamster.libraries.dlt.powerschool.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource

_IN_FLIGHT_STATUSES = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


def _build_run_request(
    code_location: str,
    changed: list[PowerSchoolTable],
    current: dict[str, dict],
) -> RunRequest:
    """RunRequest for the changed tables, passing their probed signatures.

    The probe payload rides run config (the op's PowerSchoolDltConfig.probe
    field): the op loads exactly this selection and persists these signatures
    with the load — no re-probe, no gate.
    """
    return RunRequest(
        asset_selection=[_asset_key(code_location, table.name) for table in changed],
        run_config={
            "ops": {
                f"{code_location}__powerschool": {
                    "config": {
                        "probe": {table.name: current[table.name] for table in changed}
                    }
                }
            }
        },
        tags={"dagster/max_runtime": "3600"},
    )


def build_powerschool_dlt_intraday_sensor(
    code_location: str,
    tables: list[PowerSchoolTable],
    nightly_schedule_name: str,
    minimum_interval_seconds: int = 900,
) -> SensorDefinition:
    """Build the intraday change-detection sensor for one district.

    Each tick opens the SSH tunnel, probes every intraday table (COUNT(*) +
    MAX(cursor); count-only for no-cursor tables), compares against the
    baseline stored in dlt resource state, and requests a run for only the
    changed tables — unchanged tables are never planned, and an idle tick
    launches nothing. Skips while a run launched by this sensor or by the
    nightly full-refresh schedule is in flight (the baseline advances only on
    load success, so an in-flight table would re-select and double-launch).
    See docs/superpowers/specs/2026-07-20-powerschool-dlt-intraday-sensor-design.md.
    """
    sensor_name = f"{code_location}__powerschool__dlt__intraday_sensor"

    @sensor(
        name=sensor_name,
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=[_asset_key(code_location, table.name) for table in tables],
    )
    def _sensor(
        context: SensorEvaluationContext,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> RunRequest | SkipReason:
        for tag, value in (
            ("dagster/sensor_name", sensor_name),
            ("dagster/schedule_name", nightly_schedule_name),
        ):
            records = context.instance.get_run_records(
                filters=RunsFilter(tags={tag: value}, statuses=_IN_FLIGHT_STATUSES),
                limit=1,
            )
            if records:
                return SkipReason(
                    f"run {records[0].dagster_run.run_id} in flight ({value})"
                )

        dlt_pipeline = build_powerschool_dlt_pipeline(code_location)

        with ssh_powerschool.open_ssh_tunnel():
            connection_url = db_powerschool.connection_url()

            # Restore prior signatures from the destination state table. On a
            # truly first run (no dataset) this raises; treat as no prior state.
            try:
                dlt_pipeline.sync_destination()
            except Exception as e:
                context.log.info(
                    f"dlt sync_destination failed ({e}); treating all tables "
                    "as changed"
                )

            stored = _stored_signatures(dlt_pipeline, _SOURCE_NAME)

            # One shared engine over the single tunnel, like the op's probe.
            engine = sa.create_engine(connection_url)
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

        changed = _compute_changed(tables, current, stored)

        context.log.info(
            f"powerschool probe: {len(changed)}/{len(tables)} changed; "
            f"changed={sorted(table.name for table in changed)}"
        )

        if not changed:
            return SkipReason(f"no change across {len(tables)} probed tables")

        return _build_run_request(code_location, changed, current)

    return _sensor
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/test_dlt_powerschool_sensors.py tests/libraries/test_dlt_powerschool_assets.py -v`

Expected: all PASS. If `required_resource_keys` asserts differently (e.g.
includes extras), print `sensor_def.required_resource_keys` and adjust the
assertion to the actual resource-param set — it must contain exactly the two
resources the sensor function declares.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/libraries/dlt/powerschool/sensors.py tests/libraries/test_dlt_powerschool_sensors.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "feat(dlt): powerschool intraday change-detection sensor factory"
```

---

### Task 5: Migrate `kippnewark`

**Files:**

- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/schedules.py`
- Create:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/sensors.py`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/__init__.py`,
  `src/teamster/code_locations/kippnewark/powerschool/sis/__init__.py`,
  `src/teamster/code_locations/kippnewark/powerschool/__init__.py`,
  `src/teamster/code_locations/kippnewark/definitions.py`

**Interfaces:**

- Consumes: `build_powerschool_dlt_intraday_sensor` (Task 4).
- Produces: `powerschool.sensors` list re-exported to `definitions.py`; the YAML
  membership schema (`table_name` / `cursor_column` / `intraday: bool` /
  `nightly: bool`) that Tasks 6-7 replicate.

- [ ] **Step 1: Write the YAML migration script (shared by Tasks 5-7)**

Write `.claude/scratch/migrate_ps_dlt_config.py` in the worktree (`mkdir -p` the
directory first; it is gitignored):

```python
"""Rewrite a powerschool dlt assets.yaml from schedule_tier to membership booleans.

Rule: intraday tier -> intraday only; nightly tier with a cursor (gradebook
cluster) -> nightly only; nightly tier without a cursor -> both (count-gated
intraday, authoritative nightly full refresh).
"""

import sys

import yaml

entries = yaml.safe_load(open(sys.argv[1]))["assets"]


def flags(entry):
    if entry["schedule_tier"] == "intraday":
        return True, False
    if entry["cursor_column"] is None:
        return True, True
    return False, True


groups = [
    ("intraday only: cursor-gated by the sensor", (True, False)),
    (
        "intraday + nightly: no cursor — count-gated intraday, "
        "authoritative nightly full refresh",
        (True, True),
    ),
    ("nightly only: gradebook cluster, full-refreshed nightly", (False, True)),
]

lines = ["assets:"]
for comment, membership in groups:
    members = sorted(
        (e for e in entries if flags(e) == membership),
        key=lambda e: e["table_name"],
    )
    if not members:
        continue
    lines.append(f"  # {comment}")
    for e in members:
        intraday, nightly = flags(e)
        cursor = e["cursor_column"] if e["cursor_column"] is not None else "null"
        lines.append(f"  - table_name: {e['table_name']}")
        lines.append(f"    cursor_column: {cursor}")
        lines.append(f"    intraday: {str(intraday).lower()}")
        lines.append(f"    nightly: {str(nightly).lower()}")

print("\n".join(lines))
```

- [ ] **Step 2: Migrate the kippnewark YAML**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
mkdir -p .claude/scratch
cfg=src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml
uv run python .claude/scratch/migrate_ps_dlt_config.py "$cfg" > "$cfg.new" && mv "$cfg.new" "$cfg"
```

Verify membership counts (expected output
`57 {(True, False): 27, (True, True): 18, (False, True): 12}`):

```bash
uv run python -c "
import yaml
from collections import Counter
entries = yaml.safe_load(open('src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml'))['assets']
print(len(entries), dict(Counter((e['intraday'], e['nightly']) for e in entries)))
"
```

- [ ] **Step 3: Rewrite `schedules.py`**

Replace the full contents of
`src/teamster/code_locations/kippnewark/powerschool/sis/dlt/schedules.py` with:

```python
import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())


def _nightly_targets() -> list[str]:
    assets = config["assets"]

    orphaned = [a["table_name"] for a in assets if not (a["intraday"] or a["nightly"])]
    if orphaned:
        raise ValueError(
            "table(s) in neither tier (would never materialize): "
            + ", ".join(orphaned)
        )

    return [
        f"{CODE_LOCATION}/powerschool/sis/{a['table_name']}"
        for a in assets
        if a["nightly"]
    ]


# Unconditional full refresh + re-baseline (the op's no-probe mode): the
# authoritative sweep that catches in-place edits the intraday count gate
# cannot see on no-cursor tables.
powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_nightly_targets(),
    tags={"dagster/max_runtime": "3600"},
)

schedules = [powerschool_dlt_nightly_asset_job_schedule]
```

- [ ] **Step 4: Create `sensors.py`**

Create `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/sensors.py`:

```python
import pathlib

import yaml

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
from teamster.libraries.dlt.powerschool.sensors import (
    build_powerschool_dlt_intraday_sensor,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

sensors = [
    build_powerschool_dlt_intraday_sensor(
        code_location=CODE_LOCATION,
        tables=[
            PowerSchoolTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
            if a["intraday"]
        ],
        nightly_schedule_name=(
            f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )
]
```

- [ ] **Step 5: Wire the re-export chain**

Replace `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/__init__.py`
with:

```python
from teamster.code_locations.kippnewark.powerschool.sis.dlt import (
    assets,
    schedules,
    sensors,
)

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
```

Replace `src/teamster/code_locations/kippnewark/powerschool/sis/__init__.py`
with:

```python
from teamster.code_locations.kippnewark.powerschool.sis import dlt

assets = [*dlt.assets.assets]

schedules = [*dlt.schedules.schedules]

sensors = [*dlt.sensors.sensors]

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
```

Replace `src/teamster/code_locations/kippnewark/powerschool/__init__.py` with:

```python
from teamster.code_locations.kippnewark.powerschool.sis import (
    assets,
    schedules,
    sensors,
)

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
```

In `src/teamster/code_locations/kippnewark/definitions.py`, add
`*powerschool.sensors,` to the `sensors=[...]` list (alphabetical placement
among the existing `*<module>.sensors` entries).

- [ ] **Step 6: Verify by import**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
uv run python -c "
from teamster.code_locations.kippnewark import powerschool
assert len(powerschool.schedules) == 1
assert powerschool.schedules[0].name == 'kippnewark__powerschool__dlt__nightly_asset_job_schedule'
assert len(powerschool.sensors) == 1
assert powerschool.sensors[0].name == 'kippnewark__powerschool__dlt__intraday_sensor'
print('kippnewark ok')
"
```

Expected: `kippnewark ok`. Also re-run the library suites:
`uv run pytest tests/libraries/test_dlt_powerschool_assets.py tests/libraries/test_dlt_powerschool_sensors.py -q`
— all PASS (they read the kipppaterson config, untouched here).

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/code_locations/kippnewark
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "refactor(kippnewark): powerschool dlt intraday sensor replaces intraday schedule"
```

---

### Task 6: Migrate `kippcamden`

**Files:** the exact `kippcamden` counterparts of every Task 5 file.

**IMPORTANT — read Task 5 of this plan file
(`docs/superpowers/plans/2026-07-20-powerschool-dlt-intraday-sensor.md`) before
starting: this task reuses Task 5's exact file contents and commands with
`kippnewark` → `kippcamden` substituted, and they are not repeated here.**

**Interfaces:** identical to Task 5 with `kippnewark` → `kippcamden` in every
path, import, and name. Camden's table set matches Newark's (57 tables: 27
intraday-only / 18 both / 12 nightly-only).

- [ ] **Step 1: Migrate the YAML**

Same commands as Task 5 Step 2 with
`cfg=src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml`.
Expected count check output:
`57 {(True, False): 27, (True, True): 18, (False, True): 12}`.

- [ ] **Step 2: Rewrite `schedules.py`, create `sensors.py`, wire `__init__.py`
      chain and `definitions.py`**

Apply the exact Task 5 Steps 3-5 file contents with every occurrence of
`kippnewark` replaced by `kippcamden` (module paths and imports only — the
schedule/sensor name templates already derive from `CODE_LOCATION`). The
existing camden files are byte-identical to Newark's apart from the import line,
so the replacements are mechanical.

- [ ] **Step 3: Verify by import**

Same check as Task 5 Step 6 with `kippnewark` → `kippcamden` (assert names
`kippcamden__powerschool__dlt__nightly_asset_job_schedule` /
`kippcamden__powerschool__dlt__intraday_sensor`). Expected: `kippcamden ok`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/code_locations/kippcamden
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "refactor(kippcamden): powerschool dlt intraday sensor replaces intraday schedule"
```

---

### Task 7: Migrate `kipppaterson` + rewrite config-coupled tests

**Files:**

- Modify: the exact `kipppaterson` counterparts of every Task 5 file.
- Modify: `tests/libraries/test_dlt_powerschool_assets.py` (config-schema and
  schedule tests read the paterson config)
- Modify: `tests/assets/test_powerschool_dlt_paterson_defs.py` (also fixes two
  PRE-EXISTING failures: it asserts asset keys without the `sis` segment)

**IMPORTANT — read Task 5 of this plan file
(`docs/superpowers/plans/2026-07-20-powerschool-dlt-intraday-sensor.md`) before
starting: Step 1 reuses Task 5's exact file contents and commands with
`kippnewark` → `kipppaterson` substituted, and they are not repeated here.**

**Interfaces:** identical to Task 5 with `kippnewark` → `kipppaterson`. Paterson
has 48 tables: 23 intraday-only / 14 both / 11 nightly-only.

- [ ] **Step 1: Migrate the YAML and code files**

Apply Task 5 Steps 2-5 with `kipppaterson` substituted. Expected YAML count
check output: `48 {(True, False): 23, (True, True): 14, (False, True): 11}`.

- [ ] **Step 2: Rewrite the paterson-coupled tests in
      `tests/libraries/test_dlt_powerschool_assets.py`**

The module-level table-name sets (`INTRADAY_TRANSACTION_DATE`,
`INTRADAY_WHENMODIFIED`, `NIGHTLY_WHENMODIFIED`, `NIGHTLY_NO_CURSOR`) stay
as-is. Replace `test_config_matches_spec_cursor_map` with:

```python
def test_config_matches_spec_membership_map():
    entries = yaml.safe_load(CONFIG.read_text())["assets"]
    by_name = {e["table_name"]: e for e in entries}

    assert len(entries) == 48

    for name in INTRADAY_TRANSACTION_DATE:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "transaction_date",
            "intraday": True,
            "nightly": False,
        }
    for name in INTRADAY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "intraday": True,
            "nightly": False,
        }
    for name in NIGHTLY_WHENMODIFIED:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": "whenmodified",
            "intraday": False,
            "nightly": True,
        }
    for name in NIGHTLY_NO_CURSOR:
        assert by_name[name] == {
            "table_name": name,
            "cursor_column": None,
            "intraday": True,
            "nightly": True,
        }
```

Replace `test_schedules_subset_by_tier` with:

```python
def test_nightly_schedule_and_intraday_sensor():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        powerschool_dlt_nightly_asset_job_schedule as nightly,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        schedules,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.sensors import (
        sensors,
    )

    assert schedules == [nightly]
    assert nightly.cron_schedule == "0 2 * * *"
    assert nightly.tags == {"dagster/max_runtime": "3600"}
    assert sensors[0].name == "kipppaterson__powerschool__dlt__intraday_sensor"
    assert sensors[0].minimum_interval_seconds == 900
```

Replace `test_tier_targets_sis_keys_and_counts` with:

```python
def test_nightly_targets_sis_keys_and_counts():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        _nightly_targets,
    )

    nightly = _nightly_targets()

    assert len(nightly) == 25
    assert all(t.startswith("kipppaterson/powerschool/sis/") for t in nightly)
    assert "kipppaterson/powerschool/sis/teachercategory" in nightly
    assert "kipppaterson/powerschool/sis/test" in nightly
    assert "kipppaterson/powerschool/sis/students" not in nightly
```

- [ ] **Step 3: Rewrite `tests/assets/test_powerschool_dlt_paterson_defs.py`**

Replace the full file contents with (fixes the pre-existing missing-`sis`
failures and covers the new trigger split):

```python
from dagster import AssetKey, ScheduleDefinition


def test_paterson_powerschool_dlt_asset_keys():
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import assets
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    assert len(config["assets"]) == 48

    keys = {key for a in assets.assets for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", "sis", a["table_name"]])
        for a in config["assets"]
    }


def test_paterson_powerschool_dlt_triggers():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules,
        sensors,
    )

    by_name = {s.name: s for s in schedules.schedules}

    nightly = by_name["kipppaterson__powerschool__dlt__nightly_asset_job_schedule"]

    assert isinstance(nightly, ScheduleDefinition)
    assert nightly.cron_schedule == "0 2 * * *"
    assert len(schedules.schedules) == 1  # intraday schedule replaced by sensor

    (sensor_def,) = sensors.sensors
    assert sensor_def.name == "kipppaterson__powerschool__dlt__intraday_sensor"


def test_paterson_powerschool_dlt_triggers_cover_every_table():
    """Every configured table belongs to at least one trigger.

    A table with both membership flags false would silently never
    materialize (the dlt assets carry no automation condition). The overlap
    between tiers must be exactly the no-cursor set: count-gated intraday,
    authoritative overnight.
    """
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules as schedules_module,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    def key(name):
        return f"kipppaterson/powerschool/sis/{name}"

    expected = {key(a["table_name"]) for a in config["assets"]}
    intraday = {key(a["table_name"]) for a in config["assets"] if a["intraday"]}
    no_cursor = {
        key(a["table_name"])
        for a in config["assets"]
        if a["cursor_column"] is None
    }

    # Resolve nightly targets through the real scheduling function — the exact
    # code an orphaned membership would route around.
    nightly = set(schedules_module._nightly_targets())

    assert intraday | nightly == expected
    assert intraday & nightly == no_cursor
```

- [ ] **Step 4: Run all affected tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
uv run pytest tests/libraries/test_dlt_powerschool_assets.py \
  tests/libraries/test_dlt_powerschool_sensors.py \
  tests/assets/test_powerschool_dlt_paterson_defs.py -v
```

Expected: all PASS (including the two previously-failing paterson key tests).
Also run the paterson import check (Task 5 Step 6 pattern with `kipppaterson`).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/code_locations/kipppaterson tests/libraries/test_dlt_powerschool_assets.py tests/assets/test_powerschool_dlt_paterson_defs.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "refactor(kipppaterson): powerschool dlt intraday sensor replaces intraday schedule"
```

---

### Task 8: Documentation

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/CLAUDE.md`,
  `src/teamster/code_locations/kippcamden/CLAUDE.md`,
  `src/teamster/code_locations/kipppaterson/CLAUDE.md`
- Modify: `src/teamster/libraries/dlt/CLAUDE.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update the three district CLAUDE.mds**

In each district's Active Integrations table, change the `powerschool` row's
Trigger cell from `schedules (intraday 15-min + nightly 2am)` (or that
district's equivalent wording) to
`sensor (intraday probe, 15-min) + schedule (nightly 2am full-refresh)`.

In each district's "PowerSchool Configuration" section, update the config
description: `per-table cursor_column + schedule_tier` becomes
`per-table cursor_column + intraday/nightly membership booleans`, and add one
sentence: "Intraday selection is decided by
`{loc}__powerschool__dlt__intraday_sensor` (probe + dlt-state baseline); the
nightly schedule full-refreshes its targets unconditionally and re-baselines."
Read each file first — camden/paterson wording may differ slightly from
newark's.

- [ ] **Step 2: Update `src/teamster/libraries/dlt/CLAUDE.md`**

In the `powerschool/` sub-library section, replace the first paragraph
(`Loads PowerSchool SIS Oracle tables ... asset keys ...`) with:

```markdown
Loads PowerSchool SIS Oracle tables to BigQuery over an SSH tunnel
(`table_rows` + PyArrow), full-replace. Change detection lives in the intraday
sensor, not the op. Factories:
`build_powerschool_dlt_assets(code_location, tables, op_tags=None, max_extract_workers=None)`
and
`build_powerschool_dlt_intraday_sensor(code_location, tables, nightly_schedule_name, minimum_interval_seconds=900)`
(`sensors.py`); asset keys `[code_location, "powerschool", "sis", table]`.

- **Op run-config contract** (`PowerSchoolDltConfig`): `probe` present (intraday
  sensor) → load exactly the run's asset selection with the passed per-table
  signatures — no re-probe, no gate. `probe` absent (nightly schedule / manual
  launch) → probe the selection once BEFORE the load (count-only for no-cursor
  tables), then load it all unconditionally. Signatures always persist WITH the
  load via `resource_state` (dlt commits state only from extracted resources —
  post-load writes never round-trip), so a failed load keeps the old baseline
  and the table re-selects next tick.
- **Signature shape is normalized**: `probe_signature` always returns
  `{"count": n, "max_cursor": value-or-None}` — a count-only dict would never
  compare equal to the run-config round-trip (which defaults `max_cursor` to
  None) and no-cursor tables would reload every tick.
- **Sensor tick**: skip if a sensor-launched or nightly-schedule run is in
  flight (via `dagster/sensor_name` / `dagster/schedule_name` run tags); probe
  every intraday table over one engine; compare to the dlt-state baseline
  (`sync_destination()` + `_stored_signatures`); request only changed tables
  with the probe payload in run config. Idle ticks launch nothing, so unchanged
  tables are never planned (no `ASSET_FAILED_TO_MATERIALIZE`).
```

Keep the existing `DPY-4011` bullet and everything after it unchanged.

- [ ] **Step 2b: Lint the edited markdown**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/code_locations/kippnewark/CLAUDE.md \
  src/teamster/code_locations/kippcamden/CLAUDE.md \
  src/teamster/code_locations/kipppaterson/CLAUDE.md \
  src/teamster/libraries/dlt/CLAUDE.md </dev/null
```

Expected: no NEW issues on these files. Fix any MD040/MD001/MD036 findings.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  add src/teamster/code_locations/kippnewark/CLAUDE.md src/teamster/code_locations/kippcamden/CLAUDE.md src/teamster/code_locations/kipppaterson/CLAUDE.md src/teamster/libraries/dlt/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor \
  commit -m "docs: powerschool dlt intraday sensor + membership config"
```

Note: `docs/reference/automations.md` is GENERATED and cannot be regenerated in
the codespace (kipptaf/kippmiami fail to import) — do NOT hand-edit it. Flag the
deferred regeneration in the PR body.

---

### Task 9: Full verification

**Files:** none created; verification only.

- [ ] **Step 1: Run the full affected test set**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
uv run pytest tests/libraries/test_dlt_powerschool_assets.py \
  tests/libraries/test_dlt_powerschool_sensors.py \
  tests/libraries/test_powerschool_dlt_extract_workers.py \
  tests/assets/test_powerschool_dlt_paterson_defs.py -v
```

Expected: all PASS.

- [ ] **Step 2: Validate definitions for the three districts**

The manifest is required first, then validate (per `src/teamster/CLAUDE.md`; run
in the worktree — `kippnewark` and `kippcamden` are known to import cleanly with
the manifest, paterson likewise loads district modules):

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
for loc in kippnewark kippcamden kipppaterson; do
  uv run dagster-dbt project prepare-and-package --file "src/teamster/code_locations/$loc/__init__.py"
  uv run dagster definitions validate -m "teamster.code_locations.$loc.definitions"
done
```

Expected: `Success` per location. If validate fails on missing env vars
unrelated to this change, fall back to
`uv run python -c "import teamster.code_locations.<loc>.definitions"` per the
repo guidance and confirm the error predates this branch.

- [ ] **Step 3: Trunk-check every changed file**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
git diff --name-only origin/main...HEAD | xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Expected: no new findings. Fix and amend/commit as needed.

- [ ] **Step 4: Run the wider unit suite for regressions**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-dlt-intraday-sensor
uv run pytest tests/libraries tests/schedules -q
```

Expected: no failures introduced by this branch (compare any failure against
`main` before attributing it here; the SSH suites exceed the 120s Bash timeout —
use `run_in_background` if they are included).

- [ ] **Step 5: Commit any stragglers**

Only if Steps 1-4 produced fixes; otherwise nothing to commit.

---

## Post-merge cutover checklist (not plan-executable)

These need prod access and happen after the PR merges and the three locations
deploy:

1. Confirm each location's post-merge deploy LOADED
   (`mcp__dagster__get_location_load_history`).
2. Start each sensor (`{loc}__powerschool__dlt__intraday_sensor`) via
   `mcp__dagster__start_sensor` (preview with `confirm=False` first) — repo
   sensors carry no `default_status`, so they deploy stopped; the nightly
   schedule covers freshness until started.
3. Watch the first ticks (`mcp__dagster__get_tick_history`): expect a first run
   selecting all no-cursor tables (no stored baseline yet — one-time), then
   `SkipReason` idle ticks. Measure tick duration against the 600s sensor-tick
   cap (spec risk: `COUNT(*)` on `studenttestscore`/`testscore`/`log`).
4. Confirm an idle tick plans nothing and a changed table materializes; verify
   `kippnewark/powerschool/sis/attendance`'s DEGRADED badge clears on its next
   real materialization.
5. Branch-deployment caveat if validating pre-merge: the dlt dataset is NOT
   branch-isolated — validate via probe/tick logs, not real branch loads.
