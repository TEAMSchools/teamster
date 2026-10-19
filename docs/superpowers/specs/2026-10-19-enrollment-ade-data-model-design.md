# Enrollment and ADE data model (Ops Dashboard enrollment rebuild)

Refs #6003.

## Intent

Finance does not trust the enrollment and average daily enrollment (ADE) numbers
on the Ops Dashboard, and they make budget decisions with them. Enrollment
drives school funding, so even a small miscount affects budgets. A regional
leader's first data request is "ADE in my hand."

The current numbers are untrustworthy for structural reasons, not one bug:

- All ADE math lives in Tableau calculated fields that branch on hard-coded
  region names. Paterson has no branch, so its ADE is blank. Miami's branch
  averages two fields that `rpt_tableau__ops_dashboard` hard-codes to `null`, so
  its ADE is blank too.
- Rounding is a formula someone typed into one calc: Newark rounds each student
  to the nearest tenth, Camden does not, and nothing records why.
- The workbook still carries a `Current Academic Year` calc of 2025, a 186-day
  parameter, two hard-coded Miami school ids, and legacy region codes (`TEAM`,
  `KCNA`).
- The model is one row per student-year, so any number below that grain (a date,
  a subgroup, a district of residence) has to be rebuilt in Tableau.

This design moves every enrollment and ADE number into dbt, built from the
student information system (SIS): PowerSchool for Newark, Camden and Paterson,
and Focus for Miami. Tableau only filters and displays.

The source request is finance's intake of 2026-10-16. Finance reviews the
proposal line by line on Monday 2026-10-26.

## Goals

- One definition of each number, computed once in dbt: enrolled, ADE so far,
  projected ADE, full-year ADE, and Miami's survey counts.
- Any school day can be the as-of date, with Today, Oct 15, Mar 15 and All year
  as presets, and month-over-month trends without student-day data in Tableau.
- Any number can be filtered by any mix of region, school, grade,
  self-contained, special education status or classification, English learner,
  lunch status, out-of-district placement, and New Jersey district of residence
  (every district code, for billing).
- Each region's rounding rule is data in a sheet, labeled on screen with whether
  finance has confirmed it.
- Targets compare correctly at grade, school, region and network level.
- Staff with roster access can click a count and see the students in it.
- The SIS can be reconciled against FRESH (Finalsite) as of today, with every
  student in the gap given 1 reason.
- From launch on, a monthly snapshot records what the dashboard said.

## Non-goals

- ADE for an individual student. ADE is only ever shown as a total for a group.
- Any change to the FRESH models, and any snapshot of FRESH or Finalsite data.
- Comparing the SIS with FRESH for a past date (see _Decisions to stamp with
  stakeholders_).
- Rebuilding the other Ops Dashboard views (Attrition x2, SPED, Student
  Demographics, Recent Enrollment Changes). They keep reading
  `rpt_tableau__ops_dashboard`.
- Miami Surveys 1, 4 and 5, and the Focus survey export. The vendor is still
  building that export, so v1 reads the existing state-file survey data, and the
  survey model must allow a later swap to Focus (section 6).
- Historical snapshots before launch.
- The Tableau workbook. This spec and its plan cover the dbt models and tests.
  The workbook gets its own plan once the models land, so the _Consumers_
  section below records intent, not build scope.

## Anti-goals

The work fails, even if every model builds, if any of these happen:

- A region's enrolled count disagrees with a live SIS search for the same date
  by more than refresh lag.
- A student drops out of a total without being counted somewhere visible: no
  residence code, a pending status, a zero-length stint, or a school with no
  target.
- A goal is compared against a subgroup's numbers, such as IEP students only,
  which makes every school look short.
- A student name or school-facing id reaches a finance-facing view.
- The dashboard becomes one more side source that disagrees with the SIS.

## Constraints

- Repo layering rules apply (`.claude/rules/dbt-architecture.md`): exposures
  read `rpt_` or marts, `rpt_` reads marts, and 1 model owns each grain (A4).
