# Gradebook Audit Data Model

Reference document for `rpt_tableau__gradebook_audit` — the Tableau extract that
powers the gradebook audit dashboard used by school leaders to monitor teacher
gradebook compliance with KIPP TAF grading policy.

!!! tip "Claude Code skill available" The `gradebook-audit` skill in
`.claude/skills/gradebook-audit/` provides guided procedures for common tasks:
annual flags rollover, adding/removing a flag, adding a region, and debugging a
flag that isn't firing. Invoke it by describing what you need to do with the
gradebook audit.

## What is the gradebook audit?

KIPP TAF schools require teachers to maintain PowerSchool gradebooks that follow
the network's grading policy. The gradebook audit dashboard gives school leaders
and instructional coaches a weekly view of compliance across every section,
flagging deviations from policy so they can be addressed before the end of the
quarter.

The audit operates at multiple grains simultaneously:

- **Assignment-student** — did this specific student receive a valid score on
  this assignment?
- **Class-category** — has this teacher posted the required number of
  assignments in this category this week? Are scores being entered on time?
- **Student-course** — does this student's category grade meet policy thresholds
  (grade inflation, effort/formative/summative missing)?
- **End-of-quarter (EOQ)** — during a window around the last in-session day of
  each quarter, are comments, conduct codes, and final grades correctly entered?

### Dashboard coverage (AY 2026-2027)

| Region   | School level | Coverage depth                              | Notes                                                |
| -------- | ------------ | ------------------------------------------- | ---------------------------------------------------- |
| Camden   | MS, HS       | Full audit (all applicable flags)           |                                                      |
| Camden   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook  |
| Newark   | MS, HS       | Full audit (all applicable flags)           |                                                      |
| Newark   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook  |
| Paterson | MS           | Full audit (mirrors Newark MS flags)        | Added AY 2026-2027; GradeBook plugin required        |
| Paterson | ES           | EOQ comments only (`qt_es_comment_missing`) | Added AY 2026-2027                                   |
| Miami    | n/a          | Removed                                     | Moved to Focus gradebook; excluded at scaffold level |

