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
and instructional coaches a per-quarter view of compliance across every section,
flagging deviations from policy so they can be addressed before the end of the
quarter.

The audit operates at multiple grains simultaneously:

- **Assignment-student** — did this specific student receive a valid score on
  this assignment?
- **Class-category** — has this teacher posted the required number of
  assignments in this category this week? Are scores being entered on time?
- **Student-course** — does this student's category grade meet policy thresholds
  (grade inflation, effort/formative/summative missing)?
- **End-of-quarter (EOQ)** — are comments and final grades correctly entered by
  the end of each quarter?

### Dashboard coverage (AY 2026-2027)

| Region   | School level | Coverage depth                              | Notes                                                          |
| -------- | ------------ | ------------------------------------------- | -------------------------------------------------------------- |
| Camden   | MS, HS       | Full audit (all applicable flags)           |                                                                |
| Camden   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook            |
| Newark   | MS, HS       | Full audit (all applicable flags)           |                                                                |
| Newark   | ES           | EOQ comments only (`qt_es_comment_missing`) | ES schools do not enter assignments in PS gradebook            |
| Paterson | MS           | Full audit (all applicable flags)           | Added AY 2026-2027; expectations spoofed from Newark's MS data |
| Paterson | ES           | EOQ comments only (`qt_es_comment_missing`) | Added AY 2026-2027                                             |
| Miami    | n/a          | Removed                                     | Moved to Focus gradebook; excluded at scaffold level           |

