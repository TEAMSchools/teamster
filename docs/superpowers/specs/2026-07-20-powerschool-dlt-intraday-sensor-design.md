# PowerSchool dlt intraday sensor — design

- **Date:** 2026-07-20
- **Issue:** [#4453](https://github.com/TEAMSchools/teamster/issues/4453)
- **Status:** Draft
- **Scope:** `kippnewark` first; library factory generalizes to other districts
  later.

## Problem

The PowerSchool dlt intraday sync runs on a `*/15` `ScheduleDefinition` that
targets every intraday-tier table. The schedule fixes the run's asset selection
_before_ any change detection happens; the op then opens the tunnel, probes each
selected table (`COUNT(*)` + `MAX(cursor)`), and loads only the changed ones via
a narrowed dlt source. Unchanged tables are therefore **planned but never
materialized** on every tick.

Two consequences:

1. **Planning artifacts.** A planned-but-unmaterialized asset emits
   `ASSET_FAILED_TO_MATERIALIZE`. On a normal run this is a benign `SKIPPED`
   (INFO), but when a run is terminated externally it becomes a `FAILED` and the
   asset shows a DEGRADED health badge. Run `4894b6ca` (an externally-killed
   intraday run) left `kippnewark/powerschool/sis/attendance` stuck DEGRADED
   even though its data is intact — the badge only clears on a real
   materialization, which an idle incremental will not produce.
2. **Idle-tick compute.** Every tick launches a full run, step pod, and SSH
   tunnel even when nothing changed. At `*/15` that is 96 runs/day, most of
   which load nothing.

The change-detection logic itself is sound and stays; the problem is _where_ it
runs. Deciding the selection after the plan is fixed is what generates the
artifacts.

## Goals

- Unchanged tables are never planned — no `ASSET_FAILED_TO_MATERIALIZE`, no
  DEGRADED badges from idle ticks.
- Idle ticks launch nothing (no run, pod, or tunnel).
- Run history reflects real work: a run in the timeline means a load happened.
- No-cursor tables gain intraday freshness for row add/remove.
- Failure self-healing is preserved: a table that fails to load is re-selected
  on the next tick.

## Non-goals

- Other districts. `kippnewark` is the first consumer; the factory is written to
  generalize, but wiring other locations is out of scope here.
- Changing the nightly schedule's target set (still the 30 tables it targets
  today) — only its behavior changes to unconditional full-refresh.
- Windowing/partitioning large tables — full-replace remains the load strategy
  (see the dlt `powerschool` CLAUDE.md `DPY-4011` note).

## Current architecture

- [`build_powerschool_dlt_assets`](../../../src/teamster/libraries/dlt/powerschool/assets.py)
  builds one probe-gated `@dlt_assets` multi-asset over all tables. The op
  probes `selected`, computes `changed`, and loads only `changed`; the baseline
  it compares against lives in dlt `resource_state` (persisted in the BigQuery
  `_dlt_pipeline_state` table, restored via `sync_destination()`). dlt commits
  that state **only from a resource actually extracted into a successful load**,
  which is what makes failures self-heal.
- Two `ScheduleDefinition`s subset the multi-asset by `schedule_tier`: intraday
  (`*/15`) and nightly (`0 2`). `config/assets.yaml` carries each table's
  `cursor_column` and `schedule_tier`.

## Proposed architecture

Move change detection into a sensor that requests only the changed tables, so
unchanged tables are never in a run plan. The op keeps loading and writing
signatures, but no longer decides the selection.

### Tiering

| Group                      | Count | Intraday (sensor) gate | Nightly      |
| -------------------------- | ----- | ---------------------- | ------------ |
| Cursor (existing intraday) | 27    | `count` + `max_cursor` | none         |
| No-cursor                  | 18    | `count` only           | full refresh |
| Gradebook FK cluster       | 12    | excluded               | full refresh |

- **Intraday sensor set (45):** the 27 cursor tables plus the 18 no-cursor
  tables.
- **Nightly set (30):** the 18 no-cursor tables plus the 12 gradebook cluster
  tables. Same target as today; the mode changes to unconditional full-refresh.
- **Gradebook FK cluster (12, nightly-only):** `assignmentscore`,
  `assignmentsection`, `assignmentcategoryassoc`, `districtteachercategory`,
  `teachercategory`, `gradecalcformulaweight`, `gradecalcschoolassoc`,
  `gradecalculationtype`, `gradeformulaset`, `gradeschoolconfig`,
  `gradeschoolformulaassoc`, `gradesectionconfig`. Excluded from intraday
  (`assignmentscore` is ~19M rows and its cluster changes throughout the day, so
  intraday full-replaces would be costly).

Cursor tables need no nightly refresh — their `max_cursor` catches in-place
updates intraday. No-cursor tables appear in **both** tiers: intraday `COUNT(*)`
catches net add/remove cheaply, and the nightly full-refresh is the
authoritative sweep that catches in-place edits `COUNT(*)` cannot see.

### Sensor

New library factory
`build_powerschool_dlt_intraday_sensor(code_location, tables, dlt_pipeline, minimum_interval_seconds=900)`
in `libraries/dlt/powerschool/`, wired into `kippnewark`, replacing
`powerschool_dlt_intraday_asset_job_schedule`. Requests resources
`ssh_powerschool`, `db_powerschool`, and `dlt`.

Each tick:

1. Skip if a run for the target job is already in progress or queued (the
   baseline advances only on load success, so an in-flight table would otherwise
   re-select and launch a duplicate).
