# Branching Minds SFTP Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the 13 Branching Minds nightly CSV exports from the BrM SFTP
`/exports` folder into GCS/BigQuery and build `stg_branchingminds__*` staging
models in `kipptaf`.

**Architecture:** 13 `build_sftp_file_asset` assets in a new `kipptaf`
`branchingminds` module, partitioned by fiscal year, fed by one new sensor that
keys partitions on file mtime. dbt reads the Avro partitions through external
sources; 1 staging model per file renames, casts, drops BrM demographics, and
dedupes across yearly partitions.

**Tech Stack:** Dagster, paramiko SFTP (`SSHResource`), Pydantic +
`py_avro_schema`, dbt on BigQuery.

**Spec:**
`docs/superpowers/specs/2026-10-22-branchingminds-sftp-ingest-design.md`

All paths are relative to the worktree
`/workspaces/teamster/.claude/worktrees/cbini/feat/claude-branchingminds-sftp-ingest`.
Run every command with that as cwd, `uv run` always, and `git -C <worktree>`.

## Global Constraints

- Code location `kipptaf`; SSH resource key `ssh_branchingminds` (already
  wired). No changes to `dagster-cloud.yaml`.
- Watch only `/exports`. Never match anything under `/incoming_files/`.
- Partitions:
  `FiscalYearPartitionsDefinition(start_date="2026-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7)`.
- Partition key = fiscal-year start of the file's mtime in `America/New_York`.
- Sensor cursor = per-asset max matched mtime, never wall-clock time.
- An asset run for a partition other than the current fiscal year raises.
- Avro fields are all `str | None`; staging casts.
- Staging drops BrM demographics: student name parts, state ID, grade level,
  gender, race/ethnicity, English proficiency, gifted, mandated learning plan,
  ELL status.
- The local student ID becomes `student_number` in every staging model.
- Staging keeps `district`, `school_id` where present, and
  `_dagster_partition_fiscal_year` as `source_fiscal_year`.
- Every staging model: `config.meta.contains_pii: true` at model level; every
  test sets `config: severity` explicitly.
- No PII values in commits, PR text, or issue comments. Recon output stays in
  the session scratchpad.

## Review Focus

- A file written between 00:00 and 00:59 ET on July 1 must land in the new
  fiscal year, and one at 23:59 ET on June 30 in the old one (Task 3 test).
- A drop whose mtime is older than an asset's cursor but newer than another
  asset's cursor must trigger only the asset it belongs to (Task 3 test).
- A manual launch of a past fiscal-year partition must fail, not overwrite that
  year's frozen snapshot (Task 4 test).
- A 0-byte file must not trigger a run that writes an empty partition over a
  good one (Task 3 test).
- A drop whose newest `school_year` disagrees with its partition must surface as
  a warning in dbt (Task 6 test).

---

### Task 1: SFTP recon (blocked until BrM variables are in the codespace 1Password template)

**Files:**

- Create (throwaway, never committed): `tests/test_zz_branchingminds_recon.py`
- Output: `<session scratchpad>/branchingminds-recon.md`

**Interfaces:**

- Produces for Tasks 2–6: the `/exports` path string as `listdir_attr_r` returns
  it; the 13 file names; each file's raw header row and its
  `file_to_records(..., slugify_cols=True)` key list; the list-column delimiter;
  whether `/exports` dir mtime >= max child mtime; the distinct `district`
  values; the student ID format (digits only?).

- [ ] **Step 1: Write the recon test.** Use `build_resources` with
      `SSH_RESOURCE_BRANCHINGMINDS`. List `/exports` with `listdir_attr_r`. For
      each file, write name, size, mtime, and dir mtime to the scratchpad file.
      Download each file to the scratchpad. Write its header row and the
      slugified keys from `file_to_records` (`teamster.core.utils.functions`).
      Write the distinct values of `district` and of the list columns'
      separators (count of `,` `;` `|` per cell). Write no row values for name,
      ID, or note columns.
