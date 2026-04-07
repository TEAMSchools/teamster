# dbt Materialization Cost Optimization

## Problem

BigQuery costs increased ~62% ($278 → $451) from February to March 2026. Root
cause analysis identified two model groups responsible for ~$80/month of the
$173 increase:

1. **Tableau gradebook models** (+$53/month): Four `rpt_tableau__gradebook_*`
   report models converted from views to tables in March. Consumed by a single
   Tableau dashboard refreshing once daily at 4 AM, but Dagster materializes
   them ~100x/day. The 3 audit reports all independently recompute a 1,090-line
   intermediate view (`int_tableau__gradebook_audit_flags`) — tripling compute.
2. **Topline weekly models** (+$27/month): Six `int_topline__*_weekly` models,
   all materialized as tables. Consumed by the Topline Cascade dashboard
   refreshing once daily at 5 AM, but materialized ~130x/day. Five of six join
   to an unmaterialized student×week spine view, recomputing it each time.

### Key commits that caused the increase

| Date   | Commit      | Author      | Change                                               |
| ------ | ----------- | ----------- | ---------------------------------------------------- |
| Mar 3  | `2f933990f` | Claude      | Materialize gradebook audit intermediates as tables  |
| Mar 5  | `83d63dc03` | Claude      | Materialize assessment/DDI dashboard views as tables |
| Mar 20 | `b607a07cf` | GabyRangelB | Materialize gradebook report views as tables         |

### Cost breakdown by destination table (March, production only)

| Model                                                             | Feb Cost | Mar Cost | Delta   |
| ----------------------------------------------------------------- | -------- | -------- | ------- |
| `kipptaf_tableau.rpt_tableau__gradebook_ms_hs_comments`           | $0       | $15.60   | +$15.60 |
| `kipptaf_tableau.rpt_tableau__gradebook_es_comments`              | $0       | $15.58   | +$15.58 |
| `kipptaf_tableau.rpt_tableau__gradebook_audit`                    | $0       | $15.00   | +$15.00 |
| `kipptaf_tableau.rpt_tableau__gradebook_gpa`                      | $0       | $7.28    | +$7.28  |
| `kipptaf_topline.int_topline__school_community_diagnostic_weekly` | $11.95   | $19.09   | +$7.14  |
| `kipptaf_topline.int_topline__attendance_interventions_weekly`    | $6.22    | $12.23   | +$6.01  |
| `kipptaf_topline.int_topline__attendance_contacts_weekly`         | $15.06   | $20.44   | +$5.38  |
| `kipptaf_topline.int_topline__ada_running_weekly`                 | $13.96   | $18.94   | +$4.98  |

## Design

Three-phase approach: refactor and re-layer the gradebook audit chain, then
optimize the topline weekly models, then (future) tune Dagster scheduling.

### Phase 1: Gradebook audit chain

#### 1a. Split `int_tableau__gradebook_audit_flags` by granularity

The current model is a 1,090-line 6-part `UNION ALL` where each branch unpivots
flags from a different upstream model, then pads a ~90-column wide schema with
nulls for inapplicable columns. ~600 lines are copy-pasted null padding.

Replace with two narrower models:

**`int_tableau__gradebook_audit_flags__student`** — student-level flags:

- CTEs: `student_unpivot` (from `assignments_student`, joins
  `assignments_teacher` for per-assignment teacher aggregates),
  `student_course_category` (from `student_scaffold`), `eoq_items` (from
  `student_scaffold`), `eoq_items_conduct_code` (from `student_scaffold`)
- Includes student demographic, course/section, assignment, and flag columns
- The `student_unpivot` branch includes teacher aggregate columns (`n_students`,
  `n_late`, etc.) because it joins `assignments_teacher` at the assignment
  level. The other 3 branches null-pad those columns — this null padding remains
  within the student model since these branches share the same schema
- Drops the teacher-only columns that only `teacher_unpivot_cca` and
  `teacher_unpivot_cc` populate:
  `total_expected_scored_section_quarter_week_category`,
  `total_expected_section_quarter_week_category`,
  `percent_graded_for_quarter_week_class`
- Config: `materialized: table`,
  `cluster_by: [code_type, cte_grouping, region, schoolid]`

**`int_tableau__gradebook_audit_flags__teacher`** — teacher-level flags:

- CTEs: `teacher_unpivot_cca` (from `assignments_teacher`), `teacher_unpivot_cc`
  (from `categories_teacher`)
- Includes section/course, teacher, and flag columns
- Drops student-only columns: `students_dcid`, `studentid`, `student_number`,
  `student_name`, `grade_level`, `salesforce_id`, `ktc_cohort`, `enroll_status`,
  `cohort`, `gender`, `ethnicity`, `advisory`, `year_in_school`,
  `year_in_network`, `rn_undergrad`, `is_out_of_district`, `is_self_contained`,
  `is_retained_year`, `is_retained_ever`, `lunch_status`, `gifted_and_talented`,
  `iep_status`, `lep_status`, `is_504`, `is_counseling_services`,
  `is_student_athlete`, `ada`, `ada_above_or_at_80`, `date_enrolled`,
  `quarter_course_percent_grade`, `quarter_course_grade_points`,
  `quarter_conduct`, `quarter_comment_value`, `scorepoints`, `is_expected_late`,
  `is_exempt`, `is_expected_missing`, `is_expected_zero`,
  `is_expected_academic_dishonesty`, `score_entered`,
  `assign_final_score_percent`, `assign_expected_to_be_scored`,
  `assign_expected_with_score`
