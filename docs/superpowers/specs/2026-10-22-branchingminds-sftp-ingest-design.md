# Branching Minds nightly export ingestion — design

Issue: [#5986](https://github.com/TEAMSchools/teamster/issues/5986)

## Intent

Branching Minds (BrM) is the MTSS platform for Newark, Camden, and Paterson. We
send BrM data every night but pull nothing back. BrM already drops up to 13
nightly CSV exports into `/exports` on the same SFTP server we send to. Load
them so dbt models and dashboards can use BrM intervention, tier, goal, and
progress-monitoring data.

The scope is ingestion plus staging. No consumer is named yet, so the goal is
clean, typed, deduplicated staging that any later mart can build on.

## Goals

- All 13 export files land in GCS as Avro and in BigQuery as external sources.
- A sensor picks up each nightly drop with no manual step.
- History survives BrM's July 1 rollover: the latest drop for the current school
  year, plus a frozen copy of each past year's final drop.
- 1 `stg_branchingminds__<file>` model per export, with snake_case columns, real
  types, and 1 row per record across all yearly partitions.
- Every staging model carries the student under 1 column name, `student_number`,
  so it joins to our student models.

## Non-goals

- Marts, `rpt_` models, exposures, and Cube views.
- Business rules: for example, which behavior incidents count, or whether a
  vendor-imported score beats a hand-entered one.
- Deduplicating BrM behavior or assessment rows against DeansList or vendor
  feeds. Staging keeps BrM's `data_source` / `assessment_family` columns so a
  later model can decide.
- Recovering school years that BrM already dropped before this ships.

## Anti-goals

- Copying BrM's demographic columns into the warehouse. We already hold
  demographics from the SIS, and a second copy can disagree with it and widens
  the PII surface.
- Ingesting anything under `/incoming_files/` (our own outbound extracts).
- A cursor that uses wall-clock time, which can skip a file whose mtime is older
  than the last tick.

## Constraints

- Code location `kipptaf`: 1 SFTP connection serves all BrM regions.
  `SSH_RESOURCE_BRANCHINGMINDS` (`ssh_branchingminds`) and its secrets in
  `dagster-cloud.yaml` already exist; prod needs no new secret plumbing.
- The codespace 1Password template lacks the BrM variables, so a local pytest
  cannot list `/exports`. The template is a protected path; the user adds them.
  Until then, file names, header slugs, and `district` values are unverified.
- Every file is student-level. Free text (`notes`, `Incident Description`,
  `Student Account`, `goal_description`, `task_description`), staff names and
  emails, and restraint, seclusion, and police flags are PII.
- Avro externals on overwritten-in-place partitions must be read by table models
  (staging is table by default), or the pinned file version expires.
- A new Avro external cannot be staged until its asset has materialized once.

## Approaches

Decided in conversation: **A**.

- **A. Fiscal-year partitions (chosen).** Each asset uses
  `FiscalYearPartitionsDefinition`. Each nightly drop overwrites the current
  year's partition. On July 1 a new partition starts, and the prior year keeps
  its final pre-July-1 drop, which is the snapshot. No extra job. Tradeoff: a
  June 30 drop that BrM writes after midnight lands in the new year, so the old
  year freezes on the June 29 drop.
- **B. Latest-only plus a June 30 snapshot schedule.** Unpartitioned assets plus
  a schedule that copies GCS files to an archive path. Rejected: more parts, a
  second dbt source per file, and a missed snapshot if the schedule or BrM is
  late.
- **C. dlt filesystem source straight to BigQuery.** Rejected: it bypasses the
  Avro schema check and the GCS external-table pattern every other SFTP vendor
  uses.

## Design

### Dagster

Library `src/teamster/libraries/branchingminds/`:

- `schema.py`: 1 Pydantic model per export. Every field is `str | None`; staging
  casts. Field names are the slugified header names that `file_to_records`
  produces (`slugify_cols=True`), checked against a real file for the 4 Title
  Case files (`behavior_incident_report_export`,
  `family_comms_with_demographics_export`,
  `new_behavior_incident_report_w_demographics`,
  `testing_accommodations_report_export`).
- `sensors.py`:
  `build_branchingminds_sftp_sensor(code_location, timezone, asset_selection, minimum_interval_seconds)`.
  One `listdir_attr_r_or_skip` of `/exports` per tick (no `dir_mtimes=` unless
  directory-mtime propagation is verified on this server). For each asset, a
  file matching its `remote_file_regex` with `st_mtime` above that asset's
  cursor and `st_size > 0` yields a request. The partition key is the
  fiscal-year start of the file's mtime in local time. Requests group by
  partition key into 1 run with `asset_selection` of the changed assets. The
  cursor stores each asset's max matched mtime.
- `CLAUDE.md`: what the sensor does and the partition-from-mtime rule.

Code location `src/teamster/code_locations/kipptaf/branchingminds/`:

- `schema.py`: Avro schemas generated from the library models with
  `py_avro_schema.generate()`, as other integrations do.
- `assets.py`: 13 `build_sftp_file_asset` calls. Asset key
  `kipptaf/branchingminds/<file stem>`. `remote_dir_regex` is the `/exports`
  path as the server reports it. `remote_file_regex` is the escaped exact file
  name. `ssh_resource_key="ssh_branchingminds"`. `partitions_def` is 1 shared
  `FiscalYearPartitionsDefinition(start_date="2026-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7)`.
- `sensors.py`: the sensor over all 13 assets.
- `__init__.py` and wiring in `kipptaf/definitions.py`.

The asset reads whatever file is on the server when it runs, so a backfill of a
past fiscal-year partition would overwrite that year's snapshot with today's
data. The asset must refuse a partition that is not the current fiscal year.

### dbt (`src/dbt/kipptaf/models/branchingminds/`)

- `sources-external.yml`: source `branchingminds`, schema pattern as in
  `adp/payroll/sources-external.yml`, 13 `src_branchingminds__<stem>` tables,
  AVRO with `hive_partition_uri_prefix`, `metadata_cache_mode: MANUAL`, each
  with `meta.dagster.asset_key`.
- `staging/stg_branchingminds__<stem>.sql` + `properties/`, 1 per file:
  - Rename to snake_case; cast dates, timestamps, booleans, and numbers; split
    list columns (`applicable_tiers`, `support_tags`, `monitoring_staff`,
    `template_subtask_names`, `student_tags`) into `array<string>` once the
    delimiter is known from real data.
  - Drop BrM demographics: student name parts, state ID, grade level, gender,
    race/ethnicity, English proficiency, gifted, mandated learning plan, ELL
    status.
  - The local student ID (`student_number`, `student_id`, `Student ID`,
    `Student Number` across files) becomes `student_number`, typed to match our
    `student_number`.
  - Keep `_dagster_partition_fiscal_year` as `source_fiscal_year`, and keep
    BrM's `district` and `school_id`.
  - `student_number` needs no region column in keys or joins: no
    `student_number` repeats across Newark, Camden, and Paterson in
    `stg_powerschool__students`.
  - On files that carry `school_year`, a `severity: warn` test checks that each
    partition's latest `school_year` matches `source_fiscal_year`. The partition
    comes from file mtime because BrM documents a July 1 rollover and 6 files
    have no school-year column. This test catches a rollover on another date,
    the failure mode the `renlearn` sensor hit.
  - Deduplicate across partitions to the newest fiscal year per natural key.
    BrM's export article says the files hold records from a rolling 3-year
    window (history), except `tiers_w_demographics` and
    `benchmarks_universal_screeners_w_demographics` (current year only, so
    partitions never overlap) and `testing_accommodations_report_export`
    (current-state snapshot). Snapshot files
    (`testing_accommodations_report_export`) keep `source_fiscal_year` in the
    grain instead, because each year's copy is a different snapshot.
  - Uniqueness test at `severity: error` on the natural key. A `relationships`
    test on `student_number` to our student model at `severity: warn`; it is the
    check that BrM's ID matches ours.
  - Model-level `config.meta.contains_pii: true`: every row is student-level
    content.

Proposed natural keys, to verify on real data:

| File                                            | Key                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------- |
| `academic_progress_monitoring`                  | `score_id`                                                             |
| `behavior_incident_report_export`               | `incident_id`, `student_number`                                        |
| `benchmarks_universal_screeners_w_demographics` | `score_id`                                                             |
| `behavior_progress_monitoring_plans_and_scores` | `plan_id`, `goal_id`, `period_name`, `score_date`                      |
| `daily_intervention_sessions`                   | `intervention_session_id`                                              |
| `family_comms_with_demographics_export`         | `family_communication_id`                                              |
| `goals_w_demographics`                          | `goal_id`                                                              |
| `intervention_notes`                            | `intervention_plan_id`, `notes_date`, `notes`                          |
| `intervention_plans_w_demographics`             | `intervention_plan_id`, `student_number`                               |
| `new_behavior_incident_report_w_demographics`   | `brm_detail_id`                                                        |
| `student_tasks_w_demographics`                  | `task_id`                                                              |
| `testing_accommodations_report_export`          | `student_number`, `accommodation`, `skill_topic`, `source_fiscal_year` |
| `tiers_w_demographics`                          | `tier_update_id`                                                       |

### Docs

- Regenerate `docs/reference/automations.md` for the new sensor.
- Add `branchingminds` to `src/teamster/code_locations/kipptaf/CLAUDE.md`'s
  integration list.

## Rollout

1. User adds the BrM SFTP variables to the codespace 1Password template.
2. Throwaway pytest lists `/exports`: exact path, file names, sizes, mtimes,
   directory mtimes, and a sample of each file's header and list delimiter.
   Values stay local.
3. Build Dagster pieces; verify with `dagster definitions validate` under
   pytest.
4. Open the PR non-draft; materialize all 13 assets in the branch deployment;
   stage the externals against `gs://teamster-test` with `--target staging`
   (user-authorized shared write); build the staging models.
5. After merge, launch all 13 assets in prod at once, before the first dbt tick
   requests the new staging models.

## Left to the builder

- The exact `/exports` path string and file-name regexes.
- Slug output for the Title Case headers and the resulting column names.
- The list-column delimiter and the target type for `student_number`.
- Confirming or replacing each natural key above against real rows; an
  unexpected duplicate is a finding to bring back, not a key to widen silently.
- Which student model the `relationships` test points at.
- The sensor's `minimum_interval_seconds`, matching kipptaf's other SFTP
  sensors.