!!! note "Paterson GradeBook plugin" The **KIPP NJ Gradebook Audit** plugin
cannot be installed on Paterson's PowerSchool instance, so `U_EXPECTATIONS` is
never populated there natively. Instead, `kipppaterson`'s own
`stg_powerschool__u_expectations` model (overriding the disabled `powerschool`
package version) reads Newark's real U_EXPECTATIONS data cross-project via a
`source()` on `kippnewark_powerschool`, filtered to `school_level = 'MS'` (see
`src/dbt/kipppaterson/models/powerschool/sis/staging/stg_powerschool__u_expectations.sql`).
`int_powerschool__u_expectations_qtd_unpivot`'s kipptaf-level union picks this
up as a third region alongside Camden and Newark — no different from a real
region's data at that point. Tracked:
[#3908](https://github.com/TEAMSchools/teamster/issues/3908)

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

| Code | Name              | Policy: max score per assignment | Policy: quarterly total | Policy: missing score           |
| ---- | ----------------- | -------------------------------- | ----------------------- | ------------------------------- |
| `W`  | Work Habits       | 10 pts                           | n/a                     | 5 (non-HS) / 0 (HS)             |
| `H`  | Homework          | 10 pts                           | n/a                     | 5 (non-HS) / 0 (HS)             |
| `F`  | Formative Mastery | 10 pts                           | n/a                     | 5 (non-HS) / 0 (HS)             |
| `S`  | Summative Mastery | No per-assignment max            | 200 pts                 | 0 (HS); min 50% of max (non-HS) |

## AY 2026-2027 data model

### What changed from AY 2025-2026

**Regions:**

- Miami removed — gradebook moved to Focus; excluded in scaffold via
  `_dbt_source_project != 'kippmiami'`
- Paterson added — MS mirrors Newark MS flags; ES has EOQ comments only

**Architecture:**

The AY 2026-2027 pipeline eliminated both scaffold models and collapsed the
multi-rollup chain into two new intermediates:

| Old model (AY 2025-2026)                                | New model (AY 2026-2027)                                                                             |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `int_tableau__gradebook_audit_teacher_scaffold`         | Disabled — `flags_calculations` joins `int_extracts__course_schedule_by_term` directly instead       |
| `int_tableau__gradebook_audit_student_scaffold`         | Disabled — `flags_calculations` joins `int_extracts__course_enrollments_by_term` directly instead    |
| `int_tableau__gradebook_audit_assignments_teacher`      | Disabled — function inlined in `int_tableau__gradebook_audit_flags_calculations`                     |
| `int_tableau__gradebook_audit_assignments_student`      | Disabled — function inlined in `int_tableau__gradebook_audit_flags_calculations`                     |
| `int_tableau__gradebook_audit_categories_teacher`       | Disabled — function inlined in `int_tableau__gradebook_audit_flags_calculations`                     |
| `int_tableau__gradebook_audit_flags`                    | Disabled — UNPIVOT now inline in `rpt_tableau__gradebook_audit`'s `health_calc`/`flags_unpivot` CTEs |
| `stg_google_sheets__gradebook_expectations_assignments` | `int_powerschool__u_expectations_qtd_unpivot`                                                        |
| `stg_google_sheets__gradebook_exceptions`               | Deprecated — all exception joins removed                                                             |
| `stg_google_sheets__gradebook_flags`                    | Deprecated — per-flag allowlist no longer needed (see below)                                         |

**Assignment count (QTD):** the audit now operates at quarter-grain (one row per
section × quarter × category) rather than week-grain. Q1 and Q2 are restored —
the prior `term not in ('Q1', 'Q2')` volume workaround is removed. All four
quarters are covered.

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

### Pipeline overview (AY 2026-2027)

The old scaffold models (`int_tableau__gradebook_audit_teacher_scaffold` and
`int_tableau__gradebook_audit_student_scaffold`) were eliminated. Their sources
are now joined directly inside
`int_tableau__gradebook_audit_flags_calculations`. The new pipeline:

```text
int_extracts__course_schedule_by_term  ──────────────────────────┐
int_powerschool__u_expectations_qtd_unpivot ─────────────────────┤
int_powerschool__gradebook_assignment_scores_rollup ─────────────┤
int_extracts__course_enrollments_by_term ────────────────────────┤
base_powerschool__final_grades / stg_powerschool__storedgrades ──┘
                                     │
                                     ▼
              int_tableau__gradebook_audit_flags_calculations
                                     │
                                     ▼
                   rpt_tableau__gradebook_audit
                (count_not_met_flag → flags_unpivot CTEs)
```

`flags_calculations` is a `UNION ALL` of three branches:

| Branch | `cte_grouping`       | Source                                     | Flags produced                                                                                                           |
| ------ | -------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| 1      | `sections_teacher`   | `int_extracts__course_schedule_by_term`    | None — anchor rows with all flag columns hardcoded `false`/`null`; feeds the report's "No Flags" anchor row              |
| 2      | `assignment_teacher` | `int_extracts__course_schedule_by_term`    | `assignment_has_flags`, `total_assign_count_qtd_by_cat_section_actual`, `total_assign_count_qtd_by_cat_section_no_flags` |
| 3      | `student_course`     | `int_extracts__course_enrollments_by_term` | `qt_percent_grade_greater_100`, `qt_grade_70_comment_missing`                                                            |

All three branches filter `school_level_alt != 'ES'` and
`_dbt_source_project != 'kippmiami'`.

Sections whose PowerSchool term overlaps only a single quarter are excluded
upstream by `int_extracts__course_schedule_by_term`
(`section_quarter_count >= 2` — only year and semester terms fan out to
quarters). In AY 2025-2026 data this drops a handful of trimester-term specials
(Paterson MS Music/Spanish) and short-term Newark sections; those teachers'
gradebooks are not audited.

### Expectations source: `int_powerschool__u_expectations_qtd_unpivot`

Replaces `stg_google_sheets__gradebook_expectations_assignments`. Reads the
PowerSchool `U_EXPECTATIONS` plugin table, which stores assignment count
expectations per category per week, and collapses it to the most recently
completed week per quarter. One row per
`region × school_level × quarter × assignment_category_code` (uniqueness-tested;
`academic_year` is injected as `current_academic_year`).

`week_end_sunday` — an output column consumed by
`int_tableau__gradebook_audit_flags_calculations` as the QTD assignment count
cutoff — is the Sunday ending the most recently completed school week (the
latest calendar week with
`week_start_monday < date_trunc(current_date, isoweek)`).

### Assignment and category rollup layer

#### `int_powerschool__gradebook_assignments_scores`

One row per student × assignment. Same grain and key business logic as AY
2025-2026 — the model was not renamed. The INNER JOIN to
`base_powerschool__course_enrollments` on the half-open range
`duedate >= cc_dateenrolled and duedate < cc_dateleft` scopes each assignment to
students whose enrollment was active when the assignment was due (half-open so
back-to-back enrollment stints sharing a boundary date match once). The LEFT
JOIN to `stg_powerschool__assignmentscore` means a student row exists even when
no score has been entered — `score_entered` is null in that case.

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

!!! note "KIPP Sumner base level + grade 5/6 MS override" KIPP Sumner Academy
(formerly KIPP Sumner Elementary; school 179905) is base-classified **ES**
network-wide in `stg_powerschool__schools` (matched by `abbreviation = 'Sumner'`
— high_grade alone no longer implies ES now that Sumner is K-6). Grades 5 and 6
are then overridden to MS (`school_level_alt = 'MS'`) for AY 2025+ in three
downstream models: the `scores` CTE here and
`int_extracts__course_schedule_by_term` match on `schoolid = 179905`;
`int_extracts__student_enrollments` matches on `school_abbreviation = 'Sumner'`
— never on school name, which PowerSchool has renamed once already. This ensures
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

A `UNION ALL` of three branches, all filtering `school_level_alt != 'ES'`,
`_dbt_source_project != 'kippmiami'`, and `exclude_from_gpa = 0`.

| Branch | `cte_grouping`       | Source                                     | Flags produced                                                                                                           |
| ------ | -------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| 1      | `sections_teacher`   | `int_extracts__course_schedule_by_term`    | None — anchor rows with all flag columns hardcoded `false`/`null`; feeds the report's "No Flags" anchor row              |
| 2      | `assignment_teacher` | `int_extracts__course_schedule_by_term`    | `assignment_has_flags`, `total_assign_count_qtd_by_cat_section_actual`, `total_assign_count_qtd_by_cat_section_no_flags` |
| 3      | `student_course`     | `int_extracts__course_enrollments_by_term` | `qt_percent_grade_greater_100`, `qt_grade_70_comment_missing`                                                            |

Branch 2 inner-joins `int_powerschool__u_expectations_qtd_unpivot` (on
`region × school_level × academic_year × quarter`) and left-joins
`int_powerschool__gradebook_assignment_scores_rollup` for per-assignment rollup
counts. A region with no matching expectations row produces no
`assignment_teacher` rows for that region — this no longer applies to Paterson,
whose expectations are spoofed from Newark's MS data (see the Paterson note
above); it would apply to any future region that never gets the plugin.

