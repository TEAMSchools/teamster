# Batch L — join-path FK fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all 8 originally-failing `relationships` tests in batch L by
rerouting `dim_courses` and `dim_students` to canonical PowerSchool staging and
sanitizing pre-2000 junk dates at the staging layer.

**Architecture:** `dim_courses` switches source from
`base_powerschool__course_enrollments` to `stg_powerschool__courses` with a
`_dbt_source_relation` token replacement to keep `course_key` hash-compatible
with `dim_course_sections`. `dim_students` switches source from
`int_extracts__student_enrollments` to `stg_powerschool__students` plus four
LEFT JOINs (`stg_kippadb__contact`, `stg_powerschool__u_studentsuserfields`,
`stg_powerschool__s_nj_stu_x`, `stg_powerschool__studentcorefields`) that
preserve student-grain attributes; `meal_eligibility_status` and `has_iep` are
dropped (they're enrollment attributes, not student attributes). Date
sanitization wraps offending date columns with
`if(<col> < date '2000-01-01', null, <col>)` at five staging models, with
`dbt_utils.expression_is_true` warn-severity tests guarding regressions.

**Tech Stack:** dbt-bigquery, BigQuery, dbt_utils, trunk
(sqlfluff/markdownlint).

**Spec:**
[`docs/superpowers/specs/2026-05-04-batch-l-join-path-fk-fixes-design.md`](../specs/2026-05-04-batch-l-join-path-fk-fixes-design.md)

**Worktree:**
`/workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes`

**Branch:** `cbini/fix/claude-batch-l-fk-fixes` (linked to #3719; PR closes
#3719, #3721, #3723).

**Conventions to remember:**

- All dbt commands MUST use
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` and `--target dev`.
- All git commands MUST use `git -C <worktree>` from outside the worktree, or
  `cd` once and stay there.
- Use Edit / Read / Write tools — not `cat`/`sed`/`echo` via Bash.
- Trunk formats automatically on PostToolUse; do not run `trunk fmt` manually.
- Do not commit with `--no-verify`.

---

## File Structure

**Files modified (8 SQL, 4 YAML):**

- `src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql` (rewrite)
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml` (update
  source_column metadata)
- `src/dbt/kipptaf/models/marts/dimensions/dim_students.sql` (rewrite)
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_students.yml` (drop 2
  columns, update metadata)
- `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__calendar_day.sql`
  (wrap from pure union to union+sanitize)
- `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__calendar_day.yml`
  (add expression_is_true test)
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
  (sanitize `date_taken`)
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`
  (add expression_is_true test)
- DeansList incident & consequence staging: located in Task 4c during impl
- Student-scoped assessment date origin (1900-01-01 source): located in Task 4d
  during impl

**Files NOT modified (verified during planning):**

- `dim_course_sections.sql` — keeps existing `_dbt_source_relation` value
  `...base_powerschool__sections`; the reroute fixes hash compatibility on the
  dim_courses side.
- `dim_dates.sql` — already spans 2000–9999; bad data will become NULL upstream.

---

## Task 0: Pre-flight verification

**Files:** none (verification only)

- [ ] **Step 0.1: Confirm working directory and branch**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes status
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes log --oneline -3
```

Expected: branch is `cbini/fix/claude-batch-l-fk-fixes`, recent commits include
the spec and severity-update commits, working tree clean.

- [ ] **Step 0.2: Merge latest main**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes fetch origin main
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes merge origin/main --no-edit
```

Expected: clean merge or "Already up to date."

- [ ] **Step 0.3: Snapshot pre-change CI warnings baseline**

Use `mcp__dbt__list_jobs_runs` to find the most recent successful run on `main`
for the kipptaf CI job. Then call `mcp__dbt__get_job_run_error` with
`run_id=<that run>, warning_only=true`. Save the warning list to
`.claude/scratch/batch-l-warnings-baseline.txt` (use the Write tool). This is
the comparison set for Task 6.

If the warnings list is empty, write `EMPTY` to the file. The diff in Task 6
still runs.

---

## Task 1: Audit `dim_students` consumers for to-be-dropped columns

The spec drops `meal_eligibility_status` and `has_iep` from `dim_students`
(they're enrollment attributes, not student-grain). Verify no SQL or exposure
consumer references these by name before changing the schema.

**Files:** none (audit only).

- [ ] **Step 1.1: Audit SQL references**

Run:

```bash
grep -rnE "meal_eligibility_status|has_iep" /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes/src/dbt/ --include="*.sql"
```

Expected: zero or only-self-reference (current `dim_students.sql`). If any other
model references them, STOP and surface to user before continuing.

- [ ] **Step 1.2: Audit YAML / exposure references**

Run:

```bash
grep -rnE "meal_eligibility_status|has_iep" /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes/src/dbt/ --include="*.yml" --include="*.yaml"
```

Expected: only references in `dim_students.yml` (the column definitions we're
removing). If `cube.yml` or any exposure file references either column, STOP and
surface to user.

- [ ] **Step 1.3: Document audit result**

Append findings to `.claude/scratch/batch-l-audit.md` (Write tool). Format:

```markdown
# Batch L pre-change audit (Task 1)

## meal_eligibility_status references

<list, or "none outside dim_students.{sql,yml}">

## has_iep references

<list, or "none outside dim_students.{sql,yml}">
```

---

## Task 2: Reroute `dim_courses` (#3721)

`dim_courses` switches source from `base_powerschool__course_enrollments`
(enrollment-derived; misses courses with no in-scope enrollments) to
`stg_powerschool__courses` (canonical catalog). Two design points:

1. `stg_powerschool__courses` is grain-correct on
   `(course_number, _dbt_source_relation)` — verified via BigQuery uniqueness
   check during planning. No `dbt_utils.deduplicate` needed.
2. `dim_course_sections.course_key` hashes
   `(courses_course_number, base_powerschool__sections_relation)`. To keep the
   FK chain intact, `dim_courses` must hash a `_dbt_source_relation` ending in
   `base_powerschool__sections`, not `stg_powerschool__courses`. Use a string
   `replace()` to normalize.
3. `discipline` (academic_subject) is not on `stg_powerschool__courses`; it
   comes from `stg_google_sheets__assessments__course_subject_crosswalk`, joined
   on `course_number`.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml`

- [ ] **Step 2.1: Read current `dim_courses.sql` and YAML to confirm column
      inventory**

Read both files. Current columns: `course_key`, `course_code`, `course_title`,
`credit_type`, `academic_subject`, `credits`. All preserved.

- [ ] **Step 2.2: Rewrite `dim_courses.sql`**

Replace the entire file contents with:

```sql
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "c.course_number",
                (
                    "replace(c._dbt_source_relation,"
                    " 'stg_powerschool__courses',"
                    " 'base_powerschool__sections')"
                ),
            ]
        )
    }} as course_key,

    c.course_number as course_code,
    c.course_name as course_title,
    c.credittype as credit_type,
    csc.discipline as academic_subject,
    c.credit_hours as credits,

