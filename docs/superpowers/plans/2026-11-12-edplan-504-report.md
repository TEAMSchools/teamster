# EdPlan 504 Student Report (Newark) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load Newark's `Reports/EDPlan-504StudentReport.csv` from the EdPlan
SFTP into GCS and stage it in the `edplan` dbt package.

**Architecture:** A new SFTP file asset in `kippnewark/edplan`, picked up by the
existing EdPlan SFTP sensor after its builder takes a list of assets. A new
external source and staging model in the `edplan` package keep only the latest
daily file; `kippcamden` and `kipppaterson` disable both.

**Tech Stack:** Dagster (`build_sftp_file_asset`, pydantic + `py_avro_schema`),
dbt-bigquery, `dbt_external_tables`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-edplan-504-report-design.md`

Worktree:
`/workspaces/teamster/.claude/worktrees/cbini/feat/claude-edplan-504-report`
(branch `cbini/feat/claude-edplan-504-report`). Every path below is relative to
it. Run every command from it, always via `uv run`.

## Global Constraints

- Newark only. No Camden asset; Camden's file has a different layout.
- Asset key `["kippnewark", "edplan", "section_504_student_report"]`.
- `remote_dir_regex=r"Reports"`,
  `remote_file_regex=r"EDPlan-504StudentReport\.csv"`.
- Partitions definition identical to `njsmart_powerschool` (start `2023-05-08`,
  `LOCAL_TIMEZONE`, `fmt="%Y-%m-%d"`, `end_offset=1`): both assets share one
  job.
- Source `src_edplan__section_504_student_report`; model
  `stg_edplan__section_504_student_report`.
- Staging keeps only the latest `_dagster_partition_date`. No dedup.
- Grain test: `dbt_utils.unique_combination_of_columns` on
  `internal_student_id, document_id, event_selector, event_date`,
  `severity: error`.
- PII tags (`config.meta.contains_pii: true`) on every column except
  `internal_student_id`, `document_id`, `school`, `report_date`,
  `event_selector`, `event_type`. `internal_student_id` and `document_id` are
  surrogate keys: untagged.
- Never print student rows to git, GitHub, or PR text. Counts only.

## Review Focus

- Both files land in the same sensor tick: expect 2 run requests, each scoped to
  its own asset, with distinct `run_key`s. Test in Task 1.
- A file that matches only `NJSMART-PowerSchool.txt`: expect exactly 1 run
  request, for `njsmart_powerschool` only. Test in Task 1.
- Paterson's sensor (different file name, single asset) keeps working: the
  existing `tests/libraries/test_edplan_sensor_partition_timezone.py` must still
  pass. Task 1.
- A date in an unexpected format: the model must fail the build, not null the
  date. Use `parse_datetime`, never `safe.` / `safe_cast`, for dates. Task 2.
- The 7 rows with blank `Document ID`: the grain test must still pass on the
  real file. Task 2 runs it against a dev build.

---

### Task 1: Newark 504 asset and multi-asset EdPlan sensor

**Files:**

- Modify: `src/teamster/libraries/edplan/schema.py` (add model)
- Modify: `src/teamster/code_locations/kippnewark/edplan/schema.py`
- Modify: `src/teamster/code_locations/kippnewark/edplan/assets.py`
- Modify: `src/teamster/libraries/edplan/sensors.py`
- Modify:
  `src/teamster/code_locations/{kippnewark,kippcamden,kipppaterson}/edplan/sensors.py`
- Create: `tests/libraries/test_edplan_sensor_multi_asset.py`
- Modify: `tests/sensors/sftp/test_sensors_sftp_edplan.py` (add
  `remote_port=22`)
- Modify: `tests/assets/test_assets_edplan_sftp.py` (add Newark 504 test)
- Regenerate: `docs/reference/automations.md`

**Interfaces:**

- Produces: pydantic `Section504StudentReport` in
  `teamster.libraries.edplan.schema`; `SECTION_504_STUDENT_REPORT_SCHEMA` in
  `teamster.code_locations.kippnewark.edplan.schema`; asset
  `section_504_student_report` in
  `teamster.code_locations.kippnewark.edplan.assets` (also appended to that
  module's `assets` list).
- Produces:
  `build_edplan_sftp_sensor(assets: list[AssetsDefinition], code_location: str, execution_timezone: ZoneInfo, minimum_interval_seconds=None)`.
  Job name and sensor name are unchanged.
- Produces: GCS Avro at
  `gs://teamster-test/dagster/kippnewark/edplan/section_504_student_report/`
  (from the live asset test), consumed by Task 2.

