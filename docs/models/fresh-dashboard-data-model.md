# FRESH Dashboard Data Model

## What is FRESH?

FRESH is the network's enrollment recruitment dashboard: it tracks progress
against recruitment targets (seats, new students, application/offer/ enrollment
funnel counts) broken out by region, school, and grade. It has two Tableau views
— **Progress to Goals** (`rpt_tableau__fresh_dashboard_progress_to_goals`) and
**Aggregated** (`rpt_tableau__fresh_dashboard_aggregated`) — both built from the
same underlying scaffold and goals data.

## Data model overview

```text
stg_powerschool__schools ─────────────┐
stg_powerschool__students ────────────┤
int_focus__schools ───────────────────┤
int_focus__student_enrollments ───────┼─▶ int_tableau__fresh_enrollment_scaffold ─┬─▶ rpt_tableau__fresh_dashboard_progress_to_goals
stg_google_sheets__people__locations ─┤                                           │
int_finalsite__status_report_unpivot ─┘ (net-new schools/grades only)             │
                                                                                 └─▶ int_tableau__fresh_goals_scaffold ─▶ rpt_tableau__fresh_dashboard_aggregated
                                                                                       ▲
stg_google_sheets__finalsite__goals ──────────────────────────────────────────────────┘

stg_finalsite__status_report ─▶ int_finalsite__status_report_unpivot ─┐
                                                                        ├─▶ int_tableau__finalsite_student_scaffold ─▶ both rpt_ models above
stg_google_sheets__finalsite__status_crosswalk ─▶ int_google_sheets__finalsite__status_crosswalk_unpivot ─┘                    ▲
                                                                                                                                  │
int_extracts__student_enrollments (PowerSchool-only, zero Miami rows) ──────────────────────────────────────────────────────────┤
int_focus__student_enrollments (Miami-only, Focus-sourced) ──────────────────────────────────────────────────────────────────────┘
```

The **scaffold** (school × grade spine) and the **goals** (numeric targets) are
two independent inputs that get joined together. The **actuals** (where students
actually are in the recruitment funnel) come from a completely separate
Finalsite pipeline, joined in downstream.

**Package boundaries**: `stg_finalsite__status_report`'s cleaning (grade decode,
`enrollment_type` default/initcap, `first_name` initcap,
`active_school_year_display`) lives in the `finalsite` source-system package
(`src/dbt/finalsite/models/sftp/staging/`); the kipptaf-level model of the same
name is a thin `union_relations` wrapper over the four district sources plus
`region` / `_dbt_source_project` / the `exclude_ids` filter.
`int_focus__student_enrollments` (plural) is likewise a thin kipptaf wrapper —
adding the Finalsite-ID crosswalk, the locations crosswalk, `region`,
`district`, `region_school_level` — over the `focus` package's
`int_focus__student_enrollment` (singular), which carries the full enrollment
derivation. The three `stg_focus__*` passthroughs this used to depend on
(`school_gradelevels`, `student_enrollment_codes`,
`custom_field_select_options`) no longer exist — their source entries were
removed along with them.

## The scaffold: `int_tableau__fresh_enrollment_scaffold`

This model produces one row per
`(enrollment_academic_year, region, schoolid, grade_level)` — the spine
everything else joins against. The `rpt_tableau__fresh_dashboard_*` views alias
it back to `academic_year` for the Tableau-facing column.

It is now fully SIS-derived. The hand-maintained
`stg_google_sheets__finalsite__school_scaffold` has been retired: every row type
it used to supply is computed here instead.

### How the spine is built

1. **`school_directory`** — one row per reporting school, unioned from the two
   live SIS sources. Non-Miami comes from `stg_powerschool__schools` filtered to
   `state_excludefromreporting = 0` (that table carries non-reporting
   administrative rows like the `999999` "Graduated Students" sentinel). Miami
   comes from `int_focus__schools` filtered to `max_syear is null`, which drops
   closed schools (Sunrise, Liberty) and non-instructional ones (Virtual
   Franchise, ZZ Course History), inner-joined to
   `stg_google_sheets__people__locations` on `focus_school_id` to pick up the
   school abbreviation and the PowerSchool-space `schoolid`. Focus's own
   `school_number` is a Focus code (`2332A`), not a PowerSchool id, so that join
   is what puts Miami in the same id space as everything else.
