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

### ~~Anchor-row / "in the clear" redesign~~ (implemented, superseded below)

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

**This three-branch design is being replaced** — see "Teacher/Student Split
(July 2026 revision)" below. The student-course branch (with PII) is being
extracted out entirely, and the section/assignment branches are being redesigned
around always-present boolean columns instead of filtered UNION branches.

## ~~Teacher/Student Split (July 2026 revision)~~ (implemented)

Implemented as designed below, with one deviation and one addition:

- **Deviation:** `category_summary`'s aggregates (`expectation`,
  `assignments_entered_count`, `not_enough_assignments`) are computed via window
  functions (`over (partition by project, sectionid, quarter, category)`) plus
  `dbt_utils.deduplicate()`, not a `GROUP BY` — a 30-column `GROUP BY` over
  every dimension column was flagged in review as unnecessary overhead. Window
  functions preserve the per-assignment row grain that `assignment_detail` also
  needs from the same upstream CTE, so the join runs once and each downstream
  CTE picks its own grain (dedup for the collapsed summary, a plain filter for
  the detail rows) rather than joining twice.
- **Addition:** `rpt_gsheets__gradebook_audit_student_flags` also carries
  `teacher_employee_number` and `is_current_quarter`, added after this spec was
  written to make the sheet easier to filter/action on.
- `int_tableau__gradebook_audit_flags_calculations` was deleted outright
  (confirmed zero remaining consumers), not left disabled — this repo's usual
  "disable, don't delete" convention for deprecated models was set aside here by
  explicit request.

### Why

The three-branch design above mixes two different concerns in one Tableau-facing
table: teacher/section-level gradebook compliance (assignment counts, point
values, missing scores) and student-level grade anomalies (a bad quarter grade,
a missing EOQ comment). Branch 3 carries full student PII (name, student number)
into a Tableau-facing report.

This revision splits those concerns: student-level flag data moves to a new
Google Sheet extract for ops follow-up, and the Tableau-facing report becomes
teacher/section-only, with zero student PII, redesigned around boolean flag
columns instead of filtered UNION branches.

### Goals

- Remove all student PII from `rpt_tableau__gradebook_audit`.
- Move student-level grade/comment flags to a new Google Sheet extract for ops
  review.
- Redesign the teacher-facing report around always-present boolean flag columns
  (not enough assignments, grade above 100 anywhere in the section, grade below
  70 with no comment anywhere in the section) instead of the three-branch
  filtered UNION.
- Surface actual assignment counts entered per gradebook category, regardless of
  flag status, alongside the existing expected counts.
- List individual assignments that fail the "no flags" bar, without exposing
  which specific rule they violated (that level of detail is exactly what this
  redesign is moving away from).
- Redefine "healthy gradebook" as two parallel boolean columns — one counting
  all flags, one excluding the EOQ comment-missing flag — so Tableau can
  parameter-toggle between them without needing two copies of every row.
- Fix a known data gap: student-level rows currently include enrollments for
  sections that `int_extracts__course_schedule_by_term`'s
  `section_quarter_count >= 2` filter excludes (single-quarter/trimester
  sections), so a student can be flagged for a "course" that has no
  corresponding teacher/section presence anywhere else in the pipeline. Fixed by
  scoping student data to only sections that exist in
  `int_extracts__course_schedule_by_term` — no explanatory column, just silent
  exclusion.

### Non-goals

- `rpt_tableau__gradebook_es_comments` (the ES-only EOQ-comment check) is
  unrelated and untouched by this work.
- No per-rule "reason" text is added anywhere (not for flagged assignments, not
  for flagged students) — this redesign's whole point is aggregated boolean
  signals, not granular rule-level detail. `assignment_has_flags` stays a single
  collapsed boolean; the individual rule booleans computed in
  `int_powerschool__gradebook_assignment_scores_rollup`
  (`assign_max_score_not_10`, `assign_score_above_max`, etc.) are not surfaced
  downstream of the rollup.
- No new dbt model beyond the two described below — this replaces a 4-model
  sketch (two intermediates, two reports) with two total models.
- No changes to `int_powerschool__gradebook_assignment_scores_rollup`,
  `int_powerschool__gradebook_assignments_scores`, or the summer-toggle
  mechanism itself (this revision's own toggle points follow the same pattern
  already documented in the gradebook-audit skill).

### Architecture

Two models, replacing `int_tableau__gradebook_audit_flags_calculations` and the
current three-branch `rpt_tableau__gradebook_audit` (no other new files):