- No dbt seeds. Every hand-kept lookup is a Google Sheet behind a
  `stg_google_sheets__*` model.
- `fct_student_attendance_enrollment_daily` rebuilds on a cron at 06:00 and
  15:00 America/New_York. Anything built on it can be no fresher.
- Tableau relationships, which the targets design relies on, need Tableau Server
  2020.2 or later. The server version is not yet checked.
- PII handling follows `.claude/rules/ferpa-pii.md`. The roster is the only
  model with names or school-facing ids, and it is tagged.

## Decisions to stamp with stakeholders

These go back to finance and regional leaders in writing at the 10/26 review, so
nobody later reads a limit as a defect.

- The SIS is the source of truth for every enrollment and ADE number. Finalsite
  and FRESH appear only in the reconciliation view.
- The SIS-to-FRESH comparison is as of today only. Finalsite keeps only each
  student's current status, and staff can edit status dates, so the comparison
  cannot be rebuilt for a past date such as Oct 15. We will not attempt an
  approximation.
- We will not change the FRESH models or add FRESH snapshots unless a
  stakeholder pushes back hard.
- Snapshots of enrollment and ADE start on launch day. Past years remain
  available as trends, but they are rebuilt from today's corrected SIS records,
  so they can look steadier than the live numbers looked at the time.
- ADE is never shown for an individual student.
- Goal colors apply only to rows that cover all students. When a student-group
  filter is on, goal comparisons turn off.
- Each region's rounding rule is shown on screen with its status, confirmed or
  pending.

## Definitions

Every number comes from `fct_student_attendance_enrollment_daily` (one row per
student per calendar day inside an enrollment stint, all 4 regions, stints
clamped to the school year) and the school calendar in `dim_school_calendars`.

| Term                  | Definition                                                                                                                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| School day            | A date where `dim_school_calendars.is_in_session` is true for that location.                                                                                                                                                                           |
| Enrolled on date D    | The student has a stint covering D. Point-in-time counts use stint dates, never `enroll_status`.                                                                                                                                                       |
| Membership days to D  | Per stint: the sum of `membership_value` over school days through D, whether or not attendance was taken. A half day (0.5) counts as half; none exist in AY2025 or AY2026.                                                                             |
| ADE so far at D       | Per student and school: membership days to D ÷ school days to D at that school. Summed to any group.                                                                                                                                                   |
| Projected ADE at D    | Per student and school: (membership days to D, plus the school days left after D if enrolled on D) ÷ school days in the year. Assumes no one enrolls or leaves.                                                                                        |
| Full-year ADE         | Projected ADE at the school's last school day.                                                                                                                                                                                                         |
| All year              | Distinct students with any stint in the year. Not a date and not additive (a student who changes schools counts once at region level), so it has its own table (section 2b).                                                                           |
| Out-of-district (OOD) | A special education out-of-district placement: a year-long PowerSchool designation for a student referred to an outside placement. KIPP pays for some of these students and the district pays for others. Not the same as living outside the district. |
| Survey 2, Survey 3    | Miami's state FTE survey counts (October and February), as distinct students.                                                                                                                                                                          |
| Funded average        | (Survey 2 + Survey 3) ÷ 2 at every level. A student on only 1 survey counts as half. Never the "present on Survey 2" accountability rule.                                                                                                              |

`n_membership_days_ytd` on the fact is not the ADE numerator: it counts only
days with recorded attendance, which undercounts Paterson, whose attendance
values are unreliable while membership is clean.

Verified 2026-10-19: on 2026-10-16 the fact's count of students enrolled matched
the count of `enroll_status = 0` students whose stint covered that date in all 4
regions (Newark 6,550, Camden 2,182, Miami 1,498, Paterson 832). Pre-registered
and no-show stints do not inflate the stint-date count this year. Newark's 6,550
is within 2 of the live PowerSchool search taken in the 10/16 meeting.

