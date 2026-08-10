# Focus dlt: probe-gated sync design

Issue: [#4447](https://github.com/TEAMSchools/teamster/issues/4447)

## Context

The PowerSchool dlt factory (`src/teamster/libraries/dlt/powerschool/`, landed
via #4415 and #4427) established a probe-gated incremental sync style:

- one `@dlt_assets` multi-asset over all tables, with a per-table
  `cursor_column`
- a `COUNT(*)` + `MAX(cursor)` change signature stored in dlt `resource_state`
- a full `replace` load only on signature drift
- gating in a **sensor**, so unchanged tables are never planned into a run
- parallel extract via the exported `table_rows` generator
- dlt progress streamed into the Dagster event log

`kippnewark__powerschool__dlt__intraday_sensor` runs this pattern in prod today
at a 900-second interval.

Focus (`src/teamster/libraries/dlt/focus/` +
`src/teamster/code_locations/kippmiami/dlt/focus/`) predates it: one asset
factory call per table — 77 separate ops — each an unconditional full `replace`,
all reloaded by the `0 4 * * *` / `0 12 * * *` / `0 14 * * *` schedule
regardless of upstream change.

### Why gating must live in a sensor, not the op

A `replace` resource that yields zero rows **truncates** its destination table,
so a table cannot be skipped from inside a run by yielding nothing. Excluding it
means excluding it from the run entirely. Gating inside the op would also plan
all 77 assets on every tick and emit `ASSET_FAILED_TO_MATERIALIZE` for the ones
it declined to load — the precise noise the PowerSchool design moved to a sensor
to avoid.

## Goal

Adopt the probe-gated style for Focus:

- consolidate the 77 per-table assets into one probe-gated multi-asset over the
  `public` schema
- keep asset keys (`[kippmiami, dlt, focus, table]`) and the
  `dagster_kippmiami_dlt_focus` dataset unchanged, so no dbt source edits are
  needed
- share the probe/signature helpers with the powerschool library by extracting
  them to a new module, not by copying
- run intraday at near-zero idle cost

## Non-goals

- Changing `autodetect_schema=True` on the BigQuery destination (see _Decisions_
  below).
- Migrating Illuminate (#4446). The shared module is written to serve it, but
  Illuminate is a separate change.
- A generic sensor factory shared across dlt libraries.
- Revisiting the `_dlt_id` / `_dlt_load_id` empty-table machinery from #4740.

## Findings that shaped the design

Verified against `dagster_kippmiami_dlt_focus` on 2026-08-10:

| Fact                                             | Value          |
| ------------------------------------------------ | -------------- |
| Tables in `config/focus.yaml`                    | 77             |
| Tables landed in `dagster_kippmiami_dlt_focus`   | 77 (exact 1:1) |
| Tables carrying an `updated_at` TIMESTAMP column | 75             |
| Tables without one                               | 2              |

The two exceptions are `co_teachers` and `login_history`. Cursor assignment is
therefore mechanical — `updated_at` almost everywhere — and needs no per-table
schema archaeology.

## Decisions

| Decision            | Choice                                                                                             | Why                                                                                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Intraday trigger    | Sensor at 900s replaces the 12:00 and 14:00 crons; `0 4 * * *` stays an unconditional full refresh | PowerSchool parity. The 04:00 tier is the backstop for any table whose `updated_at` the Focus app does not reliably bump.                                                          |
| Asset granularity   | One multi-asset over all 77 tables                                                                 | Template parity, and it removes a latent state race (below).                                                                                                                       |
| `autodetect_schema` | Leave `True`                                                                                       | Load-bearing with `loader_file_format="parquet"` for the 0-row truncate path (#4733); flipping it against 77 populated tables invites schema-migration failures. Out of scope.     |
| Shared module scope | Pure helpers only                                                                                  | PowerSchool needs an SSH tunnel plus an Oracle resource; Focus needs a plain Postgres URL. Two consumers with different connection lifecycles do not justify an indirection layer. |

### Freshness effect on the 12:45 delivery

`schedules.py` documents that the 12:00 pull refreshes the live-Focus snapshot
the `rpt_focus__*` import-once anti-joins read, and that the 12:45 delivery
leans on that pull finishing (observed 4-7 minutes against a 45-minute budget).

Replacing the two intraday crons with a 900-second sensor makes that snapshot
**fresher**, not staler: a change in Focus is picked up within 15 minutes
instead of waiting for the next of two fixed times. When nothing changed in
Focus, no import happened, so the existing snapshot is still valid and skipping
the load is correct. This does retire a clock-pinned timing contract in favor of
a continuous one; the 04:00 full refresh still guarantees tomorrow's delivery
regardless.

### The latent state race consolidation fixes

All 77 current ops construct pipelines sharing `pipeline_name="focus"` and one
dataset, so they share one `_dlt_pipeline_state` row. No state is written today,
so nothing races. The moment per-table signatures are written, 77 concurrent ops
would race on that state. One op removes the race by construction.

## Architecture

### File layout

| File                                                                                          | Change                                                     |
| --------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `libraries/dlt/probe.py`                                                                      | new — shared probe/gate helpers                            |
| `libraries/dlt/focus/assets.py`                                                               | one two-mode `@dlt_assets` replacing the per-table factory |
| `libraries/dlt/focus/sensors.py`                                                              | new — probe-gated intraday sensor                          |
| `libraries/dlt/powerschool/assets.py`, `sensors.py`                                           | import the shared helpers; drop the local copies           |
| `code_locations/{kippnewark,kippcamden,kipppaterson}/powerschool/sis/dlt/{assets,sensors}.py` | rename `PowerSchoolTable` to `ProbeTable`                  |
| `tests/libraries/test_dlt_powerschool_{assets,sensors}.py`                                    | same rename                                                |
| `code_locations/kippmiami/dlt/focus/assets.py`                                                | one factory call over the table list                       |
| `code_locations/kippmiami/dlt/focus/schedules.py`                                             | cron trimmed to `0 4 * * *`; schedule name unchanged       |
| `code_locations/kippmiami/dlt/focus/sensors.py`                                               | new                                                        |
| `code_locations/kippmiami/dlt/focus/__init__.py`                                              | export `sensors`                                           |
| `code_locations/kippmiami/dlt/focus/config/focus.yaml`                                        | `cursor_column` on all 77 entries                          |
| `code_locations/kippmiami/definitions.py`                                                     | register the Focus sensor                                  |
| `libraries/dlt/CLAUDE.md`, `libraries/dlt/focus/CLAUDE.md`                                    | document the new contract                                  |

### `libraries/dlt/probe.py`

Moves out of `powerschool/assets.py` unchanged in behavior, made public:

| Symbol                 | Role                                                               |
| ---------------------- | ------------------------------------------------------------------ |
| `ProbeTable`           | frozen dataclass: `name`, `cursor_column: str \| None`             |
| `ProbeSignatureConfig` | Dagster `Config` for one table's signature (`count`, `max_cursor`) |
| `probe_signature`      | `COUNT(*)` + `MAX(cursor)` for one table, JSON-safe scalars        |
| `compute_changed`      | select tables whose probed signature differs from the stored one   |
| `stored_signatures`    | read per-resource signatures out of dlt pipeline state             |
| `in_flight_run`        | first non-terminal run launched by a given sensor or schedule      |

Notes:

- `probe_signature` keeps its normalized return shape,
  `{"count": n, "max_cursor": value-or-None}`. A count-only dict would never
  compare equal to the run-config round-trip, which defaults `max_cursor` to
  `None`, and no-cursor tables would reload every tick.
- No `schema` parameter. PowerSchool reaches its tables through Oracle
  synonym/default-schema resolution, and Focus's `public` is on the default
  Postgres `search_path`, so unqualified raw SQL is correct for both. Reflection
  still passes the schema explicitly via `sa.MetaData(schema=...)`, which is a
  separate path.
- `PowerSchoolTable` is **renamed**, not aliased. An alias would leave two names
  for one thing; the rename is 8 mechanical call sites.

### Focus assets: one two-mode multi-asset

`build_focus_dlt_assets(sql_database_credentials, code_location, tables, op_tags=None)`
builds one `@dlt_assets` named `{code_location}__dlt__focus`.

`FocusDltConfig` gains `probe: dict[str, ProbeSignatureConfig] | None` and
**keeps** `refresh: str | None` plus its `REFRESH_MODES` guard — that is the
one-time migration knob from #4740 and is orthogonal to gating.

Two modes:

| `probe` | Trigger                        | Behavior                                                                                                                   |
| ------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| present | intraday sensor                | Load exactly the run's asset selection, persisting the passed signatures. No re-probe, no gate — the sensor already gated. |
| absent  | 04:00 schedule / manual launch | Probe the selection once **before** the load, then load it all unconditionally with fresh baselines.                       |

The probe runs before the load in full-refresh mode because dlt commits state
only from resources actually extracted into the load package — a post-load write
would not round-trip.

Each signature is written at the top of its resource body via
`dlt.current.resource_state()["signature"] = signature`, so it persists with the
load. A failed load therefore keeps the old baseline and the table re-selects on
the next tick: failures self-heal.

Preserved unchanged from the current factory:

- `dlt.mark.materialize_table_schema()` when `table_rows` yielded no data
  (#4740)
- `interval_to_microseconds_adapter`, `remove_nullability_adapter`,
  `reflection_level="full_with_precision"`
- the two `normalize.parquet_normalizer.add_dlt_*` knobs set in the op body
- `loader_file_format="parquet"` and `write_disposition="replace"`
- `autodetect_schema=True`, `dataset_name`, `pipeline_name="focus"`
- asset keys, `group_name="focus"`, `pool=f"dlt_focus_{code_location}"`

Two small additions mirroring powerschool:

- `_asset_key(code_location, table_name)` becomes the single source of truth for
  the key shape, used by the translator, the sensor's `asset_selection`, and the
  sensor's `RunRequest`.
- `build_focus_dlt_pipeline(code_location)` is extracted so the sensor can read
  pipeline state without duplicating destination config.
- The op repoints the pipeline's collector at `context.log`
  (`LogCollector(logger=context.log, log_period=30.0, dump_system_stats=False)`).
  Today's 77 short ops each log progress to stdout, which is tolerable; one op
  loading up to 77 tables would go dark in the Dagster UI for the whole load, so
  stdout-only progress becomes a real regression at this granularity.

No `max_extract_workers` parameter. PowerSchool caps extract workers to avoid
saturating a single SSH tunnel (DPY-4011); Focus connects directly, and dlt's
default of 5 concurrent extracts is comparable to today's pool-bounded
concurrency across separate step pods.

### Focus sensor

`build_focus_dlt_intraday_sensor(code_location, tables, sql_database_credentials, nightly_schedule_name, minimum_interval_seconds=900)`
builds `{code_location}__dlt__focus__intraday_sensor` with `asset_selection`
covering all 77 assets.

Per tick:

1. Return `SkipReason` if `in_flight_run` finds a non-terminal run launched by
   this sensor or by the nightly schedule. The baseline advances only on load
   success, so an in-flight table would re-select and double-launch.
1. `sync_destination()` to restore state from the destination, then
   `stored_signatures()`. A failure here is logged at warning and treated as no
   prior state — expected only on a brand-new dataset, and a persistent failure
   would full-reload every table every tick, so it must be visible.
1. Probe all tables over one shared engine.
1. `compute_changed()`; `SkipReason` if empty.
1. Otherwise one `RunRequest` whose `asset_selection` is the changed tables and
   whose run config carries their probed signatures under
   `ops.{code_location}__dlt__focus.config.probe`, tagged
   `dagster/max_runtime: 3600`.

Unlike powerschool's sensor, this one takes resolved credentials as a plain
value, matching how the Focus code location already resolves them at import.

### Config

`config/focus.yaml` gains `cursor_column` on every entry: `updated_at` for 75
tables, `null` for `co_teachers` and `login_history`. New tables added during
the Miami rollout declare a cursor as they are added.

## Partially resolved risk: `resource_state` on a 0-row table

**Mechanics verified via a unit test; the real BigQuery round-trip is still
open.**
`tests/libraries/test_dlt_focus_signature_state.py::test_empty_table_persists_its_signature`
proves that dlt commits `resource_state` for a resource that yields only
reflection hints plus `dlt.mark.materialize_table_schema()` — it seeds a sqlite
source (standing in for Focus Postgres, which sits behind an IP allowlist
unreachable from the codespace) and calls only `pipeline.extract()`. That
exercises dlt's in-memory state-commit code path but not a load through the real
BigQuery `_dlt_loads` / `_dlt_pipeline_state` tables. Whether the same mechanics
holds end-to-end through the actual destination is not answerable from the
codespace.

- If it round-trips through BigQuery as it does over sqlite: the table's
  signature is `{count: 0, max_cursor: null}`, it gates out from the second tick
  onward, and the acceptance criteria hold as written.
- If it does not: the table has no stored signature, so `compute_changed`
  re-selects it every tick and it re-extracts nothing every 15 minutes. Not
  harmful — the table stays correct — but noisy.

Contingencies, in order of preference, to be applied **only if** step 2 of the
branch-deployment validation shows the state does not commit:

1. Attach the signature to the marker via `dlt.mark.with_hints` so it travels
   the same path that already round-trips for empty tables.
1. Failing that, have the sensor treat "no stored signature, probed count 0, and
   the table already exists in BigQuery" as unchanged.

Neither is built up front.

## Testing

### Unit (codespace, no database)

- Move the existing powerschool helper tests to
  `tests/libraries/test_dlt_probe.py`, covering `probe_signature` shape for
  cursor and no-cursor tables, `compute_changed` drift and missing-baseline
  selection, `stored_signatures` parsing, and `in_flight_run` tag matching.
- New `tests/libraries/test_dlt_focus_sensors.py`, mirroring
  `test_dlt_powerschool_sensors.py`: in-flight skip, no-change skip, and the
  `RunRequest` asset selection plus run-config payload shape.
- Extend the Focus asset tests: the 0-row resource still yields the materialize
  marker, and a resource now also writes its signature to `resource_state`.
- `loader_file_format="parquet"` guard test stays green.

`kippmiami.definitions` cannot be imported in the codespace — it resolves
`FOCUS_DB` credentials eagerly at module load. Use `py_compile` on edited files
plus importing the affected submodule alone, per `src/teamster/CLAUDE.md`.

### Branch deployment

Required: Focus's IP allowlist admits GKE's static egress IP, not the codespace.
Branch-deployment dlt runs write to the **prod** dataset — dlt has no branch
redirect — so the sequence is ordered to minimize prod writes.

1. Sensor left stopped. Evaluate a tick via the Dagster UI's sensor test to
   confirm the probe reaches all 77 tables and reads the baseline. Zero writes.
1. Manual run over roughly three tables including one 0-row table, then
   re-evaluate the tick and confirm they gate out. **This is the step that
   confirms the destination round-trip described above.**
1. Confirm a changed table still produces output identical to today's
   full-replace load.
1. Full 77-table refresh to seed baselines.

## Cutover

1. Merge.
1. Let one `0 4 * * *` full refresh seed every table's baseline.
1. Enable the sensor by hand. It ships `defaultStatus` STOPPED deliberately —
   enabling it before a seeded baseline makes the first tick select all 77
   tables at once.

Rollback is a plain revert. Asset keys, dataset, and destination schema are all
unchanged, so no data repair is needed; the abandoned `signature` keys in dlt
state are inert.

## Acceptance

- An unchanged Focus table is probed but not reloaded, and is absent from the
  run.
- A changed table (signature drift) is fully replaced, with output identical to
  today.
- Asset keys and the destination dataset are unchanged; downstream dbt staging
  models build without source edits.
- The 04:00 schedule keeps its existing Dagster+ identity (same name), so its
  status and tick history survive.
- A 0-row table is handled per _Partially resolved risk_ above.

## Related

- #4446 — Illuminate sibling; `libraries/dlt/probe.py` is written to serve it
- #4427 — PowerSchool dlt migration umbrella, the template this adopts
- #4425 — shared `DagsterDltTranslator` base, natural to do alongside
- #4740 — Focus empty-table materialization and the `_dlt_id` migration
- #4733 — `replace` plus `autodetect_schema` requires parquet load files