```text
int_extracts__course_enrollments_by_term ──┐
int_extracts__course_schedule_by_term ─────┼──► rpt_gsheets__gradebook_audit_student_flags
quarter grade/comment data ─────────────────┘         │
                                                        │ (read for section-level
                                                        │  "any student flagged" booleans)
                                                        ▼
int_extracts__course_schedule_by_term ──┐
int_powerschool__u_expectations_qtd_unpivot ┼──► rpt_tableau__gradebook_audit
int_powerschool__gradebook_assignment_scores_rollup ┘
```

`int_tableau__gradebook_audit_flags_calculations` is disabled once
`rpt_tableau__gradebook_audit` no longer depends on it — matching how this same
pipeline already retired several predecessor models
(`int_tableau__gradebook_audit_teacher_scaffold`, `_assignments_teacher`, etc.)
by folding their logic into successor models.

**Note on layering:** `rpt_tableau__gradebook_audit` reads directly from
`rpt_gsheets__gradebook_audit_student_flags` via `ref()` — an
`rpt_`-depends-on-`rpt_` dependency. This is slightly unusual (the documented
convention is about keeping `int_` models away from external tools, not about
rpt-to-rpt refs specifically) but is the only way to land on exactly two models.
Accepted tradeoff for this design.

### Model 1: `rpt_gsheets__gradebook_audit_student_flags`

**Purpose:** flagged-student rows for ops review via an external Google Sheet.
Also the upstream source `rpt_tableau__gradebook_audit` reads for its
section-level "any student flagged" booleans.

**Grain:** one row per (`_dbt_source_project`, `academic_year`, `studentid`,
`sectionid`, `quarter`) — flagged rows only (see filter below).

**Source logic:**

- Base population: `int_extracts__course_enrollments_by_term`, carrying the same
  filters the current `student_course` branch of
  `int_tableau__gradebook_audit_flags_calculations` applies today (
  `rn_year = 1`, `enroll_status = 0`, `not is_out_of_district`,
  `school_level_alt != 'ES'`, `_dbt_source_project != 'kippmiami'`,
  `exclude_from_gpa = 0`, `quarter_start_date <= current_date`, plus the
  `academic_year` summer-toggle filter).
- **New: inner join to `int_extracts__course_schedule_by_term`** on
  (`_dbt_source_project`, `sectionid`, `quarter`, `academic_year`). This is the
  orphan-scoping fix — a student's course only produces a row here if the
  section also exists in the schedule model. No reason/diagnostic column is
  added; rows that don't match simply don't appear.
- Grade/comment source: the same `quarter_course_grades` union (
  `base_powerschool__final_grades` for the current year,
  `stg_powerschool__storedgrades` for the prior year during the summer toggle)
  already used by the current model.
