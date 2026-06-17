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
  `powerschool_student_number`). The Finalsite-minted Focus `STDT_ID` field
  appears here automatically once it carries data.
- `int_finalsite__contact_custom_attributes` — pivots every `custom_attributes`
  field to its own column, aliased to the original field name and typed by the
  populated value subtype (`_yn`/`_opt_in` booleans, `_ms` string arrays, else
  strings).

## Cross-Project Usage

Referenced as a dbt package by all four district projects (`kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`). `kipptaf` consumes the resulting
tables via `source()` (network-wide union models live in
`kipptaf/models/finalsite/`).

**The `api/` layer is enabled only where Finalsite Contacts ingestion is
wired.** Today that is `kippmiami` only; `kippnewark`, `kippcamden`, and
`kipppaterson` set `finalsite: api: +enabled: false` in their `dbt_project.yml`.
The `sftp/` layer (`status_report`) stays enabled everywhere — kipptaf unions it
across all four regions. Re-enable a region's `api` when its Finalsite contacts
ingestion lands.
