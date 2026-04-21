# Column-Naming Audit Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute all approved decisions from the column-naming audit against
mart SQL and YAML, bundled with the two upstream deduplication prerequisites.

**Architecture:** Three phases. Phase 1: upstream dedups (`#3637`, `#3633`) so
downstream `SELECT DISTINCT` workarounds can be removed. Phase 2: apply
per-domain mart changes from the authoritative inventory CSV — 170 renames, 180
removes, 19 structural adds (Groups 1 + 2; Group 3 defers). Phase 3: verify,
sweep exposures, document hash-change impact.

**Tech Stack:** dbt 1.11 on BigQuery, `dbt_utils`, Python (for inventory reading
only), no new code dependencies.

**Authoritative sources:**

- Decisions:
  [docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv](../specs/2026-04-15-column-naming-audit-inventory.csv)
  — the source of truth
- Rubric + rationale:
  [docs/superpowers/specs/2026-04-15-column-naming-audit.md](../specs/2026-04-15-column-naming-audit.md)
- Execution design:
  [docs/superpowers/specs/2026-04-21-column-naming-audit-execution-design.md](../specs/2026-04-21-column-naming-audit-execution-design.md)

---

## Procedure — Per-model change pattern

Each Phase 2 task applies this pattern per model in the domain. Reference this
section from domain tasks; do not repeat it.

### Inputs

- Mart SQL:
  `src/dbt/kipptaf/models/marts/{dimensions,facts,bridges}/<model_name>.sql`
- Mart YAML: adjacent `properties/<model_name>.yml`
- Inventory rows (filter by `model`):
  `docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv`

### Actions

For each inventory row for the model, apply per `action` column:

#### `rename` (170 total)

SQL: change the column alias at the final `SELECT` (or rename in the CTE that
produced it). Do **not** rename the upstream source column — the rename is
mart-layer only unless the inventory's `reviewer_notes` explicitly calls for an
upstream rename.

```sql
-- Before
select
    old_name,
-- After
select
    old_name as new_name,
```

YAML: update `name:` to the proposed name and update the `description:` if the
inventory's `current_description` is more accurate than the existing one.

```yaml
# Before
- name: old_name
  data_type: string
  description: <old description>
# After
- name: new_name
  data_type: string
  description: <new description if present in inventory; else keep>
```

Preserve all `data_tests:` and `config.meta` blocks — migrate them to the
renamed column.

#### `remove` (180 total)

SQL: strip the column from the final `SELECT`. If it was derived in a CTE not
used by any surviving column, remove the derivation too. For `SELECT DISTINCT`
workaround CTEs freed by Phase 1 dedups, remove the entire `SELECT DISTINCT`
CTE.

YAML: delete the column block entirely.

If a removed column was a data-test target (e.g., `unique` on a natural key
being removed), verify the replacement key carries the test.

#### `add` (25 total; 19 in-scope for this PR per Groups 1 + 2)

SQL: add the new column to the final `SELECT`. For FK adds, derive via
`dbt_utils.generate_surrogate_key` wrapping the natural key with the
nullable-wrap helper when the key can be null:

```sql
if(
    source_column is not null,
    {{ dbt_utils.generate_surrogate_key(["source_column"]) }},
    cast(null as string)
) as fk_column,
```

YAML: add the column block. For FK adds, include `not_null` (unless nullable)
and `relationships` tests pointing to the parent dim's `*_key` column.

### Verify after each model

- Run: `uv run dbt parse --project-dir src/dbt/kipptaf`
- Run: `uv run dbt compile --project-dir src/dbt/kipptaf --select <model_name>`
- Expected: parse succeeds, compile emits SQL without warnings for the model.

### Commit after each domain

One commit per Phase 2 task covering all models in the domain. Commit message:
`refactor(dbt): rename mart columns — <domain> domain per #3643`.

---

## Phase 1 — Upstream dedups