- Config: `materialized: table`,
  `cluster_by: [code_type, cte_grouping, region, schoolid]`

Both models preserve the exception anti-join pattern
(`LEFT JOIN stg_google_sheets__gradebook_exceptions ... WHERE include_row IS NULL`)
from the original.

**Disable the original** `int_tableau__gradebook_audit_flags` via
`config: enabled: false` in its YAML. Keep the file as a rollback reference.

#### 1b. Update downstream report models

| Model                                   | Current                            | Change                                                       |
| --------------------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| `rpt_tableau__gradebook_audit`          | table, reads `audit_flags`         | View, reads both `__student` and `__teacher` via `UNION ALL` |
| `rpt_tableau__gradebook_es_comments`    | table, reads `audit_flags` 3x      | View, reads `__student` only                                 |
| `rpt_tableau__gradebook_ms_hs_comments` | table, reads `audit_flags`         | View, reads `__student` only                                 |
| `rpt_tableau__gradebook_gpa`            | table (independent of audit chain) | View, no SQL changes                                         |

`rpt_tableau__gradebook_audit` currently has a 5-part internal `UNION ALL`, each
filtering `audit_flags` by different `code_type`/`cte_grouping` combinations.
After the split, each part refs whichever sub-model contains its `cte_grouping`:
`assignment_student`, `student_course_category`, and quarter-level flags come
from `__student`; `class_category_assignment` and `class_category` come from
`__teacher`. The internal structure (CTEs for `teacher_aggs` and `valid_flags`
per section) stays the same — only the source `ref()` changes per section.

#### 1c. Fallback

If any rpt view fails with a BigQuery resource/complexity error during dev
testing, re-add `materialized: table` for just that model. The `audit_flags`
split is a strict improvement regardless.

#### Expected savings

~$50/month, ~7,000 slot hours/month. Narrower schemas reduce bytes scanned per
materialization of the two sub-tables.

### Phase 2: Topline weekly models

#### 2a. Materialize the shared spine

Add `materialized: table` to `int_extracts__student_enrollments_weeks` YAML.
This model cross-joins `int_extracts__student_enrollments` ×
`int_powerschool__calendar_week` and is currently recomputed by 5 downstream
models on every build.

#### 2b. Revert topline weekly models to views

Remove `materialized: table` from all six:

- `int_topline__school_community_diagnostic_weekly`
- `int_topline__attendance_contacts_weekly`
- `int_topline__ada_running_weekly`
- `int_topline__attendance_interventions_weekly`
- `int_topline__gpa_term_weekly`
- `int_topline__gpa_cumulative_weekly`

#### 2c. Fix duplicate window functions in `ada_running_weekly`

Current code computes 4 window functions when 2 suffice — the running sums are
computed standalone and then duplicated inside `SAFE_DIVIDE`. Refactor to
compute running sums in a CTE, then divide in the final SELECT:

```sql
-- before (4 window evaluations):
sum(agg.attendance_value_sum) over (...) as attendance_value_sum_running,
sum(agg.membership_value_sum) over (...) as membership_value_sum_running,
round(safe_divide(
    sum(agg.attendance_value_sum) over (...),  -- duplicate
    sum(agg.membership_value_sum) over (...)   -- duplicate
), 3) as ada_running,

-- after (2 window evaluations + arithmetic):
-- CTE: compute running sums
-- Final SELECT: reference CTE columns, then safe_divide
```

#### 2d. Fallback

Same as Phase 1 — if any view hits complexity errors, re-materialize just that
model.

#### Expected savings

~$25/month, ~1,500 slot hours/month.

### Phase 3: Dagster materialization frequency (future)

Out of scope for this spec. For any models that remain as tables after Phases
1-2, reduce Dagster trigger frequency to match consumer cadence (1-2x/day
instead of ~100x/day). This requires Dagster automation policy changes, not dbt
changes.

## Testing plan

1. `dbt build --select int_tableau__gradebook_audit_flags__student+ int_tableau__gradebook_audit_flags__teacher+`
   in dev target — validates the split and downstream views compile and run
2. `dbt build --select int_extracts__student_enrollments_weeks+` in dev target —
   validates the topline chain
3. Compare row counts: `SELECT COUNT(*) FROM` old `audit_flags` vs
   `SELECT (SELECT COUNT(*) FROM __student) + (SELECT COUNT(*) FROM __teacher)`
   to confirm no data loss
4. Monitor `INFORMATION_SCHEMA.JOBS` for the first week post-deploy to confirm
   cost reduction
5. Watch for Tableau extract failures at 4 AM (gradebook) and 5 AM (topline)

## Risk mitigation

- All view reversions are one-line YAML changes to undo
- Phase 1 and Phase 2 are independent — can ship separately
- The `audit_flags` split is testable via row count comparison before disabling
  the original
- The original `audit_flags` model stays in the repo (disabled, not deleted) as
  a rollback path

## Files modified

### Phase 1

| File                                                                                                              | Action                             |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__student.sql`            | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__student.yml` | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_flags__teacher.sql`            | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags__teacher.yml` | Create                             |
| `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__gradebook_audit_flags.yml`          | Edit: add `enabled: false`         |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`                                        | Edit: ref new sub-models           |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_audit.yml`                             | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`                                  | Edit: ref `__student` only         |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_es_comments.yml`                       | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_ms_hs_comments.sql`                               | Edit: ref `__student` only         |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_ms_hs_comments.yml`                    | Edit: remove `materialized: table` |
| `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_gpa.yml`                               | Edit: remove `materialized: table` |

### Phase 2

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