- [ ] **Step 2: Run it.**
      `uv run pytest tests/test_zz_branchingminds_recon.py -s --tb=short`.
      Expected: 13 files listed. If fewer, stop and report which are missing.
- [ ] **Step 3: Delete the test file and the downloaded CSVs.** Keep only
      `branchingminds-recon.md`.

### Task 2: Library schemas

**Files:**

- Create: `src/teamster/libraries/branchingminds/__init__.py` (empty)
- Create: `src/teamster/libraries/branchingminds/schema.py`
- Test: `tests/libraries/test_branchingminds_schema.py`

**Interfaces:**

- Consumes: Task 1 slugified header lists.
- Produces: 13 Pydantic `BaseModel` classes, one per file, named in PascalCase
  from the file stem with the `_w_demographics` / `_with_demographics` /
  `_export` suffixes dropped: `AcademicProgressMonitoring`,
  `BehaviorIncidentReport`, `BenchmarksUniversalScreeners`,
  `BehaviorProgressMonitoringPlansAndScores`, `DailyInterventionSessions`,
  `FamilyComms`, `Goals`, `InterventionNotes`, `InterventionPlans`,
  `NewBehaviorIncidentReport`, `StudentTasks`, `TestingAccommodationsReport`,
  `Tiers`. Every field `str | None = None`.

- [ ] **Step 1: Write the failing test.** A dict `HEADERS` maps each file stem
      to its Task 1 slugified key list (header names are not PII; copy them in).
      `test_model_fields_match_slugified_headers` is parametrized over the 13
      stems and asserts `list(Model.model_fields) == HEADERS[stem]`.
- [ ] **Step 2: Run it; expect ImportError.**
      `uv run pytest tests/libraries/test_branchingminds_schema.py -q`
- [ ] **Step 3: Write the 13 models** in `schema.py`, field order matching the
      file.
- [ ] **Step 4: Run it; expect 13 passed.**
- [ ] **Step 5: Commit** `feat(branchingminds): add export schemas`.

### Task 3: Library sensor

**Files:**

- Create: `src/teamster/libraries/branchingminds/sensors.py`
- Create: `src/teamster/libraries/branchingminds/CLAUDE.md`
- Test: `tests/libraries/test_branchingminds_sensor.py`

**Interfaces:**

- Produces:
  `build_branchingminds_sftp_sensor(code_location: str, timezone: ZoneInfo, asset_selection: list[AssetsDefinition], remote_dir: str, minimum_interval_seconds: int | None = None) -> SensorDefinition`.
  Sensor name `f"{code_location}__branchingminds__sftp_sensor"`; one job
  `f"{code_location}__branchingminds__sftp_asset_job"` over all assets; the
  sensor function takes `ssh_branchingminds: SSHResource`. Cursor is a JSON
  object `{asset python identifier: max mtime float}`.

Behavior: one `ssh_branchingminds.listdir_attr_r_or_skip(remote_dir=remote_dir)`
per tick; return the `SkipReason` if one comes back. For each asset, match
`re.match(remote_file_regex, f.filename)`; take files with `st_size > 0` and
`st_mtime > cursor[asset]`. Partition key =
`FiscalYear(datetime.fromtimestamp(mtime, tz=timezone), start_month=7).start.isoformat()`.
Skip with a warning a key not in the asset's partitions def. Set `cursor[asset]`
to the max matched mtime. Group by partition key into one
`RunRequest(run_key=f"{job_name}_{partition_key}_{max_mtime}", partition_key=..., asset_selection=[keys])`.