1. **`current_grade_levels`** — which grades each school actually serves,
   derived from current enrollment rather than a static grade span.
   `stg_powerschool__students` at `enroll_status = 0` for non-Miami;
   `int_focus__student_enrollments` at `enroll_status = 0`,
   `academic_year = current_academic_year` and `rn_year = 1` for Miami. Focus
   carries multiple years, so the year filter is what scopes it to now;
   PowerSchool's table has no year column and is current-state-only.
   `rn_year = 1` takes one enrollment stint per student-year, which is correct
   here because Finalsite and the SIS are expected to agree on a student's
   grade.

   The PowerSchool branch excludes Miami (`_dbt_source_project != 'kippmiami'`)
   because those rows are a frozen pre-migration snapshot and would resurrect
   grades those schools no longer serve — Courage still carries a grade 5 there,
   which it no longer serves. The Focus branch needs no matching exclusion:
   Focus is Miami-only.

   `enroll_status = 0` alone is sufficient to get a clean 0-12 grade range, so
   there is no `grade_level >= 0` filter. Verified against real data:
   `stg_powerschool__students` has zero negative `grade_level` for any
   `enroll_status`, and its only out-of-range value (`99`, a graduated-student
   placeholder) occurs only at `enroll_status = 3`, already excluded.

1. **`sis_scaffold`** — the directory joined to grade membership on
   `(schoolid, _dbt_source_project)`. The source-project half of that key
   matters: each PowerSchool instance assigns `schoolid` independently, so a
   bare numeric join can collide across districts.

Grade membership deliberately does **not** use
`generate_array(low_grade, high_grade)`. The unreliable half is `low_grade`, not
`high_grade`: verified across all 19 reporting non-Miami schools, `high_grade`
equals each school's max enrolled grade **everywhere** — it tracks current
reality rather than an aspirational build-out — but three schools declare a
`low_grade` below what they actually serve (Hatch 3 vs 5, Purpose 4 vs 5, Rise 4
vs 5), so expanding the declared span injects four phantom rows for grades those
schools don't serve. Current enrollment yields the correct ceiling on its own,
so `high_grade` adds nothing, and enrollment is self-maintaining where
`low_grade` is not — nobody updates it when a school's band shifts.

The tradeoff is that a school's very first student in a newly-opening grade may
not be entered in the SIS yet even though Finalsite is already recruiting for
it. That case is covered by the `finalsite_new` branch below, fed by SRE
entering the school/grade in Finalsite — see "Rolling the dashboard over to a
new cycle".

### The three row types the SIS can't produce directly

- **Whole-school totals (`grade_level = -9`)** — derived in `school_priority`,
  one row per school in the spine, with `school_level` NULL because a
  whole-school row spans bands.
- **Region rollups (`schoolid = 0`)** — a `select distinct` over
  `(region, grade_level, school_level)`, with `school` set to the region name.
  This is a safe grain projection only because `school_level` is banded per
  grade (see below); a per-school value would emit more than one row per
  `(region, grade_level)` wherever a region's grade spans schools of different
  levels.
- **Net-new schools/grades** — `finalsite_new`, anti-joined against the SIS
  spine on `(region, schoolid, grade_level)` off
  `int_finalsite__status_report_unpivot`. Region is part of that key because
  PowerSchool assigns `schoolid` independently per district, so a bare numeric
  match could suppress a row by colliding with another region's.

  This CTE is gated by a predicate comparing the two year vars, which renders as
  a constant — `finalsite_recruitment_year != current_academic_year` becomes
  `2026 != 2026` today. BigQuery folds it, so the CTE contributes zero rows at
  no cost; when SRE's recruitment year runs ahead of PowerSchool's it becomes
  `2027 != 2026` and the branch activates on its own.

  The gate **is** the mechanism, not a limitation. Two vars being equal means
  Finalsite and the SIS are on the same cycle, so a Finalsite school/grade
  absent from the SIS is a data-entry error rather than a legitimately-new
  entity; the two diverging means Finalsite is recruiting ahead, which is
  exactly when not-yet-enrolled grades should be trusted. So the way to add a
  new school/grade is to have SRE enter it in Finalsite under the new Finalsite
  year and then roll the year over — see "Rolling the dashboard over to a new
  cycle" below.

  A constant `2026 != 2026` in a `WHERE` clause looks like a mistake; it isn't.
  It replaced a Jinja `{% if %}` deliberately, so the model is plain SQL like
  every other model in the repo rather than a compile-time-branching program.

**`grade_level = -9` means "whole-school total row"** in this scaffold's
convention — a reporting convenience, not a SIS concept. `-1` is reserved for
Pre-K everywhere downstream (PK = `-1`, K = `0`, 1-12 = `1`-`12`).

### `school_level` is banded per grade, and may disagree with the goals sheet