2. Open the tunnel; probe each intraday table — `COUNT(*)` +
   `MAX(cursor_column)` for cursor tables, `COUNT(*)` only for no-cursor tables.
   Reuses `probe_signature` (extended for the no-cursor case) over one shared
   engine.
3. Read the stored baseline from dlt state (`sync_destination()` then
   `_stored_signatures()` — the same path the op uses today).
4. `changed = _compute_changed(...)` — reused, with no-cursor tables gated on
   `count` drift instead of always-reload.
5. If `changed` is non-empty, emit
   `RunRequest(asset_selection=[changed keys], run_config=<probe payload>, tags={"dagster/max_runtime": "3600"})`.
   Otherwise `SkipReason`.

### Op run-argument contract

The op reads an optional `probe` config value (the probe payload from the
sensor). This one argument drives both modes and removes the gate from the op
entirely — the selection decision now belongs to the sensor (intraday) or is
absent (nightly loads all selected):

- **Probe arg present (intraday):** load exactly `selected_asset_keys` using the
  passed per-table signatures; write those signatures to `resource_state`. No
  re-probe, no gate.
- **Probe arg absent (nightly full-refresh):** load all `selected_asset_keys`
  unconditionally; re-probe the selected set once to write fresh baseline
  signatures (so the next intraday tick has a baseline). No gate.

dlt still commits signatures only on successful load in both modes, preserving
self-healing.

### Config schema

`config/assets.yaml` replaces the single `schedule_tier` enum with explicit
membership so a table can belong to both tiers:

```yaml
assets:
  - table_name: attendance
    cursor_column: transaction_date
    intraday: true # probed by the sensor
    nightly: false # full-refreshed nightly
  - table_name: log
    cursor_column: null
    intraday: true # count-gated
    nightly: true # in-place edits caught overnight
  - table_name: assignmentscore
    cursor_column: whenmodified
    intraday: false
    nightly: true
```

The old validation "intraday tables require a `cursor_column`" is removed — a
no-cursor table may be intraday (count-gated). New validation: every table sets
at least one of `intraday`/`nightly`.

## State and correctness

- **Baseline ownership.** dlt `resource_state` remains the single source of
  truth for the last successfully-loaded signature. The sensor reads it; the op
  writes it on load success. A failed load leaves the old signature, so the
  table re-selects next tick.
- **Overlapping runs.** The in-flight-skip guard prevents duplicate launches
  while a (possibly long) run is committing. The `dlt_powerschool_<loc>` pool
  additionally serializes step execution as a backstop.
- **`COUNT(*)` limits.** Count catches net row add/remove but misses a net-zero
  swap (one insert + one delete) and in-place edits. The nightly full-refresh is
  the authoritative backstop, so no-cursor freshness is "best-effort intraday,
  authoritative overnight."
- **Signature freshness.** The sensor probes at tick time (`T0`); the op stores
  those signatures at load time (`T0 + lag`). A source change in that gap causes
  at most one redundant reload next tick — benign for full-replace.
- **Bootstrap.** With no stored baseline (first tick, or a table new to
  intraday), `_compute_changed` treats the absent baseline as changed, so the
  table loads once and establishes its signature.

## Risks

- **`COUNT(*)` cost** on the larger no-cursor tables (`studenttestscore`,
  `testscore`, `log`) every 15 min over the tunnel is heavier than
  `MAX(indexed_cursor)`. Still expected to be well under the sensor-tick budget,
  but worth measuring on the first branch run.
- **`run_config` size.** The probe payload is at most 45 small entries
  (`{count, max_cursor}`), a few KB of config — within limits, but passed via
  `run_config` (structured), not tags.
- **Sensor probe failures** (tunnel/auth) surface as tick errors, like the
  existing SFTP sensors. The probe path reuses `ssh_powerschool.open_ssh_tunnel`
  and should carry the same retry treatment.

## Cutover

Single deploy: remove `powerschool_dlt_intraday_asset_job_schedule`, add the
sensor (started), switch the nightly schedule to full-refresh mode, and migrate
`config/assets.yaml` to the new membership fields. The intraday schedule and the
sensor must not both run (double loads), so this is one atomic change, not a
staged rollout. Branch-deployment note: the dlt dataset is **not**
branch-isolated (see the dlt CLAUDE.md), so branch testing writes to the prod
dataset — validate via probe/log rather than a real branch load.

## Testing

- **Unit — sensor selection.** Mock the probe and stored signatures; assert the
  `RunRequest.asset_selection` and `run_config` payload for changed tables, the
  `SkipReason` when nothing changed, and the in-flight-skip branch. Reuses
  `_compute_changed` as the tested seam.
- **Unit — no-cursor count gate.** `_compute_changed` selects a no-cursor table
  on count drift and skips it when the count is stable.
- **Unit — op modes.** Probe arg present loads the passed set with passed
  signatures (no re-probe); probe arg absent loads all selected and
  re-baselines.
- **E2E — branch deployment.** Confirm a changed table triggers a run and an
  unchanged tick skips; verify against the shared-dataset caveat above.

## Docs

- Regenerate `docs/reference/automations.md` (new sensor, removed intraday
  schedule) in a full environment where all locations import.
- Update the `kippnewark` CLAUDE.md integration table: PowerSchool trigger
  becomes "sensor (intraday) + schedule (nightly full-refresh)."
- Update the dlt `powerschool` library CLAUDE.md to describe the sensor + op
  run-arg contract.

## Follow-ups

- Generalize the sensor wiring to the other districts as their dlt PowerSchool
  migrations land.
- Revisit the intraday cadence: idle ticks are now probe-only, so a tighter
  interval is cheap on the Dagster side but multiplies the Oracle probe load —
  measure before changing.
