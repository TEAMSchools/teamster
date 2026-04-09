# dbt Materialization Cost Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce BigQuery costs ~$75/month by splitting the gradebook audit
intermediate model by granularity, reverting report models to views, and
materializing the shared topline spine.

**Architecture:** Phase 1 splits `int_tableau__gradebook_audit_flags`
(1,091-line 6-branch UNION ALL) into two narrower materialized tables
(`__student` with 4 branches, `__teacher` with 2), reverts 4 downstream reports
to views, and updates their refs. Phase 2 materializes the shared
`int_extracts__student_enrollments_weeks` spine and reverts 6 topline weekly
models to views.

**Tech Stack:** dbt (BigQuery dialect), YAML properties files

**Spec:**
`docs/superpowers/specs/2026-04-06-dbt-materialization-cost-optimization-design.md`

**Worktree:** `.worktrees/cbini/perf/claude-dbt-materialization-optimization`

---

## File Structure

### Phase 1 — Gradebook audit chain

| File                                                                                                              | Action                             |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__student.sql`            | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__student.yml` | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__teacher.sql`            | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__teacher.yml` | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags.yml`          | Edit: add `enabled: false`         |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`                                        | Edit: ref new sub-models           |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_audit.yml`                             | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`                                  | Edit: ref `__student`              |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_es_comments.yml`                       | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_ms_hs_comments.sql`                               | Edit: ref `__student`              |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_ms_hs_comments.yml`                    | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_gpa.yml`                               | Edit: remove `materialized: table` |

### Phase 2 — Topline weekly models

| File                                                                                                         | Action                             |
| ------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_weeks.yml`        | Edit: add `materialized: table`    |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__school_community_diagnostic_weekly.yml` | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_contacts_weekly.yml`         | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/topline/intermediate/int_topline__ada_running_weekly.sql`                            | Edit: refactor duplicate windows   |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__ada_running_weekly.yml`                 | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_interventions_weekly.yml`    | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__gpa_term_weekly.yml`                    | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__gpa_cumulative_weekly.yml`              | Edit: remove `materialized: table` |

---

## Phase 1: Gradebook Audit Chain

### Task 1: Create `int_tableau__gradebook_audit_flags__student.sql`

The student sub-model contains the 4 student-level CTEs and their UNION ALL
branches from the original `int_tableau__gradebook_audit_flags.sql`. It drops 3
teacher-only columns that are always NULL in these branches.

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__student.sql`
- Reference:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags.sql`

- [ ] **Step 1: Read the original model**

Read `int_tableau__gradebook_audit_flags.sql` in full to understand its
structure.

- [ ] **Step 2: Create the student SQL file**

Create
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__student.sql`
by copying the original and applying these modifications:

**CTEs to KEEP** (copy exactly, no changes):

- `student_unpivot` (original lines 2–70)
- `student_course_category` (original lines 250–284)
- `eoq_items` (original lines 158–195)
- `eoq_items_conduct_code` (original lines 197–246)

**CTEs to DROP** (do not include):

- `teacher_unpivot_cca` (original lines 72–114)
- `teacher_unpivot_cc` (original lines 116–156)

**UNION ALL branches to KEEP** (4 branches):

1. Branch from `student_unpivot` (original lines 286–419) — keep the LEFT JOIN
   to `int_tableau__gradebook_audit_assignments_teacher`
2. Branch from `student_course_category` (original lines 421–550)
3. Branch from `eoq_items` (original lines 552–679)
4. Branch from `eoq_items_conduct_code` (original lines 681–809)

**UNION ALL branches to DROP** (do not include):

5. Branch from `teacher_unpivot_cca` (original lines 811–950)
6. Branch from `teacher_unpivot_cc` (original lines 952–1091)

**Columns to REMOVE from every branch** — these 3 teacher-only columns are
always `null as ...` in all 4 student branches. Remove the lines entirely from
each branch:

- `null as total_expected_scored_section_quarter_week_category,`
- `null as total_expected_section_quarter_week_category,`
- `null as percent_graded_for_quarter_week_class,`

Branch-specific locations of these 3 lines:

| Branch                  | Original lines |
| ----------------------- | -------------- |
| student_unpivot         | 398–400        |
| student_course_category | 538–540        |
| eoq_items               | 667–669        |
| eoq_items_conduct_code  | 797–799        |

**Everything else stays exactly the same** — all other columns, refs, joins,
filters, and the `if(audit_flag_value, 1, 0)` / `if(r.audit_flag_value, 1, 0)`
expressions.

- [ ] **Step 3: Verify the file compiles**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select int_tableau__gradebook_audit_flags__student --target dev --project-dir src/dbt/kipptaf
```

