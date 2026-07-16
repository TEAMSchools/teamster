# Gradebook Audit AY 2026-2027 Design

## Background

The gradebook audit Tableau dashboard helps school leaders and instructional
coaches audit teacher gradebooks for compliance with KIPP TAF grading policy. It
is powered by `rpt_tableau__gradebook_audit` and covers the current academic
year only.

**AY 2026-2027 moves the audit from week-grain to quarter-grain.** The current
model generates one row per section × week × category. The new model generates
one row per section × quarter × category. This eliminates the `term_weeks` CTE
and the `int_powerschool__calendar_week` dependency from the teacher scaffold,
restores Q1 and Q2 coverage (previously removed as a Tableau volume workaround),
and enables EOQ flags to fire year-round without a date-window gate.

Full pipeline reference:
[`docs/reference/gradebook-audit-data-model.md`](../reference/gradebook-audit-data-model.md)

## Current coverage (AY 2025-2026)

| Region   | School level | Coverage                                    |
| -------- | ------------ | ------------------------------------------- |
| Camden   | MS, HS       | Full audit                                  |
| Camden   | ES           | EOQ comments only (`qt_es_comment_missing`) |
| Newark   | MS, HS       | Full audit                                  |
| Newark   | ES           | EOQ comments only (`qt_es_comment_missing`) |
| Miami    | ES, MS       | Full audit — **removing AY 2026-2027**      |
| Paterson | n/a          | Not on dashboard — **adding AY 2026-2027**  |

## AY 2026-2027 changes

### Quarter-grain scaffold refactor

The teacher scaffold (`int_tableau__gradebook_audit_teacher_scaffold`) is
redesigned from week-grain to quarter-grain. This is the foundational change
that all other scaffold and flag changes build on.

**What changes in the scaffold:**

- `term_weeks` CTE eliminated — the week time spine
  (`int_powerschool__calendar_week`) is removed entirely.
- `school_level_mod` CTE eliminated — its logic (Sumner G5 override,
  `region_school_level`, `section_or_period`) folds directly into the `sections`
  CTE.
- `final` CTE eliminated — becomes the main SELECT (a two-branch UNION ALL of
  `teacher_scaffold` and `teacher_category_scaffold` rows from `sections`).
- `is_quarter_end_date_range` removed — EOQ flags now fire year-round (T&L
  approved). See "EOQ flags year-round" below.
- `quarter_end_date_insession` removed — no longer needed at quarter grain;
  `quarter_end_date` from `int_powerschool__terms` is used directly.
- `is_current_week` removed — replaced by `is_current_term` from
  `int_powerschool__terms`.
- Week columns removed: `week_start_date`, `week_end_date`, `week_start_monday`,
  `week_end_sunday`, `school_week_start_date_lead`, `week_number_academic_year`,
  `week_number_quarter`.
- Q1 and Q2 restored — the `term not in ('Q1', 'Q2')` filter is removed. All
  four quarters are now covered.

**New `sections` CTE joins** (replaces all prior CTEs):

| Source                             | Fields brought in                                                                                           |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `base_powerschool__sections`       | All section/course/teacher fields; `school_abbreviation as school`, `school_level` (see prerequisite below) |
| `int_powerschool__terms`           | `quarter`, `semester`, `quarter_start_date`, `quarter_end_date`, `is_current_term`                          |
| `int_people__staff_roster`         | `teacher_tableau_username`, `manager_employee_number`, `manager_name`, `manager_tableau_username`           |
| `int_people__leadership_crosswalk` | `hos`, `school_leader`, `school_leader_tableau_username`                                                    |

**Derived inline in `sections`:**

- `region` — `initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))`
  (same pattern as `int_powerschool__calendar_week`)
- `region_school_level` —
  `concat(region, coalesce(school_level_alt, school_level))`
- `school_level` — `coalesce(school_level_alt, school_level)` (applies Sumner G5
  → MS override)
- `academic_year_display` — computed once here, not duplicated downstream
- `section_or_period` — HS uses `external_expression`; others use
  `section_number`

**Prerequisite: `base_powerschool__sections` updates**

`school_abbreviation` and `school_level` must be added to
`base_powerschool__sections` (`src/dbt/powerschool/models/sis/base/`) before the
scaffold refactor. The model already joins `stg_powerschool__schools` — add
`sch.abbreviation as school_abbreviation` and `sch.school_level`. The scaffold
selects these as `school_abbreviation as school` and `school_level`
respectively. The output column name `school` is preserved for Tableau backward
compatibility.

**New columns added to scaffold output:**

