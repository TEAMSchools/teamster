# CLAUDE.md — `dbt/finalsite/`

Source-system staging project for **Finalsite** (school website and
communications platform), plus a small SIS-agnostic intermediate layer for the
Finalsite → SIS enrollment integration.

## Model Structure

Models are split into top-level **method folders** (the amplify convention) so a
region can enable one integration method without the other:

```text
models/
  api/             # Finalsite Contacts API (Miami-only today)
    staging/       # materialized: table, contract enforced
    intermediate/  # materialized: table — SIS-agnostic enrollment models
  sftp/            # Finalsite Status Report SFTP feed (network-wide)
    staging/       # materialized: table, contract enforced
  sources-external.yml
```

`api/staging`: `stg_finalsite__contacts`,
`stg_finalsite__contact_relationships`. `sftp/staging`:
`stg_finalsite__status_report`.

`api/intermediate` models:

- `int_finalsite__enrollment_lifecycle` — one row per in-scope contact (all
  school years) with the intended SIS action (`create` / `re_enroll` /
  `transfer_out`); SIS-agnostic (feeds both the Focus and PowerSchool
  receivers).
- `int_finalsite__contact_id_attributes` — pivots every `id_attributes` field to
  its own column, aliased to the original field name (`power_school_contact_id`,
  `powerschool_student_number`, `focus_student_id`). The PIVOT enumerates fields
  explicitly — add a new `id_attributes` field to the PIVOT list in the model
  SQL; it does not surface automatically.
- `int_finalsite__contact_custom_attributes` — pivots every `custom_attributes`
  field to its own column, aliased to the original field name and typed by the
  populated value subtype (`_yn`/`_opt_in` booleans, `_ms` string arrays, else
  strings).
- `int_finalsite__contact_track_attributes` — pivots `track_attributes`
  (`assigned_school_ss`, `bsr_contact_info_updated_yn`, `promotion_status_ss`).

`stg_finalsite__contacts` carries THREE repeated key-value arrays —
`id_attributes`, `custom_attributes`, `track_attributes` (each
`STRUCT<field_name, value STRUCT<string_value, boolean_value, array_string_value>>`);
each has a pivot int model above. Scan all three when sourcing a field, and
verify by VALUES, not field name (e.g. `current_residence_ss` is McKinney-Vento
housing status, not a county).

## Contact relationships and custom-attribute gotchas

- `relationships` is bidirectional (a parent record carries the reverse
  `rel_type='child'` link). `relationships.primary` is a per-record singleton
  and **NULL, not false, when unset**; only child/student records carry a
  primary link, and that set includes non-PS-enrolled students
  (prospects/applicants). Filtering `where is_primary` yields ALL Finalsite
  student records — scope to enrolled students downstream via
  `powerschool_student_number`, not in this SIS-agnostic package.
- `custom_attributes`/`id_attributes` are **per-contact** — `is_parent2/3/4`
  (`is_parent3/4` are always false), `emrg_*`, etc. appear on ANY contact,
  including a sibling who is also a student (carrying their own). Reading a
  custom field via a relationship's `rel_id` measures the RELATED contact, not a
  parent designation of the student.

## Cross-Project Usage

Referenced as a dbt package by all four district projects (`kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`). `kipptaf` consumes the resulting
tables via `source()` (network-wide union models live in
`kipptaf/models/finalsite/`).

**The `api/` layer is enabled only where Finalsite Contacts ingestion is
wired.** Today that is `kippmiami` and `kippnewark`; `kippcamden` and
`kipppaterson` set `finalsite: api: +enabled: false` in their `dbt_project.yml`.
The `sftp/` layer (`status_report`) stays enabled everywhere — kipptaf unions it
across all four regions. Re-enable a region's `api` when its Finalsite contacts
ingestion lands.
