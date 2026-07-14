# DeansList Family Contacts Extract (`contacts.txt`) — Design

Issue: [#4400](https://github.com/TEAMSchools/teamster/issues/4400)

## Goal

Send DeansList a nightly `contacts.txt` import file for the NJ regions (Newark,
Camden, Paterson), sourced from Finalsite, containing the single "parent"
contact per student — no emergency contacts.

Template: Family Contacts tab of the
[DeansList nightly export template](https://docs.google.com/spreadsheets/d/1PBDcnNLVWZmjFIjFM2R-0gi8RVVkEZg1Jpdgv-N1_6c/edit?gid=1172599928#gid=1172599928).

## Requirements

- One row per currently enrolled NJ student with a Finalsite `contact_1` (the
  primary → financial contact pick already implemented in
  `int_finalsite__student_contacts`).
- Columns, named exactly as the template headers: `StudentID`,
  `ParentFirstName`, `ParentLastName`, `HomePhone`, `WorkPhone`, `CellPhone`,
  `Email`, `Relationship`, `Language`.
- `Language` header is present but the value is always null (per Ops decision —
  Finalsite parent-language data is too sparse/dirty to send).
- File named exactly `contacts.txt`; CSV with header row (DeansList accepts CSV
  or tab-delimited); delivered to the existing DeansList SFTP destination root
  on the existing nightly schedule (1:25 AM, within DeansList's 9 PM local
  deadline).
- Currently enrolled students only — DeansList unenrolls students that drop out
  of the file. Enrollment scoping via `stg_powerschool__students` with
  `enroll_status = 0`.

## Design

### 1. finalsite package — split contact names (PR 1)

`src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
gains two columns in every branch:

- `contact_first_name` / `contact_last_name`
- `contact_1` branch: from the joined `stg_finalsite__contacts` record
  (`cp.first_name` / `cp.last_name` — the join already exists for phones/email).
- `emergency_1`–`emergency_4` branches: from the `emrg_N_name_first_name` /
  `emrg_N_name_last_name` custom attributes (already selected; today only
  concatenated into `contact_name`).
- `contact_name` is unchanged — existing consumers are untouched.
- Properties yml gains descriptions for the two columns (this layer is not
  contract-enforced).

The model builds in all four district projects (all import the finalsite package
with the `api` layer enabled); district prods rebuild via Dagster automation
after merge.

### 2. kipptaf consumer (PR 2)

- `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_contacts.sql`
  (the `union_relations` wrapper over the NJ district models) picks up the new
  columns automatically once district prods rebuild. It gets a doc-comment edit
  in this PR to force `state:modified` so dbt Cloud CI recompiles it against the
  refreshed `zz_stg_*` district copies.
- No change to `int_students__contacts` — the extract deliberately reads the
  Finalsite intermediates directly so the feed is structurally pinned to
  Finalsite as its source system.

### 3. New model — `rpt_deanslist__family_contacts` (PR 2)

`src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
(view; contract enforced by directory default):

- From kipptaf `int_finalsite__student_contacts` where
  `contact_slot = 'contact_1'` and
  `_dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')`
  (explicit NJ pin, in case Miami is ever added to the union).
- Join `int_finalsite__contact_id_attributes` on `finalsite_enrollment_id` and
  `_dbt_source_project`; take `safe_cast(powerschool_student_number as int64)`
  as the student key (non-null required — contacts without a SIS crosswalk drop
  out).
- Inner join `stg_powerschool__students` (kipptaf union view; it already filters
  the `dcid >= 1` placeholder rows) on `student_number`, matching region, with
  `enroll_status = 0` — currently enrolled students only.
- Output columns (exact template header names, quoted in YAML where needed):

  | Column            | Source                                   |
  | ----------------- | ---------------------------------------- |
  | `StudentID`       | `powerschool_student_number`             |
  | `ParentFirstName` | `contact_first_name`                     |
  | `ParentLastName`  | `contact_last_name`                      |
  | `HomePhone`       | `phone_home`                             |
  | `WorkPhone`       | `phone_work`                             |
  | `CellPhone`       | `phone_mobile`                           |
  | `Email`           | `email`                                  |
  | `Relationship`    | `relationship` (`parent`, `guardian`, …) |
  | `Language`        | `cast(null as string)` — always null     |

- Properties yml: model + column descriptions, `unique` + `not_null` on
  `StudentID` (severity error). Name/relationship completeness checked against
  prod during implementation; add warn-level `not_null` tests only if the data
  supports them.

### 4. Dagster extract asset (PR 2)

New entry in
`src/teamster/code_locations/kipptaf/extracts/config/deanslist-annual.yaml`:

```yaml
- query_config:
    type: schema
    value:
      table:
        name: rpt_deanslist__family_contacts
        schema: kipptaf_extracts
  file_config:
    stem: contacts
    suffix: txt
```

`transform_data` serializes `txt` via `DictWriter` (CSV with header) — produces
`contacts.txt` at the DeansList SFTP root. The asset joins the existing
`deanslist_annual_extract_asset_job` on the nightly 1:25 AM schedule. No Python
changes.

## Rollout

Standard two-PR cross-project column add:

1. **PR 1** — finalsite package column add. Merge; wait for district prod
   rebuilds (verify via Dagster materializations).
2. **PR 2** — kipptaf: union-wrapper comment edit, `rpt` model + yml, extract
   YAML entry. Before CI: refresh district `zz_stg_*` copies of
   `int_finalsite__student_contacts` from prod (`dbt clone` per district —
   requires user authorization) so the wrapper recompile sees the new columns.

## Validation

- PR 1: build `int_finalsite__student_contacts` locally via a consuming district
  project-dir with `--defer`; verify name columns populate and row counts are
  unchanged.
- PR 2: build the `rpt` model locally with `--defer`; check row count ≈
  currently enrolled NJ student count, `StudentID` uniqueness, and spot-check a
  few rows against Finalsite values locally (PII stays out of the PR).
- Post-deploy: confirm the new extract asset materializes and `contacts.txt`
  lands on the DeansList SFTP.

## Out of scope

- Miami (still PowerSchool-sourced for contacts; not part of the NJ DeansList
  feed).
- Other template files (students, enrollment dates, attendance, etc.).
- Populating `Language` — revisit if Ops starts maintaining parent language in
  Finalsite.