Expected: compiles without errors. Fix any syntax issues.

---

### Task 2: Create `int_tableau__gradebook_audit_flags__student.yml`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__student.yml`
- Reference:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags.yml`

- [ ] **Step 1: Create the student YML file**

Copy the original `int_tableau__gradebook_audit_flags.yml` and apply these
changes:

1. Change `name:` to `int_tableau__gradebook_audit_flags__student`
2. Replace the `config:` block with:

```yaml
config:
  materialized: table
  cluster_by:
    - code_type
    - cte_grouping
    - region
    - schoolid
```

3. Remove these 3 column definitions (they don't exist in the student model):

```yaml
- name: total_expected_scored_section_quarter_week_category
  data_type: float64
- name: total_expected_section_quarter_week_category
  data_type: float64
- name: percent_graded_for_quarter_week_class
  data_type: float64
```

4. Keep ALL other column definitions exactly as-is.

---

### Task 3: Create `int_tableau__gradebook_audit_flags__teacher.sql`

The teacher sub-model contains the 2 teacher-level CTEs and their UNION ALL
branches. It drops all student-only columns that are always NULL in these
branches.

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__teacher.sql`
- Reference:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags.sql`

- [ ] **Step 1: Create the teacher SQL file**

Create the file from the original's teacher CTEs and branches 5–6 with
student-only columns removed.

**CTEs to KEEP** (copy exactly, no changes):

- `teacher_unpivot_cca` (original lines 72–114)
- `teacher_unpivot_cc` (original lines 116–156)

**UNION ALL branches to KEEP** (2 branches):

5. Branch from `teacher_unpivot_cca` (original lines 811–950)
6. Branch from `teacher_unpivot_cc` (original lines 952–1091)

**Columns to REMOVE from both branches** — these are always `null as ...` in the
teacher branches. Remove the lines entirely:

From branch 5 (`teacher_unpivot_cca`):

```sql
-- Remove these null student columns (original lines ~824-835):
null as students_dcid,
null as studentid,
null as student_number,
null as student_name,
null as grade_level,
null as salesforce_id,
null as ktc_cohort,
null as enroll_status,
null as cohort,
null as gender,
null as ethnicity,
null as advisory,
-- Remove these null student columns (original lines ~840-855):
null as year_in_school,
null as year_in_network,
null as rn_undergrad,
null as is_out_of_district,
null as is_self_contained,
null as is_retained_year,
null as is_retained_ever,
null as lunch_status,
null as gifted_and_talented,
null as iep_status,
null as lep_status,
null as is_504,
null as is_counseling_services,
null as is_student_athlete,
null as ada,
null as ada_above_or_at_80,
-- Remove (original line ~860):
null as date_enrolled,
-- Remove these null student columns (original lines ~893-896):
null as quarter_course_percent_grade,
null as quarter_course_grade_points,
null as quarter_conduct,
null as quarter_comment_value,
-- Remove these null student columns (original lines ~914-923):
null as scorepoints,
null as is_expected_late,
null as is_exempt,
null as is_expected_missing,
null as is_expected_zero,
null as is_expected_academic_dishonesty,
null as score_entered,
null as assign_final_score_percent,
null as assign_expected_to_be_scored,
null as assign_expected_with_score,
```

Apply the **same removals** to branch 6 (`teacher_unpivot_cc`) — the same set of
null student columns appear at similar positions (original lines ~964–1061).
Note: branch 6 also has `null as termid` — **keep that** (termid is not in the
dropped list).

**Columns to KEEP in both teacher branches** (verify these are NOT removed):

- `r.hos`, `r.region_school_level` — teacher/school-level, not student
- `null as termid` — not in the dropped list
- `null as category_quarter_percent_grade`,
  `null as category_quarter_average_all_courses` — not in the dropped list
- All `r.*` teacher aggregate columns (`n_students`, `n_late`, etc.)
- `total_expected_scored_section_quarter_week_category`,
  `total_expected_section_quarter_week_category`,
  `percent_graded_for_quarter_week_class` — these are the teacher-only columns
  that STAY (null in branch 5, real values from `r.` in branch 6)
- `sum_totalpointvalue_section_quarter_category`,
  `teacher_running_total_assign_by_cat`,
  `teacher_avg_score_for_assign_per_class_section_and_assign_id` — keep as-is
  (some null, some real depending on branch)

- [ ] **Step 2: Verify the file compiles**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select int_tableau__gradebook_audit_flags__teacher --target dev --project-dir src/dbt/kipptaf
```

