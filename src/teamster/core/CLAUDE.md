# CLAUDE.md — `teamster/core/`

Shared infrastructure used by every code location and library. Nothing here is
integration-specific — it is the foundation all other modules build on.

## Files

### `resources.py`

Shared resource instances and factory functions imported by every code
location's `definitions.py`. Two categories:

**Factories** (called with arguments per code location):

- `get_io_manager_gcs_pickle(code_location)` → `GCSIOManager` (pickle, default
  IO manager)
- `get_io_manager_gcs_avro(code_location)` → `GCSIOManager` (Avro, used by
  SFTP/API assets)
- `get_io_manager_gcs_file(code_location)` → `GCSIOManager` (raw file, used by
  paginated Deanslist)
- `get_dbt_cli_resource(dbt_project)` → `DbtCliResource` (passes
  `target="defer"` when `DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT == "1"`; otherwise
  uses the shipped profile default, which is `prod`)
- `get_powerschool_ssh_resource()` → `SSHResource` (reads from shared env vars)

All IO manager factories redirect to `teamster-test` bucket when
`DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT=1`.

**Env var gotcha**: `DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT` is `"0"` (not absent)
in full deployments — always check `== "1"`, never truthy.

**Singletons** (shared across all code locations):

- `BIGQUERY_RESOURCE`, `GCS_RESOURCE`, `DLT_RESOURCE`
- `DEANSLIST_RESOURCE`, `OVERGRAD_RESOURCE`, `ZENDESK_RESOURCE`
- `GOOGLE_DRIVE_RESOURCE`, `GOOGLE_FORMS_RESOURCE`
- `DB_POWERSCHOOL` — Oracle ODBC resource (shared env vars)
- `SSH_COUCHDROP`, `SSH_EDPLAN`, `SSH_IREADY`, `SSH_RENLEARN`, `SSH_TITAN`,
  `SSH_RESOURCE_AMPLIFY` — SFTP resources

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
files), `"file"` (writes raw bytes from a local file path). The `test=True` flag
writes local files to `/tmp/dagster` (not the `dagster-tmp` symlink — causes
`FileExistsError`) instead of `env/`, and prefixes GCS paths with `test/`.

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

### `asset_checks.py`

Two functions used by every SFTP/API asset factory:

- `build_check_spec_avro_schema_valid(asset_key)` → `AssetCheckSpec` (declare
  the check)
- `check_avro_schema_valid(asset_key, records, schema)` → `AssetCheckResult`
  (warn — not fail — if records contain fields not present in the Avro schema)

All asset factories that yield Avro output call both of these.

### `automation_conditions.py`

Three dbt-specific `AutomationCondition` builders, all sharing a common skeleton
via `_build_dbt_condition()`:

- `dbt_view_automation_condition()` — for VIEW models: re-runs on
  `newly_missing`, `code_version_changed`, or `execution_failed`. Intentionally
  omits `any_deps_updated` since views are computed on read.
- `dbt_union_relations_automation_condition()` — for views using the
  `union_relations` macro: adds recursive ancestor `code_version_changed`
  detection (but NOT `any_deps_updated`) to the view condition. Triggers only on
  code deploys that change upstream model definitions, not on data refreshes.
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

### `utils/classes.py`

- `FiscalYear(datetime, start_month)` — computes `.fiscal_year` (int), `.start`
  (date), `.end` (date). Used throughout for July-based fiscal year
  calculations.
- `FiscalYearPartitionsDefinition` — `TimeWindowPartitionsDefinition` subclass
  with `cron_schedule="0 0 {start_day} {start_month} *"`.
- `CustomJSONEncoder` — JSON encoder that handles `timedelta`, `Decimal`,
  `bytes`, `datetime`, and `date` types.

### `utils/functions.py`

- `file_to_records(file_path, ...)` / `csv_string_to_records(csv_string, ...)` —
  read CSV into `list[dict]`, slugifying column names by default (spaces/special
  chars → underscores). Empty strings become `None`. Adds `source_file_name`
  when reading from a file path.
- `regex_pattern_replace(pattern, replacements)` — replaces `(?P<name>...)`
  regex named groups with values from a dict. Core of SFTP partition key
  substitution.
- `parse_partition_key(partition_key)` / `get_partition_key_path(...)` —
  converts a partition key string to a Hive-style GCS path segment list.
- `chunk(obj, size)` — yields successive list slices.