Rounding (my call, pending finance): a rounding rule rounds each student's
projected or full-year value. It never rounds a part-year value such as ADE so
far, because every student enrolled since the first day shares the same fraction
of the year, so their rounding errors all point the same way and a region total
can swing by hundreds. Finance confirms where rounding applies (_Open
questions_, item 1).

## Design

```text
fct_student_attendance_enrollment_daily (+ 1 column) ─┐
dim_school_calendars ─────────────────────────────────┤
dim_student_enrollments ──────────────────────────────┤
dim_student_enrollment_status (+ 3 columns) ──────────┼─▶ totals rpt ─▶ monthly snapshot
stg_google_sheets__finance__ade_rules (new) ──────────┘
marts above ──────────────────────────────────────────────▶ all-year counts rpt
finance targets sheet (restructured) ─────────────────────▶ targets rpt
marts above + student identity ───────────────────────────▶ roster rpt (PII, row-level security)
survey data (state files now, Focus export later) ────────▶ Miami surveys rpt
Finalsite status (current SIS year) + SIS ────────────────▶ reconciliation rpt (today only)
```

Model names below are proposals. Rename to repo conventions as needed.

### 1. Mart additions

- `fct_student_attendance_enrollment_daily` gains a running count of membership
  days per stint (`membership_value = 1` on school days, attendance not
  required). A4 rules out a second student-day model, so the column goes on the
  existing fact.
- `dim_student_enrollment_status` (1 row per stint) gains `is_self_contained`,
  `is_out_of_district` and the district of residence code. Today these exist
  only on `int_extracts__student_enrollments`. Grep `src/cube/model/` before
  adding columns to either mart.

### 2. Totals table (`rpt_tableau__enrollment_ade_daily`)

The table Tableau reads for every number. No student rows.

- Grain: academic year × as-of date × school × grade × self-contained × special
  education code × English learner × lunch status × out-of-district × district
  of residence code. As-of dates are each school's school days.
- Status columns use each stint's status as `dim_student_enrollment_status`
  defines it (for example, New Jersey meal status is as of Oct 15 and Miami's is
  the latest). This is close to today's dashboard. The default is pending
  finance (_Open questions_, item 2).
- A `target_self_contained` key normalizes self-contained for target matching:
  it equals `is_self_contained` where the region's rule is `broken_out` and is
  false where it is `rolled_in`. Miami's `is_self_contained` is null on every
  row (no source exists), so it is treated as false. Point-in-time status would
  swap in the dated history marts (`dim_student_iep_status`,
  `dim_student_ell_status`, `dim_student_meal_eligibility_status`) here and in
  the roster.
- A missing district of residence becomes an explicit `Unknown` value, never a
  dropped row. Miami has no residence codes.
- Out-of-district students (my call, pending finance, _Open questions_ item 11):
  they stay in the totals as their own rows (`is_out_of_district` true), with
  counts and ADE, so finance can see what those placements cost. They carry no
  target, and goal comparisons count only students who are not out-of-district.
  This replaces the old dashboard's fake target of 1 per student. Verify which
  school the daily fact assigns an out-of-district stint to: the old dashboard
  grouped these students under `reporting_schoolid`, which is the placement
  program id for New Jersey and a disability placement code for Miami.
- Measures, all additive across rows:
  - students enrolled on the date
  - ADE so far
  - projected ADE, unrounded and rounded per student to the nearest tenth
  - official projected ADE: the variant the rules sheet names for the region
  - membership days to date
- Measured size: 2,090 combinations per date for AY2026 at full detail; about
  380,000 rows per year at about 180 school days. Keep the current year plus 4
  prior years (the trends page compares past years).
- An as-of date on a weekend or holiday resolves to each school's latest school
  day on or before it. For a closed year, Today means each school's own last
  school day. Never use a network-wide maximum date: calendars end on different
  days.

### 2b. All year counts (`rpt_tableau__enrollment_all_year`)

My call, so finance can see the All year preset without roster access:
distinct-student counts precomputed at 4 levels (school and grade, school,
region, network) with the totals table's status and residence columns. No
student rows. A level column tells Tableau which rows to show, since these
counts cannot be summed across levels. A test checks that each region's count is
no more than the sum of its schools' counts.