- [ ] **Step 1: Write the failing tests**, with a `MagicMock` SSH returning
      `(SFTPAttributes, path)` pairs as in
      `tests/libraries/test_edplan_sensor_partition_timezone.py`, and 2
      throwaway `build_sftp_file_asset` assets (`a.csv`, `b.csv`) on the spec
      partitions def:
  - `test_june_30_late_evening_is_prior_fiscal_year`: mtime
    `2027-06-30 23:59 EDT` → `["2026-07-01"]`.
  - `test_july_1_early_morning_is_new_fiscal_year`: mtime `2027-07-01 00:30 EDT`
    → `["2027-07-01"]`.
  - `test_cursor_is_per_asset_max_mtime`: with `t` = `2026-10-01 12:00 EDT` as
    epoch seconds, cursor `{a: t + 200, b: t + 100}`, files `a.csv` and `b.csv`
    at mtime `t + 150` → one request selecting only `b`; returned cursor
    `{a: t + 200, b: t + 150}`. (Mtimes must fall inside the partitions def, or
    the out-of-range skip hides the cursor behavior.)
  - `test_empty_file_is_skipped`: `st_size = 0` → no run requests, cursor
    unchanged.
  - `test_changed_assets_share_one_run`: both files new, same fiscal year →
    exactly 1 `RunRequest` whose `asset_selection` holds both keys.
  - `test_skip_reason_passes_through`: `listdir_attr_r_or_skip` returns a
    `SkipReason` → the sensor returns it.
- [ ] **Step 2: Run; expect ImportError.**
      `uv run pytest tests/libraries/test_branchingminds_sensor.py -q`
- [ ] **Step 3: Implement** `build_branchingminds_sftp_sensor` per the behavior
      above.
- [ ] **Step 4: Run; expect 6 passed.**
- [ ] **Step 5: Write `CLAUDE.md`:** one sensor for all BrM exports; the
      partition comes from mtime because BrM rolls its window July 1 and 6 files
      have no school-year column; cursor is per-asset max mtime.
- [ ] **Step 6: Commit** `feat(branchingminds): add SFTP sensor`.

### Task 4: Current-partition guard and kipptaf code location

**Files:**

- Modify: `src/teamster/libraries/sftp/assets.py` (`build_sftp_file_asset`)
- Modify: `src/teamster/libraries/sftp/CLAUDE.md`
- Create: `src/teamster/code_locations/kipptaf/branchingminds/__init__.py`,
  `schema.py`, `assets.py`, `sensors.py`
- Modify: `src/teamster/code_locations/kipptaf/definitions.py`
- Modify: `src/teamster/code_locations/kipptaf/CLAUDE.md` (integration list)
- Test: `tests/libraries/test_sftp_file_asset_current_partition.py`

**Interfaces:**

- Consumes: Task 2 models, Task 3 builder, Task 1 path and file names.
- Produces: `build_sftp_file_asset(..., current_partition_only: bool = False)`.
  When true and the run's partition key is not
  `partitions_def.get_last_partition_key()`, raise `ValueError` naming both keys
  before any SFTP call. Module `teamster.code_locations.kipptaf.branchingminds`
  exports `assets` (list of 13) and `sensors` (list of 1). Asset keys
  `["kipptaf", "branchingminds", <file stem>]`.

- [ ] **Step 1: Write the failing test.** Build a file asset with
      `current_partition_only=True` on the spec partitions def;
      `materialize([asset], partition_key=<an earlier key>, resources={ssh key: MagicMock()})`
      with `raise_on_error=False` → failed, error contains `ValueError`, and the
      mock SSH was never called. Use `dagster`'s `instance_for_test` and choose
      the earlier key from the def so the test does not depend on today's date
      beyond needing ≥2 partitions (create the def with
      `start_date="2020-07-01"` in the test).
- [ ] **Step 2: Run; expect TypeError on the unknown kwarg.**
- [ ] **Step 3: Add the parameter and guard.** Document it in
      `libraries/sftp/CLAUDE.md` in one line.
- [ ] **Step 4: Run; expect pass.** Also run
      `uv run pytest tests/libraries/test_sftp_archive_remote_dir.py tests/libraries/test_sftp_local_filepath.py -q`
      for regressions.
