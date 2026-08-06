# CLAUDE.md — `dbt/finalsite/`

Source-system staging project for **Finalsite** (school website and
communications platform), plus a small SIS-agnostic intermediate layer for the
Finalsite → SIS enrollment integration.

## Model Structure

Models are split into top-level **method folders** (the amplify convention) so a
region can enable one integration method without the other:

```text
models/
  api/             # Finalsite Contacts API (all four regions)
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
- `int_finalsite__contacts__households` — one row per (contact, household), the
  per-contact-household flattening off `stg_finalsite__contacts`'s raw
  `households` array. Moved out of the staging layer since it reads a
  contract-widened column on `stg_finalsite__contacts` rather than the raw
  source directly; not contract-enforced (the `api/intermediate` directory
  default), though every column still carries a `data_type` per convention.
- `int_finalsite__contact_address_of_record` — one row per Finalsite contact
  (students and adults alike) carrying that contact's resolved address. A
  household is a candidate once it has a street line — completeness is
  deliberately not required. A contact with several candidates gets the most
  complete one, ties broken by lowest `household_id`, flagged `picked`; only a
  contact with no street-bearing household at all gets no address.
- `int_finalsite__student_address_of_record` — one row per student record (a
  contact carrying a workflow status; adults sit at `not_in_workflow`) with the
  resolved address of record: their primary contact's household when
  `int_finalsite__contact_address_of_record` gives them one, else the student's
  own, else no address and an `unresolved` flag. Also carries the primary
  contact's phone, since student records almost never hold one.
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

Vendor API ground truth lives in-repo: `docs/superpowers/specs/references/`
(`finalsite-api-spec.yml`, plus `focus-api-spec.md` / `focus-db-erd.md`).
Consult it before web-searching vendor docs — the hosted Finalsite API reference
is login-gated.

- `relationships` is bidirectional (a parent record carries the reverse
  `rel_type='child'` link). `relationships.primary` is a per-record singleton
  and **NULL, not false, when unset**; only child/student records carry a
  primary link, and that set includes non-PS-enrolled students
  (prospects/applicants). Filtering `where is_primary` yields ALL Finalsite
  student records — scope to enrolled students downstream via
  `powerschool_student_number`, not in this SIS-agnostic package.
- `custom_attributes`/`id_attributes` are **per-contact**, and the parent-slot
  fields (`is_parent2/3/4`, `p1_*`–`p4_*`, `emrg_*`) live ONLY on student
  records — `is_parent2` means "this student has a Parent 2" and is never set on
  the parent's own record (0 in tenant data), so never gate on it via `rel_id`.
  Parent identity comes from `relationships`: `primary` = Parent 1 (a verified
  per-student singleton), an additional `financial`-without-`primary`
  relationship = Parent 2. `households` carry only id + address — membership has
  no roles.

## Cross-Project Usage

Referenced as a dbt package by all four district projects (`kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`). `kipptaf` consumes the resulting
tables via `source()` (network-wide union models live in
`kipptaf/models/finalsite/`).

**The `api/` layer is enabled only where Finalsite Contacts ingestion is
wired.** Today that is all four regions (`kippmiami`, `kippnewark`,
`kippcamden`, `kipppaterson`). The `sftp/` layer (`status_report`) stays enabled
everywhere — kipptaf unions it across all four regions. Set
`finalsite: api: +enabled: false` in a region's `dbt_project.yml` if its
Finalsite contacts ingestion is ever removed.