- `manager_employee_number` — ADP employee number of the teacher's direct
  manager
- `manager_name` — formatted name (Last, First) of the manager
- `manager_tableau_username` — SAM account name of the manager

### EOQ flags year-round

`is_quarter_end_date_range` is removed from the scaffold and from all flag
conditions. EOQ flags (`qt_grade_70_comment_missing`, `qt_es_comment_missing`,
etc.) now fire whenever the condition is true, regardless of calendar date
within the quarter. T&L approved this change. The dashboard will show EOQ flag
status for all quarters at all times.

### Restore Q1 and Q2 coverage

The `term not in ('Q1', 'Q2')` filter is removed as a natural consequence of the
quarter-grain refactor. Q1 and Q2 were excluded as a Tableau volume workaround
(not a policy change). Full-year coverage is restored.

### Replace Google Sheet expectations with PS-native model

`stg_google_sheets__gradebook_expectations_assignments` is deprecated and
replaced by a PS-native intermediate model (`int_powerschool__u_expectations` or
`int_powerschool__u_expectations_unpivot` if the model unpivots internally).

The new model sources from `stg_powerschool__u_expectations` (the U_EXPECTATIONS
PowerSchool plugin) joined to `int_powerschool__calendar_week` for region. It
provides the expected assignment count per category per quarter for the current
region/school_level. Plugin source and deployment scripts live at
[TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins).

**Naming convention:** if the model unpivots `cnt_w/h/f/s` to long format
internally, it must be named `int_powerschool__u_expectations_unpivot` per
Charlie's convention.

**Coverage at launch:** Newark only. Camden is blocked on PR #4077 (Bini's
integration work). Paterson is blocked on PS instance access — deploy the plugin
from [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins) once
access is available. Until each region has PS data, category-level audit rows
will be silent for that region.

The deprecated Google Sheet model is **disabled** (`config: enabled: false`),
not deleted, pending operational decisions after July 1, 2026.

### QTD cumulative assignment count

`w/h/f/s_expected_assign_count_not_met` changes from a weekly per-category check
to a quarter-to-date cumulative check: "as of today, has the teacher posted the
total expected assignments for this category through the current date this
quarter?"

The QTD expectations come from the PS-native model described above.

**Blocked on PR #4077** — the intermediate model that provides QTD expectations
must land in prod before this task can be executed.

### Remove Miami

Miami ES and MS are migrating to Focus gradebook. All Miami rows are removed
from `stg_google_sheets__gradebook_flags`. All Miami-specific SQL branches
(conduct code flags, `qt_comment_missing`,
`qt_effort/formative/summative_grade_missing`, `s_max_score_greater_100`,
`qt_teacher_s_total_greater/less_100`) are removed as dead code.

### Add Paterson

Paterson joins the dashboard for AY 2026-2027.

**Paterson MS:** same flags and expectations as Newark MS. Delivered:
`kipppaterson`'s own `stg_powerschool__u_expectations` model (overriding the
disabled `powerschool` package version) reads Newark's real U_EXPECTATIONS data
cross-project via a `source()` on `kippnewark_powerschool`, filtered to
`school_level = 'MS'` — Paterson's PS instance still can't run the plugin
natively.

**Paterson ES:** `qt_es_comment_missing` only (Q3 and Q4). Same pattern as
Camden ES and Newark ES.

**Paterson HS:** no HS schools in Paterson.

**Paterson in `rpt_tableau__gradebook_gpa`:** the `region != 'Paterson'` filter
in the `student_roster` CTE of that model is removed so Paterson students appear
in the GPA view.

**Flag rows for the sheet:** moot — the flags sheet
(`stg_google_sheets__gradebook_flags`) and its source were disabled during
implementation; the three active flags are hardcoded in
`rpt_tableau__gradebook_audit` and no sheet rollover exists anymore (see the
[Start-of-year procedure](../reference/gradebook-audit-data-model.md) in the
reference doc).

### Remove FYI flags

Three flags are excluded from the Tableau health score via a calculated field
but still generate rows in the extract. Remove them from SQL and config:

- `w_grade_inflation`
- `assign_s_hs_score_not_conversion_chart_options`
- `assign_s_ms_score_not_conversion_chart_options`

(`qt_teacher_s_total_less_200` is also FYI but handled under Summative 200
removal. `qt_student_is_ada_80_plus_gpa_less_2` is split into two new booleans —
see below.)

### Remove Summative 200 point-value flags

`qt_teacher_s_total_greater_200` and `qt_teacher_s_total_less_200` are removed
from `int_tableau__gradebook_audit_categories_teacher` and all downstream
models.