---

### Task 4: Create `int_tableau__gradebook_audit_flags__teacher.yml`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__teacher.yml`
- Reference:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags.yml`

- [ ] **Step 1: Create the teacher YML file**

Copy the original `int_tableau__gradebook_audit_flags.yml` and apply these
changes:

1. Change `name:` to `int_tableau__gradebook_audit_flags__teacher`
2. Replace the `config:` block with:

```yaml
config:
  materialized: table
  cluster_by:
    - code_type
    - cte_grouping
    - region
    - schoolid
```

3. Remove these student-only column definitions:

```yaml
- name: students_dcid
  data_type: int64
- name: studentid
  data_type: int64
- name: student_number
  data_type: int64
- name: student_name
  data_type: string
- name: grade_level
  data_type: int64
- name: salesforce_id
  data_type: string
- name: ktc_cohort
  data_type: int64
- name: enroll_status
  data_type: int64
- name: cohort
  data_type: int64
- name: gender
  data_type: string
- name: ethnicity
  data_type: string
- name: advisory
  data_type: string
- name: year_in_school
  data_type: int64
- name: year_in_network
  data_type: int64
- name: rn_undergrad
  data_type: int64
- name: is_out_of_district
  data_type: boolean
- name: is_self_contained
  data_type: boolean
- name: is_retained_year
  data_type: boolean
- name: is_retained_ever
  data_type: boolean
- name: lunch_status
  data_type: string
- name: gifted_and_talented
  data_type: string
- name: iep_status
  data_type: string
- name: lep_status
  data_type: boolean
- name: is_504
  data_type: boolean
- name: is_counseling_services
  data_type: int64
- name: is_student_athlete
  data_type: int64
- name: ada
  data_type: float64
- name: ada_above_or_at_80
  data_type: boolean
- name: date_enrolled
  data_type: date
- name: quarter_course_percent_grade
  data_type: float64
- name: quarter_course_grade_points
  data_type: float64
- name: quarter_conduct
  data_type: string
- name: quarter_comment_value
  data_type: string
- name: scorepoints
  data_type: float64
- name: is_expected_late
  data_type: int64
- name: is_exempt
  data_type: int64
- name: is_expected_missing
  data_type: int64
- name: is_expected_zero
  data_type: int64
- name: is_expected_academic_dishonesty
  data_type: int64
- name: score_entered
  data_type: float64
- name: assign_final_score_percent
  data_type: float64
