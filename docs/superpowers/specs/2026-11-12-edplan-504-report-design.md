# EdPlan 504 student report: Newark ingestion

Issue: #6350

## Intent

PowerSchool misses most 504 students. EdPlan, where schools write 504 plans,
exports a 504 event report to its SFTP. Loading and staging that report gives
the later `is_504` decision a source that lists every student with a 504 plan.
This change loads and stages the file only.

## Goals

- Land Newark's `Reports/EDPlan-504StudentReport.csv` in GCS through Dagster.
- Stage it in the `edplan` dbt package with an enforced contract, column
  descriptions, PII tags, and an error-severity uniqueness test.

## Non-goals

- Changing `is_504` in `int_students__student_enrollments`.
- Camden ingestion. Camden's SFTP has a file with the same name, but it is a
  different report (tab-delimited, 20 columns, 1 row per eligible student, no
  event history). Camden's EdPlan admin has been asked to switch to Newark's
  layout. Once it matches, Camden needs only the asset and a dbt enable.
- Paterson ingestion.
- EdPlan's R100 eligibility report.

## Findings from the live file (2026-11-12)

- Comma-delimited, quoted fields, CRLF, UTF-8, 24 columns, header row. Matches
  the issue's column list.
- 1 row per student per 504 event.
- `Document ID` is unique where present. 7 rows have a blank `Document ID`; all
  are `Previous:` determinations.
- (`Internal Student ID`, `Document ID`, `Event Selector`, `Event Date`) is
  unique across all rows. No blank `Event Date`. No exact duplicate rows.
- No student has more than 1 `Currently Valid: Section 504 Plan` row.
- The file appears to be overwritten daily (same pattern as
  `NJSMART-PowerSchool.txt`); only 1 listing was seen.

## Approaches

Camden's file does not match Newark's, so 3 options were weighed:

- **A. Newark now, Camden after its export changes.** Chosen. One grain for the
  later `is_504` work; Camden later needs config only.
- B. Both now, as 2 models with different grains. Rejected: a second schema and
  model, and the `is_504` work would reconcile 2 grains with different meanings.
- C. Hold everything until Camden matches. Rejected: Newark data is useful on
  its own.

## Design

### Dagster

- Pydantic model for the report in `src/teamster/libraries/edplan/schema.py`,
  fields named by the SFTP asset's default header slugify, plus
  `source_file_name`. Avro schema in `kippnewark/edplan/schema.py`.
- Asset `kippnewark/edplan/section_504_student_report`: `remote_dir_regex`
  `Reports`, `remote_file_regex` `EDPlan-504StudentReport\.csv`, `ssh_edplan`,
  eager automation.
- Builder's call: same daily partitions definition as `njsmart_powerschool`,
  because both assets share one job and a job rejects mixed partitions
  definitions.
- Builder's call: `build_edplan_sftp_sensor` takes `assets: list`. The job
  selects all of them; each matched file yields a run request scoped to its
  asset. Cursor stays keyed per asset. A second sensor was rejected because the
  job name `{code_location}_edplan_sftp_asset_job` would collide. Camden and
  Paterson pass `[njsmart_powerschool]`.

### dbt

- Source `src_edplan__section_504_student_report` in the `edplan` package's
  `sources-external.yml`.
- Model `stg_edplan__section_504_student_report`:
  - Builder's call: keep only the latest partition. Each file is a full export
    carrying its own `Previous:` history, so stacking daily files would only
    repeat rows.
  - Parse `YYYY/MM/DD 0:00:00` dates to `date`; trim the leading spaces on
    ethnicity and race; cast `student_number` to int.
  - Drop `source_file_name` and the `_dagster_partition_*` columns.
  - No dedup: the data has no duplicates on the key.
  - Enforced contract, column descriptions, PII tags per
    `.claude/rules/ferpa-pii.md`. `Internal Student ID` and `Document ID` are
    surrogate keys and stay untagged.
  - Error-severity `dbt_utils.unique_combination_of_columns` on
    (`internal_student_id`, `document_id`, `event_selector`, `event_date`). The
    issue's warn test for duplicate source rows is dropped: with no dedup, there
    is nothing for it to guard.
- Disable the model and its source in `kippcamden` and `kipppaterson`.

### Also

- Add `remote_port=22` to `tests/sensors/sftp/test_sensors_sftp_edplan.py`.
  Without it, dagster-ssh passes `None` and paramiko times out on port 0.
- Add a Newark asset test next to the existing EdPlan SFTP asset test.
- Regenerate `docs/reference/automations.md` with
  `uv run scripts/gen-automations-doc.py` (never edit it by hand).

## Done when

- The Newark asset materializes from the sensor and lands Avro in GCS.
- The external source stages, and the model builds in `kippnewark` with its
  contract and uniqueness test passing.
- `kippcamden` and `kipppaterson` parse with the model and source disabled.
- The count of students with `Currently Valid: Section 504 Plan` matches the
  source file.

## Left to the builder

- Exact slugified column names (read the slugify function, do not guess).
- Column descriptions.

## Revision 2026-11-12: unpartitioned 504 asset

PR review raised that the shared daily partitions definition gave the 504 asset
partitions back to 2023-05-08, all empty. Each file already carries the full
event history, so a daily partition adds nothing.

- The 504 asset is unpartitioned. Each load replaces the last.
  `njsmart_powerschool` keeps its own daily partitions.
- `build_edplan_sftp_sensor` targets `asset_selection=assets` instead of a named
  job. That runs on the implicit asset job, which accepts mixed partitions
  definitions. The sensor keeps its name, so its cursor carries over. A run
  request sets `partition_key` only for a partitioned asset.
- The source drops `hive_partition_uri_prefix`. The staging model drops the
  latest-file filter and `report_date`.
- Cost: no daily copy of the point-in-time columns (`date_snapshot_*_y_n`,
  `student_status`, `grade_abbrev`). The event history with its begin and end
  dates stays in every file.