**Reason:** the makeup work policy means teachers legitimately exceed or fall
short of the 200-point target without it indicating a compliance problem. These
flags produce false positives and are not actionable.

The Miami 100-pt variants (`qt_teacher_s_total_greater_100`,
`qt_teacher_s_total_less_100`) are removed as part of the Miami dead-code
cleanup.

### Migrate `qt_student_is_ada_80_plus_gpa_less_2`

This flag is being removed from the gradebook audit and split into two new
booleans for use in other dashboards:

**`int_extracts__student_enrollments`** — new boolean
`is_ada_above_or_at_80_cum_gpa_less_2`: student's ADA is at or above 80% AND
`cumulative_y1_gpa < 2.0`. Student-level grain, available to any dashboard.

**`rpt_tableau__gradebook_gpa`** — new boolean
`is_ada_above_or_at_80_gpa_y1_less_2`: same ADA condition AND `gpa_y1 < 2.0`
(year-to-date per-course GPA grain). Added directly to the GPA view.

**Open question for T&L:** should the threshold be strictly below 2.0 (`< 2.0`)
or below-or-equal (`<= 2.0`)? Current code uses `< 2.0`. See issue #3908
comment.

### Drop `grade_level` from `stg_google_sheets__gradebook_flags`

`grade_level` was only populated for Miami conduct code flags (KG vs G1-G8
distinction). With Miami removed and those CTEs deleted, the column is
permanently unused. The staging model is updated to
`SELECT * EXCEPT (grade_level)` and the column is removed from its properties
YAML.

### Remove the exceptions mechanism

`stg_google_sheets__gradebook_exceptions` and all 15+ LEFT JOINs to it across
five intermediate models are removed. The model is **disabled**
(`config: enabled: false`) rather than deleted, pending operational decisions
after July 1, 2026.

### ~~7-day grace period for percent-graded flags~~ (dropped as policy)

**Dropped (July 2026).** T&L officially dropped the grace period as policy — it
will not be implemented. The AY 2026-2027 pipeline shipped without one:
`is_expected` in `int_powerschool__gradebook_assignments_scores` has no due-date
condition (its code comment points here). An assignment counts as expected the
moment it is due.

The original design, kept for history: `percent_graded_min_not_met` should only
fire for assignments that have been due for at least 7 days. At quarter grain
this becomes a per-assignment check: for each assignment where
`current_date >= duedate + 7`, check whether the teacher has scored it for the
required percentage of students.

**Grain decision (resolved):** `percent_graded_min_not_met` shipped at
per-assignment grain in `int_powerschool__gradebook_assignment_scores_rollup`
(threshold 0.90), as one input to `assignment_has_flags` — without the grace
condition.

## Out of scope for this implementation

### ~~Anchor-row / "in the clear" redesign~~ (implemented)

Originally deferred, this was implemented as a three-branch UNION in
`rpt_tableau__gradebook_audit`:

- **Branch 1** (`sections_teacher`, `and h.is_healthy_gradebook`): one
  `audit_flag_name = 'No Flags'` anchor row per section × quarter for teachers
  where **no** flag fired
- **Branch 2** (`assignment_teacher`, `and s.expected_assign_count_not_met`):
  one `expected_assign_count_not_met` row per assignment in a short category (or
  a single null-`assignmentid` row when zero assignments were entered). A
  `not h.is_healthy_gradebook` predicate would be redundant — any row with the
  count flag true is necessarily in an unhealthy partition — and was dropped
- **Branch 3** (`student_course`, `flags_unpivot`): the two unpivoted
  student-course flag rows

`is_healthy_gradebook` is a `health_calc` `GROUP BY` aggregate (not a window
function), partitioned by teacher × school × quarter:
`not max(audit_flag_value)` — so `true` means **no** flag fired that quarter,
the inverse of a bare `max()`.

## Open questions

**For T&L:**

- **ADA + GPA flag threshold** — current code fires when GPA is strictly below
  2.0. Should students with exactly 2.0 also be flagged? Applies to both the
  cumulative version (`int_extracts`) and the per-course version
  (`rpt_tableau__gradebook_gpa`). See issue #3908 comment.

**For implementation:**

- ~~**Percent-graded flag grain**~~ — resolved: shipped at per-assignment grain
  (`percent_graded_min_not_met` in
  `int_powerschool__gradebook_assignment_scores_rollup`, threshold 0.90, one
  input to `assignment_has_flags`), without the 7-day grace condition (dropped
  as policy — see the grace-period section above).