- [ ] **Step 5: Write the code location.** `schema.py`: one Avro schema per
      model via
      `py_avro_schema.generate(..., options=NO_DOC | NO_AUTO_NAMESPACE)` as in
      `kipptaf/adp/payroll/schema.py`. `assets.py`: 13 `build_sftp_file_asset`
      calls with `remote_dir_regex` = the Task 1 path, `remote_file_regex` =
      `re.escape(<file name>)`, `ssh_resource_key="ssh_branchingminds"`, the
      shared partitions def, and `current_partition_only=True`. `sensors.py`:
      the Task 3 builder with `minimum_interval_seconds` equal to kipptaf's
      other SFTP sensors (`60 * 10`). Add `branchingminds` to the imports,
      `assets=`, and `sensors=` lists in `definitions.py`, matching neighbors.
- [ ] **Step 6: Validate definitions.** Run
      `uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py`
      then
      `uv run pytest tests/test_dagster_definitions.py -k kipptaf --tb=short 2>&1 | tail -n 20`.
      Expected: pass.
- [ ] **Step 7: Commit** `feat(branchingminds): add kipptaf export assets`.

### Task 5: dbt sources and the two template staging models

**Files:**

- Create: `src/dbt/kipptaf/models/branchingminds/sources-external.yml`
- Create:
  `src/dbt/kipptaf/models/branchingminds/staging/stg_branchingminds__intervention_plans.sql`
  and `staging/properties/stg_branchingminds__intervention_plans.yml`
- Create: `stg_branchingminds__testing_accommodations.sql` and its properties
- Modify: `src/dbt/kipptaf/dbt_project.yml` only if `branchingminds:` needs a
  `+schema` entry like its neighbors

**Interfaces:**

- Produces: source `branchingminds`, tables `src_branchingminds__<file stem>`
  (13), each mirroring `adp/payroll/sources-external.yml` with
  `meta.dagster.asset_key: [kipptaf, branchingminds, <stem>]`. Model names drop
  the same suffixes as the Task 2 class names:
  `stg_branchingminds__academic_progress_monitoring`,
  `__behavior_incident_report`, `__benchmarks_universal_screeners`,
  `__behavior_progress_monitoring`, `__daily_intervention_sessions`,
  `__family_comms`, `__goals`, `__intervention_notes`, `__intervention_plans`,
  `__new_behavior_incident_report`, `__student_tasks`,
  `__testing_accommodations`, `__tiers`.

The template pattern every staging model follows: a `source` CTE selecting
non-demographic columns with casts (`safe_cast` for numbers and dates, since BrM
types are loose; list columns `split(<col>, '<delimiter from Task 1>')`);
student ID renamed and cast to `student_number` (type from Task 1, matching
`stg_powerschool__students.student_number`);
`_dagster_partition_fiscal_year as source_fiscal_year`; history files end with
`qualify row_number() over (partition by <key> order by source_fiscal_year desc) = 1`
(allowed in `stg_`, rule A5). The snapshot file keeps `source_fiscal_year` in
its grain and has no `qualify`.

- [ ] **Step 1: Write the sources file and the 2 models.** Keys from the spec
      table: `intervention_plan_id, student_number` and
      `student_number, accommodation, skill_topic, source_fiscal_year`.
- [ ] **Step 2: Write properties.** Model and column descriptions; model
      `config.meta.contains_pii: true`;
      `dbt_utils.unique_combination_of_columns` on the key at `severity: error`;
      `relationships` from `student_number` to
      `ref('stg_powerschool__students')` field `student_number` at
      `severity: warn`, description naming BrM's local ID as the thing to fix in
      BrM.
- [ ] **Step 3: Add a dbt unit test** on
      `stg_branchingminds__intervention_plans` (`format: sql` input, since the
      source is not staged yet): the same `intervention_plan_id` +
      `student_number` in fiscal years 2027 and 2028 → 1 row with
      `source_fiscal_year = 2028`.