from {{ ref("stg_powerschool__courses") }} as c
left join
    {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
    on c.course_number = csc.powerschool_course_number
```

Notes:

- Single source — no union model joining needed beyond the cross-source
  crosswalk (which is keyed on course_number alone, no `_dbt_source_relation`).
- The `replace()` token rewrites `..._powerschool.stg_powerschool__courses` to
  `..._powerschool.base_powerschool__sections`, matching the
  `_dbt_source_relation` value used by `dim_course_sections`.

- [ ] **Step 2.3: Update `dim_courses.yml` source_column metadata**

The `course_code` column already documents
`source_model: stg_powerschool__courses`, `source_column: course_number` — keep
as-is.

The `credit_type` column currently has
`source_model: stg_powerschool__storedgrades`, `source_column: credit_type` —
this is wrong (stale). Update to:

```yaml
config:
  meta:
    source_system: PowerSchool
    source_model: stg_powerschool__courses
    source_column: credittype
```

The `academic_subject` column has no source metadata — add:

```yaml
config:
  meta:
    source_system: Google Sheets
    source_model: stg_google_sheets__assessments__course_subject_crosswalk
    source_column: discipline
```

The model description currently says "Attributes represent the most recent
non-null values from the PowerSchool course table as observed in enrollment
records." This is no longer accurate — replace with:

```yaml
description: >-
  Course catalog dimension. One row per course per source region. Course numbers
  are not unique across regions, so the surrogate key includes the source
  relation. Sourced from the canonical PowerSchool course catalog;
  academic_subject joins the assessment course-subject crosswalk by course
  number.
```

- [ ] **Step 2.4: Build the model and run uniqueness test**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select dim_courses --target dev --project-dir src/dbt/kipptaf
```

Expected: model builds, uniqueness test passes.

If the build fails with "table not found" on a staging dependency, follow
`src/dbt/CLAUDE.md` → "Dev `--defer` for unstaged externals" — add
`--defer --state=src/dbt/kipptaf/target/prod/`.

- [ ] **Step 2.5: Run `dim_course_sections.course_key` relationships test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt test --select dim_course_sections --target dev --project-dir src/dbt/kipptaf
```

Expected:
`relationships_dim_course_sections_course_key__course_key__ref_dim_courses_`
passes (was failing with 30,241 rows).

If it fails, query the orphan set:

```sql
select count(*) from `<dev_schema>.dim_course_sections` cs
left join `<dev_schema>.dim_courses` c using (course_key)
where c.course_key is null
```

Expected: 0.

- [ ] **Step 2.6: Hash spot-check (5 known courses)**

Pick 5 distinct `course_key` values from the prod `dim_courses`:

```sql
select course_key, course_code from `teamster-332318.kipptaf_marts.dim_courses` limit 5
```

Then verify each appears in the dev rebuild:

```sql
select course_key from `<dev_schema>.dim_courses` where course_key in ('<key1>', ..., '<key5>')
```

Expected: all 5 found. If any are missing, the hash strategy is wrong — STOP and
re-check the `replace()` token.

- [ ] **Step 2.7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes
git add src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml
git commit -m "fix(dbt): reroute dim_courses to stg_powerschool__courses (closes #3721)

Sources from canonical course catalog instead of
base_powerschool__course_enrollments. Hash-compatible via _dbt_source_relation
token replacement so dim_course_sections.course_key FK still resolves.
academic_subject joins course-subject crosswalk by course number."
```

---

## Task 3: Reroute `dim_students` (#3723)

`dim_students` switches source from `int_extracts__student_enrollments`
(current-enrollment-scoped) to `stg_powerschool__students` (canonical, includes
graduated/transferred). Drops `meal_eligibility_status` and `has_iep`
(enrollment attributes, not student attributes per user direction). Keeps
`is_gifted` and `is_ell` via simplified joins (deferred enrollment-attribute
relocation).

**Hash discipline:** `student_key = generate_surrogate_key([student_number])` —
single column, no `_dbt_source_relation`. Hash unchanged across reroute.

**Source map for retained columns:**

| Mart column                   | Source table                                                                        | Column / logic                                                                                                                                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `lea_student_identifier`      | `stg_powerschool__students`                                                         | `student_number`                                                                                                                                                                                 |
| `district_student_identifier` | derived                                                                             | Miami-only: `state_studentnumber` (the host district MDCPS ID surfaces here for Miami); null for NJ. Region derived from `_dbt_source_relation`.                                                 |
| `state_student_identifier`    | mixed                                                                               | Miami: `suf.fleid`. NJ: `s.state_studentnumber`.                                                                                                                                                 |
| `salesforce_contact_id`       | `stg_kippadb__contact` (LEFT JOIN on `s.student_number = adb.school_specific_id`)   | `adb.id`                                                                                                                                                                                         |
| `full_name`                   | `stg_powerschool__students`                                                         | `concat(s.last_name, ', ', s.first_name)` (simplified — current `lastfirst` is `"Last, First, Mi."`; the simplification drops middle initial, which is consistent with student-grain projection) |
| `birth_date`                  | `stg_powerschool__students`                                                         | `dob`                                                                                                                                                                                            |
| `gender_identity`             | `stg_powerschool__students`                                                         | `gender`                                                                                                                                                                                         |
| `enrollment_status`           | `stg_powerschool__students`                                                         | CASE on `enroll_status` (verbatim from current `dim_students`)                                                                                                                                   |
| `is_gifted`                   | `stg_powerschool__s_nj_stu_x` (njs) + `stg_powerschool__u_studentsuserfields` (suf) | `coalesce(njs.gifted_and_talented, suf.gifted_and_talented, 'N') != 'N'` (simplified to boolean)                                                                                                 |
| `is_ell`                      | `stg_powerschool__studentcorefields` (scf)                                          | `scf.lep_status` (boolean). Simplified — drops the NJ enrollment-date-window logic which requires enrollment context.                                                                            |
| `race`                        | `stg_powerschool__students`                                                         | CASE on `ethnicity` (verbatim from current `dim_students`)                                                                                                                                       |

**Important constraint:** the kipptaf-level `stg_powerschool__students` is a
pure union view. The downstream join targets (`u_studentsuserfields`,
`s_nj_stu_x`, `studentcorefields`) all key on `students_dcid` per district — but
`stg_powerschool__students.dcid` is the same key (DCID is unique per district
per student). All four staging tables carry `_dbt_source_relation`; use
`union_dataset_join_clause` for cross-source safety.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_students.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_students.yml`

- [ ] **Step 3.1: Verify column availability on each join target**

Run BigQuery queries to confirm the columns exist on each kipptaf-level staging:

```sql
select table_name, column_name
from `teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS`
where table_name in (
  'stg_powerschool__u_studentsuserfields',
  'stg_powerschool__s_nj_stu_x',
  'stg_powerschool__studentcorefields'
)
and column_name in (
  'studentsdcid', '_dbt_source_relation',
  'fleid', 'gifted_and_talented',
  'lep_status', 'spedlep'
)
order by table_name, column_name
```

Required:

- `stg_powerschool__u_studentsuserfields`: `studentsdcid`,
  `_dbt_source_relation`, `fleid`, `gifted_and_talented`
- `stg_powerschool__s_nj_stu_x`: `studentsdcid`, `_dbt_source_relation`,
  `gifted_and_talented`
- `stg_powerschool__studentcorefields`: `studentsdcid`, `_dbt_source_relation`,
  `lep_status`

Verify `stg_kippadb__contact` has `id` and `school_specific_id`:

```sql
select column_name from `teamster-332318.kipptaf_kippadb.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'stg_kippadb__contact'
and column_name in ('id', 'school_specific_id')
```

Required: both present. If any column is missing or differently named, update
the SQL in Step 3.2 to match. Document any deviation in
`.claude/scratch/batch-l-audit.md`.

- [ ] **Step 3.2: Rewrite `dim_students.sql`**

Replace the entire file contents with:

```sql
with
    students_with_region as (
        select
            s.*,
            initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')) as region,
        from {{ ref("stg_powerschool__students") }} as s
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.student_number"]) }} as student_key,

    s.student_number as lea_student_identifier,

    if(
        s.region = 'Miami', s.state_studentnumber, cast(null as string)
    ) as district_student_identifier,

    if(s.region = 'Miami', suf.fleid, s.state_studentnumber) as state_student_identifier,

    adb.id as salesforce_contact_id,

    concat(s.last_name, ', ', s.first_name) as full_name,

    s.dob as birth_date,
    s.gender as gender_identity,

    coalesce(njs.gifted_and_talented, suf.gifted_and_talented, 'N')
    != 'N' as is_gifted,

    scf.lep_status as is_ell,

    case
        when s.ethnicity = 'B'
        then 'Black/African American'
        when s.ethnicity = 'H'
        then 'Hispanic or Latino'
        when s.ethnicity = 'T'
        then 'Two or More Races'
        when s.ethnicity = 'W'
        then 'White'
        when s.ethnicity = 'I'
        then 'American Indian or Alaska Native'
        when s.ethnicity = 'A'
        then 'Asian'
        when s.ethnicity = 'P'
        then 'Native Hawaiian or Other Pacific Islander'
        when s.ethnicity = 'N'
        then 'Not Hispanic or Latino'
        else 'Not Listed'
    end as race,

    case
        s.enroll_status
        when -2
        then 'Inactive'
        when -1
        then 'Pre-registered'
        when 0
        then 'Currently Enrolled'
        when 1
        then 'Inactive'
        when 2
        then 'Transferred Out'
        when 3
        then 'Graduated'
        when 4
        then 'Imported as Historical'
    end as enrollment_status,

from students_with_region as s
left join
    {{ ref("stg_kippadb__contact") }} as adb
    on s.student_number = adb.school_specific_id
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on s.dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="suf") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
    on s.dcid = njs.studentsdcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="njs") }}
left join
    {{ ref("stg_powerschool__studentcorefields") }} as scf
    on s.dcid = scf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="scf") }}
```

Notes:

- ST06 column ordering: plain refs from `s` first, then constants/functions,
  then logicals (CASE, IF). Re-order during sqlfluff fix-up if needed.
- Join order matches dependency direction (kippadb is the only non-PowerSchool
  source).
- The model description in YAML already documents the
  `district_student_identifier` "Miami-only" semantics — no doc update needed
  for that column.

- [ ] **Step 3.3: Update `dim_students.yml`**

Three changes:

**(a) Drop the `meal_eligibility_status` block** (lines 101-106 in current file,
both the column entry and any data_tests).

**(b) Drop the `has_iep` block** (lines 130-134 in current file).

**(c) Update source_column metadata for retained columns:**

For `lea_student_identifier`: `source_model` is already
`stg_powerschool__students` and `source_column: student_number` — keep.

For `state_student_identifier`: change `source_column` to:

```yaml
config:
  meta:
    source_system: PowerSchool
    source_model:
      stg_powerschool__students, stg_powerschool__u_studentsuserfields
    source_column: state_studentnumber (NJ); fleid (Miami)
    contains_pii: true
```

For `salesforce_contact_id`: add `config.meta`:

```yaml
config:
  meta:
    source_system: Salesforce (KIPPADB)
    source_model: stg_kippadb__contact
    source_column: id
    contains_pii: true
```

For `full_name`: change `source_column`:

```yaml
config:
  meta:
    source_system: PowerSchool
    source_model: stg_powerschool__students
    source_column: last_name, first_name
    contains_pii: true
```

For `is_gifted` description, update to reflect new logic:

```yaml
- name: is_gifted
  data_type: boolean
  description: >-
    TRUE if the student has a gifted-and-talented identification on either the
    PowerSchool NJ extension or Miami user-fields extension.
  config:
    meta:
      source_system: PowerSchool
      source_model:
        stg_powerschool__s_nj_stu_x, stg_powerschool__u_studentsuserfields
      source_column: gifted_and_talented
```

For `is_ell` description, update to reflect simplification:

```yaml
- name: is_ell
  data_type: boolean
  description: >-
    TRUE if the student is currently classified as an English Language Learner
    per the PowerSchool student core fields. Reflects current status only — does
    not reflect historical enrollment-date-window LEP status.
  config:
    meta:
      source_system: PowerSchool
      source_model: stg_powerschool__studentcorefields
      source_column: lep_status
```

For `enrollment_status`, source_model is already correct — keep.

For the model description (lines 3-6), it currently says "Contains stable
person-level attributes only. Enrollment history is in
dim_student_enrollments..." That's still accurate — keep.

- [ ] **Step 3.4: Build and test**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select dim_students --target dev --project-dir src/dbt/kipptaf
```

Expected: model builds, uniqueness/not_null tests pass.

- [ ] **Step 3.5: Run `bridge_student_contacts.student_key` relationships test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt test --select bridge_student_contacts --target dev --project-dir src/dbt/kipptaf
```

Expected:
`relationships_bridge_student_contacts_student_key__student_key__ref_dim_students_`
passes (was failing with 9,835 rows).

If it fails, query the orphan set:

```sql
select count(*) from `<dev_schema>.bridge_student_contacts` b
left join `<dev_schema>.dim_students` d using (student_key)
where d.student_key is null
```

Expected: 0.

- [ ] **Step 3.6: Hash spot-check (5 known students)**

Pick 5 `student_key` values from prod:

```sql
select student_key, lea_student_identifier from `teamster-332318.kipptaf_marts.dim_students` limit 5
```

Verify each appears in dev:

```sql
select student_key from `<dev_schema>.dim_students` where student_key in ('<key1>', ..., '<key5>')
```

Expected: all 5 found. If any missing, hash inputs drifted — STOP.

- [ ] **Step 3.7: Spot-check downstream student-FK facts**

For each fact that FKs to `dim_students.student_key`, run its relationships
test:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt test --select fct_assessment_scores_enrollment_scoped fct_assessment_scores_student_scoped fct_behavioral_incidents fct_behavioral_consequences --target dev --project-dir src/dbt/kipptaf 2>&1 | grep -E "student_key|PASS|FAIL|WARN"
```

Expected: every `*_student_key__student_key__ref_dim_students_` test PASSes (or
stays at its prior pass/warn state — no new regressions). If a test that was
passing now fails, the dim grew/shrank in an unexpected direction — STOP and
investigate.

- [ ] **Step 3.8: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes
git add src/dbt/kipptaf/models/marts/dimensions/dim_students.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_students.yml
git commit -m "fix(dbt): reroute dim_students to stg_powerschool__students (closes #3723)

Sources from canonical PowerSchool student catalog (includes
graduated/transferred students) instead of int_extracts__student_enrollments.
LEFT JOINs kippadb contact for salesforce_contact_id and PS extension tables
for fleid, gifted_and_talented, lep_status. Drops meal_eligibility_status and
has_iep (enrollment attributes, not student attributes). is_ell simplified to
current PS core-fields lep_status flag (drops enrollment-date-window logic)."
```

---

## Task 4: Sanitize pre-2000 dates at staging (#3719)

Apply `if(<col> < date '2000-01-01', null, <col>)` at the staging model where
each fact's date originates. Add `dbt_utils.expression_is_true` test at
`severity: warn` per spec.

Five sites to patch:

1. `stg_powerschool__calendar_day.date_value` → `dim_school_calendars.date_key`
2. DeansList incident close-date staging →
   `fct_behavioral_incidents.close_date_key`
3. DeansList consequence start/end-date staging →
   `fct_behavioral_consequences.{start,end}_date_key`
4. `int_assessments__response_rollup.date_taken` →
   `fct_assessment_scores_enrollment_scoped.test_date_key`
5. Student-scoped assessment date origin (1900-01-01, 100 rows) →
   `fct_assessment_scores_student_scoped.test_date_key`

### Task 4a: PowerSchool `calendar_day` (3 rows, `1900-01-01`)

The kipptaf-level `stg_powerschool__calendar_day` is currently a pure
`union_relations()` macro call. To add sanitization, wrap it.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__calendar_day.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__calendar_day.yml`

- [ ] **Step 4a.1: Read current SQL and YAML**

Read both files. Confirm the kipptaf-level SQL is a pure union, and the YAML has
a `data_tests:` block (or model-level config) we can add an `expression_is_true`
to.

- [ ] **Step 4a.2: Rewrite `stg_powerschool__calendar_day.sql`**

Replace contents with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__calendar_day"),
                    source("kippcamden_powerschool", "stg_powerschool__calendar_day"),
                    source("kippmiami_powerschool", "stg_powerschool__calendar_day"),
                    source("kipppaterson_powerschool", "stg_powerschool__calendar_day"),
                ]
            )
        }}
    )

select
    * except (date_value),

    if(date_value < date '2000-01-01', null, date_value) as date_value,
from union_relations
```

- [ ] **Step 4a.3: Add expression_is_true test to
      `stg_powerschool__calendar_day.yml`**

Locate the `date_value` column entry in the YAML. Add a `data_tests:` block (or
extend the existing one). The full column spec should look like:

```yaml
- name: date_value
  data_tests:
    - dbt_utils.expression_is_true:
        arguments:
          expression: "date_value is null or date_value >= '2000-01-01'"
        config:
          severity: warn
```

If the column already has tests, append the new one. If the YAML doesn't
currently list `date_value` as a column entry, add the entry.

- [ ] **Step 4a.4: Build and test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select stg_powerschool__calendar_day --target dev --project-dir src/dbt/kipptaf
```

Expected: build passes, new test passes (warn severity).

- [ ] **Step 4a.5: Build and test `dim_school_calendars`**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select dim_school_calendars --target dev --project-dir src/dbt/kipptaf
```

Expected:
`relationships_dim_school_calendars_date_key__date_key__ref_dim_dates_` passes
(was failing with 3 rows).

### Task 4b: DeansList incident close-date

- [ ] **Step 4b.1: Locate the upstream date column**

`fct_behavioral_incidents.close_date_key` originates in DeansList. Find the
producing model:

```bash
grep -rln "close_date_key\|closed_at" /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes/src/dbt/kipptaf/models --include="*.sql"
```

Then trace from `fct_behavioral_incidents.sql` upward to find the staging
`stg_deanslist__*` or `int_deanslist__*` model that emits the column ultimately
mapped to `close_date_key`.

Document the exact producing file path and column name in
`.claude/scratch/batch-l-audit.md`.

- [ ] **Step 4b.2: Apply sanitization in the producing staging/intermediate
      model**

In the model identified in 4b.1, wrap the date column with the standard guard.
If the column is currently `select cast(<source_col> as date) as <col>`, change
to:

```sql
if(
    cast(<source_col> as date) < date '2000-01-01',
    null,
    cast(<source_col> as date)
) as <col>
```

Or if the column is already a `date` value passed through, change `<col>` to
`if(<col> < date '2000-01-01', null, <col>) as <col>`.

- [ ] **Step 4b.3: Add expression_is_true test in the producing model's
      properties YAML**

Same pattern as Task 4a.3, on the producing column.

- [ ] **Step 4b.4: Build and test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select <producing_model>+ fct_behavioral_incidents --target dev --project-dir src/dbt/kipptaf
```

Expected: builds pass,
`relationships_fct_behavioral_incidents_close_date_key__date_key__ref_dim_dates_`
passes (was failing with 3 rows).

### Task 4c: DeansList consequence start/end-date

- [ ] **Step 4c.1: Locate the upstream date columns**

Trace `fct_behavioral_consequences.start_date_key` and `.end_date_key` to their
staging/intermediate origin. They likely come from a single producing model with
both columns.

```bash
grep -rln "start_date_key\|end_date_key\|consequence" /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes/src/dbt/kipptaf/models/deanslist /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes/src/dbt/deanslist --include="*.sql"
```

Document the path and column names.

- [ ] **Step 4c.2: Apply sanitization to both columns in the producing model**

Same pattern as 4b.2, applied to both date columns.

- [ ] **Step 4c.3: Add expression_is_true tests for both columns**

Two test entries in the YAML, one per column.

- [ ] **Step 4c.4: Build and test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select <producing_model>+ fct_behavioral_consequences --target dev --project-dir src/dbt/kipptaf
```

Expected: both
`relationships_fct_behavioral_consequences_*_date_key__date_key__ref_dim_dates_`
tests pass (were failing with 1 + 3 rows).

### Task 4d: Illuminate response-rollup `date_taken`

`fct_assessment_scores_enrollment_scoped.test_date_key` (Illuminate branch)
sources from `int_assessments__response_rollup.date_taken`. The 0001-01-01,
0006-01-01, 0201-01-01, 1901-01-15, 1969-12-31, and borderline 1999-12-16 dates
all originate here (~347 rows).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`

- [ ] **Step 4d.1: Read the current model SQL**

Read `int_assessments__response_rollup.sql`. Locate every `select` clause that
emits or passes through `date_taken`. The earlier exploration showed line 21
(`s.date_taken`), line 76 (`(date_taken is null) asc`), line 77
(`date_taken asc`), line 89 (`canonical_administered_at as administered_at`),
line 106 (`min(date_taken) as date_taken`), line 130, line 166.

The cleanest sanitize point is at the staging entry — the first SELECT that
pulls `date_taken` from the source assessment table. Wrap it there so all
downstream CTEs see sanitized values.

Open the file to identify the exact source CTE.

- [ ] **Step 4d.2: Apply sanitization at the source CTE**

In the first CTE that pulls `date_taken` from upstream, change:

```sql
s.date_taken,
```

to:

```sql
if(s.date_taken < date '2000-01-01', null, s.date_taken) as date_taken,
```

Verify subsequent CTEs that reference `date_taken` (line 76, 77, 106, etc.)
continue to work unchanged — they consume the now-sanitized value.

- [ ] **Step 4d.3: Add expression_is_true test on `date_taken`**

In `properties/int_assessments__response_rollup.yml`, find the `date_taken`
column entry and add:

```yaml
data_tests:
  - dbt_utils.expression_is_true:
      arguments:
        expression: "date_taken is null or date_taken >= '2000-01-01'"
      config:
        severity: warn
```

If the column doesn't have an entry, add one.

- [ ] **Step 4d.4: Build and test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select int_assessments__response_rollup+ fct_assessment_scores_enrollment_scoped --target dev --project-dir src/dbt/kipptaf
```

Expected:
`relationships_fct_assessment_scores_enrollment_scoped_test_date_key__date_key__ref_dim_dates_`
passes (was failing with 347 rows).

### Task 4e: Student-scoped assessment date (100 rows, `1900-01-01`)

`fct_assessment_scores_student_scoped.test_date_key = 1900-01-01` (100 rows).
Need to locate the source.

- [ ] **Step 4e.1: Locate the producing model**

Read `fct_assessment_scores_student_scoped.sql` (find via
`find ... -name "fct_assessment_scores_student_scoped*"`). Identify the upstream
model that supplies `test_date_key` (or its pre-aliased equivalent).

Likely candidates: Renaissance, iReady, Amplify, or a state-assessment
intermediate. The 1900-01-01 sentinel is a classic vendor placeholder. Trace via
`ref()` calls to the staging/intermediate source.

Run a BigQuery query to identify which vendor:

```sql
select <vendor_field>, count(*) as n
from `teamster-332318.kipptaf_marts.fct_assessment_scores_student_scoped`
where test_date_key = date '1900-01-01'
group by 1
```

If the fact has no vendor column, join its `assessment_administration_key` to
`dim_assessment_administrations` and filter by 1900-01-01 to recover the vendor.

Document the producing file in `.claude/scratch/batch-l-audit.md`.

- [ ] **Step 4e.2: Apply sanitization at the producing model**

Same pattern as 4d.2.

- [ ] **Step 4e.3: Add expression_is_true test**

Same pattern as 4d.3.

- [ ] **Step 4e.4: Build and test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select <producing_model>+ fct_assessment_scores_student_scoped --target dev --project-dir src/dbt/kipptaf
```

Expected:
`relationships_fct_assessment_scores_student_scoped_test_date_key__date_key__ref_dim_dates_`
passes (was failing with 100 rows).

### Task 4f: Commit

- [ ] **Step 4f.1: Stage and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes
git add -u
git commit -m "fix(dbt): sanitize pre-2000 dates at staging (closes #3719)

Wraps date columns producing dim_dates FK orphans with
'if(d < 2000-01-01, null, d)' at five staging/intermediate sites:
calendar_day, deanslist incidents/consequences, illuminate response-rollup,
student-scoped assessment vendor. Adds expression_is_true tests at
severity: warn so future upstream typos surface in the warnings audit
without blocking CI."
```

---

## Task 5: Full-graph rebuild and final test sweep

Run the complete affected slice end-to-end to confirm nothing else regressed.

- [ ] **Step 5.1: Build all affected models**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes && uv run dbt build --select dim_courses dim_course_sections dim_students bridge_student_contacts dim_school_calendars fct_assessment_scores_enrollment_scoped fct_assessment_scores_student_scoped fct_behavioral_incidents fct_behavioral_consequences --target dev --project-dir src/dbt/kipptaf 2>&1 | tee .claude/scratch/batch-l-build.log
```

Expected: all models build, all 8 originally-failing relationships tests pass.

- [ ] **Step 5.2: Verify acceptance criteria**

Grep the build log for the 8 originally-failing tests:

```bash
grep -E "relationships_(dim_course_sections_course_key|bridge_student_contacts_student_key|dim_school_calendars_date_key|fct_assessment_scores_(enrollment|student)_scoped_test_date_key|fct_behavioral_incidents_close_date_key|fct_behavioral_consequences_(start|end)_date_key)" .claude/scratch/batch-l-build.log
```

Expected: 8 lines, all PASS.

- [ ] **Step 5.3: Verify the 5 new expression_is_true tests pass at warn**

```bash
grep "expression_is_true" .claude/scratch/batch-l-build.log
```

Expected: 5 entries, all PASS or WARN (warn severity is fine — currently they
should PASS since we sanitized everything).

---

## Task 6: Push, open PR, CI-warnings audit

- [ ] **Step 6.1: Run trunk check on the worktree**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes
```

Expected: clean (no issues). Fix any reported issues before pushing.

- [ ] **Step 6.2: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-batch-l-fk-fixes push origin cbini/fix/claude-batch-l-fk-fixes
```

- [ ] **Step 6.3: Open the PR**

Use the `.github/pull_request_template.md` body. Title:
`fix(dbt): batch L — join-path FK fixes`. Body must reference all three issues
with `Closes` syntax:

```markdown
## Summary

Resolves the 8 `relationships` test failures in
[PR batch L](https://github.com/orgs/TEAMSchools/projects/4):

- `dim_courses` and `dim_students` rerouted from enrollment-derived
  intermediates to canonical PowerSchool staging.
- 5 staging/intermediate models gained pre-2000 date-sanitization guards plus
  regression `expression_is_true` tests at `severity: warn`.
- `meal_eligibility_status` and `has_iep` removed from `dim_students`
  (enrollment attributes; not student-grain).
- `is_ell` simplified to `studentcorefields.lep_status` (drops
  enrollment-date-window logic).

## Closes

- Closes #3719
- Closes #3721
- Closes #3723

## Spec / plan

- Spec: `docs/superpowers/specs/2026-05-04-batch-l-join-path-fk-fixes-design.md`
- Plan: `docs/superpowers/plans/2026-05-04-batch-l-join-path-fk-fixes.md`

## Test plan

- [x] All 8 originally-failing relationships tests pass on dev
- [x] 5 new expression_is_true tests pass at severity: warn
- [x] Hash spot-check: 5 known student_keys + 5 known course_keys verified
      stable
- [ ] dbt Cloud CI passes
- [ ] CI warnings audit completed (see comment after CI green)
```

Use `mcp__github__create_pull_request` with `base="main"`,
`head="cbini/fix/claude-batch-l-fk-fixes"`, `draft=false` (or `true` if you want
to wait on CI before review).

- [ ] **Step 6.4: Wait for dbt Cloud CI**

Find the PR's CI run via:

```bash
gh pr checks <PR_NUMBER> --repo TEAMSchools/teamster
```

When the dbt Cloud check is `success`, proceed.

- [ ] **Step 6.5: Pull post-CI warnings**

Use `mcp__dbt__get_job_run_error` with
`run_id=<the CI run id>, warning_only=true`. Save to
`.claude/scratch/batch-l-warnings-post.txt` (Write tool).

- [ ] **Step 6.6: Diff against baseline**

Compare `.claude/scratch/batch-l-warnings-baseline.txt` (from Task 0.3) and
`.claude/scratch/batch-l-warnings-post.txt`. Categorize each delta into:

- **Bonus closures** — warnings present in baseline but absent post-PR. Look up
  whether each maps to an open issue. If yes, add `Closes #<num>` to the PR
  body.
- **New regressions** — warnings absent in baseline but present post-PR.
  Investigate and fix before merge. STOP if you can't resolve them.
- **Newly surfaced** — warnings absent in baseline AND absent post-PR but only
  because tests that were previously erroring (and skipping warn-level checks
  downstream) are now passing. Less common; identify by inspecting the baseline
  failure list.

Write the categorization to a PR comment via `mcp__github__add_issue_comment`:

```markdown
## CI warnings audit

### Bonus closures

<list, or "none">

### New regressions

<list, or "none">

### Newly surfaced

<list, or "none">

Baseline: `<run_id_baseline>`. Post-PR: `<run_id_post>`.
```

If "Bonus closures" is non-empty, also update the PR body to add `Closes #<num>`
for each bonus issue (use `mcp__github__update_pull_request`).

- [ ] **Step 6.7: Mark PR ready for review**

If opened as draft, mark as ready via
`gh pr ready <PR_NUMBER> --repo TEAMSchools/teamster`.

---

## Self-review checklist (run before declaring complete)

- [ ] All 3 issues closed via PR body
- [ ] All 8 acceptance-criteria tests pass
- [ ] All 5 new expression_is_true tests added and passing
- [ ] Hash spot-checks succeed (no `student_key` or `course_key` drift)
- [ ] CI warnings diff posted and bonus closures linked
- [ ] No `meal_eligibility_status` or `has_iep` references remaining outside
      `dim_students.{sql,yml}` (re-grep)
- [ ] Trunk check clean
- [ ] PR description matches `.github/pull_request_template.md` shape