`school_level` is computed from the enrolled grade (`>= 9` HS, `>= 5` MS, else
ES), **not** read from either SIS's own per-school field
(`stg_powerschool__schools.school_level` or the locations sheet's `grade_band`).
Two reasons: it reproduces the retired sheet exactly, and a value determined by
`grade_level` alone is what keeps the region rollup at one row per grade.

A per-school value cannot reproduce the sheet in any case — the sheet's
`school_level` varies _within_ a school (Sumner reports `ES` for grades 0-4 and
`MS` for 5-6, though the school is classified `ES` network-wide), while both
per-school sources are constant down all of a school's rows.

**These bands are NJ bands, and Miami's real ES/MS boundary is 5/6, not 4/5.**
So Royalty and Legacy ES — officially `ES`, serving grades 0-5 — report their
grade-5 rows as `MS` here. That matches the retired sheet, but it does **not**
match `stg_google_sheets__finalsite__goals`, which uses Miami's real boundary
and reports those same rows as `ES`.

That divergence is accepted, not a bug to fix. The goals sheet stays manually
entered because some goals are standard by grade level across the network rather
than by school level, which is why it splits ES/MS the way it does. Consequence
to be aware of when reading the dashboards:
`rpt_tableau__fresh_dashboard_progress_to_goals` takes `school_level` from this
scaffold, while `rpt_tableau__fresh_dashboard_aggregated` takes it from
`int_tableau__fresh_goals_scaffold` (i.e. from the goals sheet) — so for Miami
grade 5 the two views legitimately report different `school_level` values. The
goals sheet is also internally inconsistent on the Miami region-rollup row for
grade 5, carrying both `MS` and `ES`; that one is a sheet data-entry issue worth
cleaning up.

### Miami is now Focus-sourced, not sheet-sourced

Miami's SIS moved to Focus (`src/dbt/powerschool/CLAUDE.md`, #4441) and no
longer consumes the PowerSchool package. Miami is excluded from the PowerSchool
branch of both `school_directory` and `current_grade_levels`, and supplied
entirely from `int_focus__schools` / `int_focus__student_enrollments` instead.
This replaces the previous carve-out, where Miami was 100% sheet-sourced.

One label change came with it: the retired sheet called schoolid `30200805`
`MTH`, while the locations sheet and `int_people__location_crosswalk` both call
it `Miami Tech`. `MTH` existed only in the sheets, so the scaffold now emits
`Miami Tech` — which also aligns it with `int_finalsite__status_report_unpivot`,
the student-level side, which already resolved to `Miami Tech`. No join in the
chain keys on the school name.

## The current academic year: a dedicated var, not `current_academic_year`

"The current Finalsite recruitment cycle" is the `finalsite_recruitment_year`
dbt var (`src/dbt/kipptaf/dbt_project.yml`), read at every FRESH site that needs
it — not a column or joined value, and not the same var as
`current_academic_year`. It's a distinct var because Finalsite can carry **two
concurrent academic years of live student data at once** during a transition
period — individual students and regions roll over on their own uncoordinated
timeline, with no standardized cadence — so there's no reliable signal in the
ingested data for "which year is current now." SRE's own recruitment-cycle
timeline is similarly fluid, with no fixed date (unlike PowerSchool's
`var('current_academic_year')`, which bumps on a predictable July 1 cadence) to
key an automatic bump off of.

See the fresh-dashboard skill's "Procedure: Update the Finalsite recruitment
year" section for the full file list and update steps — always confirm the new
year with SRE before changing it.

`status_crosswalk` still holds config for **exactly one academic year at a
time** by convention, guarded by
`test_stg_google_sheets__finalsite__status_crosswalk_single_year` (asserting
`count(distinct file_year) = 1`) — this guards against the sheet's config ever
drifting out of sync with whatever year `finalsite_recruitment_year` is
currently set to.

## Goal definitions

The `Enrollment` goal_type group is **not** computed via `status_crosswalk` at
all — plain numeric targets entered directly on the goals sheet:

| `goal_name`            | Definition                                                                                                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Seat Target`          | Total seats/capacity the school is targeting for the year.                                                                                                                                                        |
| `FDOS Target`          | Enrollment target as of First Day of School.                                                                                                                                                                      |
| `New Student Target`   | Target count of new (not returning) students to enroll.                                                                                                                                                           |
| `Budget Target`        | The enrollment number the school's budget was built against.                                                                                                                                                      |
| `Re-Enroll Projection` | Projected count of currently-enrolled students expected to persist (return) — "persistence," not "retention"; retention refers to grade repetition in this org's vocabulary and is a distinct, unrelated concept. |

Everything else is a computed roll-up of the Finalsite recruitment funnel via
`status_crosswalk`'s `status_group_value` mapping and `grouped_status_timeframe`
(`Ever` = cumulative, counts a student who ever reached this status even if they
later moved past or reversed; `Current` = point-in-time, latest status only):

| `goal_name` (`goal_type`)                                                           | Timeframe | Definition                                                                                                                      |
| ----------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `Inquiries`                                                                         | Ever      | Family ever submitted an inquiry.                                                                                               |
| `App Target` (`Applications`)                                                       | Ever      | Family ever completed/submitted an application.                                                                                 |
| `Offers Target` (`Offers`)                                                          | Ever      | Student was ever offered a seat.                                                                                                |
| `Accepted`                                                                          | Ever      | Family ever accepted an offered seat.                                                                                           |
| `Waitlisted`                                                                        | Current   | Student's current status is waitlisted.                                                                                         |
| `Deferred`                                                                          | Current   | Student's current status is deferred.                                                                                           |
| `Enrollment In Progress`                                                            | Current   | Student is currently mid-enrollment paperwork/process.                                                                          |
| `Pending Offers` (+ `<= 4 Days` / `>= 5 & <= 10 Days` / `> 10 Days`)                | Current   | Student has an outstanding offer awaiting a family response, bucketed by days pending — an SLA/staleness tracker for follow-up. |
| `Conversion` — `Accepted to Enrolled` / `Offers to Accepted` / `Offers to Enrolled` | Ever      | Funnel conversion-rate metrics between two funnel stages.                                                                       |

### Full `grouped_status` → `goal_type` / `goal_name` crosswalk

`grouped_status` (the crosswalk sheet's `status_group_value`) is the thing
`roster`'s `CASE` logic in `int_tableau__finalsite_student_scaffold.sql`
actually renames -- everything above is the human-readable summary. The table
below is the complete, verified mapping (every distinct `grouped_status` the
crosswalk sheet currently defines, AY2026): only `Applications` → `App Target`
and `Offers` → `Offers Target` (both `Ever`-only) and the three
`Accepted to Enrolled(*)`/`Offers to Accepted(*)`/`Offers to Enrolled(*)` pairs
(→ `Conversion`) get renamed -- every other `grouped_status` passes through
unchanged as both `goal_type` and `goal_name`. `Current`-timeframe `goal_name`
never gets renamed at all (`goal_name` = `grouped_status` verbatim); the
`Applications`/`Offers` rename only applies to `Ever`. `Pending Offers`
(`Current`) additionally splits into `<= 4 Days` / `>= 5 & <= 10 Days` /
`> 10 Days` sub-buckets via `filter_days_in_status`, not reflected in this table
(see the row above).

| Timeframe | `grouped_status` (status_group_value) | `goal_type`                 | `goal_name`                 |
| --------- | ------------------------------------- | --------------------------- | --------------------------- |
| Current   | `Academic Hold`                       | `Academic Hold`             | `Academic Hold`             |
| Current   | `Accepted to Enrolled Num`            | `Conversion`                | `Accepted to Enrolled Num`  |
| Current   | `Campus Transfer Requested`           | `Campus Transfer Requested` | `Campus Transfer Requested` |
| Current   | `Currently Accepted`                  | `Currently Accepted`        | `Currently Accepted`        |
| Current   | `Deferred`                            | `Deferred`                  | `Deferred`                  |
| Current   | `Enrolled`                            | `Enrolled`                  | `Enrolled`                  |
| Current   | `Enrollment In Progress`              | `Enrollment In Progress`    | `Enrollment In Progress`    |
| Current   | `Financial Hold`                      | `Financial Hold`            | `Financial Hold`            |
| Current   | `Mid Year Withdrawal`                 | `Mid Year Withdrawal`       | `Mid Year Withdrawal`       |
| Current   | `Never Attended`                      | `Never Attended`            | `Never Attended`            |
| Current   | `Not Enrolling`                       | `Not Enrolling`             | `Not Enrolling`             |
| Current   | `Offers to Accepted Num`              | `Conversion`                | `Offers to Accepted Num`    |
| Current   | `Offers to Enrolled Num`              | `Conversion`                | `Offers to Enrolled Num`    |
| Current   | `Parent Declined`                     | `Parent Declined`           | `Parent Declined`           |
| Current   | `Pending Offers`                      | `Pending Offers`            | `Pending Offers`            |
| Current   | `Retained Date`                       | `Retained Date`             | `Retained Date`             |
| Current   | `Summer Withdraw`                     | `Summer Withdraw`           | `Summer Withdraw`           |
| Current   | `Waitlisted`                          | `Waitlisted`                | `Waitlisted`                |
| Ever      | `Accepted`                            | `Accepted`                  | `Accepted`                  |
| Ever      | `Accepted to Enrolled`                | `Conversion`                | `Accepted to Enrolled`      |
| Ever      | `Applications`                        | `Applications`              | `App Target`                |
| Ever      | `Inquiries`                           | `Inquiries`                 | `Inquiries`                 |
| Ever      | `Offers`                              | `Offers`                    | `Offers Target`             |
| Ever      | `Offers to Accepted`                  | `Conversion`                | `Offers to Accepted`        |
| Ever      | `Offers to Enrolled`                  | `Conversion`                | `Offers to Enrolled`        |

`int_finalsite__status_report_unpivot.sql` resolves each row's `assigned_school`
to a PowerSchool `schoolid`/`school` abbreviation via
`int_people__location_crosswalk`. `assigned_school` is null for enrollment
stages tracked only at region/grade-level granularity (e.g. `Inquiries`,
`Applications` -- before Finalsite has assigned a school), so those rows fall
back to `schoolid = 0` / `school = 'No School Assigned'`. `schoolid = 0` is the
sentinel the goals join keys on to connect these rows to a Region/Grade Level
goals-sheet row instead of a specific school's goals; `'No School Assigned'` is
the same condition reflected on the `school` label.

For the same reason, `int_tableau__finalsite_student_scaffold.sql`'s
`latest_status_calc` CTE overrides `school` to the row's `region` (instead of
its real `school`) when `status_group_value` is `Inquiries` or `Applications` --
those two funnel stages are only ever tracked at region/grade-level granularity,
so `school` carries the region for them instead of a specific (and structurally
absent, at that funnel stage) school.

`int_tableau__finalsite_student_scaffold.sql` also stamps every row with
`aligned_enrollment_type = 'All'` (a constant, alongside the row's real
`enrollment_type` of `New`/`Returning`).
`rpt_tableau__fresh_dashboard_progress_to_goals.sql` unions the actuals twice
per scaffold row -- once keyed on the real `enrollment_type`, once keyed on
`aligned_enrollment_type` -- so a school/grade's `New` and `Returning` counts
combine into a single `All` bucket, matching the scaffold's own
`cross join unnest(['All', 'New', 'Returning'])` `enrollment_type` dimension.

## Known data model caveats

These are permanent properties of how Finalsite works, not defects — they
explain real, recurring sources of count discrepancy between raw Finalsite
numbers and the dashboard:

- **Concurrent academic years, non-standardized rollover.** Two years of live
  student data can coexist; individual students/regions roll over on their own
  uncoordinated timeline.
- **Status dates are mutable and student-scoped, not year-scoped.** A status
  date is tied to the student record and can be overwritten when someone edits
  the status in the Finalsite UI — not an immutable audit trail.
- **`grouped_status_order` (the 8-stage funnel sequence) is a best-assumption
  ordering.** Real students can skip steps or move backward through
  Inquiries→...→Enrolled.
- **`detailed_status_ranking` (crosswalk sheet) is hand-duplicated into a
  hardcoded `status_order` `CASE` in `int_finalsite__status_report_unpivot.sql`,
  and the two can drift out of sync** (per this repo's convention against
  staging-layer joins to Google Sheets). Guarded by
  `test_int_finalsite__status_order_matches_crosswalk_ranking`, which compares
  the sheet's ranking against a static list mirroring the `CASE`'s declaration
  (not a live query of that model's actual rows — a `fs_status_field` declared
  in the `CASE` but never populated in the data, e.g. `retained_date` as of this
  writing, would otherwise produce a false mismatch, since BigQuery's `UNPIVOT`
  never emits a row for an all-NULL source column). If that `CASE` is ever
  edited, the test's static list needs a matching manual update.
- **Same-day status ties can pick the wrong "latest status," and this is
  permanent and unfixable at the data layer.** The pipeline only compares dates
  (not full timestamps), and the tie-break (`status_order desc`) assumes "higher
  rank wins" — which breaks for an exit status (e.g. `Parent Declined`, rank 15)
  vs. an in-progress one (`Enrollment In Progress`, rank 16) set the same day.
  **The established fix is the "Reset Protocol™":** (1) put the student in
  another status, (2) wait a day, (3) put them in the status you want — waiting
  a day breaks the date-tie so the new status wins outright. To fix: check the
  FRESH Dashboard's Progress-to-Goals tab for students on the dashboard but not
  in `Enrolled` status, using the **OPEN ROSTER** button (top right) to see
  every student's current status. To prevent: avoid giving a student two status
  changes on the same calendar day.
- **Ingestion lag.** `stg_finalsite__status_report` ingests via a
  sensor/file-drop-triggered Couchdrop SFTP asset, not a fixed cron — a status
  cleanup done late in one team member's workday (e.g. a Spain-based team member
  whose day ends mid-US-night) may not show on the dashboard until the next
  day's pull. Unconfirmed whether this specifically applies to Miami.
- **Miami's point-in-time enrollment flags (`enroll_status`, `is_enrolled_fdos`,
  `is_enrolled_oct01`, `is_enrolled_oct15`, `is_enrolled_mar15`) are always
  NULL, on top of and separate from the scaffold's Miami carve-out above.**
  `int_tableau__finalsite_student_scaffold.sql` backfills these 5 fields via a
  `left join` to `int_extracts__student_enrollments`, keyed on
  `(academic_year, infosnap_id)` -- `int_extracts__student_enrollments` is
  PowerSchool-only and carries **zero Miami rows** (verified: `0` of `9,917`
  total rows for AY2026). The `left join` means Miami students still appear on
  the dashboard (this isn't the scaffold gap -- it affects every Miami student,
  not just growing-school edge cases), but every one of them shows NULL for
  these 5 fields. Fixing this needs the same Focus-sourced data as the scaffold
  carve-out, plus this specific field set, joinable by `infosnap_id` -- see the
  Open Questions entry below.
- **All regions' point-in-time enrollment flags go NULL for a while right after
  the Finalsite recruitment year is toggled forward (separate from the
  Miami-specific gap above).** `enrollment_lookup` scopes
  `int_extracts__student_enrollments` to the Finalsite recruitment year rather
  than `var("current_academic_year")` -- these two only match once PowerSchool
  independently rolls over to the new year, which happens later, on its own
  schedule. Until then PowerSchool has no real enrollment rows for that year at
  all, so
  `enroll_status`/`is_enrolled_fdos`/`is_enrolled_oct01`/`is_enrolled_oct15`/`is_enrolled_mar15`
  are NULL for every student, network-wide. Expected, not fixable by the toggle
  -- see the fresh-dashboard skill's year-toggle procedure.
- **Fake/test Finalsite records not yet excluded inflate counts, at any time,
  not just at year rollover.** `stg_google_sheets__finalsite__exclude_ids` is
  enforced upstream of everything FRESH touches, but a test record created today
  isn't excluded until someone adds its id to the sheet.
- **The goals sheet is a live-read Google Sheets external table** — every query
  against `stg_google_sheets__finalsite__goals` reflects whatever is in the
  sheet _at that exact moment_, with no caching. A value can change between two
  queries run seconds apart if someone is actively editing the sheet. A
  dashboard number that doesn't match a materialized dbt table's numbers may
  simply mean the sheet was edited after that table's last build — not a bug.

### How Finalsite's `latest_status` becomes an expected enrollment status

`int_tableau__finalsite_student_scaffold` carries two enrollment-status columns
that are easy to mix up, because the naming runs opposite to intuition:

| column             | where it comes from                                                                                                        |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `enroll_status`    | the **SIS** — PowerSchool via `int_extracts__student_enrollments`, or Focus via `int_focus__student_enrollments` for Miami |
| `ps_enroll_status` | **Finalsite**, derived from `latest_status` — despite the `ps_` prefix, nothing about it is read from PowerSchool          |

`ps_enroll_status` is the status the SIS _ought_ to show if Finalsite is right,
mapped from the student's `latest_status`:

| `latest_status`                                            | `ps_enroll_status` | meaning                       |
| ---------------------------------------------------------- | ------------------ | ----------------------------- |
| `Enrolled`                                                 | `0`                | should be active in the SIS   |
| `Mid Year Withdrawal`, `Never Attended`, `Summer Withdraw` | `1`                | should be inactive in the SIS |
| anything else                                              | `NULL`             | no expectation                |

The `NULL` case is deliberate and covers most of the funnel — an applicant who
is Waitlisted or Enrollment In Progress has no business having an SIS enrollment
record yet, so there is nothing to compare and no mismatch can fire.

`is_active_inactive_mismatch` then fires when the expectation and the SIS
disagree in either direction:

- Finalsite says enrolled (`ps_enroll_status = 0`) but the SIS says withdrawn or
  graduated (`enroll_status in (2, 3)`)
- Finalsite says withdrawn (`ps_enroll_status = 1`) but the SIS says currently
  enrolled (`enroll_status = 0`)

Note the asymmetry: the enrolled-side check accepts SIS `2` (withdrawn) and `3`
(graduated) as contradicting, while the withdrawn-side check only treats SIS `0`
as contradicting. `enroll_status = 1` (inactive) and `-1` (pre-registered) never
trigger a mismatch on either side.

## Rolling the dashboard over to a new cycle

There is no fixed date for this. SRE's recruitment cycle advances on its own
timeline, so the rollover starts when SRE says it has — not on a calendar
trigger, and not when PowerSchool's `current_academic_year` bumps on July 1.

The order matters. `finalsite_recruitment_year` is the switch that repoints the
whole pipeline at the new cycle, and several models `inner join` against sheets
scoped to that year. Flipping the var before those sheets carry the new year's
rows does not error — it silently returns zero rows.

### Steps, in order

| #   | Step                                                              | Owner           |
| --- | ----------------------------------------------------------------- | --------------- |
| 1   | Enter any new schools/grades in Finalsite under the new FS year   | SRE             |
| 2   | Agree which Finalsite enrollment year is now active               | SRE + data team |
| 3   | Update `status_crosswalk`'s partition key and confirm its columns | Analyst + SRE   |
| 4   | Supply the new goals workbook URL                                 | SRE             |
| 5   | Reconcile the goals sheet against SRE's workbook                  | Data team + SRE |
| 6   | Review `exclude_ids` for the new cycle's test records             | Analyst         |
| 7   | Bump `finalsite_recruitment_year` in `dbt_project.yml`            | Data team       |
| 8   | Build and verify the FRESH models                                 | Data team       |

#### 1-2. New schools and grades come from Finalsite

There is nothing to hand-enter into a scaffold sheet. A school or grade that is
being recruited for but has nobody enrolled yet is entered **in Finalsite** by
SRE under the new Finalsite academic year. Once that data is in Finalsite and
SRE and the data team have agreed which Finalsite enrollment year is active, the
year bump brings those rows in through `finalsite_new` — see "The three row
types the SIS can't produce directly" above.

This is why the Finalsite year is a separate var from `current_academic_year`:
the two being different is the signal that Finalsite is recruiting ahead of the
SIS, and that signal is what activates the net-new branch. Agreeing on the
active year (step 2) is therefore the real gate on the whole rollover, not a
formality.

#### 3. `status_crosswalk`

Two things, both on the sheet itself rather than in code:

- **Replace the `_dagster_partition_key` value (column A)** so it matches the
  new Finalsite enrollment year. This is a replace, not an append — the sheet
  holds exactly one year at a time, guarded by
  `test_stg_google_sheets__finalsite__status_crosswalk_single_year`.
- **Confirm with SRE that columns D, H, and I→P still make sense** for the new
  cycle. See the column reference below for what each one drives. These encode
  institutional judgment about the recruitment funnel, so there is no generator
  and no way to derive them.

Getting this wrong is the loudest failure mode in the rollover:
`latest_status_calc` inner-joins the crosswalk on the year, so a partition key
that doesn't match the active year drops every status and the dashboard goes
empty.

#### 4-5. Goals

SRE supplies a **new workbook each cycle**, so the first move is asking for the
URL rather than assuming last cycle's. Then:

- Confirm the **goal names are unchanged**. The goals sheet joins on
  `goal_name`, so a renamed goal silently stops matching.
- Reconcile SRE's workbook against `stg_google_sheets__finalsite__goals` and
  hand the analyst the missing rows to paste in.
- Repeat until there are no discrepancies. The goals sheet is a live read, so
  each round of pasting is immediately visible to the next comparison.

**Run this reconciliation whenever goals change, not only at rollover.** SRE
does not always flag mid-year goal changes, so it is worth offering proactively
at the start of any FRESH work. See the `fresh-dashboard` skill for the
procedure.

#### 7. The var bump

One line in one file. Every model and test site reads
`var("finalsite_recruitment_year")`, so there are no other literals to chase.

### `status_crosswalk` column reference

The staging model is `select *`, so sheet column letters map straight to
columns. The four groups SRE should re-confirm each cycle are marked.

| col     | column                                                                                                                                              | what it drives                                                                                                                                                                                                                                               |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A       | `_dagster_partition_key`                                                                                                                            | the cycle year. Replaced at rollover; `file_year` is derived from it                                                                                                                                                                                         |
| B       | `enrollment_type`                                                                                                                                   | New vs Returning                                                                                                                                                                                                                                             |
| C       | `detailed_status`                                                                                                                                   | the Finalsite status name being mapped                                                                                                                                                                                                                       |
| **D**   | `detailed_status_ranking`                                                                                                                           | **confirm with SRE.** Orders statuses when a student has several. Hand-mirrored by the `status_order` CASE in `int_finalsite__status_report_unpivot` — change one, change both; `test_int_finalsite__status_order_matches_crosswalk_ranking` guards the pair |
| E       | `detailed_status_branched_ranking`                                                                                                                  | currently unused — declared and passed through, read by nothing                                                                                                                                                                                              |
| F       | `valid_detailed_status`                                                                                                                             | `false` silently drops the row. Encodes "is this status legitimate for this `enrollment_type`"                                                                                                                                                               |
| G       | `fs_status_field`                                                                                                                                   | the Finalsite date column the status came from                                                                                                                                                                                                               |
| **H**   | `qa_flag`                                                                                                                                           | **confirm with SRE.** `true` silently drops the row                                                                                                                                                                                                          |
| **I-P** | `status_enrollment`, `status_group_numerator`, `status_group_denominator`, `conversion_metric_numerator_1..3`, `conversion_metric_denominator_1..2` | **confirm with SRE.** The goal-group mapping. Unpivoted into `status_group_name` / `status_group_value`, which is how a raw status becomes a `goal_type` / `goal_name` on the dashboard                                                                      |
| Q       | `file_year`                                                                                                                                         | derived in the staging model from column A; not in the sheet                                                                                                                                                                                                 |

### What no longer needs doing

The scaffold sheet is retired, so the old steps for it are gone: nobody hand-
enters `-9` whole-school rows, region rollup rows, or per-grade rows any more,
and the `-9` candidate-row generator is obsolete.
`int_tableau__fresh_enrollment_scaffold` derives all of it from PowerSchool and
Focus, picks up new schools and grades once the SIS has an enrolled student in
them, and picks up not-yet-enrolled ones from Finalsite per steps 1-2 above.

### After the bump

Expect `enrollment_lookup`'s PowerSchool-vs-Finalsite quality-check columns
(`enroll_status`, `is_enrolled_*`) in `int_tableau__finalsite_student_scaffold`
to be null network-wide for a while. That CTE scopes
`int_extracts__student_enrollments` to the Finalsite recruitment year, and
PowerSchool has no enrollment rows for a year it hasn't rolled into yet. This is
expected, resolves on its own once PowerSchool catches up, and needs no action.

## Open questions

- **`stg_finalsite__status_report.active_school_year` could give the blend a
  finer per-record rollover signal.** Format is `YYYY-YYYY` (e.g. `2026-2027`)
  -- it's the school year a given student's Finalsite record is currently active
  under, and it's genuinely mixed at any moment (verified: as of this writing
  27,511 rows sit on `2026-2027`, 1,492 are still on the prior `2025-2026`, and
  a handful are already on `2027-2028`/`2028-2029`). Comparing this per-record
  value against `finalsite_recruitment_year` could give the scaffold a
  per-student or per-school rollover signal, instead of relying solely on the
  single network-wide current-year anchor. Not yet designed or implemented -- an
  idea to explore, not a decision.
- **Historical / multi-year scaffold reporting is not solved by this model.**
  Both SIS sources are scoped to the current cycle -- PowerSchool's
  `stg_powerschool__students` is current-state only, and the Focus branch
  filters to `current_academic_year` -- so the scaffold carries one cycle at a
  time. Needs a dedicated design discussion if this becomes a real requirement.
- **`detailed_status_branched_ranking` (column E of `status_crosswalk`) has no
  consumer.** It is declared in the staging and unpivot properties and passes
  through, but nothing reads it. Either something was intended to and never
  landed, or it should come out of the sheet and both ymls.

### Resolved (kept for reference, no longer open)

Four questions in earlier versions of this doc are now answered by the
SIS-derived scaffold:

- **Whether the Miami/Focus carve-out can be removed** -- done. Miami is sourced
  from `int_focus__schools` and `int_focus__student_enrollments`; no part of the
  scaffold reads the sheet for Miami.
- **The Miami scaffold sheet missing Liberty (30200802) and Sunrise (30200801)**
  -- moot. The sheet is retired, and both schools are closed (`max_syear = 2025`
  in Focus), so they are excluded deliberately rather than missing accidentally.
- **Focus school ids need translating to PowerSchool school numbers** -- built.
  `school_directory` joins `int_focus__schools` to
  `stg_google_sheets__people__locations` on `focus_school_id` and takes
  `powerschool_school_id`, so Focus's alphanumeric codes (`2332A`) never reach
  the `schoolid` column.
- **What Focus needs to supply for Miami to work on FRESH** -- both gaps are
  closed. The scaffold's schools/grade-membership gap is covered by the two
  `int_focus__*` models above, and the point-in-time enrollment flags
  (`enroll_status`, `is_enrolled_*`) are covered by
  `int_tableau__finalsite_student_scaffold` reading
  `int_focus__student_enrollments` alongside
  `int_extracts__student_enrollments`.