### Task 1: Deduplicate `stg_people__employee_numbers` (#3637)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/staging/stg_people__employee_numbers.sql`
- Modify:
  `src/dbt/kipptaf/models/people/staging/properties/stg_people__employee_numbers.yml`
  (or wherever the model's properties live — verify during step 1)
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql` (remove
  workaround)

- [ ] **Step 1: Read the current staging model + properties**

Read `stg_people__employee_numbers.sql` and its properties YAML. Identify the
columns available (especially `is_active`, any date/timestamp column that could
order "most recent"). Confirm the source table.

- [ ] **Step 2: Confirm duplicate pattern empirically**

Run (adjust project path as needed):

```sql
select employee_number, count(*) as n
from `teamster-332318.kipptaf_people.stg_people__employee_numbers`
group by 1 having count(*) > 1
order by n desc
```

Expected: 91 employee_numbers with n>1. Inspect a sample of duplicates to
identify the ordering column for `active-then-recent`.

- [ ] **Step 3: Apply `dbt_utils.deduplicate`**

Wrap the final `select` in a deduplicate call:

```sql
with base as (
    -- existing logic
)
select * from base
qualify row_number() over (
    partition by employee_number
    order by is_active desc, <recent_column> desc
) = 1
```

Or equivalently with `dbt_utils.deduplicate` macro per `src/dbt/CLAUDE.md`
conventions. Per CLAUDE.md, prefer the macro over manual `qualify`:

```sql
{{ dbt_utils.deduplicate(
    relation="base",
    partition_by="employee_number",
    order_by="is_active desc, <recent_column> desc"
) }}
```

Choose `<recent_column>` based on Step 2 findings — document the choice in a SQL
comment.

- [ ] **Step 4: Add uniqueness test in properties YAML**

```yaml
- name: employee_number
  data_type: int64
  description: <existing or updated>
  data_tests:
    - unique
    - not_null
```

- [ ] **Step 5: Remove `dim_staff` workaround**

Open `src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql`. Find the
`SELECT DISTINCT employee_number` CTE with the `-- TODO: #3637` comment. Replace
it with a plain `SELECT employee_number` (the CTE itself may become redundant
and can be inlined).

- [ ] **Step 6: Verify — parse + test**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt build --project-dir src/dbt/kipptaf --select stg_people__employee_numbers+ --target defer
```

Expected: parse succeeds, the new `unique` test passes, `dim_staff` (now without
the DISTINCT) still materializes with a unique `staff_key`.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/people/staging/stg_people__employee_numbers.sql \
        src/dbt/kipptaf/models/people/staging/properties/stg_people__employee_numbers.yml \
        src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql
git commit -m "fix(dbt): deduplicate stg_people__employee_numbers (#3637)

Closes #3637. Picks canonical adp_associate_id per employee_number by
active-then-recent ordering. Removes the SELECT DISTINCT workaround in
dim_staff."
```

---

### Task 2: Deduplicate `int_people__location_crosswalk` (#3633)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__location_crosswalk.sql`
  (verify exact path)
- Modify: its properties YAML
- Modify (8 files, remove DISTINCT workarounds): `dim_locations.sql`,
  `dim_school_calendars.sql`, `dim_student_enrollments.sql`,
  `dim_course_sections.sql`, `dim_assessment_targets.sql`,
  `fct_student_attendance_daily.sql`,
  `fct_student_attendance_interventions.sql`, `fct_behavioral_incidents.sql`

- [ ] **Step 1: Investigate root cause**

Read `int_people__location_crosswalk.sql`. Per `src/dbt/kipptaf/CLAUDE.md`:
"int_people\_\_location_crosswalk is NOT a union model — it has no
\_dbt_source_relation ... produces duplicate rows per
(location_powerschool_school_id, location_dagster_code_location)." Determine
whether dedup belongs upstream (fixing an unintentional join fan-out) or at the
crosswalk itself.

- [ ] **Step 2: Confirm duplicate pattern**

```sql
select location_powerschool_school_id, location_dagster_code_location, count(*) as n
from `teamster-332318.kipptaf_people.int_people__location_crosswalk`
group by 1, 2 having count(*) > 1
order by n desc
```

Capture sample rows to determine which duplicate is canonical.

- [ ] **Step 3: Apply dedup**

If Step 1 found the fan-out source, fix that. Otherwise, apply
`dbt_utils.deduplicate` at
`(location_powerschool_school_id, location_dagster_code_location)` with explicit
`order_by`:

```sql
{{ dbt_utils.deduplicate(
    relation="base",
    partition_by="location_powerschool_school_id, location_dagster_code_location",
    order_by="<canonical_ordering>"
) }}
```

- [ ] **Step 4: Add composite uniqueness test**

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - location_powerschool_school_id
          - location_dagster_code_location
```

- [ ] **Step 5: Remove `SELECT DISTINCT` workarounds in 8 mart consumers**

For each of the 8 files listed in #3633 (see Files above): find the CTE that
does `SELECT DISTINCT` from `int_people__location_crosswalk` (and usually has a
`-- TODO: #3633` comment). Replace with plain `SELECT`, or inline the reference
directly.

- [ ] **Step 6: Verify**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt build --project-dir src/dbt/kipptaf \
    --select int_people__location_crosswalk+ --target defer
```

Expected: parse succeeds, new composite unique test passes, no duplicate errors
in the 8 downstream marts.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/people/intermediate/int_people__location_crosswalk.sql \
        src/dbt/kipptaf/models/people/intermediate/properties/*.yml \
        src/dbt/kipptaf/models/marts/dimensions/dim_locations.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_course_sections.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_assessment_targets.sql \
        src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql \
        src/dbt/kipptaf/models/marts/facts/fct_student_attendance_interventions.sql \
        src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql
git commit -m "fix(dbt): deduplicate int_people__location_crosswalk (#3633)

Closes #3633. Adds composite unique test on (location_powerschool_school_id,
location_dagster_code_location). Removes the SELECT DISTINCT workarounds
from the 8 mart consumers previously flagged with -- TODO: #3633."
```

---

## Phase 2 — Per-domain mart changes

Each task below applies the Procedure section to the listed models. The
inventory CSV is the source of truth for the specific rename targets, remove
sets, and add derivations. Use `pandas` or `uv run python` to filter inventory
rows per model during execution.

For each domain task, the commit message is:

```text
refactor(dbt): rename mart columns — <domain> domain per #3643

Applies <N renames, N removes, N adds> per the audit inventory.
```

### Task 3: IT domain (1 model, validation)

**Models:**

- `fct_support_tickets` — 9 renames, 1 remove, 0 adds

- [ ] **Step 1: Filter inventory**

```bash
uv run --with pandas python <<'PY'
import pandas as pd
df = pd.read_csv('docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv', keep_default_na=False, na_values=[''])
u = df[(df['domain']=='IT') & (df['action'].isin(['rename','remove','add']))]
print(u[['model','current_column','action','proposed_name']].to_string())
PY
```

- [ ] **Step 2: Apply the Procedure to `fct_support_tickets`**

Per inventory: rename `ticket_subject` (keep), `category` → `ticket_category`,
`reply_time_in_minutes_business` → `business_minutes_to_first_reply`,
`assignee_stations` → `agent_reassignment_count`, `group_stations` →
`group_reassignment_count`, `created_date` → `ticket_created_date`, `created_at`
→ `created_timestamp`, `initially_assigned_at` → `initially_assigned_timestamp`,
`assignee_updated_at` → `assignee_updated_timestamp`, `solved_at` →
`solved_timestamp`. Remove `ticket_id`. Fix stale description on `ticket_status`
per inventory `current_description`.

- [ ] **Step 3: Verify**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt compile --project-dir src/dbt/kipptaf --select fct_support_tickets
```

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_support_tickets.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_support_tickets.yml
git commit -m "refactor(dbt): rename mart columns — IT domain per #3643"
```

---

### Task 4: Course domain (4 models)

**Models:**

- `bridge_course_section_teachers`, `bridge_course_section_terms`,
  `dim_course_sections`, `dim_courses` — 7 renames, 5 removes

- [ ] **Step 1: Filter inventory by `domain='Course'` for
      `action in ('rename','remove')`**
- [ ] **Step 2: Apply Procedure per model. Key renames include
      `dim_courses.discipline` → `academic_subject`.**
- [ ] **Step 3: Verify**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt compile --project-dir src/dbt/kipptaf --select bridge_course_section_teachers bridge_course_section_terms dim_course_sections dim_courses
```

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/bridges/bridge_course_section_teachers.sql \
        src/dbt/kipptaf/models/marts/bridges/bridge_course_section_terms.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_course_sections.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql \
        src/dbt/kipptaf/models/marts/**/properties/bridge_course_section_teachers.yml \
        src/dbt/kipptaf/models/marts/**/properties/bridge_course_section_terms.yml \
        src/dbt/kipptaf/models/marts/**/properties/dim_course_sections.yml \
        src/dbt/kipptaf/models/marts/**/properties/dim_courses.yml
git commit -m "refactor(dbt): rename mart columns — Course domain per #3643"
```

---

### Task 5: Staffing domain (1 model)

**Models:**

- `dim_staffing_positions` — 5 renames, 7 removes, 0 adds

Apply Procedure. Key changes: `entity` → REMOVE (blocked by spec follow-up; per
audit notes the cascade requires dim_regions.legal_entity; for this task: remove
the column and accept the traversal loss documented in the spec's Region cascade
section), `grade_band` → REMOVE, `plan_status` → `is_active` (with type coercion
string → boolean), `staffing_status` → keep, `job_title` → `position_title`.

- [ ] **Step 1: Filter inventory**
- [ ] **Step 2: Apply Procedure. Special case — for `plan_status` rename, cast
      to boolean in SQL:
      `case plan_status when 'Active' then true when 'Inactive' then false end as is_active`.**
- [ ] **Step 3: Verify (`dbt compile --select dim_staffing_positions`)**
- [ ] **Step 4: Commit**

---

### Task 6: Talent domain (3 models)

**Models:**

- `dim_job_candidates`, `dim_job_postings`, `fct_job_candidate_applications` —
  24 renames, 26 removes, 1 add

Key changes:

- `candidate_email` → `email`; `candidate_first_and_last_name` → `full_name`;
  `candidate_first_name` → `first_name`; `candidate_last_name` → `last_name`
- `dim_job_postings.job_title` → `position_title`; `.job_city` → `city`;
  `.department_internal` → `department_name`; `.department_org_field_value` →
  `organizational_hierarchy`; `.recruiters` → `recruiter_names`
- `fct_job_candidate_applications.source` → `application_source`;
  `application_field_phone_interview_score` → `phone_interview_score`;
  `application_status_interview_performance_task_date` →
  `application_status_interview_performance_task_timestamp`; `last_update_date`
  → `last_updated_date`
- Removes include `candidate_id`, `candidate_source*` (6 dead cols),
  `job_title`/`department_internal`/`department_org_field_value`/`job_city`/`recruiters`
  on the fact (R9 via `job_posting_key`), `application_status` (dead), 10
  application\_\* dead SmartRecruiters fields, `school_shared_with`
- ADD: `shared_with_location_key` (FK to dim_locations)

- [ ] **Step 1: Filter inventory for `domain='Talent'`**
- [ ] **Step 2: Apply Procedure per model. For `shared_with_location_key`:
      derive via
      `{{ dbt_utils.generate_surrogate_key(["school_shared_with"]) }}` wrapped
      for nullability.**
- [ ] **Step 3: Verify**
- [ ] **Step 4: Commit**

---

### Task 7: Survey domain (7 models)

**Models:**

- `bridge_survey_questions`, `dim_survey_administrations`,
  `dim_survey_expectations`, `dim_survey_questions`, `dim_surveys`,
  `fct_survey_responses`, `fct_survey_submissions` — 5 renames, 11 removes, 0
  adds

Key changes: `dim_surveys.subject_area` → `category`;
`dim_survey_expectations.respondent_population` → `respondent_type`;
`fct_survey_submissions.respondent_population` → `respondent_type`;
`dim_survey_administrations.term_name` REMOVE;
`fct_survey_responses.question_shortname` REMOVE.

- [ ] **Step 1–4: filter, apply, verify, commit**

---

### Task 8: College domain (2 models)

**Models:**

- `dim_college_enrollments`, `dim_colleges` — 3 renames, 4 removes, 0 adds

Key changes: `dim_colleges.college_state` → `state_abbreviation`;
`.is_strong_oos_option` → `is_strong_out_of_state_option`; `.selectivity` →
`selectivity_tier`; REMOVE `dim_college_enrollments.college_code_branch` (R9 via
`college_key`), `two_year_four_year` (dead + redundant), `degree_pursued` (no
upstream source), `candidate_source*` not applicable here.

- [ ] **Step 1–4**

---

### Task 9: Attendance domain (4 models)

**Models:**

- `dim_student_attendance_intervention_types`, `fct_student_attendance_daily`,
  `fct_student_attendance_interventions`, `fct_student_attendance_streaks` — 6
  renames, 12 removes, 2 adds

Key changes:

- `dim_student_attendance_intervention_types.commlog_reason` →
  `family_communication_reason`, `region` REMOVE, ADD `region_key` FK
- `fct_student_attendance_daily`: 6 float→int64 coercions on
  `is_absent`/`is_tardy`/`is_ontime`/`is_oss`/`is_iss`/`is_suspended`;
  `is_present_weighted` → `present_weight` (keep float64); `streak_type` on
  sibling renamed to `attendance_code`
- `fct_student_attendance_interventions`: `intervention_status` → `is_complete`
  (string → boolean cast); `is_ca_exception` → `is_chronic_absence_exception`;
  REMOVE 7 `commlog_*` columns (R9 via new family_communication_key); REMOVE
  `intervention_status_required_int` (redundant); ADD `family_communication_key`
  FK

- [ ] **Step 1–4**

---

### Task 10: Conformed domain (5 models)

**Models:**

- `dim_locations`, `dim_regions`, `dim_school_calendars`, `dim_terms` — 6
  renames, 7 removes, 7 adds

Key changes (cross-cutting cascade):

- `dim_regions.region` → `region_name`
- `dim_locations.region` REMOVE, `powerschool_school_id` REMOVE,
  `deanslist_school_id` REMOVE; ADD `region_key`
- `dim_terms.region` REMOVE, `school_id` REMOVE; ADD `region_key`,
  `location_key`; `lockbox_date` → `data_freeze_date`
- `dim_dates`: 4 week\_\* renames (`week_start_date` →
  `calendar_week_start_date`, `week_end_date` → `calendar_week_end_date`,
  `week_start_monday` → `school_week_start_date`, `week_end_sunday` →
  `school_week_end_date`)

- [ ] **Step 1: Filter inventory for `domain='Conformed'`**
- [ ] **Step 2: Apply Procedure. The region_key FK derivation:**

```sql
if(
    region_name is not null,
    {{ dbt_utils.generate_surrogate_key(["region_name"]) }},
    cast(null as string)
) as region_key,
```

Ensure `dim_regions` PK logic produces the same hash (surrogate_key of `region`
which stays stable as `region_name` string).

- [ ] **Step 3: Verify. Include downstream models that already have `region_key`
      FK (dim_assessment_comparisons) to confirm no cascade breakage.**
- [ ] **Step 4: Commit**

---

### Task 11: Behavioral domain (3 models)

**Models:**

- `fct_behavioral_consequences`, `fct_behavioral_incidents`,
  `fct_family_communications` — 5 renames, 9 removes, 2 adds

Key changes: `num_days` → `days_assigned`; `num_periods` → `periods_assigned`;
`infraction` → `infraction_description`; `fct_family_communications.status` →
`communication_outcome`. ADDS: `referring_staff_key` on
fct_behavioral_incidents, `staff_key` on fct_family_communications. Description
fixes on `consequence_start_date`, `consequence_end_date`, `incident_status`.

- [ ] **Step 1–4**

---

### Task 12: Student domain (5 models)

**Models:**

- `bridge_student_contacts`, `dim_student_contact_persons`,
  `dim_student_enrollments`, `dim_student_section_enrollments`, `dim_students` —
  8 renames, 5 removes, 2 adds

Key changes: `dim_students.lunch_status` → `meal_eligibility_status`; ADD
`district_student_identifier` and `salesforce_contact_id` (per multi-ID
structural additions in spec). Description fixes on
`dim_student_contact_persons.email`/`phone` (flagged as model bug — KEEP with
updated reviewer_notes).

- [ ] **Step 1–4**

---

### Task 13: Gradebook domain (4 models)

**Models:**

- `fct_grades_assignments`, `fct_grades_category`, `fct_grades_gpa`,
  `fct_grades_term` — 7 renames, 9 removes, 2 adds

**⚠ Group 3 structural split is DEFERRED for this PR** —
`fct_grades_assignments.points_earned` + `numeric_grade_earned` stay as proposed
adds in inventory but do not ship in this PR (they require staging changes). In
this task:

- Do NOT add `points_earned` or `numeric_grade_earned` to
  `fct_grades_assignments`.
- Do NOT remove `score` or `score_type` from `fct_grades_assignments` (they
  depend on the split).
- Update `fct_grades_assignments.points_possible` → `max_points` (Ed-Fi rename).
- Apply the other 6 renames, 9 removes, and any other adds.

- [ ] **Step 1: Filter inventory. Skip rows where `current_column` is `score`,
      `score_type`, `points_earned`, or `numeric_grade_earned` on
      fct_grades_assignments.**
- [ ] **Step 2: Apply Procedure; `exclude_from_gpa` → `is_excluded_from_gpa`
      requires type coercion int → boolean (or keep int64 per R3 flag convention
      — inventory says "Convert int64 0/1 to BOOLEAN").**
- [ ] **Step 3–4**

---

### Task 14: Observation domain (8 models)

**Models:**

- `dim_staff_observation_expectations`, `dim_staff_observation_microgoal_types`,
  `dim_staff_observation_rubric_measurements`, `dim_staff_observation_rubrics`,
  `dim_staff_observation_types`, `fct_staff_observation_microgoals`,
  `fct_staff_observation_scores`, `fct_staff_observations` — 19 renames, 36
  removes, 2 adds

Key changes:

- Model renames: `dim_staff_observation_microgoal_types` →
  `dim_staff_observation_goal_types`; `fct_staff_observation_microgoals` →
  `fct_staff_observation_goals`. **Model renames are non-trivial** — cascading
  refactor of the SQL file name, `ref()` callers, and the `dbt_project.yml` if
  the model is explicitly named there.
- All `*_microgoal_*` column renames derive from these model renames.
- `fct_staff_observations.glows` → `positive_feedback`; `.grows` →
  `growth_areas`; `.observation_score` keep; remove `eval_date`,
  `assignment_status`, `term_type`, `term_code`, `term_name`, `term_start_date`,
  `term_end_date` (R9 via `term_key`)
- `dim_staff_observation_rubric_measurements.measurement_row_style` REMOVE
  (plumbing)
- `dim_staff_observation_rubrics.district` REMOVE (plumbing)
- ADDS: `staff_observation_type_key` and `staff_observation_rubric_key` on
  fct_staff_observations

- [ ] **Step 1: Filter inventory for `domain='Observation'`**
- [ ] **Step 2: Apply model renames first (affect file paths and refs), then
      per-model column changes.**
- [ ] **Step 3: Verify with `dbt parse` (both old names should be gone from
      `ref()` calls).**
- [ ] **Step 4: Commit**

---

### Task 15: Assessment domain (6 models)

**Models:**

- `dim_assessment_comparisons`, `dim_assessment_targets`, `dim_assessments`,
  `dim_student_assessment_expectations`,
  `fct_assessment_scores_enrollment_scoped`,
  `fct_assessment_scores_student_scoped` — 10 renames, 24 removes, 4 adds

Key changes:

- `dim_assessments.subject_area` → `academic_subject`; `.scope` →
  `assessment_category` (⚠ **coexistence flag** — dim_assessments also has
  `assessment_scope` per Structural follow-ups; keep both, verify they're
  semantically distinct); `.title` → `assessment_title`
- ADDS: `aligned_academic_subject`, `combined_academic_subject`,
  `credit_category` on dim_assessments; `student_key` on
  dim_student_assessment_expectations
- REMOVES on `fct_assessment_scores_student_scoped`: `subject_area`,
  `course_discipline`, `aligned_subject`, `aligned_subject_area`,
  `assessment_scope` (R9 via assessment_key — all move to dim). Rename
  `rn_highest` → `score_rank`; `score_source` → `score_provider`
- REMOVES on `fct_assessment_scores_enrollment_scoped`: `subject_area`,
  `module_code`, `region`, `assessment_category` denormalized — all R9 via
  `assessment_key`. Rename `score_source` → `score_provider`
- `dim_assessment_targets.illuminate_subject_area` → `academic_subject`;
  `.school_level` REMOVE; `.region` REMOVE

- [ ] **Step 1–4**

---

### Task 16: Staff domain (14 models)

**Models:** `dim_staff`, `dim_staff_status`, `dim_staff_work_assignments`,
`dim_work_assignment_jobs`, `dim_work_assignment_locations`,
`dim_work_assignment_organizational_units`,
`dim_work_assignment_reporting_relationships`, `dim_work_assignment_status`,
`dim_work_assignment_types`, `fct_staff_attrition`,
`fct_staff_benefits_enrollments`, `fct_staff_membership_enrollments`,
`fct_work_assignment_additional_earnings`, `fct_work_assignment_compensation` —
54 renames, 24 removes, 3 adds

**⚠ Largest domain.** Consider splitting this commit into two if the diff is
unreviewably large: `dim_staff` + `dim_staff_work_assignments` in one commit,
the work*assignment*\* SCD2 dims + fcts in another. Still one Phase 2 task but
two commits.

**⚠ Group 3 structural split is DEFERRED** — on `dim_work_assignment_locations`,
do NOT remove the 8 address columns (location_name, address_line_one/two,
city_name, postal_code, country_code, state_code, location_code); do NOT add
`location_key` FK. These all depend on `dim_locations` address unification
(Group 3) which is out of scope.

Key in-scope changes:

- `dim_staff`: `employee_number` → `staff_unique_id`, `formatted_name` →
  `full_name`, `given_name` → `first_name`, `family_name_1` → `last_name`,
  `race_ethnicity_reporting` → `race`, `personal_cell` → `personal_cell_phone`,
  `sam_account_name` → `active_directory_username`
- `dim_staff_work_assignments`: `full_time_equivalence_ratio` →
  `full_time_equivalency`; 7 `*_code__code_value` / `*_name` ADP-structure
  renames per inventory; 4 `worker_time_profile__*` renames;
  `time_and_attendance_indicator` → `is_time_and_attendance_active`; ADD
  `time_service_supervisor_staff_key`
- All SCD2 dims: `effective_date_start` → `effective_start_date`,
  `effective_date_end` → `effective_end_date`, `is_current_record` →
  `is_current` (uniform pattern)
- `dim_work_assignment_jobs.job_title` → `position_title`; `.job_code_name` →
  `job_code_description`
- `dim_work_assignment_reporting_relationships`: 6 manager\_\* column removes
  (R9); ADD `manager_staff_key` FK
- `fct_work_assignment_compensation`: `annual_rate` → `annual_wage`,
  `hourly_rate` → `hourly_wage`
- `fct_staff_benefits_enrollments.enrollment_status` REMOVE (100% Active, dead)

- [ ] **Step 1–4** (consider 2 commits per note above)

---

## Phase 3 — Verification and cleanup

### Task 17: Exposure sweep

**Files:**

- Check: `src/dbt/kipptaf/models/exposures/**/*.yml`

- [ ] **Step 1: Enumerate renamed columns**

```bash
uv run --with pandas python <<'PY'
import pandas as pd
df = pd.read_csv('docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv', keep_default_na=False, na_values=[''])
for _, r in df[df['action']=='rename'].iterrows():
    print(f"{r['current_column']}\t{r['proposed_name']}")
PY
```

- [ ] **Step 2: Grep exposures for renamed column names**

```bash
cd src/dbt/kipptaf/models/exposures
uv run python /tmp/check.py  # use output from Step 1
# For each old name, run:
# grep -rn "<old_name>" .
```

- [ ] **Step 3: Update any matches**

For each hit, update the exposure YAML to reference the new column name.
External tools (Tableau workbooks, Google Sheets destinations) may also
reference these — flag the list as follow-up work but don't block the PR.

- [ ] **Step 4: Commit (if changes)**

```bash
git add src/dbt/kipptaf/models/exposures/
git commit -m "refactor(dbt): update exposures for renamed mart columns per #3643"
```

---

### Task 18: Final verification + spec update

- [ ] **Step 1: Full-project parse + compile**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt compile --project-dir src/dbt/kipptaf
```

Expected: zero errors.

- [ ] **Step 2: Run a targeted build on the changed models**

```bash
uv run dbt build --project-dir src/dbt/kipptaf \
    --select state:modified+ --target defer --full-refresh
```

Expected: all tests pass, all models build. Note: hash-change surrogate keys
will cause downstream reference tests to fail if the parent dim and the child
fact are not both in the modified set — `state:modified+` expands downstream to
catch this. If any `relationships` test fails because of hash drift that you did
not intend, investigate rather than ignore.

- [ ] **Step 3: Update spec's Hash-change posture with enumerated keys**

Edit `docs/superpowers/specs/2026-04-15-column-naming-audit.md` section
"Hash-change posture". Replace the prose description with an explicit list of
surrogate keys whose input composition changed, their before/after derivation,
and the expected hash-change cause. Use the output of `dbt compile` diffs to
identify them precisely.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-15-column-naming-audit.md
git commit -m "docs(spec): enumerate hash-change surrogate keys for #3643"
```

- [ ] **Step 5: Push branch and open PR**

```bash
git push -u origin cbini/feat/claude-column-naming-audit
gh pr create --title "refactor(dbt): mart column naming alignment + upstream dedups" --body "$(cat <<'EOF'
## Summary

Executes the column-naming audit (#3643) bundled with two upstream dedup
blockers (#3633, #3637).

- Applies 170 renames, 180 removes, and 19 structural adds (Groups 1 + 2)
  per the finalized audit inventory.
- Deduplicates `stg_people__employee_numbers` and
  `int_people__location_crosswalk` upstream, removing 9 downstream
  `SELECT DISTINCT` workarounds.
- Ed-Fi / CEDS aligned naming across assessment, staff, location, and
  gradebook domains.
- Group 3 structural adds (fct_grades_assignments score split,
  dim_locations address unification) deferred to follow-up PRs under
  issue #3631.

## Test plan

- [ ] `dbt parse` clean
- [ ] `dbt compile` clean
- [ ] CI `dbt build` against staging passes
- [ ] New uniqueness tests on `stg_people__employee_numbers` and
      `int_people__location_crosswalk` pass
- [ ] Hash-change posture in the spec is updated with the enumerated
      surrogate keys whose composition changed
- [ ] Exposure sweep complete; Tableau/Google Sheets follow-ups flagged

Closes #3643, #3633, #3637.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Execution notes

- **Worktree posture**: user has said to continue in-place on this branch. All
  commits land on `cbini/feat/claude-column-naming-audit`.
- **Commit granularity**: one commit per domain task (two for Staff if diff is
  large). Phase 1 is 2 commits, Phase 2 is 14–15 commits, Phase 3 is 2–3
  commits. Total target: ~18–20 commits.
- **No test runs between domains**: only parse + compile. Full `dbt build` is
  Task 18 (Phase 3) to avoid redundant BQ costs.
- **If a mart consumes a model that's been partially renamed**: consumer may
  fail to compile. Mitigate by doing cross-cutting Conformed (Task 10) early
  relative to consumers. Staff (Task 16) depends on nothing else in this PR.
  Observation (Task 14) requires the model renames to cascade through ref()
  calls — do that first within the domain.
- **The inventory CSV is append-only during execution**: do NOT edit
  `reviewer_notes` or decisions during execution. If you discover an error, stop
  and document it separately.
