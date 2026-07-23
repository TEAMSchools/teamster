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
stg_powerschool__schools ─┐
stg_powerschool__students ┼─▶ int_finalsite__enrollment_scaffold ─┬─▶ rpt_tableau__fresh_dashboard_progress_to_goals
stg_google_sheets__finalsite__school_scaffold ─┘                  │
                                                                    └─▶ int_finalsite__goals_scaffold ─▶ rpt_tableau__fresh_dashboard_aggregated
                                                                          ▲
stg_google_sheets__finalsite__goals ─────────────────────────────────────┘

stg_finalsite__status_report ─▶ int_finalsite__status_report_unpivot ─┐
                                                                        ├─▶ int_tableau__finalsite_student_scaffold ─▶ both rpt_ models above
stg_google_sheets__finalsite__status_crosswalk ─▶ int_google_sheets__finalsite__status_crosswalk_unpivot ─┘                    ▲
                                                                                                                                  │
int_extracts__student_enrollments (PowerSchool-only, zero Miami rows) ──────────────────────────────────────────────────────────┘

stg_google_sheets__finalsite__status_crosswalk.finalsite_current_academic_year ─▶ (collapsed to one row and cross-joined by every model above needing "the current cycle")
```

The **scaffold** (school × grade spine) and the **goals** (numeric targets) are
two independent inputs that get joined together. The **actuals** (where students
actually are in the recruitment funnel) come from a completely separate
Finalsite pipeline, joined in downstream.

## The scaffold: `int_finalsite__enrollment_scaffold`

This model produces one row per `(academic_year, region, schoolid, grade_level)`
— the spine everything else joins against. It replaced a fully hand-maintained
Google Sheet with a model that prefers PowerSchool-native data and falls back to
the sheet only where PowerSchool doesn't have it.

**Two builders, blended, controlled by one dbt var (`finalsite_scaffold_source`,
`kipptaf/dbt_project.yml`, default `blend`):**

| Value             | Behavior                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `gsheet`          | Sheet builder only.                                                                                                                  |
| `powerschool`     | PowerSchool builder only. Never produces `-1` rows on its own.                                                                       |
| `blend` (default) | PowerSchool builder, plus sheet rows whose `(schoolid, grade_level)` key is absent from it. PowerSchool wins on any overlapping key. |

- **PowerSchool builder** — grade membership comes from actual current
  enrollment (`stg_powerschool__students`, `enroll_status = 0`), joined to
  `stg_powerschool__schools` for school metadata (name, region). **Not**
  `stg_powerschool__schools.low_grade`/`high_grade` — that field encodes a
  school's eventual, fully-built-out grade span, not what it currently serves.
  Verified during design: growing schools (Hatch, Rise, Purpose as of AY2026)
  carry a `low_grade` years below any student they've ever enrolled, so
  expanding that range produced phantom all-null scaffold rows for grades that
  don't exist yet at that school. Tradeoff: a school's very first student in a
  newly-opening grade may not be entered in PowerSchool yet even though
  Finalsite is already recruiting for that grade — this scaffold won't carry
  that grade until PowerSchool has at least one enrolled student in it (no clean
  signal exists for "we're opening this grade but haven't enrolled anyone yet"
  short of a manual sheet entry for that specific transition year).
  `stg_powerschool__schools` is filtered to `state_excludefromreporting = 0`
  first — it includes non-reporting/ administrative rows (e.g. the `999999`
  "Graduated Students" sentinel) that would otherwise produce garbage scaffold
  rows. `current_grade_levels` also filters `grade_level >= 0` — PowerSchool's
  own grade-level domain uses negative values for a different, real meaning
  (pre-registration/pre-K), and must never produce a `grade_level = -1` row
  indistinguishable from the scaffold's own `-1` sentinel (see below).
- **Sheet builder** — `stg_google_sheets__finalsite__school_scaffold`, filtered
  to the current academic year (via
  `stg_google_sheets__finalsite__status_crosswalk.finalsite_current_academic_year`,
  so a stale row from a prior, closed cycle can never look like "PowerSchool
  doesn't have this yet"). Supplies what PowerSchool structurally can't: every
  school's `grade_level = -1` whole-school-total row, and genuinely new
  schools/grades not yet live in PowerSchool.

**Important: `grade_level = -1` means "whole-school total row" in this
scaffold's convention** — a reporting convenience, not a PowerSchool concept.
The PowerSchool builder never synthesizes a `-1` row — it's always
sheet-sourced, by design.

**Miami carve-out (deliberate and temporary):** Miami is excluded from the
PowerSchool builder entirely, unconditionally, regardless of the
`finalsite_scaffold_source` var. Miami's SIS moved to Focus
(`src/dbt/powerschool/CLAUDE.md`, #4441) and no longer consumes the PowerSchool
package — `stg_powerschool__schools`' Miami rows are a frozen pre-migration
snapshot, not a live source of truth. Some actively-recruited Miami schools
(Legacy ES, Legacy MS, MTH as of AY2026) were never onboarded to PowerSchool
post-migration at all — a permanent gap, not a transitional one PowerSchool
coverage will ever close on its own. Miami stays 100% sheet-sourced (a full
spine — every school, every grade, not just `-1` rows and net-new entries) until
Focus is ready as a scaffold source and this is revisited.

Because the PowerSchool builder never emits a `-1` row and never covers Miami,
`blend`'s single rule ("PowerSchool wins on any overlapping key; sheet fills the
rest") naturally and correctly handles `-1` rows, genuinely-new grades/schools,
and all of Miami — no special-casing needed for any of them.

**`school_level` on PowerSchool-sourced rows is derived per expanded
grade_level** (`>=9` HS, `>=5` MS, else ES) — **not** read from
`stg_powerschool__schools.school_level`, which is a single per-school value and
would incorrectly apply one classification to a school spanning two bands (e.g.
Sumner, Camden — base-classified `ES` network-wide in
`stg_powerschool__schools`, with grades 5/6 overridden to `MS` in three _other_
downstream models that need that override). Because this scaffold computes
`school_level` fresh, per grade, it already gets Sumner right (`ES` for grades
0–4, `MS` for grades 5/6) with zero special-casing.

## The current academic year: `finalsite_current_academic_year`

A column on `stg_google_sheets__finalsite__status_crosswalk` itself:
`max(file_year) over ()`, computed once at the staging layer rather than in a
separate model. Every row in the table carries the same value (see below), so a
consumer needing "the current Finalsite cycle" collapses it to one row —
`select distinct finalsite_current_academic_year` — before cross-joining, rather
than hardcoding a year. This intentionally lives on the staging model, not a
`var()` — distinct from `var('current_academic_year')`, which is the
PowerSchool/network year, not the Finalsite cycle year.

Why not derive it from raw Finalsite ingestion instead? Finalsite can carry
**two concurrent academic years of live student data at once** during a
transition period — individual students and regions roll over on their own
uncoordinated timeline, with no standardized cadence. So "which year has the
newest raw data" isn't reliable. `status_crosswalk` holds config for **exactly
one academic year at a time** by convention, guarded by
`test_stg_google_sheets__finalsite__status_crosswalk_single_year` (asserting
`count(distinct file_year) = 1` — exactly one, not "at most one," since an empty
table would otherwise silently null out `finalsite_current_academic_year`, and
every downstream `cross join ... where x = cy.academic_year` comparison against
`NULL` evaluates to unknown, quietly zeroing out the entire pipeline with no
error).

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

## Annual rollover checklist

1. Review/update `stg_google_sheets__finalsite__exclude_ids` for the new cycle's
   Finalsite test/fake records.
2. Add the new cycle's `status_crosswalk` config row(s) — manual, no generator
   (the status→category mapping is institutional judgment, not computable).
3. Add the scaffold sheet's `-1` rows and any genuinely new grade/school rows —
   see the `fresh-dashboard` skill's `-1` candidate-row generator.
4. Add the goals sheet's gap rows for the new cycle — see the skill's
   goals-sheet gap-row generator.

## Open questions

- **Historical / multi-year scaffold reporting is not solved by this model.**
  `stg_powerschool__schools` is current-state only, and the scaffold sheet has
  never carried prior-year rows in practice. Needs a dedicated design discussion
  if this becomes a real requirement.
- **Whether the Miami/Focus carve-out can be removed** depends entirely on
  Focus's readiness as a data source — not yet determined as of this writing
  (2026-07-20).
- **Pinned: the Miami scaffold sheet is missing two real, currently-operating
  schools** -- Liberty Academy (PowerSchool `school_number` 30200802) and
  Sunrise Academy (30200801) -- confirmed against
  `int_people__location_crosswalk`, which has valid `location_focus_school_id`
  values for both. PowerSchool can't backstop this gap either: those two rows
  exist in `stg_powerschool__schools` but with `state_excludefromreporting = 1`
  (excluded), and three OTHER Miami schools (Legacy ES, Legacy MS, MTH) are
  missing from `stg_powerschool__schools` entirely -- confirming PowerSchool's
  Miami data is a stale, incomplete post-Focus-cutover snapshot, not just for
  the scaffold but for any PowerSchool-sourced Miami model (e.g.
  `int_extracts__student_enrollments`). Fixing the sheet gap is intentionally
  deferred until there's clarity on where Miami data should come from now that
  the region is moving to Focus (pending follow-up with Walters and Charlie) --
  in the meantime, blend mode's existing rule (a sheet row always survives
  unless a PowerSchool row already covers that `schoolid`/`grade_level`)
  requires no code change to preserve whatever the sheet currently has.
- **If/when a Focus-based Miami builder is built, it needs an id translation
  step -- Focus school ids are not PowerSchool school numbers.** The scaffold's
  `schoolid` column is `int64`, matching PowerSchool's `school_number` format
  (e.g. `30200803`). Focus's own school ids are alphanumeric strings (e.g.
  `"2332B"`, `"2008A"`) --
  `int_people__location_crosswalk.location_focus_school_id` is `STRING`. Focus's
  native id cannot be cast directly into `schoolid`. The crosswalk already has a
  clean mapping for all 7 real Miami schools between `location_focus_school_id`
  and `location_powerschool_school_id` (the same integer id every other region's
  scaffold already uses), so a Focus builder should translate through that
  crosswalk rather than changing the scaffold's schema -- whatever Focus feed
  eventually lands needs to carry either the Focus school id itself or a
  matching school name to join back to it. Worth raising with whoever scopes the
  Focus extract so this isn't a surprise later.
- **Full field list for "what do we need from Focus to make Miami work on FRESH"
  -- two separate gaps, not one:**
  1. **The scaffold** (`int_finalsite__enrollment_scaffold`'s PowerSchool
     builder) needs a schools-equivalent (id, name/abbreviation, an
     exclude-from-reporting flag if Focus mixes in non-reporting entities) and a
     students-equivalent (schoolid, grade_level, a currently-enrolled status
     flag).
  2. **The point-in-time enrollment flags**
     (`int_tableau__finalsite_student_scaffold`'s `left join` to
     `int_extracts__student_enrollments`, see Known data model caveats above)
     needs `enroll_status` plus `is_enrolled_fdos`/`is_enrolled_oct01`/
     `is_enrolled_oct15`/`is_enrolled_mar15`, joinable back to Finalsite via
     `infosnap_id`.

  Both gaps need the Focus→PowerSchool school-id translation above. Confirm with
  whoever scopes the Focus extract that both are covered -- fixing only the
  scaffold (gap 1) would leave gap 2 (the enrollment flags) silently NULL for
  Miami exactly as it is today.