The `exclude_from_gpa = 0` filter intentionally excludes teachers who teach only
GPA-excluded courses (~22 teachers per quarter in AY 2025 data). Those sections
do not appear in `rpt_tableau__gradebook_audit`.

### Final extract: `rpt_tableau__gradebook_audit`

Three-branch `UNION ALL`. `is_healthy_gradebook` is computed once, in a
`health_calc` CTE, as a `GROUP BY` aggregate — **not** a window function —
partitioned by
`_dbt_source_project, academic_year, schoolid, teacher_number, quarter`:

```sql
not max(audit_flag_value) as is_healthy_gradebook
```

This unpivots all three audit flags (`qt_percent_grade_greater_100`,
`qt_grade_70_comment_missing`, `expected_assign_count_not_met` — the last added
by a `count_not_met_flag` CTE that fires when
`total_assign_count_qtd_by_cat_section_no_flags < expectation`, i.e. the count
of **valid** (unflagged) assignments falls short of the category's weekly
expectation. Flagged assignments do not count toward the valid total, and a
category with zero assignments entered fires because `0 < expectation`). Because
of the `not`, `is_healthy_gradebook = true` means **no** flag fired for that
teacher that quarter — the opposite of a bare `max()`.

A separate `flags_unpivot` CTE unpivots only the two `student_course` flags
(`qt_percent_grade_greater_100`, `qt_grade_70_comment_missing`) for use in
Branch 3 below; `expected_assign_count_not_met` is emitted there as a literal,
not unpivoted.

- **Branch 1** (`sections_teacher`, `and h.is_healthy_gradebook`) — one
  `audit_flag_name = 'No Flags'` anchor row per section × quarter, for
  teacher/school/quarters where health_calc found **no** flag
- **Branch 2** (`assignment_teacher`, `and s.expected_assign_count_not_met`) —
  one `expected_assign_count_not_met` row per assignment in a short category (or
  a single null-`assignmentid` row for a category where zero assignments were
  entered). The `and not h.is_healthy_gradebook` predicate is omitted as
  redundant: any row with `expected_assign_count_not_met = true` is necessarily
  in an unhealthy partition
- **Branch 3** (`flags_unpivot`, `student_course`) — the two unpivoted
  student-course flag rows, always emitted with `is_healthy_gradebook = false`

---

??? note "AY 2025-2026 data model"

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
    The `src_google_sheets__gradebook_exceptions` source is also disabled
    (`config: enabled: false` in `sources-external.yml`) — Dagster no longer
    pulls the sheet into BigQuery.

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

