# Gradebook grades/GPA Tableau rebuild — design

- **Issue**: [#4340](https://github.com/TEAMSchools/teamster/issues/4340)
- **Date**: 2026-07-07
- **Status**: approved design, pending implementation plan
- **Mock rows**: reviewed during the design session (Claude artifact, fabricated
  students) — the column groups and NULL semantics below match that mock.

## Goal

Replace the GPA/grades side of the gradebook Tableau reporting family with two
new views purpose-built for the from-scratch dashboard rebuild, fully decoupled
from the gradebook-audit/fidelity lineage: no assignment-level data, no audit
flags, no comment or citizenship columns.

## Non-goals

- The audit family (`rpt_tableau__gradebook_audit`,
  `rpt_tableau__assignment_checks`, both comments models) — owned by the AY26-27
  audit revamp ([#4132](https://github.com/TEAMSchools/teamster/pull/4132)).
- Dropping the four existing GPA-family models — they retire with the old
  dashboard, in a later cleanup.
- Marts/Cube surfacing of these measures.

## Architecture

Two new views in `models/extracts/tableau/` (view materialization and
`contract: enforced` inherited from the directory config):

| Model                                | Grain                                      | Window                        |
| ------------------------------------ | ------------------------------------------ | ----------------------------- |
| `rpt_tableau__student_course_grades` | student x term x course section x category | current + prior academic year |
| `rpt_tableau__gpa_cumulative_year`   | student x academic year                    | all years                     |

Tableau consumption: **one data source**. The main extract is flat (no related
tables — LOD/window-calc limitations and alias fragility ruled them out); the
companion is the single low-risk relationship, related on `student_number`,
giving year-over-year cumulative GPA without forcing year grain into the main
view.

## Main view: `rpt_tableau__student_course_grades`

### Spine

- Roster: `int_extracts__student_enrollments` (`rn_year = 1`, not
  out-of-district, `enroll_status != -1`), current + prior academic year.
- Terms: `int_powerschool__terms` quarters plus a Y1 row per year (same pattern
  as today's `rpt_tableau__gradebook_gpa`).
- Course enrollments: `base_powerschool__course_enrollments` with the existing
  lunch/logistics course-number exclusions, left-joined so no-course students
  keep their roster rows.

**Planned migration**: once #4132 merges, re-platform this spine onto
`int_extracts__course_enrollments_by_term` (extended from current-year-only to
the 2-year window). Open a follow-up issue when #4132 lands; do not block on it
now.

### Grades, split by year

| Source                             | Populates                                                          | Years        |
| ---------------------------------- | ------------------------------------------------------------------ | ------------ |
| `base_powerschool__final_grades`   | quarter grades, in-progress Y1, `need_60/70/80/90`                 | current only |
| `stg_powerschool__storedgrades`    | prior-year Q1-Q4 term grades and Y1 finals (credits, grade points) | prior year   |
| `int_powerschool__category_grades` | category rows, both years (history verified present)               | both         |
| `int_powerschool__gpa_term`        | term GPA block                                                     | both         |

Categories stay **long** (rows per category). Prior-year rows carry NULL for
in-progress and `need_*` columns by construction.

### Student-grain, as-of-today column groups

Populated on current-year rows only; NULL on prior-year rows:

- **Cumulative + needed-GPA** (join `int_powerschool__gpa_cumulative` directly
  in the rpt — do not widen `int_extracts__student_enrollments`; an optional
  later promotion is noted in #4340): `cumulative_y1_gpa` family,
  `core_cumulative_y1_gpa`, `potential_gpa_credits_cum_projected`,
  `potential_gpa_credits_current_year`, `gpa_needed_for_cumulative_3_0`,
  `is_cumulative_3_0_attainable`.
- **GPA lookback** (join `int_powerschool__gpa_term_lookback` on `studentid`,
  `schoolid`, district relation): `gpa_y1`, `gpa_y1_unweighted`, `n_failing_y1`,
  each at 1/2/4 weeks prior (9 columns). Also NULL early in the year when a
  boundary predates the year's first snapshot version. The lookback model's
  withdrawn-student caveat (check-strategy snapshots return last-known values)
  is handled by the roster join's enrollment scope — no extra filtering.

### Demographics block

Same set as today's `rpt_tableau__gradebook_gpa` roster block, all sourced from
`int_extracts__student_enrollments`: `enroll_status`, `cohort`,
`graduation_year`, `ktc_cohort`, `salesforce_id`, `gender`, `ethnicity`,
`advisory`, `year_in_school`, `year_in_network`, `rn_undergrad`,
`is_out_of_district`, `is_pathways`, `is_retained_year`, `is_retained_ever`,
`lunch_status`, `gifted_and_talented`, `iep_status`, `lep_status`, `is_504`,
`is_counseling_services`, `is_student_athlete`, `ada`, `ada_above_or_at_80`,
`hos`, `school_leader`, `school_leader_tableau_username` — **plus**
`student_slideback` (today only on the cumulative model). Course-level:
`teacher_tableau_username` (RLS), `date_enrolled`, `tutoring_nj`,
`nj_student_tier`.

### Dropped relative to today's model

`quarter_citizenship`, `quarter_comment_value` (fidelity/report-card content —
audit family's job), `roster_type` (single-value constant), and every
audit/assignment reference.

### Population

All school levels. Regions: Newark, Camden, and Paterson. **Miami is
hard-excluded from both views** — the region is not supported in the rebuilt
dashboard next year (aligned with #4132, which also excludes Miami from the
audit pipeline). Paterson inclusion is gated on an implementation-time check
that Paterson gradebook data (`base_powerschool__final_grades`,
`int_powerschool__category_grades`, `int_powerschool__gpa_term`) is populated —
if not, ship excluded with a `TODO` naming the gap.

## Companion view: `rpt_tableau__gpa_cumulative_year`

- Source: `int_powerschool__gpa_cumulative_year` (merged in #4338) joined to
  `int_extracts__student_enrollments` for that year's attributes — demographics
  are **as-of-that-year** (grade 9 row shows grade 9's school, advisory, ADA),
  which is what trajectory vizzes need.
- Grain: **one row per student x academic year**. The union model's grain
  includes `schoolid`; dedupe to the year's primary enrollment (the roster's
  `rn_year = 1` row and matching `schoolid`). Validate multi-school and
  cross-district year frequency during implementation.
- Measures: `earned_credits_cum`, `potential_gpa_credits_cum`,
  `cumulative_y1_gpa`, `cumulative_y1_gpa_unweighted`, `is_projected` (the
  current-year row is the projected row and ties out to the main view's
  `cumulative_y1_gpa_projected` columns exactly).
- Population: **Miami hard-excluded**, matching the main view.

## Tests

Both models (rpt-layer requirements: contract enforced + uniqueness):

- Main view: `dbt_utils.unique_combination_of_columns` over
  (`_dbt_source_relation`, `studentid`, `academic_year`, `quarter`, `sectionid`,
  `category_name_code`). NULL `sectionid` (no-course students) and NULL category
  (Y1 rows) group as equal values — verify no collisions in validation.
- Companion: `dbt_utils.unique_combination_of_columns` over (`student_number`,
  `academic_year`).
- Properties yml with full column descriptions for both.

## Validation plan

1. Row-count and measure parity against the old models for the current year:
   term/category grades and GPA columns from the new main view reconcile with
   `rpt_tableau__gradebook_gpa`; companion current-year rows reconcile with
   `rpt_tableau__gradebook_gpa_cumulative` and with
   `int_powerschool__gpa_cumulative_year` district counts (Newark 48,555 /
   Camden 13,281 as of 2026-07-07; Miami's 6,218 rows are excluded by the Miami
   hard-exclude).
2. Extract-size decision point: 2-year window projected at ~1.8M rows (current
   year ~900k with categories). **Fallback approved in design**: report the
   actual row count at validation and let the owner decide between keeping 2
   years, dropping prior-year category rows (course-grain prior year, ~1.2M), or
   current-year-only.
3. Lookback NULL semantics: prior-year rows NULL; early-year boundaries NULL.
4. Paterson population check (see Population above).
5. Companion-to-main tie-out: projected row values match
   `cumulative_y1_gpa_projected` / `_unweighted` verbatim.

## Dependencies and sequencing

1. **Hard dependency: PR #4316** (`int_powerschool__gpa_term_lookback`) must
   merge first — the lookback columns come from that model. It is user-owned and
   mergeable now.
2. **Not a dependency: PR #4132.** Its only interaction is the future spine
   switchover (see Spine above), explicitly deferred to a follow-up issue.
3. New Tableau exposure entries in `models/exposures/tableau.yml` land with the
   dashboard rebuild once the workbook LSID exists.
