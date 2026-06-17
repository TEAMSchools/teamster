# CLAUDE.md — `dbt/finalsite/`

Source-system staging project for **Finalsite** (school website and
communications platform), plus a small SIS-agnostic intermediate layer for the
Finalsite → SIS enrollment integration.

## Model Structure

```text
models/
  staging/         # materialized: table
  intermediate/    # materialized: table — SIS-agnostic enrollment models
  sources-external.yml
```

Intermediate models:

- `int_finalsite__enrollment_lifecycle` — one row per in-scope contact with the
  intended SIS action (`create` / `re_enroll` / `transfer_out`); SIS-agnostic
  (feeds both the Focus and PowerSchool receivers).
- `int_finalsite__contact_id_attributes` — pivots `id_attributes` →
  `focus_student_id` (the field named by the `finalsite_focus_student_id_field`
  var).
- `int_finalsite__contact_custom_attributes` — pivots `custom_attributes` →
  typed custom fields (`is_latino_hispanic`, extensible).

## Vars

`cloud_storage_uri_base`, `bigquery_external_connection_name`, `local_timezone`
(null here, set by consuming projects), plus intermediate-layer vars with
package defaults that consumers override: `current_academic_year` (default `0`)
and `finalsite_focus_student_id_field` (default `""`).

## Cross-Project Usage

Referenced as a dbt package by all four district projects (`kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`). `kipptaf` consumes the resulting
tables via `source()`.

**The `intermediate/` layer is enabled only where Finalsite ingestion is
wired.** Today that is `kippmiami` only; `kippnewark`, `kippcamden`, and
`kipppaterson` set `finalsite: intermediate: +enabled: false` in their
`dbt_project.yml` (the staging models build empty there, but the intermediate
models would have no data). Re-enable a region when its Finalsite contacts
ingestion lands.