- Two boolean flag columns, computed once per row (mutually exclusive by
  definition — a grade can't be both above 100 and below 70):
  - `qt_percent_grade_greater_100`
  - `qt_grade_70_comment_missing`
- Final filter: keep only rows where at least one of the two booleans is true.

**Columns:** student identity (`studentid`, `student_number`, `student_name`,
`grade_level`), section/course identity (`sectionid`, `course_number`,
`course_name`, `section_number`, `external_expression`, `section_or_period`),
teacher identity (`teacher_number`, `teacher_name`, `teacher_employee_number`),
school/region (`schoolid`, `school`, `region`, `school_level`), term (`quarter`,
`semester`, `quarter_start_date`, `quarter_end_date`), the raw
`quarter_course_percent_grade` and `quarter_comment_value`, and the two boolean
flags.

**Tests:** `dbt_utils.unique_combination_of_columns` on (`_dbt_source_project`,
`academic_year`, `studentid`, `sectionid`, `quarter`).

### Model 2: `rpt_tableau__gradebook_audit` (reworked)

**Purpose:** teacher/section-facing gradebook compliance report. Zero student
PII.

**Grain:** floor of one row per (`_dbt_source_project`, `academic_year`,
`schoolid`, `teacher_number`, `sectionid`, `quarter`,
`assignment_category_code`) — i.e. exactly four rows per section per quarter
(W/H/F/S categories), present even when nothing is flagged. Each assignment that
fails the "no flags" bar for that category adds one additional row, with
assignment-identity columns (`assignmentid`, `assignment_name`, `duedate`,
`scoretype`, `totalpointvalue`) populated on the detail row and null on the
category-summary row — the same "union of differently-shaped branches, same
column set" pattern the current model already uses for its anchor rows. A
teacher with zero flags anywhere has exactly `(number of sections) × 4` rows for
the quarter; no separate anchor row concept is needed.

A `row_type` column (`'category_summary'` or `'assignment_detail'`)
distinguishes the two shapes explicitly, so Tableau can filter to one or the
other rather than inferring it from `assignmentid` being null. The
count/expectation columns (`expectation`, actual assignment count,
`not_enough_assignments`) are populated **only on `category_summary` rows** and
null on `assignment_detail` rows — these are category-level facts, and repeating
them on every detail row would make a naive `SUM` in Tableau over-count them
once per extra flagged assignment. This is the opposite choice from the
section-level flag/health booleans below, which are deliberately broadcast onto
every row (including detail rows) because those are meant to be readable off any
single row without a self-join.

**Structure (CTEs within the single model):**

1. **Category summary** — from `int_extracts__course_schedule_by_term` joined to
   `int_powerschool__u_expectations_qtd_unpivot` (one row per section × quarter
   × category) left joined to
   `int_powerschool__gradebook_assignment_scores_rollup` aggregated up to
   category grain. Produces, per category row: `expectation` (expected count),
   `assignments_entered_count` (actual count of assignments entered regardless
   of flag status), and `not_enough_assignments` (boolean;
   actual-count-of-non-flagged assignments below expectation — same comparison
   the current `expected_assign_count_not_met` uses, renamed for the
   boolean-column scheme).
2. **Assignment detail** — same join chain, but selecting individual assignment
   rows where `assignment_has_flags` is true, with identity columns populated.
3. **Combined** — `UNION ALL` of (1) and (2), tagging each side with its
   `row_type` (`'category_summary'` or `'assignment_detail'`).
4. **Student flags aggregate** — reads
   `rpt_gsheets__gradebook_audit_student_flags`, grouped to
   (`_dbt_source_project`, `sectionid`, `quarter`) grain, computing
   `has_grade_above_100` and `has_grade_below_70_no_comment` via `count(*) > 0`
   per flag type (no PII carried through — only the booleans and the join keys).
5. **With section flags** — left join (3) to (4) on (`_dbt_source_project`,
   `sectionid`, `quarter`), broadcasting the two student-derived booleans onto
   every row (all 4 category rows, plus any assignment-detail rows) for that
   section/quarter. These two columns are intentionally identical across all
   rows for a given section — they are section-level facts, not category-level
   ones.
6. **Health calc** — aggregates over (5) at (`_dbt_source_project`,
   `academic_year`, `schoolid`, `teacher_number`, `quarter`) grain (across _all_
   of a teacher's sections, not just one), producing two boolean columns:
   - `is_healthy_gradebook_all_flags` — false if any of
     `not_enough_assignments`, `has_grade_above_100`, or
     `has_grade_below_70_no_comment` is true anywhere for that teacher/quarter.
   - `is_healthy_gradebook_excl_comments` — same, but
     `has_grade_below_70_no_comment` is excluded from the check (still present
     as a column on every row, just not counted toward this health definition).
     A Tableau parameter selects which column to read.
7. **Final select** — join (5) to (6) on (`_dbt_source_project`,
   `academic_year`, `schoolid`, `teacher_number`, `quarter`), broadcasting the
   two health columns onto every row for that teacher/quarter.

**Columns:** all existing teacher/section/school identity columns from the
current model (region, school, section, teacher — including
`teacher_employee_number`, `manager_employee_number`, etc.), `row_type`,
category dimension (`assignment_category_code`, `assignment_category_name`,
`assignment_category_term`, `expectation` — nullable, populated on
`category_summary` rows only), assignment-detail columns (nullable, populated on
`assignment_detail` rows only), the three flag booleans
(`not_enough_assignments` — nullable, populated on `category_summary` rows only;
`has_grade_above_100`, `has_grade_below_70_no_comment` — broadcast on every
row), the two health booleans (broadcast on every row), and
`assignments_entered_count` (nullable, populated on `category_summary` rows
only).

**Tests:** `dbt_utils.unique_combination_of_columns` on (`_dbt_source_project`,
`academic_year`, `sectionid`, `quarter`, `assignment_category_code`,
`assignmentid`) — category-summary rows are unique per category with a null
`assignmentid`; assignment-detail rows are unique per real `assignmentid`.

### Validation plan

- Dev build both models; confirm both uniqueness tests pass.
- Confirm the row-count floor empirically: for a teacher with zero flags in a
  quarter, `count(*) = sections × 4` exactly.
- Confirm the orphan-scoping join actually removes the previously-identified
  gap: re-run the `section_quarter_count` orphan check from the PR review (83
  sections / ~800 students in AY2025) against the new model and confirm zero
  remain.
- Spot-check `is_healthy_gradebook_all_flags` vs.
  `is_healthy_gradebook_excl_comments` disagree only on rows/teachers whose sole
  flag is `has_grade_below_70_no_comment`.
- Confirm `rpt_gsheets__gradebook_audit_student_flags` row count matches the
  count of true values across both flags in the pre-filter population (no rows
  lost or duplicated by the filter).

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
