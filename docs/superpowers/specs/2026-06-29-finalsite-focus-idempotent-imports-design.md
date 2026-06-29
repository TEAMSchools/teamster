# Finalsite to Focus idempotent imports — design

Tracking issue: [#4279](https://github.com/TEAMSchools/teamster/issues/4279)
(closes [#4208](https://github.com/TEAMSchools/teamster/issues/4208)).

## Problem

The five `rpt_focus__*` SFTP extracts (Demographics, Student_Enrollment,
Addresses, Contacts, Linked_Students) re-emit **every** in-scope Finalsite row
on every run. Nothing compares the outbound data to what already lives in Focus,
so Focus is asked to re-import unchanged rows continuously and entry/withdrawal
codes risk being overwritten. We also need to resolve the #4208 enrollment-code
gap and apply the Florida-required student-id prefix.

## Current architecture

```text
Finalsite (API)  ->  kipptaf_extracts.rpt_focus__*   (desired state, all rows)
                          |  source("kipptaf_extracts", ...)
                          v
                     kippmiami_extracts.rpt_focus__*  (thin pass-through)
                          |  Dagster build_bigquery_query_sftp_asset
                          v
                     Focus SFTP  incoming/*.csv
```

- Desired-state logic lives in `kipptaf` and reads `stg_finalsite__*`,
  `int_finalsite__*`, and Google-Sheets crosswalks.
- The `kippmiami` models are pass-throughs that the Dagster extract reads.
- The `focus` dbt package (current Focus SIS state, dlt-loaded) is a package of
  `kippmiami` **only** — `kipptaf` cannot reach it.

### Identity / match key

`int_finalsite__contact_id_attributes.focus_student_id` is a 6-digit
Finalsite-minted id (e.g. `305000`). Focus `students.student_id` is the 10-digit
Florida id (e.g. `8400305000`). The relationship is:

```text
focus.students.student_id = 8400000000 + finalsite.focus_student_id
                          = concat('8400', focus_student_id)
```

1,376 of 3,088 minted ids already exist in Focus; the remainder are new. After
requirement 5 (prefix) the exported id equals `students.student_id` directly, so
all diffs join on a single clean key.

## Requirements

1. **Addresses, Contacts, Linked Students — import once.** Drop a student from
   the extract once a row exists in that extract's Focus destination table.
2. **Demographics — diff.** Emit only unmatched students and students whose
   populated values differ from Focus.
3. **Student Enrollment — diff with code exception.** Emit only unmatched and
   changed records, EXCEPT entry and withdrawal codes, which import once and are
   never overwritten.
4. **#4208 codes.** `ENROLLMENT_CODE` = `E05` for KG, `E01` for everyone else.
   `DROP_CODE` comes from the Finalsite field `fl_state_withdraw_codes_ss`.
5. **8400 id prefix.** Prefix `focus_student_id` with the constant `8400` on
   every emitted student id. Florida-required; Finalsite autoincrement cannot
   hold the full value.

## Design

Division of labor stays aligned with the existing layers:

- **`kipptaf` (desired state)** — work with no Focus dependency: the 8400 prefix
  (req 5) and the grade-based enrollment code (req 4). It also carries the raw
  withdraw label forward for downstream decode.
- **`kippmiami` (reconciliation)** — everything that needs current Focus state:
  the drop-code decode, all diff/import-once filtering, and the new Focus
  staging models. This is the only layer with both the `finalsite` and `focus`
  packages.

### Req 5 — 8400 prefix (kipptaf, all five models)

Replace every `ida.focus_student_id as <id>` projection with:

```sql
concat('8400', ida.focus_student_id) as student_id
```

Applies to `rpt_focus__demographics` (`stdt_id`), `rpt_focus__addresses`,
`rpt_focus__contacts`, `rpt_focus__student_enrollment` (`student_id`), and both
ids in `rpt_focus__linked_students`. `concat` returns `NULL` when
`focus_student_id` is `NULL`, preserving current null behavior. In
`linked_students`, `least`/`greatest` over the prefixed fixed-width strings keep
the same pair-normalization (equal prefix preserves order).

### Req 4 — enrollment + withdraw codes

`kipptaf/.../rpt_focus__student_enrollment.sql`:

- **ENROLLMENT_CODE** — drop the `enrollment_code_crosswalk` join. Derive from
  grade, only for entry actions:

  ```sql
  case
      when l.lifecycle_action = 'transfer_out'
      then cast(null as string)
      when l.grade_canonical_name = 'k'
      then 'E05'
      else 'E01'
  end as enrollment_code
  ```

  `E05` = "Entering PK or KG First Time"; `E01` = "In District Previous Year"
  (verified against `stg_focus__student_enrollment_codes`). Assumption: req 4 is
  purely grade-based for all entries, including re-enrollers (per the literal
  instruction "everyone else E01").

- **DROP_CODE** — drop the `drop_code_crosswalk` join. Carry the raw
  `cca.fl_state_withdraw_codes_ss` forward as `state_withdraw_label` (a renamed
  carrier column). The decode to a Focus short code happens in `kippmiami`
  (needs `stg_focus__student_enrollment_codes`).

The withdraw label is a human string such as `(W02) In District Transfer`. It
matches `stg_focus__student_enrollment_codes.title` (where `type = 'Drop'`) at
100% across the 7 distinct values present, yielding the `short_name` (`W02`,
`W3A`, `W3D`, `OUTAPP`, ...). Decode in `kippmiami`:

```sql
left join {{ ref("stg_focus__student_enrollment_codes") }} as dc
    on e.state_withdraw_label = dc.title
    and dc.type = 'Drop'
-- then: dc.short_name as drop_code
```

### Req 2 — demographics diff (kippmiami)

`kippmiami/.../rpt_focus__demographics.sql` joins current Focus state and keeps
a row when the student is **unmatched** OR any **populated** export value
differs.

Comparison set (only columns present on both sides; null-placeholder export
columns and Focus-absent columns such as `nickname`/`photo_vid_perm` are
excluded from the diff):

| Export column                              | Focus source                                       | Normalization for comparison             |
| ------------------------------------------ | -------------------------------------------------- | ---------------------------------------- |
| `last_name` / `first_name` / `middle_name` | `stg_focus__students`                              | direct string                            |
| `dt_birth` (`YYYYMMDD`)                    | `students.birthdate` (timestamp)                   | `format_date('%Y%m%d', birthdate)`       |
| `gender` (`M`/`F`)                         | `int_focus__students__pivot.sex_label` (`Male[M]`) | `regexp_extract(sex_label, r'\[(.+)\]')` |
| `stdt_email`                               | `students.student_e_mail_address`                  | direct string                            |
| `ethnic_hl` (`Y`/`N`)                      | `ethnicity_hispanic_or_latino_label` (`Yes`/`No`)  | map `Yes`->`Y`, `No`->`N`                |
| `race_*` (`Y`/null)                        | `race_*_label` (`Yes`/`No`)                        | map `Yes`->`Y`, `No`->null               |
| `lang` (FLDOE code)                        | `language_label` (`EN`)                            | compare code to label directly           |

Match key: `demographics.stdt_id = students.student_id` (both 8400-prefixed
after req 5). A NULL-safe per-field comparison (`a is distinct from b`) over the
normalized values drives the keep predicate; unmatched students
(`students.student_id is null`) are always kept.

### Req 3 — enrollment diff with code import-once (kippmiami)

`kippmiami/.../rpt_focus__student_enrollment.sql`:

- Match a desired enrollment to a Focus enrollment on
  `(student_id, start_date)`. This is the natural grain of
  `stg_focus__student_enrollment`: verified `(student_id, start_date)` is unique
  (9,591 of 9,591 rows), while `(student_id, syear, school_id)` collides (9,487)
  because a student can have multiple spans in one year+school. `syear`,
  `school_id`, and `grade_id` are enrollment attributes, not key. Focus
  `start_date` is a `DATE` (`2024-07-01`) and the export emits `YYYYMMDD`, so
  the join normalizes one side
  (`format_date('%Y%m%d', fe.start_date) = e.start_date`).
- **Keep** a row when unmatched OR any non-code field (`grade_id`, `syear`,
  `school_id`, `end_date`) differs from the Focus enrollment.
- **ENROLLMENT_CODE / DROP_CODE import-once:** emit the computed code only when
  the matched Focus enrollment does not already carry one; otherwise emit `NULL`
  so Focus never overwrites:

  ```sql
  if(fe.enrollment_code is null, e.enrollment_code, cast(null as string))
      as enrollment_code,
  if(fe.drop_code is null, e.decoded_drop_code, cast(null as string))
      as drop_code,
  ```

  (`fe` = matched `stg_focus__student_enrollment` row.) For unmatched
  enrollments `fe.*` is null, so both codes emit in full on first import.

### Req 1 — import once for addresses / contacts / linked students (kippmiami)

These exclude a student once the matching Focus destination row exists.
Destinations (from the import templates and `dlt/focus/config/focus.yaml`):

| Extract         | Focus destination                                            | Exclusion test                              |
| --------------- | ------------------------------------------------------------ | ------------------------------------------- |
| Addresses       | `students_join_address` -> `address`                         | student has any `students_join_address` row |
| Contacts        | `students_join_people` -> `people` -> `people_join_contacts` | student has any `students_join_people` row  |
| Linked Students | `students_join_students`                                     | the (primary, secondary) pair exists        |

**Prerequisite (blocker):** `students_join_address`, `students_join_people`,
`people`, and `students_join_students` are listed in the dlt config but were
**never materialized** in BigQuery (Focus source has no rows yet), and have no
`stg_focus__` models. Work:

1. **dlt** — confirm why these tables do not materialize (likely the
   `sql_database` source skips empty/absent source tables) and ensure they are
   created (even empty) on the next pull, so dbt sources resolve.
2. **focus staging** — add `stg_focus__students_join_address`,
   `stg_focus__students_join_people`, `stg_focus__people`, and
   `stg_focus__students_join_students` (contract-enforced, soft-delete filtered
   where applicable), plus `sources-bigquery.yml` entries.
3. **kippmiami extracts** — left join the relevant link table on
   `student_id`/pair and keep only rows with no match (anti-join).

Until the source tables exist the staging models cannot build; the dlt task
gates the rest of req 1.

## Files

**Modify (`kipptaf`):**

- `models/extracts/focus/rpt_focus__{demographics,addresses,contacts,student_enrollment,linked_students}.sql`
  (+ matching `properties/*.yml`) — 8400 prefix; enrollment + carrier label
  changes; drop the two crosswalk joins in `student_enrollment`.

**Modify (`kippmiami`):**

- `models/extracts/focus/rpt_focus__*.sql` (+ `properties/*.yml`) — Focus joins,
  diff/import-once filters, drop-code decode.
- `models/extracts/sources.yml` — any new cross-project/source wiring.

**Create (`focus` package):**

- `models/staging/stg_focus__students_join_address.sql` (+ yml)
- `models/staging/stg_focus__students_join_people.sql` (+ yml)
- `models/staging/stg_focus__people.sql` (+ yml)
- `models/staging/stg_focus__students_join_students.sql` (+ yml)
- `models/staging/sources-bigquery.yml` — four new source tables.

**Modify (Dagster):**

- `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml` / related
  — ensure the four link tables materialize.

## Testing

- dbt **unit tests** per modified extract model: mock Finalsite inputs + a
  mocked Focus state row and assert (a) unmatched rows pass through, (b)
  byte-identical matched rows are dropped, (c) a single changed field re-emits,
  (d) import-once nulls codes when Focus already has them, (e) the 8400 prefix
  is applied, (f) `E05`/`E01` by grade, (g) the withdraw-label decode.
- `dbt build` of the focus staging additions once the dlt tables exist.
- Full diff sanity check in BigQuery against live `kippmiami_focus` after build.

## Open questions / assumptions

1. **Enrollment match grain — RESOLVED.** `(student_id, start_date)` is the
   unique grain (9,591/9,591); `syear`/`school_id`/`grade_id` are attributes.
2. **School-id alignment.** `school_id` is now a compared attribute (not a join
   key). Export `school_id` (`location_focus_school_id`) and
   `stg_focus__student_enrollment.school_id` must share the same value domain or
   the diff will treat every matched row as changed; verify during
   implementation.
3. **Enrollment code scope.** Assumed purely grade-based for all entries
   (re-enrollers included). Confirm with registrar if re-enrollers should keep
   an R-code instead of `E01`.
4. **dlt link-table materialization.** Root cause of the missing
   `students_join_*` tables to be confirmed; may need a dlt source-config change
   or a one-time pull.

## Out of scope

- Race/ethnicity value mapping beyond the confirmed `Yes`/`No` -> `Y`/`N`/null
  normalization.
- Any change to the SFTP transport (filenames, schedule, headers).
- Backfilling or correcting historical Focus data.
