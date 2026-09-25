# CLAUDE.md — `teamster/core/`

Shared infrastructure used by every code location and library. Nothing here is
integration-specific — it is the foundation all other modules build on.

## Files

### `resources.py`

**Env var gotcha**: `DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT` (drives the IO
managers' `teamster-test` redirect) is `"0"` (not absent) in full deployments —
always check `== "1"`, never truthy.

### `io_managers/gcs.py` — `GCSIOManager`

Custom IO manager extending `dagster-gcp`'s `PickledObjectGCSIOManager`. The key
extension is Hive-style partitioned GCS paths:

- **Date/datetime partition keys** → decomposed into
  `_dagster_partition_fiscal_year=YYYY/_dagster_partition_date=YYYY-MM-DD/_dagster_partition_hour=HH/_dagster_partition_minute=MM/data`
- **Non-date partition keys** → `_dagster_partition_key=<value>/data`
- **Multi-partition keys** → concatenated Hive partitions, sorted by dimension
  name

The epoch timestamp (`1970-01-01`) is treated as a resync signal and replaced
with the current timestamp.

Three `object_type` modes: `"pickle"`, `"avro"` (writes Fastavro container
files), `"file"` (writes raw bytes from a local file path). `AvroGCSIOManager`
**always uploads to GCS** (`bucket=teamster-{code_location}`, object path =
asset-key-based); `test=True` only redirects the LOCAL temp dir to
`/tmp/dagster` (not the `dagster-tmp` symlink — causes `FileExistsError`) and
writes a debug JSON — it does NOT change the GCS path. So a pytest
`materialize(..., get_io_manager_gcs_avro(code_location="test", test=True))`
seeds `gs://teamster-test/dagster/<asset_key>/...` — the same path branch
deployments write to.

**Codespace SA can't read prod GCS blobs.** `codespaces@…` lacks
`storage.objects.list/get` (and `buckets.get`) on `teamster-<location>` buckets
— scripts that read Avro blobs 403 from the codespace. Run them where ADC has
GCS perms (locally / in-cluster), not here. Use `client.bucket(name)`, not
`get_bucket(name)`, to skip the `buckets.get` metadata probe.

### `freshness.py`

**`FreshnessPolicy` UI surface**: evaluations do NOT appear on the asset's
Checks tab — state lives on the Overview sidebar's Freshness panel; alerts fire
via Dagster+ "Freshness policy violations" policies, not asset-check alerts. Do
not add `build_last_update_freshness_checks` (it's `@superseded`) to force
Checks-tab visibility.

**`FreshnessPolicy.cron` window**: valid materialization window is
`[deadline - lower_bound_delta, deadline]`. A materialization landing AFTER the
deadline is outside the window. Set `deadline_cron` past the asset's typical
arrival time, not before, or the check flaps FAIL→PASS every cycle.

### `automation_conditions.py`

Four dbt-specific `AutomationCondition` builders, all sharing a common skeleton
via `_build_dbt_condition()`:

- `dbt_view_automation_condition()` — for VIEW models: re-runs on
  `newly_missing`, `code_version_changed`, or `execution_failed`. Intentionally
  omits `any_deps_updated` since views are computed on read.
- `dbt_union_relations_automation_condition()` — for views using the
  `union_relations` macro: adds one trigger to the view condition, firing on the
  tick a parent's post-code-change materialization lands (parent's own code or
  any ancestor's; looks through view parents). Not on the deploy tick, and not
  on data refreshes (no `any_deps_updated`). The trigger resets only on
  `newly_requested`, so a stale in-flight run cannot consume it.
- `dbt_cron_automation_condition(cron_schedule, cron_timezone)` — for expensive
  TABLE models whose consumers refresh on a schedule: replaces the
  ancestor-updated trigger with `cron_tick_passed`. NOT stock `on_cron()` (its
  all-deps-updated gate starves on mixed-cadence upstreams). Opted into per
  model via `meta.dagster.automation_condition.cron_schedule` (tables only; the
  translator ignores it on views). Timezone defaults to the code location's
  `LOCAL_TIMEZONE` via the translator.
- `dbt_table_automation_condition()` — for TABLE models: also triggers on
  upstream data changes, including through intermediate views via
  `_build_any_ancestor_updated()` (recursive `any_deps_match` up to
  `_MAX_VIEW_DEPTH` levels, currently 10)

**Unsynced badge behavior**: Dagster's "unsynced" indicator is driven by its
data versioning system, not the automation condition. When an upstream table
materializes, directly-dependent view assets are marked "unsynced" in the UI
even though the automation condition correctly suppresses any run. There is no
built-in Dagster API to suppress this per-asset.

**Deploy rollover + `code_version_changed` race**: if a run completes during
deploy rollover, the materialization may be stamped with the new deployment's
code version. `code_version_changed()` returns false permanently — manual
materialization is the only fix. See dagster-io/dagster#33708.

**`union_relations` wrapper can still freeze in two edge cases** (#4290): a
parent that reloads and finishes rebuilding within one sensor tick, or a parent
table that does a data rebuild before its changed ancestor rebuilds. Symptom:
downstream reads fail `... failed to parse view` and it does NOT self-heal.
Rematerialize the wrapper + its consumers via `launch_run`. Diagnose by
comparing the wrapper's stored `input_data_version/<upstream>` materialization
tag to the upstream's current `data_version`. `code_version_changed()` is true
for exactly one tick (cursor compare), so never build a gate on it alone.

**No dep-code-version gate**: `_build_dbt_condition()` does NOT block
materialization when a direct dep has
`code_version_changed().since(newly_updated())`. A previous gate did, but the
operator is cursor-based — its SINCE memory could capture phantom "true" state
from any past tick (sensor restart, condition change, manifest re-parse) and
never reset on a FRESH dep (no `newly_updated` event to clear it), producing
permanent deadlocks. The in-CL race the gate nominally prevented is already
covered by dbt's intra-build DAG ordering plus `any_deps_missing` /
`any_deps_in_progress`; cross-CL races fail at BigQuery query time (recoverable,
not silent corruption). If a downstream table looks "stuck," the cause is
elsewhere — start with `any_deps_missing` / `any_deps_in_progress` evaluator
nodes.

**Dep fan-out rule**: An unpartitioned dep of a partitioned asset fans out to
ALL partitions on every materialization. To preserve per-partition triggering,
the dep must itself be partitioned with the same `PartitionsDefinition`.