- [ ] **Step 1: Write the failing sensor test**

`tests/libraries/test_edplan_sensor_multi_asset.py`, modeled on
`test_edplan_sensor_partition_timezone.py` (MagicMock `ssh_edplan`,
`build_sensor_context`), importing `sftp_sensor` from
`teamster.code_locations.kippnewark.edplan.sensors`:

- `test_both_files_request_one_run_per_asset`: listing returns
  `Reports/NJSMART-PowerSchool.txt` and `Reports/EDPlan-504StudentReport.csv`
  (size 100, same `st_mtime`). Assert 2 run requests; the set of
  `asset_selection` values is
  `{(AssetKey(["kippnewark","edplan","njsmart_powerschool"]),), (AssetKey(["kippnewark","edplan","section_504_student_report"]),)}`;
  the 2 `run_key`s differ.
- `test_only_njsmart_file_requests_only_njsmart`: listing returns only the
  NJSMART file. Assert 1 run request whose `asset_selection` is the
  `njsmart_powerschool` key.

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run pytest tests/libraries/test_edplan_sensor_multi_asset.py -q`
Expected: FAIL (import error on the missing asset, or a single run request).

- [ ] **Step 3: Add the schema and asset**

- `Section504StudentReport(BaseModel)`: every field `str | None = None`, named
  as the SFTP asset's slugify produces them, plus `source_file_name`. The 24
  slugs are:
  `internal_student_id, school, last_name, first_name, state_id, student_id, date_of_birth, gender, ethnicity, race_abbrev_csv_list, grade_abbrev, student_status, date_snapshot_section_504_eligibility_y_n, date_snapshot_historical_section_504_eligibility_y_n, section_504_case_manager, event_selector, event_type, document_id, event_date, primary_disability, secondary_disability, third_disability, begin_date, end_date`.
- `504 Case Manager` slugifies to `504_case_manager`, which is not a valid Avro
  name. Pass
  `slugify_replacements=[["504 Case Manager", "Section 504 Case Manager"]]` to
  the asset so it lands as `section_504_case_manager`.
- Avro schema built exactly like `NJSMART_POWERSCHOOL_SCHEMA`.
- Asset per _Global Constraints_, `ssh_resource_key="ssh_edplan"`,
  `automation_condition=AutomationCondition.eager()`. The file is
  comma-delimited UTF-8, so the `file_sep` / `file_encoding` defaults hold.

- [ ] **Step 4: Change the sensor builder to take a list**

Job selection is the whole list. Loop over `assets`; inside, run the existing
file loop with that asset's `remote_file_regex` and cursor key. Each
`RunRequest` adds `asset_selection=[asset.key]`. Keep the partition-key and
cursor logic as is. Update the 3 callers to `assets=[...]`: Newark passes
`[njsmart_powerschool, section_504_student_report]`; Camden and Paterson pass
`[njsmart_powerschool]`.

- [ ] **Step 5: Run the unit tests**

Run:
`uv run pytest tests/libraries/test_edplan_sensor_multi_asset.py tests/libraries/test_edplan_sensor_partition_timezone.py -q`
Expected: all pass.

- [ ] **Step 6: Fix the live sensor test and add the live asset test**

Add `remote_port=22` to both `SSHResource(...)` calls in
`tests/sensors/sftp/test_sensors_sftp_edplan.py` (without it dagster-ssh passes
`None` and paramiko times out on port 0). Add
`test_edplan_kippnewark_section_504` to
`tests/assets/test_assets_edplan_sftp.py` calling `_test_asset` with the new
asset and `code_location="kippnewark"`.

- [ ] **Step 7: Run the live tests (they hit the real SFTP; run in background)**

Run:
`uv run pytest tests/sensors/sftp/test_sensors_sftp_edplan.py tests/assets/test_assets_edplan_sftp.py -k "kippnewark" -q --tb=short`
Expected: pass. The asset test's schema check (`extras.text == ""`) proves the
pydantic model covers every column. It also uploads the Avro Task 2 needs.

- [ ] **Step 8: Validate definitions and regenerate the automations doc**

Run:
`uv run pytest tests/test_dagster_definitions.py -k "kippnewark or kippcamden or kipppaterson" -q`
then `uv run scripts/gen-automations-doc.py` (see `scripts/CLAUDE.md`
_Prerequisites_). Expected: pass; the Newark EdPlan sensor row lists both
assets.

- [ ] **Step 9: Commit**

`git add -u` plus the new test file; commit
`feat(edplan): ingest the Newark 504 student report` with `Refs #6350`.