- name: assign_expected_to_be_scored
  data_type: boolean
- name: assign_expected_with_score
  data_type: boolean
```

4. KEEP these column definitions (they exist in the teacher model):

- `hos`, `region_school_level`, `termid`, `category_quarter_percent_grade`,
  `category_quarter_average_all_courses`
- All teacher aggregate columns (`n_students` through `n_expected_scored`)
- `total_expected_scored_section_quarter_week_category`,
  `total_expected_section_quarter_week_category`,
  `percent_graded_for_quarter_week_class` (the 3 teacher-only columns)
- All other section/course/teacher/schedule columns

---

### Task 5: Disable original model and update YAML configs

**Files:**

- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags.yml`
- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_audit.yml`
- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_es_comments.yml`
- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_ms_hs_comments.yml`
- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_gpa.yml`

- [ ] **Step 1: Disable the original audit_flags model**

In `int_tableau__gradebook_audit_flags.yml`, add `enabled: false` to the config:

```yaml
models:
  - name: int_tableau__gradebook_audit_flags
    config:
      enabled: false
      cluster_by: cte_grouping
      # materialized: table
```

- [ ] **Step 2: Remove `materialized: table` from all 4 report YMLs**

In each of these files, remove the `materialized: table` line from the config
block (the `extracts/` directory default is already `view`):

1. `rpt_tableau__gradebook_audit.yml`:

```yaml
# before
config:
  materialized: table
# after — remove the entire config block (no other config keys)
```

2. `rpt_tableau__gradebook_es_comments.yml`: same change
3. `rpt_tableau__gradebook_ms_hs_comments.yml`: same change
4. `rpt_tableau__gradebook_gpa.yml`: same change

---

### Task 6: Refactor `rpt_tableau__gradebook_audit.sql`

The report model currently reads from the single `audit_flags` model via 2
shared CTEs (`teacher_aggs`, `valid_flags`) and a 5-branch UNION ALL. After the
split, it needs 4 CTEs (2 per source model) and each branch references the
correct CTE pair.

**Key insight**: Branches 1–3 filter to student-level `cte_grouping` values
(`assignment_student`, `student_course_category`, and quarter-level flags).
Branches 4–5 filter to teacher-level `cte_grouping` values
(`class_category_assignment`, `class_category`). No branch crosses the
student/teacher boundary.

**Files:**

- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`

- [ ] **Step 1: Replace the 2 CTEs with 4 CTEs**

Replace the current `teacher_aggs` and `valid_flags` CTEs with these 4 CTEs. The
column lists are identical between student/teacher pairs except for 3
teacher-only columns (null in student, real in teacher) and student-only columns
in valid_flags (real in student, null in teacher).

**`student_teacher_aggs`** — same column list as current `teacher_aggs`, reading
from `__student`, with 3 null columns:

```sql
student_teacher_aggs as (
    select
        academic_year,
        academic_year_display,
        region,
        school_level,
        region_school_level,
        schoolid,
        school,
        `quarter`,
        semester,
        week_number_quarter as audit_qt_week_number,
        quarter_start_date,
        quarter_end_date,
        is_current_term as is_current_quarter,
        is_quarter_end_date_range,
        week_start_monday as audit_start_date,
        week_end_sunday as audit_end_date,
        school_week_start_date_lead as audit_due_date,
        is_current_week,
        assignment_category_name,
        assignment_category_code,
        assignment_category_term,
        expectation,
        notes,
        section_or_period,
        sectionid,
        sections_dcid,
        section_number,
        external_expression,
        credit_type,
        course_number,
        course_name,
        exclude_from_gpa,
        is_ap_course,
        teacher_number,
        teacher_name,
        teacher_tableau_username,
        school_leader,
        school_leader_tableau_username,
        assignmentid as teacher_assign_id,
        assignment_name as teacher_assign_name,
        duedate as teacher_assign_due_date,
        scoretype as teacher_assign_score_type,
        totalpointvalue as teacher_assign_max_score,
        n_students,
        n_late,
        n_exempt,
        n_missing,
        n_null,
        n_academic_dishonesty,
        n_is_null_missing,
        n_is_null_not_missing,
        n_expected,
        n_expected_scored,

        null as total_expected_scored_section_quarter_week_category,
        null as total_expected_section_quarter_week_category,
        null as percent_graded_for_quarter_week_class,

        sum_totalpointvalue_section_quarter_category,
        teacher_running_total_assign_by_cat,
        teacher_avg_score_for_assign_per_class_section_and_assign_id,
        audit_category,
        cte_grouping,
        code_type,
        audit_flag_name,

        max(audit_flag_value) as audit_flag_value,

    from {{ ref("int_tableau__gradebook_audit_flags__student") }}
    group by all
),
```

**`teacher_teacher_aggs`** — same column list but reads from `__teacher` with
real values for the 3 teacher-only columns:

```sql
teacher_teacher_aggs as (
    select
        academic_year,
        academic_year_display,
        region,
        school_level,
        region_school_level,
        schoolid,
        school,
        `quarter`,
        semester,
        week_number_quarter as audit_qt_week_number,
        quarter_start_date,
        quarter_end_date,
        is_current_term as is_current_quarter,
        is_quarter_end_date_range,
        week_start_monday as audit_start_date,
        week_end_sunday as audit_end_date,
        school_week_start_date_lead as audit_due_date,
        is_current_week,
        assignment_category_name,
        assignment_category_code,
        assignment_category_term,
        expectation,
        notes,
        section_or_period,
        sectionid,
        sections_dcid,
        section_number,
        external_expression,
        credit_type,
        course_number,
        course_name,
        exclude_from_gpa,
        is_ap_course,
        teacher_number,
        teacher_name,
        teacher_tableau_username,
        school_leader,
        school_leader_tableau_username,
        assignmentid as teacher_assign_id,
        assignment_name as teacher_assign_name,
        duedate as teacher_assign_due_date,
        scoretype as teacher_assign_score_type,
        totalpointvalue as teacher_assign_max_score,
        n_students,
        n_late,
        n_exempt,
        n_missing,
        n_null,
        n_academic_dishonesty,
        n_is_null_missing,
        n_is_null_not_missing,
        n_expected,
        n_expected_scored,
        total_expected_scored_section_quarter_week_category,
        total_expected_section_quarter_week_category,
        percent_graded_for_quarter_week_class,
        sum_totalpointvalue_section_quarter_category,
        teacher_running_total_assign_by_cat,
        teacher_avg_score_for_assign_per_class_section_and_assign_id,
        audit_category,
        cte_grouping,
        code_type,
        audit_flag_name,

        max(audit_flag_value) as audit_flag_value,

    from {{ ref("int_tableau__gradebook_audit_flags__teacher") }}
    group by all
),
```

**`student_valid_flags`** — same column list as current `valid_flags`, reading
from `__student`:

```sql
student_valid_flags as (
    select
        academic_year,
        region,
        schoolid,
        `quarter`,
        week_number_quarter as audit_qt_week_number,
        assignment_category_term,
        sectionid,
        teacher_number,
        assignmentid as teacher_assign_id,
        studentid,
        student_number,
        student_name,
        grade_level,
        salesforce_id,
        ktc_cohort,
        enroll_status,
        cohort,
        gender,
        ethnicity,
        advisory,
        year_in_school,
        year_in_network,
        rn_undergrad,
        is_out_of_district,
        is_retained_year,
        is_retained_ever,
        lunch_status,
        gifted_and_talented,
        iep_status,
        lep_status,
        is_504,
        is_counseling_services,
        is_student_athlete,
        ada,
        ada_above_or_at_80,
        date_enrolled,
        category_quarter_percent_grade,
        category_quarter_average_all_courses,
        quarter_course_percent_grade,
        quarter_course_grade_points,
        quarter_conduct,
        quarter_comment_value,
        scorepoints as raw_score,
        score_entered,
        assign_final_score_percent,
        is_exempt,
        is_expected_late,
        is_expected_missing,
        is_expected_academic_dishonesty,
        audit_category,
        cte_grouping,
        code_type,
        audit_flag_name,
        audit_flag_value as flag_value,

    from {{ ref("int_tableau__gradebook_audit_flags__student") }}
    where audit_flag_value = 1
),
```

**`teacher_valid_flags`** — same column list but reads from `__teacher` with
null student columns:

```sql
teacher_valid_flags as (
    select
        academic_year,
        region,
        schoolid,
        `quarter`,
        week_number_quarter as audit_qt_week_number,
        assignment_category_term,
        sectionid,
        teacher_number,
        assignmentid as teacher_assign_id,

        null as studentid,
        null as student_number,
        null as student_name,
        null as grade_level,
        null as salesforce_id,
        null as ktc_cohort,
        null as enroll_status,
        null as cohort,
        null as gender,
        null as ethnicity,
        null as advisory,
        null as year_in_school,
        null as year_in_network,
        null as rn_undergrad,
        null as is_out_of_district,
        null as is_retained_year,
        null as is_retained_ever,
        null as lunch_status,
        null as gifted_and_talented,
        null as iep_status,
        null as lep_status,
        null as is_504,
        null as is_counseling_services,
        null as is_student_athlete,
        null as ada,
        null as ada_above_or_at_80,
        null as date_enrolled,

        category_quarter_percent_grade,
        category_quarter_average_all_courses,

        null as quarter_course_percent_grade,
        null as quarter_course_grade_points,
        null as quarter_conduct,
        null as quarter_comment_value,
        null as raw_score,
        null as score_entered,
        null as assign_final_score_percent,
        null as is_exempt,
        null as is_expected_late,
        null as is_expected_missing,
        null as is_expected_academic_dishonesty,

        audit_category,
        cte_grouping,
        code_type,
        audit_flag_name,
        audit_flag_value as flag_value,

    from {{ ref("int_tableau__gradebook_audit_flags__teacher") }}
    where audit_flag_value = 1
)
```

- [ ] **Step 2: Update the 5 UNION ALL branches**

The 5 UNION ALL branches stay structurally identical. Only the CTE aliases
change:

| Branch | Filter                                                                        | Old CTEs                          | New CTEs                                          |
| ------ | ----------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------- |
| 1      | `code_type='Gradebook Category' AND cte_grouping='assignment_student'`        | `teacher_aggs t`, `valid_flags v` | `student_teacher_aggs t`, `student_valid_flags v` |
| 2      | `cte_grouping='student_course_category'`                                      | `teacher_aggs t`, `valid_flags v` | `student_teacher_aggs t`, `student_valid_flags v` |
| 3      | `code_type='Quarter' AND cte_grouping!='student_course_category'`             | `teacher_aggs t`, `valid_flags v` | `student_teacher_aggs t`, `student_valid_flags v` |
| 4      | `code_type='Gradebook Category' AND cte_grouping='class_category_assignment'` | `teacher_aggs t`, `valid_flags v` | `teacher_teacher_aggs t`, `teacher_valid_flags v` |
| 5      | `code_type='Gradebook Category' AND cte_grouping='class_category'`            | `teacher_aggs t`, `valid_flags v` | `teacher_teacher_aggs t`, `teacher_valid_flags v` |

In each branch, replace the `FROM` and `JOIN` CTE references:

- Branches 1–3: `from teacher_aggs as t` → `from student_teacher_aggs as t`,
  `valid_flags as v` → `student_valid_flags as v`
- Branches 4–5: `from teacher_aggs as t` → `from teacher_teacher_aggs as t`,
  `valid_flags as v` → `teacher_valid_flags as v`

The column selections (`t.*`, `v.studentid`, etc.), join predicates, and WHERE
filters all stay exactly the same.

- [ ] **Step 3: Verify compilation**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select rpt_tableau__gradebook_audit --target dev --project-dir src/dbt/kipptaf
```