!!! note "Paterson GradeBook plugin" Paterson's PowerSchool instance requires
the GradeBook plugin to populate `int_powerschool__category_grades` and
`int_powerschool__gradebook_assignments`. Until the plugin is deployed, Paterson
teacher rows will have null `category_quarter_percent_grade` and zero assignment
counts. Tracked: [#3908](https://github.com/TEAMSchools/teamster/issues/3908)

### Dashboard coverage (AY 2025-2026)

| Region   | School level | Coverage depth                              | Notes                                               |
| -------- | ------------ | ------------------------------------------- | --------------------------------------------------- |
| Camden   | MS, HS       | Full audit (all applicable flags)           |                                                     |
| Camden   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook |
| Newark   | MS, HS       | Full audit (all applicable flags)           |                                                     |
| Newark   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook |
| Miami    | ES, MS       | Full audit (all applicable flags)           | Removed AY 2026-2027 — moved to Focus               |
| Paterson | n/a          | Not on dashboard                            | Added AY 2026-2027                                  |

## Grading policy overview

KIPP TAF teachers use four assignment categories in PowerSchool:

| Code | Name              | Policy: max score per assignment | Policy: quarterly total                  | Policy: missing score           |
| ---- | ----------------- | -------------------------------- | ---------------------------------------- | ------------------------------- |
| `W`  | Work Habits       | 10 pts                           | n/a                                      | 5 (non-HS) / 0 (HS)             |
| `H`  | Homework          | 10 pts                           | n/a                                      | 5 (non-HS) / 0 (HS)             |
| `F`  | Formative Mastery | 10 pts                           | n/a                                      | 5 (non-HS) / 0 (HS)             |
| `S`  | Summative Mastery | No per-assignment max            | 200 pts (Camden/Newark); 100 pts (Miami) | 0 (HS); min 50% of max (non-HS) |

Summative scores for MS must fall on the conversion chart:
`50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100`.

Summative scores for HS (non-AP) must fall on the conversion chart:
`50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100`. AP courses are
excluded from conversion chart enforcement.

## AY 2026-2027 data model

### What changed from AY 2025-2026

**Regions:**

- Miami removed — gradebook moved to Focus; excluded in scaffold via
  `_dbt_source_project != 'kippmiami'`
- Paterson added — MS mirrors Newark MS flags; ES has EOQ comments only

**Architecture:**

The AY 2026-2027 pipeline collapsed the old multi-model rollup chain into two
models:

| Old model (AY 2025-2026)                                | New model (AY 2026-2027)                                    |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| `int_tableau__gradebook_audit_teacher_scaffold`         | `int_tableau__gradebook_audit_scaffold` (branch 1–3)        |
| `int_tableau__gradebook_audit_student_scaffold`         | `int_tableau__gradebook_audit_scaffold` (branch 4–5)        |
| `int_tableau__gradebook_audit_assignments_teacher`      | Inline in `int_tableau__gradebook_audit_flags_calculations` |
| `int_tableau__gradebook_audit_assignments_student`      | Inline in `int_tableau__gradebook_audit_flags_calculations` |
| `int_tableau__gradebook_audit_categories_teacher`       | Inline in `int_tableau__gradebook_audit_flags_calculations` |
| `int_tableau__gradebook_audit_flags`                    | `int_tableau__gradebook_audit_flags_calculations`           |
| `stg_google_sheets__gradebook_expectations_assignments` | `int_powerschool__u_expectations_qtd_unpivot`               |
| `stg_google_sheets__gradebook_exceptions`               | Deprecated — all exception joins removed                    |

**Assignment count (QTD):** `teacher_running_total_assign_by_cat` now counts
only assignments with `duedate <= week_end_sunday` (the Sunday ending the most
recently completed school week) rather than all assignments in the quarter. This
gives a true quarter-to-date count as of the last completed school week, aligned
with the Monday audit cadence.

**Deprecated flags** (removed from `stg_google_sheets__gradebook_flags` for AY
2026; boolean columns remain in SQL for future years):

- `w_grade_inflation`
- `qt_student_is_ada_80_plus_gpa_less_2`
- `qt_teacher_s_total_greater_200` / `qt_teacher_s_total_less_200`
- `assign_s_hs_score_not_conversion_chart_options`
- `assign_s_ms_score_not_conversion_chart_options`

**Assignment score flags** — the 12 per-category per-school-level boolean
columns were consolidated to 5 merged flags. See
[`int_powerschool__gradebook_assignments_scores`](#int_powerschool__gradebook_assignments_scores)
below.

### New scaffold: `int_tableau__gradebook_audit_scaffold`

Five-branch `UNION ALL`. Each branch is filtered by `scaffold_name` in
downstream `int_tableau__gradebook_audit_flags_calculations`:

| Branch | `scaffold_name`               | Has students? | Has category? | Source                                                |
| ------ | ----------------------------- | ------------- | ------------- | ----------------------------------------------------- |
| 1      | `teacher_scaffold_course`     | No            | No            | `int_extracts__course_schedule_by_term`               |
| 2      | `teacher_scaffold_category`   | No            | Yes           | above + `int_powerschool__u_expectations_qtd_unpivot` |
| 3      | `teacher_scaffold_assignment` | No            | Yes           | above + `int_powerschool__gradebook_assignments`      |
| 4      | `student_scaffold_course`     | Yes           | No            | above + `int_extracts__student_enrollments`           |
| 5      | `student_scaffold_category`   | Yes           | Yes           | above + `int_powerschool__category_grades`            |

All branches filter:

- `academic_year = current_academic_year`
- `school_level_alt != 'ES'` (ES rows excluded from teacher/assignment branches;
  ES students included in student branches for EOQ flags)
- `_dbt_source_project != 'kippmiami'`

The `week_end_sunday` column (from
`int_powerschool__u_expectations_qtd_unpivot`) is populated on branches 2, 3,
and 5; null on branches 1 and 4.

### Expectations source: `int_powerschool__u_expectations_qtd_unpivot`

Replaces `stg_google_sheets__gradebook_expectations_assignments`. Reads the
PowerSchool `U_EXPECTATIONS` plugin table, which stores teacher-entered
assignment count expectations per category per week. One row per
`region × school_level × academic_year × quarter × week_start_monday`.

`week_end_sunday` is derived as the Sunday ending the most recently completed
school week (i.e.,
`week_start_monday < date_trunc(current_date, week(monday))`). This value
propagates through the scaffold and is used as the QTD assignment count cutoff
in `int_tableau__gradebook_audit_flags_calculations`.

### Assignment and category rollup layer

#### `int_powerschool__gradebook_assignments_scores`

One row per student × assignment. Same grain and key business logic as AY
2025-2026 — the model was not renamed. The INNER JOIN to
`base_powerschool__course_enrollments` on
`duedate between cc_dateenrolled and cc_dateleft` scopes each assignment to
students whose enrollment was active when the assignment was due. The LEFT JOIN
to `stg_powerschool__assignmentscore` means a student row exists even when no
score has been entered — `score_entered` is null in that case.

**What changed in AY 2026-2027**: the 12 per-category per-school-level boolean
flag columns were consolidated to 5 merged flags using `category_code in (...)`
predicates. The `assign_null_score` and `assign_score_above_max` flags are
unchanged.

**Key computed columns** (unchanged):

| Column                            | Definition                                                                 |
| --------------------------------- | -------------------------------------------------------------------------- |
| `is_expected`                     | True if not exempt and `iscountedinfinalgrade = 1`                         |
| `is_expected_null`                | `is_expected` and `score_entered is null`                                  |
| `is_expected_zero`                | `is_expected` and `score_entered = 0`                                      |
| `is_expected_missing`             | `is_expected` and `is_missing = 1`                                         |
| `is_expected_late`                | `is_expected` and `is_late = 1`                                            |
| `is_expected_scored`              | `is_expected` and `score_entered is not null`                              |
| `is_expected_academic_dishonesty` | `is_expected`; HS; `score_entered = 0` and not missing                     |
| `score_entered`                   | `scorepoints` for POINTS; `actualscoreentered` cast to numeric for PERCENT |
| `half_total_point_value`          | `totalpointvalue / 2`                                                      |

**Consolidated assignment flag columns** (AY 2026-2027):

| Flag                                 | Fires when                                                                                   |
| ------------------------------------ | -------------------------------------------------------------------------------------------- |
| `assign_null_score`                  | `is_expected_null = 1` (score field is blank)                                                |
| `assign_score_above_max`             | `is_expected` and `score_entered > totalpointvalue`                                          |
| `assign_mh_hwf_score_less_5`         | H/W/F category; `is_expected` and `is_missing = 0`; `score_entered < 5`                      |
| `assign_ms_hwf_missing_score_not_5`  | H/W/F category; MS; `is_expected_missing = 1`; `score_entered != 5`                          |
| `assign_hs_hwfs_missing_score_not_0` | H/W/F/S category; HS; `is_expected_missing = 1`; `score_entered != 0`                        |
| `assign_ms_s_score_less_50p`         | S category; MS; `is_expected`; `score_entered < half_total_point_value`                      |
| `assign_hs_s_score_less_50p`         | S category; HS; `is_expected` and `is_missing = 0`; `score_entered < half_total_point_value` |

**Consolidation from AY 2025-2026** (12 flags → 5):

| AY 2025-2026 flags                                                                                                             | AY 2026-2027 replacement             |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `assign_w_score_less_5`, `assign_h_score_less_5`, `assign_f_score_less_5`                                                      | `assign_mh_hwf_score_less_5`         |
| `assign_w_missing_score_not_5`, `assign_h_missing_score_not_5`, `assign_f_missing_score_not_5`                                 | `assign_ms_hwf_missing_score_not_5`  |
| `assign_w_missing_score_not_0`, `assign_h_missing_score_not_0`, `assign_f_missing_score_not_0`, `assign_s_missing_score_not_0` | `assign_hs_hwfs_missing_score_not_0` |
| `assign_s_score_less_50p` (non-HS only)                                                                                        | `assign_ms_s_score_less_50p`         |
| `assign_s_hs_score_less_50p`                                                                                                   | `assign_hs_s_score_less_50p`         |

!!! note "KIPP Sumner G5 school_level override" Grade 5 sections at KIPP Sumner
Elementary (school 179905) are treated as MS (`school_level_alt = 'MS'`) for AY
2025+. This override is hardcoded in the `scores` CTE and is what ensures
HS-vs-non-HS flag conditions apply consistently to those students.

Feeds `int_powerschool__gradebook_assignment_scores_rollup`.

#### `int_powerschool__gradebook_assignment_scores_rollup`

One row per `_dbt_source_project × assignmentsectionid` (class-assignment
grain). New in AY 2026-2027. Aggregates
`int_powerschool__gradebook_assignments_scores` to produce per-assignment
summary counts and assignment-level compliance flags. Downstream consumers join
this model directly rather than computing inline rollups.

**Uniqueness test**: `dbt_utils.unique_combination_of_columns` on
`(_dbt_source_project, assignmentsectionid)`.

**CTE chain**:

1. `transformations` — groups to `_dbt_source_project × assignmentsectionid`
   grain (with assignment metadata as group-by keys); excludes
   `_dbt_source_project = 'kippmiami'`. Produces all count and average columns.

2. `flags` — derives `assign_max_score_not_10`, `overly_exempt_assignment`, and
   `assign_percent_graded` from the aggregated counts.

3. `invalid_assign_check` — computes `flags_sum` (sum of all per-student flag
   counts) and `percent_graded_min_not_met`.

4. Final `SELECT` — adds `assignment_has_flags`.

**Count columns** (from `transformations`):

| Column                                 | Definition                                                             |
| -------------------------------------- | ---------------------------------------------------------------------- |
| `n_students`                           | `count(students_dcid)` — all students with an assignment row           |
| `n_expected`                           | `countif(is_expected)` — not exempt and counted in final grade         |
| `n_expected_scored`                    | `countif(is_expected_scored)` — expected students with a score entered |
| `n_late`                               | `sum(is_expected_late)`                                                |
| `n_exempt`                             | `sum(is_exempt)`                                                       |
| `n_missing`                            | `sum(is_expected_missing)`                                             |
| `n_null`                               | `sum(is_expected_null)`                                                |
| `n_score_above_max`                    | Count of students where `assign_score_above_max` fired                 |
| `n_academic_dishonesty`                | Count of expected HS students with score = 0 and not missing           |
| `n_assign_mh_hwf_score_less_5`         | Count of students where `assign_mh_hwf_score_less_5` fired             |
| `n_assign_ms_hwf_missing_score_not_5`  | Count of students where `assign_ms_hwf_missing_score_not_5` fired      |
| `n_assign_hs_hwfs_missing_score_not_0` | Count of students where `assign_hs_hwfs_missing_score_not_0` fired     |
| `n_assign_ms_s_score_less_50p`         | Count of students where `assign_ms_s_score_less_50p` fired             |
| `n_assign_hs_s_score_less_50p`         | Count of students where `assign_hs_s_score_less_50p` fired             |
| `n_is_null_missing`                    | Expected students with null score also marked missing                  |
| `n_is_null_not_missing`                | Expected students with null score not marked missing                   |
| `avg_score_for_assign`                 | Average `assign_final_score_percent` across expected scored students   |

**Assignment-level flags** (from `flags` and `invalid_assign_check`):

| Column                       | Definition                                                                                                                                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `assign_max_score_not_10`    | True when H/W/F category and `totalpointvalue != 10`                                                                                                                                                   |
| `overly_exempt_assignment`   | True when `n_exempt >= 0.5 * n_students`                                                                                                                                                               |
| `assign_percent_graded`      | `safe_divide(n_expected_scored, n_expected)`                                                                                                                                                           |
| `flags_sum`                  | `n_null + n_score_above_max + n_assign_mh_hwf_score_less_5 + n_assign_ms_hwf_missing_score_not_5 + n_assign_hs_hwfs_missing_score_not_0 + n_assign_ms_s_score_less_50p + n_assign_hs_s_score_less_50p` |
| `percent_graded_min_not_met` | True when `assign_percent_graded < 0.90`                                                                                                                                                               |
| `assignment_has_flags`       | True when `assign_max_score_not_10` OR `overly_exempt_assignment` OR `flags_sum > 0` OR `percent_graded_min_not_met`                                                                                   |

`assignment_has_flags` is the single rollup signal: `false` = fully compliant,
`true` = at least one check failed. The individual flag columns and counts
remain available for diagnostic drill-down.

### Flags and calculations: `int_tableau__gradebook_audit_flags_calculations`

!!! warning "In progress" This model is being refactored as part of the AY
2026-2027 revamp. Full documentation will be added once stable.

    **Known changes from AY 2025-2026:**

    - Replaces `int_tableau__gradebook_audit_flags` (the old six-branch UNION
      ALL assembly model)
    - Joins `int_powerschool__gradebook_assignment_scores_rollup` directly for
      assignment-level rollup counts instead of computing them inline
    - All `stg_google_sheets__gradebook_exceptions` joins removed (deprecated)
    - Outputs feed `int_tableau__gradebook_audit_scaffold_unpivot`

### Scaffold unpivot: `int_tableau__gradebook_audit_scaffold_unpivot`

!!! warning "In progress" This model is being refactored as part of the AY
2026-2027 revamp. Full documentation will be added once stable.

    **Known changes from AY 2025-2026:**

    - UNPIVOT list reduced from ~17 flags to ~10 flags (5 unchanged + 5
      consolidated from 12 AY 2025-2026 flags)
    - Student-level dimensional columns removed from final SELECT

### Final extract: `rpt_tableau__gradebook_audit`

!!! warning "In progress" This model is being refactored as part of the AY
2026-2027 revamp. Full documentation will be added once stable.

    **Known issues under investigation:**

    - Branch 2 logic flag: `and not f.is_healthy_gradebook` may need to be
      `and f.is_healthy_gradebook` — pending confirmation.

---

??? note "AY 2025-2026 data model" Lineage diagram for
`rpt_tableau__gradebook_audit`:

    ```mermaid
    flowchart TD
        %% ── Sources ──────────────────────────────────────────────────────────────
        subgraph SRC ["Sources"]
            direction TB
            src_ps_sec["PowerSchool\nsections / courses"]
            src_ps_cc["PowerSchool\ncourse_enrollments"]
            src_ps_ga["PowerSchool\ngradebook_assignments\n+ scores"]
            src_ps_grades["PowerSchool\nfinal_grades\n+ stored_grades"]
            src_ps_terms["PowerSchool\nterms / calendar_week"]
            src_ps_sch["PowerSchool\nschools"]
            src_gs_flags["Google Sheets\ngradebook_flags"]
            src_gs_exp["Google Sheets\ngradebook_expectations\n_assignments"]
            src_gs_exc["Google Sheets\ngradebook_exceptions"]
        end

        %% ── Staging / Base ───────────────────────────────────────────────────────
        subgraph STG ["Staging & Base"]
            direction TB
            stg_flags["stg_google_sheets__\ngradebook_flags"]
            stg_exp["stg_google_sheets__\ngradebook_expectations\n_assignments"]
            stg_exc["stg_google_sheets__\ngradebook_exceptions"]
            base_sec["base_powerschool__\nsections"]
            base_ce["base_powerschool__\ncourse_enrollments"]
            base_fg["base_powerschool__\nfinal_grades"]
            stg_sg["stg_powerschool__\nstoredgrades"]
        end

        %% ── Intermediate – Upstream ──────────────────────────────────────────────
        subgraph INT_UP ["Intermediate · Upstream"]
            direction TB
            int_terms["int_powerschool__terms\n+ calendar_week"]
            int_catgr["int_powerschool__\ncategory_grades"]
            int_ga["int_powerschool__\ngradebook_assignments"]
            int_gas["int_powerschool__\ngradebook_assignments_scores"]
            int_enroll["int_extracts__\nstudent_enrollments"]
            int_staff["int_people__staff_roster"]
            int_lead["int_people__\nleadership_crosswalk"]
        end

        %% ── Intermediate – Audit Scaffolds ───────────────────────────────────────
        subgraph INT_SCAF ["Intermediate · Audit Scaffolds"]
            direction TB
            int_tscaf["int_tableau__\ngradebook_audit_teacher_scaffold"]
            int_sscaf["int_tableau__\ngradebook_audit_student_scaffold"]
        end

        %% ── Intermediate – Audit Rollups ─────────────────────────────────────────
        subgraph INT_ROLL ["Intermediate · Audit Rollups"]
            direction TB
            int_at["int_tableau__\ngradebook_audit_assignments_teacher"]
            int_as["int_tableau__\ngradebook_audit_assignments_student"]
            int_ct["int_tableau__\ngradebook_audit_categories_teacher"]
        end

        %% ── Flag Assembly + Final ─────────────────────────────────────────────────
        int_flags["int_tableau__\ngradebook_audit_flags"]
        RPT(["rpt_tableau__gradebook_audit"])

        %% ── Edges: Sources → Staging/Base ────────────────────────────────────────
        src_gs_flags --> stg_flags
        src_gs_exp   --> stg_exp
        src_gs_exc   --> stg_exc
        src_ps_sec   --> base_sec
        src_ps_cc    --> base_ce
        src_ps_grades --> base_fg
        src_ps_grades --> stg_sg

        %% ── Edges: Sources → Upstream Intermediates ──────────────────────────────
        src_ps_terms --> int_terms
        src_ps_sch   --> int_terms
        src_ps_grades --> int_catgr
        src_ps_ga    --> int_ga
        src_ps_ga    --> int_gas

        %% ── Edges: → Teacher Scaffold ────────────────────────────────────────────
        base_sec   --> int_tscaf
        int_terms  --> int_tscaf
        int_staff  --> int_tscaf
        int_lead   --> int_tscaf
        stg_exp    --> int_tscaf
        stg_exc    --> int_tscaf

        %% ── Edges: → Student Scaffold ────────────────────────────────────────────
        int_enroll --> int_sscaf
        base_ce    --> int_sscaf
        base_fg    --> int_sscaf
        stg_sg     --> int_sscaf
        int_tscaf  --> int_sscaf
        int_catgr  --> int_sscaf
        stg_exp    --> int_sscaf
        stg_exc    --> int_sscaf

        %% ── Edges: → Rollups ─────────────────────────────────────────────────────
        int_tscaf --> int_at
        int_ga    --> int_at
        int_gas   --> int_at
        stg_exc   --> int_at

        int_sscaf --> int_as
        int_gas   --> int_as

        int_tscaf --> int_ct
        int_ga    --> int_ct
        int_gas   --> int_ct
        stg_exc   --> int_ct

        %% ── Edges: → Flag Assembly ───────────────────────────────────────────────
        int_as    --> int_flags
        int_at    --> int_flags
        int_ct    --> int_flags
        int_sscaf --> int_flags
        stg_flags --> int_flags
        stg_exc   --> int_flags

        %% ── Edges: → Final ───────────────────────────────────────────────────────
        int_flags --> RPT

        %% ── Styling ───────────────────────────────────────────────────────────────
        classDef source   fill:#e8f4f8,stroke:#5b9bd5,color:#000
        classDef staging  fill:#e2f0d9,stroke:#70ad47,color:#000
        classDef intmodel fill:#fce4d6,stroke:#ed7d31,color:#000
        classDef report   fill:#d9e1f2,stroke:#4472c4,color:#000,font-weight:bold

        class src_ps_sec,src_ps_cc,src_ps_ga,src_ps_grades,src_ps_terms,src_ps_sch,src_gs_flags,src_gs_exp,src_gs_exc source
        class stg_flags,stg_exp,stg_exc,base_sec,base_ce,base_fg,stg_sg staging
        class int_terms,int_catgr,int_ga,int_gas,int_enroll,int_staff,int_lead,int_tscaf,int_sscaf,int_at,int_as,int_ct,int_flags intmodel
        class RPT report
    ```

    ### Layer summary

    | Layer                  | Count | Purpose                                                                                      |
    | ---------------------- | ----- | -------------------------------------------------------------------------------------------- |
    | Sources                | 9     | PowerSchool gradebook, enrollment, and calendar data; three Google Sheets config tables      |
    | Staging & Base         | 7     | Light cleaning of config sheets; union of district PowerSchool tables                        |
    | Upstream intermediates | 7     | Gradebook assignments/scores, enrollment, terms, staff/leadership — shared with other models |
    | Audit scaffolds        | 2     | Time spine (section × week × category) and student roster with EOQ flag columns              |
    | Audit rollups          | 3     | Assignment and category metrics at teacher and student grain                                 |
    | Flag assembly          | 1     | UNION ALL + UNPIVOT of all flag sources; applies allowlist and suppressions                  |
    | Report                 | 1     | Final 5-branch UNION joining teacher aggregates to student flag rows                         |

    ### Key data flows

    **Teacher/section stream** — tracks what teachers have posted: how many
    assignments per category per week, whether max scores are correct, whether the
    class is keeping up with grading. Teacher-scoped; no individual student
    identifiers. Flows through `int_tableau__gradebook_audit_teacher_scaffold` →
    `int_powerschool__gradebook_assignments_scores` →
    `int_tableau__gradebook_audit_assignments_teacher` and
    `int_tableau__gradebook_audit_categories_teacher`.

    **Student stream** — tracks what each individual student has received: whether
    scores are valid, whether missing assignments are coded correctly, and whether
    EOQ requirements are satisfied. Flows through
    `int_tableau__gradebook_audit_student_scaffold` →
    `int_powerschool__gradebook_assignments_scores` →
    `int_tableau__gradebook_audit_assignments_student`.

    Both streams converge in `int_tableau__gradebook_audit_flags`, where boolean
    flag columns are unpivoted to rows and filtered through the configuration
    allowlist and suppression tables. The final extract joins teacher-aggregated
    flag rows to individual student flag rows via a LEFT JOIN — teacher-level flags
    (class-category, class-category-assignment) appear with `null` student fields
    unless a student-level row also fired that flag.

    ---

    ### Configuration: `stg_google_sheets__gradebook_expectations_assignments`

    Deprecated in AY 2026-2027. Replaced by
    `int_powerschool__u_expectations_qtd_unpivot`.

    Defined the minimum number of assignments a teacher was expected to have posted
    per category by each week of each quarter.

    **Grain**: one row per
    `academic_year × region × school_level × quarter × week_number × assignment_category_code`
    (after staging unpivot).

    The source sheet stored expectations in a wide format — one column per category
    code (`W`, `H`, `F`, `S`) — with rows for each region / school level / quarter /
    week combination. Staging unpivoted to one row per category (dropping nulls,
    meaning that category was not expected that week in that context) and computed:

    - `assignment_category_term` — `code || right(quarter, 1)`, e.g. `W3` for Work
      Habits in Q3
    - `assignment_category_name` — full name from code (`W` → `'Work Habits'`, etc.)

    `int_tableau__gradebook_audit_teacher_scaffold` inner-joined to this table to
    expand each section × week to one row per category. If a region / school level /
    week combination had no rows here, the teacher category scaffold produced no
    rows for that context — the audit was silent rather than erroring.

    ---

    ### Configuration: `stg_google_sheets__gradebook_exceptions`

    Deprecated in AY 2026-2027. All exception joins removed from the pipeline.

    Was the suppression table. Used in 15+ LEFT JOINs across five intermediate
    models to permanently or temporarily exclude specific rows from the audit output.

    **Grain**: no natural grain — each row was an override instruction addressed to a
    specific model and CTE, identified by `view_name` + `cte`.

    **How suppression worked**: every consuming CTE did a LEFT JOIN to this table,
    then added `WHERE e.include_row IS NULL`. A row where `include_row` is non-null
    caused the matched data rows to be dropped from that CTE's output.

    **Call sites** — `view_name` and `cte` together identified where in the code a
    row applied:

    | `view_name`                 | `cte`                     | Where used                                         | Effect                                                          |
    | --------------------------- | ------------------------- | -------------------------------------------------- | --------------------------------------------------------------- |
    | `teacher_scaffold`          | `sections`                | `int_tableau__gradebook_audit_teacher_scaffold`    | Removed an entire section from the audit                        |
    | `teacher_scaffold`          | `null`                    | `int_tableau__gradebook_audit_teacher_scaffold`    | Removed section-weeks from the final scaffold output            |
    | `teacher_category_scaffold` | `final`                   | `int_tableau__gradebook_audit_teacher_scaffold`    | Removed a gradebook category from the teacher category scaffold |
    | `assignments_teacher`       | `null`                    | `int_tableau__gradebook_audit_assignments_teacher` | Suppressed assignment rollup counts for a course                |
    | `categories_teacher`        | `null`                    | `int_tableau__gradebook_audit_categories_teacher`  | Removed category-level rows                                     |
    | `categories_teacher`        | `assignment_score_rollup` | `int_tableau__gradebook_audit_categories_teacher`  | Excluded students from `n_expected` / `n_expected_scored`       |
    | `audit_flags`               | `student_unpivot`         | `int_tableau__gradebook_audit_flags`               | Suppressed specific student-assignment flags                    |
    | `audit_flags`               | `teacher_unpivot_cca`     | `int_tableau__gradebook_audit_flags`               | Suppressed teacher assignment flags                             |
    | `audit_flags`               | `teacher_unpivot_cc`      | `int_tableau__gradebook_audit_flags`               | Suppressed teacher category flags                               |
    | `audit_flags`               | `eoq_items`               | `int_tableau__gradebook_audit_flags`               | Suppressed EOQ student flags (non-conduct)                      |
    | `audit_flags`               | `eoq_items_conduct_code`  | `int_tableau__gradebook_audit_flags`               | Suppressed conduct code flags                                   |
    | `audit_flags`               | `student_course_category` | `int_tableau__gradebook_audit_flags`               | Suppressed student-category flags                               |

    **Permanent vs. temporary suppression** was controlled by
    `is_quarter_end_date_range`:

    | Value   | Suppression applied when    |
    | ------- | --------------------------- |
    | `NULL`  | Always (permanent)          |
    | `TRUE`  | Only during the EOQ window  |
    | `FALSE` | Only outside the EOQ window |

    !!! warning "Silent failures" A typo in `view_name` or `cte` meant the exception
    was never matched and silently had no effect. There was no validation that these
    values corresponded to actual call sites in the SQL.

    ---

    ### Scaffold layer

    #### `int_tableau__gradebook_audit_teacher_scaffold`

    The time spine for the audit. One row per active section × calendar week ×
    scaffold variant for the current academic year. Feeds directly into
    `int_tableau__gradebook_audit_student_scaffold` — changes here cascaded
    immediately to the student scaffold.

    **Why two scaffold variants**: some audit flags apply at the section level (e.g.
    a teacher hasn't set up their gradebook at all), while others apply at the
    section × gradebook category level (e.g. too few homework grades in a given
    category). The `scaffold_name` field distinguishes the two variants downstream —
    flags referencing `scaffold_name = 'teacher_scaffold'` are section-level only;
    flags referencing `scaffold_name = 'teacher_category_scaffold'` are per category.

    **Scope**: `current_academic_year` only; Q3 and Q4 only; sections with zero
    enrolled students excluded (`sections_no_of_students != 0`).

    **Source table temporal scope**:

    | Source                             | Scope         |
    | ---------------------------------- | ------------- |
    | `base_powerschool__sections`       | Multi-year    |
    | `int_powerschool__terms`           | Multi-year    |
    | `int_powerschool__calendar_week`   | Multi-year    |
    | `int_people__staff_roster`         | Year-agnostic |
    | `stg_powerschool__schools`         | Year-agnostic |
    | `int_people__leadership_crosswalk` | Year-agnostic |

    **CTE chain**:

    1. `sections` — active sections from `base_powerschool__sections` joined to
       `int_people__staff_roster` for `teacher_tableau_username`; filters to
       `current_academic_year` and excludes zero-student sections; applies
       section-level exceptions.
    2. `term_weeks` — joins `int_powerschool__terms` to
       `int_powerschool__calendar_week` on `yearid + schoolid + quarter`; joins
       `stg_powerschool__schools` for the school abbreviation; joins
       `int_people__leadership_crosswalk` for HoS and school leader names; computes
       `quarter_end_date_insession` (last in-session day of the quarter via window
       `max(week_end_date)`).
    3. `school_level_mod` — crosses sections and term weeks; computes
       `is_quarter_end_date_range`, `region_school_level`, and `section_or_period`
       (HS uses `external_expression`; others use `section_number`); applies
       scaffold-level exceptions.
    4. `final` — UNION ALL of the two scaffold variants:
       - `teacher_scaffold` — bare section × week row; category columns are `null`
       - `teacher_category_scaffold` — inner-joined to
         `stg_google_sheets__gradebook_expectations_assignments` on
         `region + school_level + academic_year + quarter + week_number`; carries
         category columns; applies category exceptions

    **`is_quarter_end_date_range`** — boolean computed against `current_date`;
    controls when EOQ-only flags fire and which exception rows apply:

    | Context                      | `TRUE` when `current_date` is...                                 |
    | ---------------------------- | ---------------------------------------------------------------- |
    | Miami (all levels)           | 9 days before through 28 days after `quarter_end_date_insession` |
    | HS, Q3                       | 9 days after through 20 days after `quarter_end_date_insession`  |
    | HS, Q3 (outside above range) | Never (`FALSE`)                                                  |
    | All others                   | 5 days before through 14 days after `quarter_end_date_insession` |

    !!! note "KIPP Sumner Elementary grade 5" Grade 5 sections at KIPP Sumner
    Elementary were treated as MS (`school_level_alt = 'MS'`) rather than ES. This
    override was applied in the `sections` CTE and propagated through
    `region_school_level` and all downstream school-level filters.

    #### `int_tableau__gradebook_audit_student_scaffold`

    Added enrolled students to the teacher scaffold. Mirrored the two-branch
    structure of `int_tableau__gradebook_audit_teacher_scaffold` at the student
    grain — `student_scaffold` produced quarter-level flags, and
    `student_category_scaffold` produced flags tied to a specific gradebook
    category.

    **Scope**: `current_academic_year`, `enroll_status = 0`, not out-of-district,
    `rn_year = 1` (deduplicated enrollment), `sections_no_of_students != 0`.
    Inherited all section and category exclusions from the teacher scaffold via
    INNER JOIN.

    **Source table temporal scope**:

    | Source                                          | Scope             |
    | ----------------------------------------------- | ----------------- |
    | `int_extracts__student_enrollments`             | Multi-year        |
    | `base_powerschool__course_enrollments`          | Multi-year        |
    | `int_powerschool__category_grades`              | Multi-year        |
    | `base_powerschool__final_grades`                | Current year only |
    | `stg_powerschool__storedgrades`                 | Multi-year        |
    | `int_tableau__gradebook_audit_teacher_scaffold` | Current year only |

    !!! note "quarter_course_grades CTE — summer refresh toggle" The
    `quarter_course_grades` CTE UNIONed two sources:

        - `'current_year'` — from `base_powerschool__final_grades` (current year
          only), filtered to `termbin_start_date <= current_date`
        - `'last_year'` — from `stg_powerschool__storedgrades` for
          `current_academic_year - 1`, `storecode_type = 'Q'`, non-transfer grades

        The JOIN filtered to `grades_type = 'current_year'` during the school year.
        After PowerSchool rolled over in summer, flip to `grades_type = 'last_year'`
        to keep the dashboard operational. Flip back when new-year data was ready.

    **`student_scaffold`** — boolean columns unpivoted in
    `int_tableau__gradebook_audit_flags`:

    | Column                                 | Fires when                                                                              |
    | -------------------------------------- | --------------------------------------------------------------------------------------- |
    | `qt_student_is_ada_80_plus_gpa_less_2` | Non-ES (Camden/Newark/Miami-MS); ADA >= 80% and quarter GPA < 2.0                       |
    | `qt_percent_grade_greater_100`         | Camden and Miami (ES/MS/HS) only; quarter course percent grade > 100                    |
    | `qt_grade_70_comment_missing`          | Non-ES; EOQ window; grade < 70; comment is null                                         |
    | `qt_comment_missing`                   | MiamiES; EOQ window; comment is null                                                    |
    | `qt_es_comment_missing`                | CamdenES or NewarkES; EOQ window; credit type in (HR, MATH, ENG, RHET); comment is null |
    | `qt_g1_g8_conduct_code_missing`        | Miami G1-G8; EOQ window; non-HR course; conduct is null                                 |
    | `qt_g1_g8_conduct_code_incorrect`      | Miami G1-G8; EOQ window; non-HR course; conduct not in (A, B, C, D, E, F)               |
    | `qt_kg_conduct_code_missing`           | MiamiES KG; EOQ window; HR course; conduct is null                                      |
    | `qt_kg_conduct_code_incorrect`         | MiamiES KG; EOQ window; HR course; conduct not in (E, G, S, M)                          |
    | `qt_kg_conduct_code_not_hr`            | MiamiES KG; EOQ window; non-HR course; conduct is not null                              |

    **`student_category_scaffold`** — category-level boolean columns:

    | Column                       | Fires when                                                                        |
    | ---------------------------- | --------------------------------------------------------------------------------- |
    | `w_grade_inflation`          | Non-ES; student's W% differs from class-wide W average by >= 30 percentage points |
    | `qt_effort_grade_missing`    | Miami (ES and MS); W category; EOQ window; category grade is null                 |
    | `qt_formative_grade_missing` | MiamiES only; F category; EOQ window; category grade is null                      |
    | `qt_summative_grade_missing` | MiamiES only; S category; non-ENG/MATH; EOQ window; category grade is null        |

    ---

    ### Assignment and category rollup layer

    #### `int_powerschool__gradebook_assignments_scores`

    One row per student × assignment. Generated every assignment a student should
    have a score for based on enrollment dates — including assignments in exempt
    courses or gradebook categories, which were filtered out downstream.

    **Key business logic**: The INNER JOIN to
    `base_powerschool__course_enrollments` on
    `duedate between cc_dateenrolled and cc_dateleft` scoped each assignment to
    only the students whose enrollment was active when the assignment was due. The
    LEFT JOIN to `stg_powerschool__assignmentscore` meant a student row existed
    even when no score had been entered.

    **Key computed columns**:

    | Column                            | Definition                                                                 |
    | --------------------------------- | -------------------------------------------------------------------------- |
    | `is_expected`                     | True if not exempt and `iscountedinfinalgrade = 1`                         |
    | `is_expected_null`                | `is_expected` and `score_entered is null`                                  |
    | `is_expected_zero`                | `is_expected` and `score_entered = 0`                                      |
    | `is_expected_missing`             | `is_expected` and `is_missing = 1`                                         |
    | `is_expected_late`                | `is_expected` and `is_late = 1`                                            |
    | `is_expected_scored`              | `is_expected` and `score_entered is not null`                              |
    | `is_academic_dishonesty`          | HS; `score_entered = 0` and not marked missing                             |
    | `is_expected_academic_dishonesty` | `is_expected` and HS; `score_entered = 0` and not marked missing           |
    | `score_entered`                   | `scorepoints` for POINTS; `actualscoreentered` cast to numeric for PERCENT |
    | `half_total_point_value`          | `totalpointvalue / 2`                                                      |

    **Per-student per-assignment flags** (AY 2025-2026 — 16 flags):

    | Flag                                             | Fires when                                                   |
    | ------------------------------------------------ | ------------------------------------------------------------ |
    | `assign_null_score`                              | `is_expected_null = 1` (score field is blank)                |
    | `assign_score_above_max`                         | `score_entered > totalpointvalue`                            |
    | `assign_w_score_less_5`                          | W; not missing; `score_entered < 5`                          |
    | `assign_h_score_less_5`                          | H; not missing; `score_entered < 5`                          |
    | `assign_f_score_less_5`                          | F; not missing; `score_entered < 5`                          |
    | `assign_w_missing_score_not_5`                   | W; non-HS; marked missing; `score_entered != 5`              |
    | `assign_h_missing_score_not_5`                   | H; non-HS; marked missing; `score_entered != 5`              |
    | `assign_f_missing_score_not_5`                   | F; non-HS; marked missing; `score_entered != 5`              |
    | `assign_w_missing_score_not_0`                   | W; HS; marked missing; `score_entered != 0`                  |
    | `assign_h_missing_score_not_0`                   | H; HS; marked missing; `score_entered != 0`                  |
    | `assign_f_missing_score_not_0`                   | F; HS; marked missing; `score_entered != 0`                  |
    | `assign_s_missing_score_not_0`                   | S; HS; marked missing; `score_entered != 0`                  |
    | `assign_s_score_less_50p`                        | S; non-HS; `score_entered < half_total_point_value`          |
    | `assign_s_hs_score_less_50p`                     | S; HS; not missing; `score_entered < half_total_point_value` |
    | `assign_s_ms_score_not_conversion_chart_options` | S; MS; not exempt; not null; score not on MS chart           |
    | `assign_s_hs_score_not_conversion_chart_options` | S; HS; not AP; not exempt; not null; score not on HS chart   |

    Feeds `int_tableau__gradebook_audit_assignments_student` (student-level flags)
    and `int_tableau__gradebook_audit_assignments_teacher` (teacher-level flags).

    #### `int_tableau__gradebook_audit_assignments_student`

    One row per student × assignment × week. Joined
    `int_tableau__gradebook_audit_student_scaffold` (`student_category_scaffold`
    variant) to `int_powerschool__gradebook_assignments_scores` on
    `sections_dcid + students_dcid + category_code + duedate within week`.

    Assignment-level filters in the JOIN condition: `iscountedinfinalgrade = 1` and
    `scoretype in ('POINTS', 'PERCENT')`. Assignments that failed these criteria
    were excluded entirely rather than producing a flag.

    #### `int_tableau__gradebook_audit_assignments_teacher`

    One row per section × assignment × week. Joined the teacher category scaffold
    to `int_powerschool__gradebook_assignments` on
    `sections_dcid + category_name + duedate within week window`, then to
    `int_powerschool__gradebook_assignments_scores` aggregated by
    `assignmentsectionid`.

    **Exception handling** — own exception join to
    `stg_google_sheets__gradebook_exceptions` (`view_name = 'assignments_teacher'`,
    `cte is null`, keyed by `course_number` and `is_quarter_end_date_range`). When
    an exception row matched, all aggregate rollup columns were set to `null`.

    **Class-level max-score flags**:

    | Flag                        | Fires when                                     |
    | --------------------------- | ---------------------------------------------- |
    | `w_assign_max_score_not_10` | W assignment; `totalpointvalue != 10`          |
    | `h_assign_max_score_not_10` | H assignment (non-ES); `totalpointvalue != 10` |
    | `f_assign_max_score_not_10` | F assignment; `totalpointvalue != 10`          |
    | `s_max_score_greater_100`   | Miami S assignment; `totalpointvalue > 100`    |

    **Aggregates passed downstream**:

    - `n_students`, `n_late`, `n_exempt`, `n_missing`, `n_null`,
      `n_academic_dishonesty`, `n_is_null_missing`, `n_is_null_not_missing`,
      `n_expected`, `n_expected_scored`
    - `teacher_avg_score_for_assign_per_class_section_and_assign_id`
    - `sum_totalpointvalue_section_quarter_category`
    - `teacher_running_total_assign_by_cat`

    #### `int_tableau__gradebook_audit_categories_teacher`

    One row per section × category × week. Joined the teacher category scaffold to
    `int_powerschool__gradebook_assignments` and
    `int_powerschool__gradebook_assignments_scores`, then aggregated to category
    level.

    **Per-category per-section flags**:

    | Flag                              | Fires when                                             |
    | --------------------------------- | ------------------------------------------------------ |
    | `w_expected_assign_count_not_met` | W; `teacher_running_total_assign_by_cat < expectation` |
    | `h_expected_assign_count_not_met` | H; same                                                |
    | `f_expected_assign_count_not_met` | F; same                                                |
    | `s_expected_assign_count_not_met` | S; same                                                |
    | `w_percent_graded_min_not_met`    | W; `percent_graded_for_quarter_week_class < 0.70`      |
    | `h_percent_graded_min_not_met`    | H; same                                                |
    | `f_percent_graded_min_not_met`    | F; same                                                |
    | `s_percent_graded_min_not_met`    | S; same                                                |
    | `qt_teacher_s_total_greater_200`  | S; non-MiamiES; `sum_totalpointvalue > 200`            |
    | `qt_teacher_s_total_less_200`     | S; non-MiamiES; `sum_totalpointvalue < 200`            |
    | `qt_teacher_s_total_greater_100`  | S; MiamiES; `sum_totalpointvalue > 100`                |
    | `qt_teacher_s_total_less_100`     | S; MiamiES; `sum_totalpointvalue < 100`                |

    ---

    ### Flag assembly: `int_tableau__gradebook_audit_flags`

    Six-branch `UNION ALL` that converted boolean flag columns to rows, applied the
    active-flag allowlist, and applied suppressions. Single source for
    `rpt_tableau__gradebook_audit`.

    #### Design principle: `cte_grouping` determines what columns a row carries

    Each flag in `stg_google_sheets__gradebook_flags` had a `cte_grouping` value
    that encoded the grain of information that flag needed. The UNION ALL schema was
    wide enough to hold every grain, but each branch only populated the columns
    meaningful for its grouping — everything else was `null`.

    | `cte_grouping`              | Carries                                             | Nulls out                              |
    | --------------------------- | --------------------------------------------------- | -------------------------------------- |
    | `assignment_student`        | Student + section + assignment + teacher aggregates | Category-level agg columns             |
    | `student_course`            | Student + section (quarter grain)                   | Category, assignment, teacher agg cols |
    | `student_course_category`   | Student + section + category                        | Assignment, teacher agg columns        |
    | `class_category_assignment` | Section + assignment + teacher agg counts           | Student columns                        |
    | `class_category`            | Section + category-level agg columns                | Student columns, per-assignment counts |

    #### Pattern per CTE

    ```sql
    <source_model> UNPIVOT (audit_flag_value FOR audit_flag_name IN (...flags...))
    INNER JOIN stg_google_sheets__gradebook_flags   -- allowlist
    LEFT JOIN stg_google_sheets__gradebook_exceptions  -- suppression
    WHERE e.include_row IS NULL
    ```

    #### CTE inventory

    | CTE                       | Source                                             | `cte_grouping`              | Flags |
    | ------------------------- | -------------------------------------------------- | --------------------------- | ----- |
    | `student_unpivot`         | `int_tableau__gradebook_audit_assignments_student` | `assignment_student`        | 16    |
    | `teacher_unpivot_cca`     | `int_tableau__gradebook_audit_assignments_teacher` | `class_category_assignment` | 4     |
    | `teacher_unpivot_cc`      | `int_tableau__gradebook_audit_categories_teacher`  | `class_category`            | 12    |
    | `eoq_items`               | `int_tableau__gradebook_audit_student_scaffold`    | `student_course`, `student` | 7     |
    | `eoq_items_conduct_code`  | `int_tableau__gradebook_audit_student_scaffold`    | `student_course`            | 5     |
    | `student_course_category` | `int_tableau__gradebook_audit_student_scaffold`    | `student_course_category`   | 4     |

    ---

    ### Final extract: `rpt_tableau__gradebook_audit`

    **Design intent**: Every possible flag slot — whether or not a flag actually
    fired — must appear as a row so Tableau can compute a teacher health score
    (active errors / total possible checks). `teacher_aggs` produced that full set.
    The LEFT JOIN to `valid_flags` attached student data and set `flag_value = 1`
    when a flag fired; unmatched slots got `coalesce(v.flag_value, 0) = 0`.

    !!! note "FYI Flags — excluded from the Tableau health score" Five flags were
    informational only. They appeared in the extract but were excluded from the
    gradebook completion rate in Tableau via a calculated field on
    `[Audit Flag Name]`:

        - `qt_student_is_ada_80_plus_gpa_less_2`
        - `w_grade_inflation`
        - `qt_teacher_s_total_less_200`
        - `assign_s_hs_score_not_conversion_chart_options`
        - `assign_s_ms_score_not_conversion_chart_options`

    **Five-branch UNION ALL**:

    | Branch | `cte_grouping` / `code_type`                                                      | Includes `teacher_assign_id`? | Includes `assignment_category_term`? |
    | ------ | --------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------ |
    | 1      | `code_type = 'Gradebook Category'` + `cte_grouping = 'assignment_student'`        | Yes                           | Yes                                  |
    | 2      | `cte_grouping = 'student_course_category'`                                        | No                            | Yes                                  |
    | 3      | `code_type = 'Quarter'` + `cte_grouping != 'student_course_category'`             | No                            | No                                   |
    | 4      | `code_type = 'Gradebook Category'` + `cte_grouping = 'class_category_assignment'` | Yes                           | Yes                                  |
    | 5      | `code_type = 'Gradebook Category'` + `cte_grouping = 'class_category'`            | No                            | Yes                                  |

    All branches filtered
    `audit_start_date <= current_date('{{ var("local_timezone") }}')` and
    `not is_current_week`. The current week was always excluded — grading was still
    in progress.

---

## Configuration: `stg_google_sheets__gradebook_flags`

The flag allowlist. A flag only appears in the dashboard if a matching row
exists in this table — making it the primary on/off switch for every audit
check.

**Grain**: one row per
`academic_year × region × school_level × code × audit_flag_name`.

| Column            | Purpose                                                                                  |
| ----------------- | ---------------------------------------------------------------------------------------- |
| `code_type`       | `'Quarter'` (EOQ flags) or `'Gradebook Category'` (weekly flags)                         |
| `code`            | Quarter (`Q3`, `Q4`) or category code (`W`, `H`, `F`, `S`)                               |
| `audit_category`  | Human-readable grouping shown in Tableau (e.g., `'Missing Score'`, `'Conduct Code'`)     |
| `audit_flag_name` | Snake-case name matching the boolean column in the source model                          |
| `cte_grouping`    | Which UNION branch in `int_tableau__gradebook_audit_flags_calculations` this row targets |
| `grade_level`     | Set only for conduct code flags that require a grade-level-specific join                 |
| `alt_code`        | Computed in staging; maps student-category flags to their category code for joining      |

Activating a new flag for a region requires adding a row here. Deactivating a
flag removes or disables its row. There is no validation that `audit_flag_name`
values in this sheet match the column names in the SQL — a typo silently
excludes all rows for that flag without raising an error.

---

## Start-of-year procedure

At the start of each academic year, the flags configuration sheet must be
updated before the audit will produce data for the new year.

### Step 1 — Update `stg_google_sheets__gradebook_flags`

Add rows for the new `academic_year`. The process is:

1. **Generate the new rows** by running the query below against the current prod
   staging table. It copies all prior-year rows for active regions, bumps
   `academic_year` to the new year, and excludes any flags that were deprecated
   for the new year. It also generates Paterson rows from the Newark template.
   The query output can be pasted directly into the Google Sheet as
   tab-separated values.

2. **Verify with T&L** that no flags should be added or removed before pasting.

3. **Paste** the output into the sheet starting at the first empty row.

```sql
-- Generate AY 2027 flag rows (adjust the academic_year values each rollover)
SELECT * FROM (

  -- Camden and Newark: copy prior year, bump academic_year
  -- Column order matches the sheet: academic_year, region, school_level,
  -- grade_level, code_type, code, audit_category, audit_flag_name, cte_grouping
  SELECT
    2027 AS academic_year,
    region,
    school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region IN ('Newark', 'Camden')
    AND academic_year = 2026
    AND audit_flag_name NOT IN (
      -- list any flags being deprecated for the new year here
    )

  UNION ALL

  -- Paterson MS: mirror Newark MS
  SELECT
    2027 AS academic_year,
    'Paterson' AS region,
    school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region = 'Newark'
    AND school_level = 'MS'
    AND academic_year = 2026
    AND audit_flag_name NOT IN (
      -- same deprecated list
    )

  UNION ALL

  -- Paterson ES: EOQ comments only (Q3 and Q4)
  SELECT
    2027 AS academic_year,
    'Paterson' AS region,
    'ES' AS school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region = 'Newark'
    AND school_level = 'ES'
    AND academic_year = 2026
    AND code IN ('Q3', 'Q4')

)
ORDER BY region, school_level, code_type, code, audit_flag_name
```

The `grade_level` column will be blank for all rows unless grade-level-specific
flags (e.g., conduct code flags) are active. That is expected.

!!! warning "Empty flags sheet blocks the audit" If
`stg_google_sheets__gradebook_flags` has no rows for the new academic year, the
teacher category scaffold produces no rows (inner join fails) and the entire
audit is empty — no error, just no data.

---

## Recent change: Q1/Q2 removal (May 2026)

Q1 and Q2 were removed from `int_tableau__gradebook_audit_teacher_scaffold` by
adding `t.term not in ('Q1', 'Q2')` to the `term_weeks` CTE. This was not a
policy change — the audit policy for Q1 and Q2 was unchanged — but a volume
reduction to address Tableau Server refresh failures. The audit now covers Q3
and Q4 only for the current academic year.

Tracking issue: [#3908](https://github.com/TEAMSchools/teamster/issues/3908)

---

## Open questions and future work

- **`flags_calculations` and `scaffold_unpivot`**: Both models are still being
  refactored (see in-progress stubs above). Documentation will be finalized once
  the models are stable.
- **6h.8 — exposure split**: `gradebook_audit` and `gradebook_gpa` Tableau
  workbooks may need separate dbt exposures; pending LSID confirmation.
- **Task 9 — assignment validity filter**: A pre-filter that marks an assignment
  as "valid" (`assignment_has_flags = false`) before counting it toward QTD.
  Design documented in the
  [implementation plan](../superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md).
- **Version rename**: Once stable, `_v4` suffix will be dropped from model names
  and the prior version renamed `_v3`. No version numbers in AY 2026-2027 model
  names.

See [GitHub issue #3908](https://github.com/TEAMSchools/teamster/issues/3908)
for the full AY 2026-2027 tracking issue.