### Task 2: Source, staging model, and district disables

**Files:**

- Modify: `src/dbt/edplan/models/sources-external.yml`
- Create:
  `src/dbt/edplan/models/staging/stg_edplan__section_504_student_report.sql`
- Create:
  `src/dbt/edplan/models/staging/properties/stg_edplan__section_504_student_report.yml`
- Modify: `src/dbt/kippcamden/dbt_project.yml`,
  `src/dbt/kipppaterson/dbt_project.yml`

**Interfaces:**

- Consumes: the GCS Avro from Task 1 Step 7.
- Produces: `stg_edplan__section_504_student_report` with the columns below.

- [ ] **Step 1: Add the source**

Copy the `src_edplan__njsmart_powerschool` entry; change `name`, the asset-key
last element, and both GCS paths to `section_504_student_report`.

- [ ] **Step 2: Write the model**

One CTE adds `max(_dagster_partition_date) over () as latest_partition_date`;
the final select keeps `where _dagster_partition_date = latest_partition_date`.
Output columns (all others pass through as string under their slug names):

| Output                                                  | From                                             | Type   |
| ------------------------------------------------------- | ------------------------------------------------ | ------ |
| `report_date`                                           | `_dagster_partition_date`                        | date   |
| `student_number`                                        | `safe_cast(student_id as int)`                   | int64  |
| `state_studentnumber`                                   | `safe_cast(state_id as int)`                     | int64  |
| `ethnicity`, `race_abbrev_csv_list`                     | `trim(...)`                                      | string |
| `date_of_birth`, `event_date`, `begin_date`, `end_date` | `date(parse_datetime('%Y/%m/%d %k:%M:%S', ...))` | date   |

Drop `source_file_name`, `student_id`, `state_id`, and the
`_dagster_partition_*` columns. Do not interpret the two `date_snapshot_*_y_n`
columns; they pass through as text. Confirm the date format against the dev
build in Step 5; if `%k` rejects `0:00:00`, use the format that parses every
row, never a `safe.` variant.

- [ ] **Step 3: Write the properties file**

Model `description`, model-level `data_tests:` grain test per _Global
Constraints_, then every output column with `data_type`, `description`, and PII
tag per _Global Constraints_. Describe `event_selector` with its 6 values and
that `Currently Valid:` marks the current record.

- [ ] **Step 4: Disable in Camden and Paterson**

In both `dbt_project.yml` files: under `models: edplan: staging:` add
`stg_edplan__section_504_student_report: +enabled: false`; under `sources:` add
`edplan: edplan: src_edplan__section_504_student_report: +enabled: false` (merge
into an existing `edplan:` key if present).

- [ ] **Step 5: Build in dev against the Task 1 Avro**

Follow the `dbt-local-dev` skill. From `src/dbt`:
`uv run dbt run-operation stage_external_sources --project-dir kippnewark --target dev --args "select: edplan.src_edplan__section_504_student_report" --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kippnewark, ext_full_refresh: true}'`
then
`uv run dbt build --project-dir kippnewark --target dev --select stg_edplan__section_504_student_report --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kippnewark}'`.
Expected: contract and grain test pass.

- [ ] **Step 6: Check counts against the file**

BigQuery MCP on the dev table: row count equals the file's data rows, and
`count(distinct student_number) where event_selector = 'Currently Valid: Section 504 Plan'`
matches the file. Report counts only.

- [ ] **Step 7: Parse Camden and Paterson**

Run: `uv run dbt parse --no-partial-parse --project-dir kippcamden` and the same
for `kipppaterson`. Expected: no errors.

- [ ] **Step 8: Lint and commit**

`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed sql/yml> </dev/null`;
fix findings. Commit `feat(edplan): stage the 504 student report`, `Refs #6350`.

### Before the PR (hand to the user)

dbt Cloud CI reads `zz_stg_*`, which needs the new external staged with
`--target staging`, a shared write. Draft the command for the user:
`uv run dbt run-operation stage_external_sources --project-dir kippnewark --target staging --args "select: edplan.src_edplan__section_504_student_report" --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kippnewark, ext_full_refresh: true}'`.
Post-merge: launch the asset in prod immediately (`.claude/rules/dbt-yaml.md`
_External Table Pattern_), then re-stage staging to the prod location.
