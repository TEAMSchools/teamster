# DeansList Family Contacts Extract — Add Emergency Contacts — Design

Issue: [#4478](https://github.com/TEAMSchools/teamster/issues/4478)

## Background

The DeansList nightly `contacts.txt` feed (`rpt_deanslist__family_contacts`,
shipped in [#4400](https://github.com/TEAMSchools/teamster/issues/4400)) sends
one row per currently enrolled NJ student: their single `contact_1` (the
Finalsite primary → financial parent pick). Emergency contacts were explicitly
out of scope then. This change adds them.

The upstream `int_finalsite__student_contacts` already carries the emergency
rows in prod today: `contact_slot` ∈ (`contact_1`, `emergency_1` …
`emergency_4`), a boolean `is_emergency`, a per-row `relationship`, split
`contact_first_name` / `contact_last_name`, phones, and email. So no upstream or
district work is required — only the kipptaf `rpt` view and its properties
change.

## Goal

Include emergency contacts alongside the primary parent in the DeansList
`contacts.txt` feed for the NJ regions (Newark, Camden, Paterson), with each
emergency slot numbered so Ops can distinguish (and exclude from guardian
messaging) the emergency rows.

## Requirements

- Emit every populated contact slot per enrolled NJ student: `contact_1` plus
  any of `emergency_1` … `emergency_4`.
- `Relationship` values: `contact_1` keeps its Finalsite `rel_type` (`parent`,
  `guardian`, etc.); each emergency slot is labeled `Emergency N`, where `N` is
  the slot number (`emergency_1` → `Emergency 1`).
- Grain `(StudentID, Relationship)` is unique, enforced at severity error.
- No change to the nine DeansList template columns, the file name, or the
  nightly schedule.
- Currently enrolled students only (`enroll_status = 0`) — unchanged.

## Design

### Model — `rpt_deanslist__family_contacts.sql`

- Drop the `sc.contact_slot = 'contact_1'` filter; keep the NJ-region pin
  (`_dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')`) and
  `xw.powerschool_student_number is not null`.
- Rename the `parent_contacts` CTE to `contacts` — it is no longer parent-only.
- Derive `Relationship` in that CTE with a `CASE` on `contact_slot`, replacing
  the passthrough `sc.relationship`:

  ```sql
  case sc.contact_slot
      when 'emergency_1' then 'Emergency 1'
      when 'emergency_2' then 'Emergency 2'
      when 'emergency_3' then 'Emergency 3'
      when 'emergency_4' then 'Emergency 4'
      else sc.relationship
  end as relationship,
  ```

- `contact_slot` is referenced only inside the `CASE`; it is not projected into
  the feed (the nine template columns are unchanged).
- All other columns, the `enrolled_students` join, and the final `SELECT` are
  unchanged.

### Properties — `properties/rpt_deanslist__family_contacts.yml`

- Remove the standalone `unique` test from `StudentID`; keep its `not_null`
  (error).
- Add a model-level test:

  ```yaml
  data_tests:
    - dbt_utils.unique_combination_of_columns:
        arguments:
          combination_of_columns:
            - StudentID
            - Relationship
        config:
          severity: error
  ```

- Update the model `description` (emergency contacts are now included and
  numbered) and the `Relationship` column `description` (`contact_1` carries the
  Finalsite `rel_type`; emergency slots carry `Emergency N`).
- `ParentLastName` `not_null` stays at warn — it flags the small number of
  emergency rows with a null last name (DeansList requires the field, so the
  warning is the correct signal to Ops rather than a hard failure).

## Grain and uniqueness

`(StudentID, Relationship)` is a genuine unique key:

- The upstream grain is `(student, contact_slot)` — each slot occurs at most
  once per student.
- Every emergency slot maps 1:1 to a distinct `Emergency N` label, and a student
  has exactly one `contact_1` row whose `rel_type` is never an `Emergency N`
  string. So no two rows for a student share a `Relationship` value.

Verified against prod: `(StudentID, Relationship)` is unique at 30,478 / 30,478
rows. `Relationship` is never null.

Only three students network-wide have a slot gap (an `emergency_N` present with
`emergency_(N-1)` absent), so numbering by slot is effectively dense. Those
students get a harmless label gap (e.g. `Emergency 1` and `Emergency 3`).
Numbering by slot keeps the SQL a plain `CASE` and avoids a window function to
re-rank.

### Prod data profile (current)

| `contact_slot` | rows  | null last name | rows w/ no phone or email |
| -------------- | ----- | -------------- | ------------------------- |
| `contact_1`    | 9,685 | 0              | 4                         |
| `emergency_1`  | 9,107 | 3              | 167                       |
| `emergency_2`  | 8,818 | 4              | 311                       |
| `emergency_3`  | 2,094 | 1              | 49                        |
| `emergency_4`  | 774   | 0              | 21                        |

Total after the change: ~30,478 rows over 9,685 students (~3× the current feed).

## Rollout

Single kipptaf-only PR, two files (`rpt_deanslist__family_contacts.sql` and its
properties yml). No district, source-schema, staging-seed, or Dagster/Python
changes — every upstream column already exists in prod, so there is no
cross-project seeding step (unlike #4400).

dbt Cloud CI rebuilds the `rpt` view under `state:modified+`. Post-merge,
Dagster rematerializes the view and the existing `contacts_txt` extract asset
emits the wider file on the next nightly run (1:25 AM). No change to the extract
config, transport, or schedule.

## Validation

- Build the `rpt` model locally against the district projects with `--defer`;
  confirm ~30,478 rows, `(StudentID, Relationship)` uniqueness, correct
  `Emergency N` labels, and `contact_1` rows retaining their real relationship.
  Spot-check a handful of students against Finalsite (PII stays local — never in
  the PR).
- Post-deploy: confirm `contacts.txt` on the DeansList SFTP now carries the
  emergency rows.

## Out of scope

- Deduplicating a person who is both the primary parent and an emergency contact
  (633 students). Per Ops decision these ship as separate rows; the numbered
  `Relationship` keeps them distinct on the DeansList side.
- Densely re-ranking emergency numbers across the three slot-gap students.
- Miami (still PowerSchool-sourced for contacts), other DeansList template
  files, populating `Language`, and phone-number formatting
  (`only numbers or x`).