- [ ] **Step 4: Parse and compile.**
      `uv run dbt deps --project-dir src/dbt/kipptaf` (own call), then
      `uv run dbt compile --select branchingminds --project-dir src/dbt/kipptaf 2>&1 | tail -n 20`.
      Expected: no errors.
- [ ] **Step 5: Lint.**
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/branchingminds </dev/null`.
      Fix findings.
- [ ] **Step 6: Commit**
      `feat(branchingminds): add sources and template staging models`.

### Task 6: Remaining 11 staging models

**Files:**

- Create: the other 11 `stg_branchingminds__*.sql` and properties under
  `src/dbt/kipptaf/models/branchingminds/staging/`.

**Interfaces:**

- Consumes: Task 5 source tables and template pattern.

- [ ] **Step 1: Write the 11 models and properties** per the template, keys from
      the spec table. `tiers` and `benchmarks_universal_screeners` still get the
      `qualify` (harmless when partitions never overlap).
      `new_behavior_incident_report` keeps `data_source`;
      `academic_progress_monitoring` and `benchmarks_universal_screeners` keep
      `assessment_family` / `assessment_provider`.
- [ ] **Step 2: Add the school-year check.** Write one generic test,
      `src/dbt/kipptaf/tests/generic/test_branchingminds_school_year_matches_partition.sql`
      (`model`, `column_name`). It returns each `source_fiscal_year` whose
      `max(<normalized school_year>)` differs from it. The normalization depends
      on the format Task 1 found (`2026`, `2026-2027`, or `25-26`), mapped to
      the fiscal year that school year ends in. Declare it at `severity: warn`
      on the `school_year` column of every model that has one, with the
      description "BrM rolled its export window on a date other than July 1".
      Staging is the right host despite the dedupe: a new partition that still
      holds last year's data wins the dedupe, so its rows show
      `source_fiscal_year` = new year with `school_year` = old year, which the
      test flags.
- [ ] **Step 3: Compile and lint** as in Task 5, steps 4–5.
- [ ] **Step 4: Commit** `feat(branchingminds): add remaining staging models`.

### Task 7: Docs, PR, branch deployment, staging

**Files:**

- Modify: `docs/reference/automations.md` (generated)

- [ ] **Step 1: Regenerate** `uv run scripts/gen-automations-doc.py` (see
      `scripts/CLAUDE.md` _Prerequisites_). Commit
      `docs(branchingminds): regenerate automations reference`.
- [ ] **Step 2: Push and open the PR non-draft** from
      `.github/pull_request_template.md`, `Closes #5986`.
- [ ] **Step 3: Materialize all 13 assets in the branch deployment** (current
      fiscal-year partition) via `mcp__dagster-plus__launch_asset_run` with the
      branch deployment name. Expected: 13 successes, schema checks pass.
- [ ] **Step 4: Ask the user to authorize** staging the externals and building
      the models (shared `zz_stg_kipptaf_branchingminds` write). On a yes, in
      separate Bash calls:
      `uv run dbt run-operation stage_external_sources --project-dir src/dbt/kipptaf --target staging --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kipptaf, ext_full_refresh: true}' --args "select: branchingminds"`,
      then
      `uv run dbt build --select branchingminds --project-dir src/dbt/kipptaf --target staging 2>&1 | tail -n 30`.
      Expected: every uniqueness test passes. A key that fails is a finding for
      the user, not a key to widen.
- [ ] **Step 5: Check the student ID match** by reading the `relationships` warn
      counts; report the orphan count per model (counts only).
- [ ] **Step 6: Watch CI and process `claude-review`** per `pr-ci-review`.
- [ ] **Step 7: After merge, hand the user** the prod launch of all 13 assets
      (before the first dbt tick), and remind them that
      `stage_external_sources --target staging` must re-run against the prod
      location once the prod files exist.