---

### Task 7: Update `rpt_tableau__gradebook_es_comments.sql`

This model reads `audit_flags` in 3 places: `valid_flags` CTE, `teacher_aggs`
CTE (indirectly via `valid_flags`), and a LEFT JOIN for effort grade. All
student-level data — change all refs to `__student`.

**Files:**

- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`

- [ ] **Step 1: Update all 3 refs to `__student`**

1. Line 105 (`valid_flags` CTE source):

```sql
-- before
        from {{ ref("int_tableau__gradebook_audit_flags") }}
-- after
        from {{ ref("int_tableau__gradebook_audit_flags__student") }}
```

2. Line 241 (effort grade LEFT JOIN):

```sql
-- before
    {{ ref("int_tableau__gradebook_audit_flags") }} as e
-- after
    {{ ref("int_tableau__gradebook_audit_flags__student") }} as e
```

- [ ] **Step 2: Replace 3 missing columns with NULLs**

The `__student` model does not have the 3 teacher-only columns. Replace them
with NULLs in both CTEs.

In the `valid_flags` CTE (around lines 99–101):

```sql
-- before
            total_expected_scored_section_quarter_week_category,
            total_expected_section_quarter_week_category,
            percent_graded_for_quarter_week_class,
-- after
            null as total_expected_scored_section_quarter_week_category,
            null as total_expected_section_quarter_week_category,
            null as percent_graded_for_quarter_week_class,