### 3. Rules sheet (`stg_google_sheets__finance__ade_rules`)

A new Google Sheet tab, 1 row per region per academic year, edited by the data
team after finance decides:

| Column                    | Values                                                                                                                                                                                                          |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rounding_rule`           | `none` or `nearest_tenth`                                                                                                                                                                                       |
| `rounding_status`         | `confirmed` or `pending`                                                                                                                                                                                        |
| `status_as_of_rule`       | `latest` for now (item 2)                                                                                                                                                                                       |
| `self_contained_handling` | `broken_out` (own rows and own targets: Camden, Newark) or `rolled_in` (counted against the school's regular targets: Miami, and Paterson, which has no self-contained students). Neither value drops students. |
| `notes`                   | free text shown in the dashboard's definitions                                                                                                                                                                  |

A test fails if any region in the totals table lacks a rule row for its year.

### 4. Targets (`rpt_tableau__enrollment_targets`)

- Grain: academic year × school × grade × self-contained, with seat target
  (`target_enrollment` today) and target ADE (`financial_model_enrollment`
  today). Self-contained targets come by campus, ideally by campus and grade.
- Source: the finance targets sheet behind
  `stg_google_sheets__finance__enrollment_targets`, restructured to add
  Paterson, new schools and grades, and self-contained rows. Laz and Charlie
  decide the structure (school ids or a new column). The data team generates the
  scaffold rows and finance fills in the values.
- Retire the synthetic target of 1 per self-contained or out-of-district student
  that `rpt_tableau__ops_dashboard` adds for Newark and Miami.
- In Tableau, the targets table is related to the totals table, not joined, on
  year, school, grade and self-contained. Relationships add each table up at its
  own grain, so school and network targets sum correctly. A join would repeat
  each target on every totals row and multiply it.
- Goal comparisons show only when a row covers all students. A Tableau calc
  compares the filtered total with an unfiltered fixed-level total and turns the
  comparison off when they differ. Prototype this before promising it.

### 5. Roster (`rpt_tableau__enrollment_roster`)

- Grain: student × stint × academic year. Columns: name, `student_number`,
  school, grade, entry and exit dates, and the same status and residence columns
  as the totals table. Tag PII per `.claude/rules/ferpa-pii.md`.
- Row-level security follows the existing pattern: a Tableau username column for
  the staff allowed to see each row, as in `rpt_tableau__student_course_grades`.
  Finance users get no rows.
- Serves click-through. A test checks that, for sample dates, the roster's count
  of students enrolled matches the totals table.

### 6. Miami surveys (`rpt_tableau__miami_fte_surveys`)

- Grain: academic year × school × grade × survey (2 and 3).
- Source now: the existing survey data in dbt, which comes from the state survey
  files (PDFs dropped in a Drive folder, landing in kippmiami `stg_fldoe__fte`;
  AY2021 to AY2025 today). Survey counts are distinct students per survey.
- Source later: a special Focus export that the vendor is building. It is not in
  hand and has no date. When it arrives, it replaces the state-file source.
- One interface model sits between the source and the `rpt_`: 1 row per student
  per year per survey, with school, grade and FTE. Swapping the state files for
  the Focus export changes only that model's upstream, never the `rpt_` or the
  dashboard.
- kipptaf reads the surveys today through `int_fldoe__fte_pivot`, which keeps
  only student, year and FTE per survey (joined to students on state student
  number) and drops school and grade. A student can sit at different schools for
  Survey 2 and Survey 3, so the interface model reads `stg_fldoe__fte` through a
  new kipptaf source and union passthrough instead of reshaping the pivot. That
  model carries student names, so tag PII on the passthrough.
- Count each survey at the school and grade the state file gives. Before a
  survey's file lands, that survey shows no number. Finance watches enrolled
  headcount from Focus in the totals table until then.
- Do not use `int_students__fldoe_fte` for funding counts: it keeps only
  students present at least once (`attendancevalue = 1`), the accountability
  rule finance rejected.
- `fte_capped` tops out at 0.5 per survey, so summing FTE across both surveys
  already equals the funded average. Never average FTE values, or the number is
  halved twice.

### 7. FRESH reconciliation (`rpt_tableau__enrollment_fresh_reconciliation`)

As of today only. Counts by region, school and reason. No student rows leave the
data team.

- SIS side: students enrolled today, from the daily fact.
- Finalsite side: the current SIS year's records in
  `stg_finalsite__status_report` (partitioned by school year, overwritten by
  each file), with each student's latest status picked the way FRESH picks it
  (`int_finalsite__status_report_unpivot` plus the `status_order` tie-break) and
  FRESH's enrolled rule (latest status `Enrolled` or `Enrollment In Progress`,
  with a school assigned).
- Layering rules keep an `rpt_` from reading staging or source intermediates, so
  a new intermediate holds each student's current-year latest Finalsite status.
  It is a new model; no FRESH model changes.
- Do not read the FRESH `rpt_` models or
  `int_tableau__finalsite_student_scaffold`: they follow
  `finalsite_recruitment_year`, which moves to next year's recruiting before the
  SIS year ends.
- Matching: NJ through `infosnap_id` on `int_extracts__student_enrollments`;
  Miami through `int_finalsite__contact_id_attributes`.
- Each student found on only 1 side gets exactly 1 reason, in this priority
  order:
  1. No Finalsite record, or IDs not linked
  2. Finalsite shows withdrawn or pending; SIS shows enrolled
  3. Finalsite counts the student; no SIS record
  4. No school assigned in Finalsite
  5. Different school (moves between schools; nets to 0 at region)
  6. Different grade (moves between grades; nets to 0 at school)
  7. SIS changed after the latest Finalsite file
  8. Unexplained
- Show gross and net: students only in the SIS, only in Finalsite, and the
  difference. A test checks that the signed reasons sum exactly to SIS minus
  FRESH.
- Thresholds on gross unexplained students per region (about 20 to warn, about
  100 to error, values pending finance) run as dbt tests, so they surface as
  Dagster asset checks. Test the table, not a view, so the checks rerun on new
  data.
- Drift guard: while `current_academic_year` equals
  `finalsite_recruitment_year`, a test compares this model's Finalsite-side
  count per region with FRESH's Progress to Goals count.

### 8. Monthly snapshot

- Append the totals table's rows for the snapshot date on the 1st of each month,
  on Oct 15, on Mar 15, and on each school's last school day. Start at launch.
- Keyed by snapshot date. The Trends page compares "then" (snapshot) with "now"
  (today's recomputed value for that date).
- There is no launch date until the 10/26 review. The snapshot ships with
  whatever launches as v1; its first row is the first snapshot date after
  launch.
- Enrollment and ADE only. No FRESH or Finalsite data.

### 9. Freshness and cadence

- Every page shows when the data last updated, from the totals table's build
  time.
- Build the totals, roster, surveys and reconciliation tables on the daily
  fact's cron tick (06:00 and 15:00 America/New_York). The current Ops Dashboard
  refreshes hourly. Finance confirms twice daily is enough (item 9).

### 10. Consumers

- A new Tableau workbook, Enrollment & ADE, with pages Overview, Schools &
  grades, Reconciliation, Trends and Definitions, each with an exposure in
  `models/exposures/tableau.yml`. A mockup exists on claude.ai (ask Anthony).
- In the old Ops Dashboard workbook, the `Enrollment Dashboard` and
  `Enrollment (Sch/Gr)` views become a single page that links to the new
  workbook and explains the change, then are removed after a set period.
- At launch, a one-time note per region explains how the new numbers differ from
  the old ones: Paterson and Miami ADE now filled in, which rounding applies,
  and which definition of enrolled.
- Cube is not a v1 consumer. Keeping the ADE inputs on the mart leaves that door
  open.

## Phase 0 (before 10/26)

Read-only queries, not models, using the definitions above: enrolled today and
projected ADE by region, a Newark SIS-to-FRESH gap broken into the reasons in
section 7, Miami's enrolled headcount (plus Survey 2 if the state file has
landed), and a past-year check of finance's 2 rules of thumb. Delivered as a
dated one-page brief labeled approximate.

Finance's rules of thumb, from the intake:

- Headcount: about 2% lower from the current count to the end of the year.
- ADE: about 1% lower from the Oct 15 count to the end of the year.

Inputs to collect:

- Laz's draft ADE query (not in the repo). Ask Laz for it; acceptance check 4
  compares against it.
- The PowerSchool enrollment flag that dropped 16 Paterson students in 2025-26
  is not yet identified. Finding it is part of Phase 0 (acceptance check 5).

## Acceptance checks

1. Newark enrolled today matches a PowerSchool all-district active search for
   the same day, within refresh lag.
2. Each region's enrolled count equals distinct students active in the daily
   fact on that date.
3. Roster counts match totals counts for sample dates.
4. Projected ADE by region matches Laz's draft query, with every difference
   explained (rounding, the Paterson enrollment flag).
5. The 16 Paterson students that a PowerSchool enrollment flag dropped in
   2025-26 are counted, or the flag's effect is shown and explained. The same
   check runs for 2026-27.
6. Miami state survey counts by school sum to the state file totals for every
   year on file.
7. Reconciliation reasons sum exactly to SIS minus FRESH, and the Finalsite-side
   count matches FRESH while the year settings match.
8. Every school and grade in the totals table has a target row or an explicit
   "no target" state, and targets sum to the sheet's totals.
9. Every region and year has a rules row.
10. Only the roster carries names or school-facing ids.

## Open questions

Finance and stakeholders, for the 10/26 review:

1. Rounding: confirm Newark's nearest tenth, set Paterson's and Miami's, and
   confirm that rounding applies to each student's projected or full-year value.
2. Status timing: should a student's IEP, English learner or lunch status for
   ADE be their latest status, their status on each day, or their status on a
   fixed date such as Oct 15?
3. Residence moves: when a student moves districts mid-year, does each district
   pay for its own days, or the latest district for all of them?
4. Variance thresholds for the FRESH gap, as a count, a percent, or both, and at
   school or region level.
5. Miami funded average: is it counted in students or in state FTE units? A few
   students carry less than full FTE.
6. Does any district bill for a period, such as a month or quarter, rather than
   year to date? If so, period ADE comes from membership days, which the totals
   table already stores.
7. Is the Camden ADE+ weighted-funding calc in the old workbook still used? Its
   ratios live on the targets sheet.
8. What does the NOL column mean?
9. Is twice-daily refresh enough, against today's hourly?
10. Which demographic fields do other teams need (Nadja: IEP and free/reduced
    lunch percentages)?

11. Out-of-district students: should they count toward a school's enrollment and
    ADE against its targets, or stay on their own rows with no target (the
    default in section 2), or get their own budget target like self-contained?
    The 10/16 meeting defined the term but did not decide this.

Data team:

1. Targets sheet structure for self-contained rows (Laz and Charlie).
2. Tableau Server version: 2020.2 or later for relationships. If older, compute
   school and network target totals in dbt instead.

## Left to the builder

- Final model names and folders, within repo conventions.
- How the click-through tells the roster which student group was clicked (IEP,
  English learner, free/reduced). Prototype a Tableau action first. Fallback: a
  small companion table at school × grade × date × student group.
- The roster's entitlement source for row-level security.
- Snapshot mechanism (an incremental append on a cron, or a dbt snapshot).
- How the as-of date presets resolve to school days in Tableau.
- Materializations and automation conditions, matching the daily fact's cron.
- Whether to validate district of residence codes against the state's district
  code list, kept as a sheet. The current data has 89 New Jersey enrollment
  records with no code and 42 codes with only 1 or 2 students.