!!! warning "Deprecated in AY 2026-2027" This model is disabled
(`config: enabled: false`) as of AY 2026-2027.

    **Why it was removed:** the AY 2026-2027 refactor consolidated all
    individual flag signals into a single binary, `is_healthy_gradebook`.
    The audit no longer calculates a per-flag gradebook score or reports
    individual flags to Tableau — it surfaces only whether a teacher's
    gradebook is healthy or not. With no per-flag filtering needed, the
    per-flag allowlist sheet became vestigial.

    The source sheet, staging SQL, and YAML remain in the repository in case
    the per-flag reporting approach is restored in a future year. The INNER
    JOIN to this model was removed from the pipeline in AY 2026-2027, and the
    `audit_category` and `code_type` columns it provided were dropped from
    `rpt_tableau__gradebook_audit`.

    The `src_google_sheets__gradebook_flags` source is also disabled
    (`config: enabled: false` in `sources-external.yml`) as of AY 2026-2027 —
    MS signed off on the same audit model as HS, so the sheet has no remaining
    consumer in any region. Dagster no longer pulls the sheet into BigQuery.
    Re-enable the source before re-enabling the staging model if this is ever
    restored.

Previously, this was the flag allowlist. A flag only appeared in the dashboard
if a matching row existed in this table, making it the primary on/off switch for
every audit check.

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

---

## Start-of-year procedure

As of AY 2026-2027, there is no flags configuration sheet to roll over. The
`stg_google_sheets__gradebook_flags` model is disabled. The three active audit
flags (`qt_percent_grade_greater_100`, `qt_grade_70_comment_missing`,
`expected_assign_count_not_met`) are hardcoded in
`rpt_tableau__gradebook_audit`'s `health_calc` CTE and require no annual
configuration.

### Step 1 — Confirm assignment expectations are updated in PowerSchool

The expectations data that drives `expected_assign_count_not_met` comes from
`int_powerschool__u_expectations_qtd_unpivot`, which reads the `U_EXPECTATIONS`
table populated by the **KIPP NJ Gradebook Audit** PowerSchool plugin. The
`U_EXPECTATIONS` table does not have an `academic_year` field — it reflects the
current state of expectations in PowerSchool. Until the T&L team member
responsible for gradebook expectations updates the table for the new year, the
audit will continue to report against the prior year's expectation values.

Plugin source and update instructions:
[TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins)

### Step 2 — Revert the summer toggle (if applied)

If the summer toggle was applied to
`int_tableau__gradebook_audit_flags_calculations` during the off-season
(switching year filters to `current_academic_year - 1` and grades type to
`'last_year'`), revert both changes before the new school year begins. See the
`gradebook-audit` skill for the exact lines.

---

## Historical: Q1/Q2 removal (May 2026, superseded)

In May 2026, Q1 and Q2 were removed from the (now disabled)
`int_tableau__gradebook_audit_teacher_scaffold` by adding
`t.term not in ('Q1', 'Q2')` to its `term_weeks` CTE. This was not a policy
change — the audit policy for Q1 and Q2 was unchanged — but a volume reduction
to address Tableau Server refresh failures. The AY 2026-2027 quarter-grain
pipeline restored full Q1-Q4 coverage, superseding this workaround.

Tracking issue: [#3908](https://github.com/TEAMSchools/teamster/issues/3908)

---

## Open questions and future work

- **Task 9 — assignment validity filter**: delivered (July 2026). Flagged
  assignments (`assignment_has_flags = true`) do not count toward the QTD valid
  total, and `expected_assign_count_not_met` fires when
  `total_assign_count_qtd_by_cat_section_no_flags < expectation`. Still open
  from the original ask: whether to keep or consolidate the individual
  per-student score flags (plan Step 9.4 — a T&L/Tableau-layout decision). See
  Task 9 in the
  [implementation plan](../superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md).
- ~~**Paterson expectations**~~ — resolved. The KIPP NJ Gradebook Audit plugin
  still cannot be installed on Paterson's PowerSchool instance, so
  `U_EXPECTATIONS` is never populated there natively — but `kipppaterson` now
  ships its own `stg_powerschool__u_expectations` override that reads Newark's
  real MS data cross-project (see the Paterson note above). No remaining code
  gap for the `assignment_teacher` branch.

See [GitHub issue #3908](https://github.com/TEAMSchools/teamster/issues/3908)
for the full AY 2026-2027 tracking issue.