```

In the `teacher_aggs` CTE (around lines 164–166):

```sql
-- before
            total_expected_scored_section_quarter_week_category,
            total_expected_section_quarter_week_category,
            percent_graded_for_quarter_week_class,
-- after
            null as total_expected_scored_section_quarter_week_category,
            null as total_expected_section_quarter_week_category,
            null as percent_graded_for_quarter_week_class,
```

- [ ] **Step 3: Verify compilation**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select rpt_tableau__gradebook_es_comments --target dev --project-dir src/dbt/kipptaf
```

---

### Task 8: Update `rpt_tableau__gradebook_ms_hs_comments.sql`

Same pattern as ES comments but without the effort grade join.

**Files:**

- Edit:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_ms_hs_comments.sql`

- [ ] **Step 1: Update the ref to `__student`**

Line 105 (`valid_flags` CTE source):

```sql
-- before
        from {{ ref("int_tableau__gradebook_audit_flags") }}
-- after
        from {{ ref("int_tableau__gradebook_audit_flags__student") }}
```

- [ ] **Step 2: Replace 3 missing columns with NULLs**

Same as ES comments — replace the 3 teacher-only column references with NULLs in
both the `valid_flags` CTE and the `teacher_aggs` CTE.

- [ ] **Step 3: Verify compilation**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select rpt_tableau__gradebook_ms_hs_comments --target dev --project-dir src/dbt/kipptaf
```

---

### Task 9: Validate Phase 1

Run full compilation and test for all modified models and their downstream
dependents.

**Files:** None (validation only)

- [ ] **Step 1: Compile the full Phase 1 graph**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select int_tableau__gradebook_audit_flags__student+ int_tableau__gradebook_audit_flags__teacher+ --target dev --project-dir src/dbt/kipptaf
```

Expected: all models compile without errors. The `+` suffix includes downstream
models (the 4 rpt views).

- [ ] **Step 2: Verify the original model is disabled**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt ls --select int_tableau__gradebook_audit_flags --target dev --project-dir src/dbt/kipptaf
```

Expected: no output (model is disabled).

- [ ] **Step 3: Verify new models are listed**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt ls --select int_tableau__gradebook_audit_flags__student int_tableau__gradebook_audit_flags__teacher --target dev --project-dir src/dbt/kipptaf
```

Expected: both models listed.

---

### Task 10: Commit Phase 1

- [ ] **Step 1: Stage and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && git add -u && git add src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__student.sql src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__student.yml src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__teacher.sql src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__teacher.yml
```

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && git commit -m "perf(dbt): split gradebook audit flags by granularity and revert reports to views"
```

---

## Phase 2: Topline Weekly Models

### Task 11: Materialize the shared spine

**Files:**

- Edit:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_weeks.yml`

- [ ] **Step 1: Add `materialized: table` to the config**

```yaml
# before
models:
  - name: int_extracts__student_enrollments_weeks
    config:
      schema: extracts
# after
models:
  - name: int_extracts__student_enrollments_weeks
    config:
      materialized: table
      schema: extracts
```

---

### Task 12: Revert topline weekly models to views

**Files:**

- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__school_community_diagnostic_weekly.yml`
- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_contacts_weekly.yml`
- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__ada_running_weekly.yml`
- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_interventions_weekly.yml`
- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__gpa_term_weekly.yml`
- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__gpa_cumulative_weekly.yml`

- [ ] **Step 1: Remove `materialized: table` from all 6 YML files**

Each file currently looks like:

```yaml
models:
  - name: int_topline__<model_name>_weekly
    config:
      materialized: table
```

Remove the entire `config:` block from each file:

```yaml
models:
  - name: int_topline__<model_name>_weekly
```

Apply to all 6 files listed above.

---

### Task 13: Refactor `int_topline__ada_running_weekly.sql`

The current model computes 4 window function evaluations when 2 suffice. The
running sums for `attendance_value_sum` and `membership_value_sum` are computed
as standalone columns AND duplicated inside `SAFE_DIVIDE`. Extract the running
sums into an intermediate CTE.

**Files:**

- Edit:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__ada_running_weekly.sql`

- [ ] **Step 1: Replace the final SELECT with a 2-CTE approach**

Replace the current final `select` (lines 27–63) with:

```sql
running as (
    select
        co.student_number,
        co.academic_year,
        co.week_start_monday,
        co.week_end_sunday,

        sum(agg.attendance_value_sum) over (
            partition by co.studentid, co.academic_year, co.schoolid
            order by co.week_start_monday asc
        ) as attendance_value_sum_running,

        sum(agg.membership_value_sum) over (
            partition by co.studentid, co.academic_year, co.schoolid
            order by co.week_start_monday asc
        ) as membership_value_sum_running,
    from {{ ref("int_extracts__student_enrollments_weeks") }} as co
    left join
        agg_weeks as agg
        on co.studentid = agg.studentid
        and co.schoolid = agg.schoolid
        and co.academic_year = agg.academic_year
        and co.week_start_monday = agg.week_start_monday
    where co.academic_year >= {{ var("current_academic_year") - 1 }}
)

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    attendance_value_sum_running,
    membership_value_sum_running,

    round(
        safe_divide(attendance_value_sum_running, membership_value_sum_running),
        3
    ) as ada_running,
from running
```

This reduces 4 window evaluations to 2 + simple arithmetic.

- [ ] **Step 2: Verify compilation**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select int_topline__ada_running_weekly --target dev --project-dir src/dbt/kipptaf
```

---

### Task 14: Validate Phase 2

- [ ] **Step 1: Compile the full Phase 2 graph**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && uv run dbt compile --select int_extracts__student_enrollments_weeks+ --target dev --project-dir src/dbt/kipptaf
```

Expected: all models compile without errors.

---

### Task 15: Commit Phase 2

- [ ] **Step 1: Stage and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-dbt-materialization-optimization && git add -u && git commit -m "perf(dbt): materialize topline spine and revert weekly models to views"
```
