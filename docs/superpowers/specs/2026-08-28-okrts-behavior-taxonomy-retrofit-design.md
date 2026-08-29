# OKRTS behavior taxonomy retrofit: carrying two culture systems in one model

Refs [#5062](https://github.com/TEAMSchools/teamster/issues/5062). Adjacent:
[#4747](https://github.com/TEAMSchools/teamster/issues/4747),
[#4858](https://github.com/TEAMSchools/teamster/issues/4858),
[#5063](https://github.com/TEAMSchools/teamster/issues/5063).

Revised after two adversarial reviews. Every claim below was verified against
production or source; the "Corrections from review" section at the end records
what the first draft got wrong.

## Problem

The new culture policy renamed and added behavior categories in Newark, Camden,
and Paterson. `rpt_tableau__okrts_behavior` gates on a hardcoded list of 11
category names. No new name is on that list, so the OKRTS Dashboard shows no
corrective behaviors for AY2026.

Measured against `kipptaf_deanslist.stg_deanslist__behavior` for
`behavior_date >= '2026-08-01'`, New Jersey only:

| Outcome                                | Rows                           |
| -------------------------------------- | ------------------------------ |
| Passes the allowlist                   | 758,025 (all `BEAT`, `Values`) |
| Dropped                                | 151,429                        |
| Reaches `category_type = 'Corrective'` | 0                              |

`Corrective Behaviors` no longer exists in New Jersey. Three categories took its
place and none of them map.

The constraint that shapes this design: **filtering the dashboard back to AY2025
must still render every view.** The model keeps two academic years, so it has to
carry both taxonomies at once rather than swap one for the other.

## What the dashboard actually depends on

23 of 74 worksheets touch the taxonomy, through two derived columns.

`category_type` is today 2-valued: `BEAT` and `Corrective`. Every
worksheet-level filter on it pins to `"BEAT"`. `Corrective` reaches the workbook
only through 3 calculated fields on `LP - Tree Data - BEAT Points`, all written
`[category_type] = 'Corrective'`.

`referral_tier` drives the referral worksheets and still resolves under the new
policy — the `Tier 1 -`, `Tier 2 -`, `Tier 3 -` prefixes predate the change — so
this spec leaves it alone.

Every `behavior` filter is `level-members`, meaning show-all, so new behavior
names flow through with no workbook edit.

**There are two data-source-scoped filters.** The workbook's `shared-views`
block applies `Exclude Paterson (TEMP)` to the `okrts_referrals` data source and
`Exclude Paterson [TEMP]` to `okrts_behavior`, each a group defined
`function='except'` over `[region]`. The dashboard owner added them last year
when Paterson data was broken and removes them at the republish this work
depends on. Until then Paterson is invisible on every tab regardless of what the
warehouse holds.

## Design

### `category_type` is derived once, then filtered

The current model carries two independent literal lists — a `where ... in (...)`
allowlist and a `case` — with no guard between them. A category that passes the
allowlist but matches no `case` branch lands in the extract with
`category_type = NULL`: invisible to every workbook filter, yet still fanning
out the spine columns. Growing both lists to 15 names and trusting a human to
keep them in sync recreates exactly the coupling that produced this bug.

Instead: derive `category_type` in one CTE, then
`where category_type is not null`. The allowlist stops existing as a second
list, and the drift becomes structurally impossible.

| Category                                    | `category_type`        | Era            |
| ------------------------------------------- | ---------------------- | -------------- |
| `Corrective Behaviors`                      | `Corrective`           | NJ, ≤AY2025    |
| `Tier 1 - Corrective Behaviors`             | `Corrective`           | NJ, AY2026+    |
| `Tier 1 - Habits of Excellence Corrections` | `Habits of Excellence` | NJ, AY2026+    |
| `Values`                                    | `BEAT`                 | NJ, both       |
| `Values (5)`                                | `BEAT`                 | NJ, AY2026+    |
| `Values (10 Point Bonus)`                   | `BEAT`                 | NJ, AY2024+    |
| `Written Reminders`, `Big Reminders`        | `Corrective`           | Miami, ≤AY2025 |
| Miami's 7 parenthetical value categories    | `BEAT`                 | Miami, ≤AY2025 |

The Miami and New Jersey category names are disjoint — verified in production —
so the branches need no region guard. Dropping the guard is what closes the NULL
hole: today a Miami row reading `Values` matches no branch and survives as NULL.

### `category_type` gains a third value

`Habits of Excellence` becomes a peer of `BEAT` and `Corrective`, not a fold
into `Corrective`. Only 8 of 19 schools log it and it is middle- and high-school
only, so blending it would inflate the corrective rate at exactly the schools
that adopted it — and `# Corrective Behaviors per Student per Day` is a
landing-page headline.

The 3 existing corrective calculated fields stay corrective-only. Any Habits of
Excellence measure is added alongside them.

### The raw category is exposed

A new `behavior_category` column carries the DeansList category verbatim, so the
workbook can separate the 3 `Values` families. This is what makes admitting the
bonus categories safe.

`behavior_category` is already selected and grouped in the
`behavior_aggregation` CTE — it is simply not projected — so adding it changes
no grain.

### The bonus categories come in, kept separable

`Values (5)` and `Values (10 Point Bonus)` have never been on the allowlist.
They come in now, both `BEAT`, distinguishable through `behavior_category`.

Evidence: excluded points run 109% of counted points for AY2026 to date, and
9,956 of 10,164 students hold at least one `Values (5)` award. The dashboard
shows a student with 82 points whose progress report reads 171.

Both are bulk staff awards, not student behavior. `Values (5)` grants all 4
values in one event — all 22,868 events, exactly 20 points and 4 rows each — and
`Values (10 Point Bonus)` swings from 96% of base `Values` points in Newark
AY2024 to 9.6% in AY2025. So they must stay separable rather than merged into
one `BEAT` total: the workbook filters `behavior_category = 'Values'` wherever
it compares years, and sums all 3 where it wants the full award total.

**This does not reproduce the progress-report total, and the spec does not claim
it does.** The `behaviors` CTE inner-joins `int_students__calendar_week`, so any
behavior dated outside a school calendar week is dropped. For AY2026 that is
41,856 of 45,180 bonus rows and 39,044 of 91,472 `Values (5)` rows — **100% of
them dated before the school year started.** Those are illegitimate entries that
schools are asked to delete and do not; dropping them is the desired behavior,
not a defect. AY2025 also shows ~10,000 bonus rows landing mid-year but outside
any calendar week (holidays, breaks, retroactive weekend entries); plain
`Values` already drops that way, so this is pre-existing, not a regression.

What the dashboard shows is **in-session points**. State that, rather than
implying parity with the progress report.

`Values (5)` inflates `behavior_count` as well as `total_points`, at 4 rows per
event. The `behavior_category = 'Values'` filter fixes both.

### `TEAMwork` normalizes to `Teamwork`

The casing split is inside AY2026, not only across years: `Values` logs
`TEAMwork` while `Values (5)` and `Values (10 Point Bonus)` both log `Teamwork`.

The workbook contains **zero** references to `TEAMwork` and 6 to `Teamwork`,
including a manual-sort dictionary (`Effort`, `Accountability`, `Teamwork`) and
color-encoding buckets. So today AY2026's `TEAMwork` misses both its color and
its sort position. Normalizing is the fix, not a risk.

**Normalize the CASE output, not the raw value.** An equality test written
before the parenthetical-stripping regex would miss a
`TEAMwork (Community)`-shaped value. Derive the behavior first, normalize
second.

No renamed or split behavior is mapped. `Off Task/Not Following Directions` does
not become `NFD/Off Task`. Those members change between years, which the
show-all filters absorb.

### Miami leaves AY2026, keeps its history

Miami's DeansList feed stopped 2026-06-25 for behavior and 2026-06-03 for
incidents. Miami students stay in the AY2026 enrollment spine, sourced from
Focus, so the left joins produce rows with zero behaviors and zero referrals and
the dashboard reads 5 schools with perfect conduct.

CRDC is unaffected by the exclusion: Miami's Civil Rights Data Collection
submission is handled by their local LEA this year. Data Quality is unaffected
too — Miami is off DeansList entirely, so there is nothing left to reconcile.

**The exclusion is a macro plus a var, not three hand-written predicates.** This
follows the `exclude_frozen` idiom in `macros/utils.sql`, whose whole point is
that adding or removing a location is one edit to a var. Miami returns in
quarter 2 once its replacement behavior platform is ingested, and that reversal
must not require finding three literals in three files.

**The exclusion is applied after the window functions, not in the same
`where`.** `rpt_tableau__okrts_referrals` computes `is_week_ytd` as
`max(if(academic_year = <current>, week_number, 0)) over (partition by co.schoolid)`
— partitioned by school alone, deliberately reaching across years so a prior
year can be cut to the current year's week. Filtering Miami's AY2026 rows out
before that window leaves Miami partitions holding only AY2025 rows, the `max`
evaluates to 0, and **every Miami AY2025 row flips to `is_week_ytd = false`** —
blanking the year the spec promises to protect. Row counts are unchanged, so a
count-based validation would not catch it. Wrapping the existing select in a CTE
and filtering in an outer select preserves every window's semantics exactly.

| Model                               | Join shape | Change                   |
| ----------------------------------- | ---------- | ------------------------ |
| `rpt_tableau__okrts_behavior`       | left       | exclude, in outer select |
| `rpt_tableau__okrts_referrals`      | left       | exclude, in outer select |
| `rpt_tableau__suspension_over_time` | left       | exclude, in outer select |
| `rpt_tableau__home_instruction`     | inner      | none needed              |

## Column contract

`rpt_tableau__okrts_behavior` gains 1 column. Nothing is removed or renamed.

| Column              | Type     | Note                                        |
| ------------------- | -------- | ------------------------------------------- |
| `behavior_category` | `string` | Raw DeansList category, new                 |
| `category_type`     | `string` | Gains a third value, `Habits of Excellence` |
| `behavior`          | `string` | `TEAMwork` normalized to `Teamwork`         |

**Contracts are enforced on these models.** `dbt_project.yml` sets
`extracts: +contract: enforced: true` with `tableau:` nested underneath, so the
config inherits. `behavior_category` must be added to
`rpt_tableau__okrts_behavior.yml` **with `data_type: string`** or the build
fails hard. Column order does not matter — contracts match on name and type.

## Exposure fix

`okrts_dashboard` lists 3 of the 4 data sources the workbook uses;
`rpt_tableau__home_instruction` is missing. Add it to `depends_on`.

This is a **lineage and staleness** fix, not a scheduling one. The
extract-refresh `ScheduleDefinition` targets the single exposure asset and its
body is one `workbooks.refresh()` REST call; `refs` become `deps`, which are
graph edges, not an execution gate. The 4 AM tick does not wait for the three
refs it already lists either.

## Paterson

DeansList sends `Paterson Prep ES` and `Paterson Prep MS`. Neither string was in
`int_people__location_crosswalk`, so the inner join dropped all 23,652 Paterson
behavior rows.

**Completed 2026-08-28** by the dashboard owner, in spreadsheet
`1FCc28XWxFj3gSfItGGJ2tVU0C1fYD1JxKRxuSFqisMo` (titled **People**). The
`sheet_range` values in `sources-external.yml` are named ranges, not tab names —
searching the workbook for them finds nothing.

| Named range in dbt                        | Tab                  | `gid`       |
| ----------------------------------------- | -------------------- | ----------- |
| `src_people__location_crosswalk_v2`       | `Location Crosswalk` | `81209161`  |
| `src_google_sheets__people__locations_v3` | `Locations`          | `179943835` |

Rows added to `Location Crosswalk`: `Paterson Prep ES` →
`Paterson Prep Elementary School`, `Paterson Prep MS` →
`Paterson Prep Middle School`. IDs set on `Locations`: `Deanslist School ID` 966
and 1070.

Verified in production: both rows reach `int_people__location_crosswalk` with
PowerSchool ids 1234 and 2 resolved, all 23,652 behavior rows now match, and
`int_students__calendar_week` covers both schoolids for AY2026 with 41 weeks
each.

**Two things still block Paterson from appearing on the dashboard**, neither in
this repo:

1. The `Exclude Paterson (TEMP)` data-source filters, removed at republish.
1. `Role Access` and `Regional User Filter` have no Paterson AD group, so
   Paterson staff cannot open the workbook. Tracked in
   [#5063](https://github.com/TEAMSchools/teamster/issues/5063).

**The `Deanslist School ID` fill has consumers beyond this dashboard.** About 20
models read the column, and three were structurally pinned to zero for Paterson
until now: `int_topline__suspension_weekly` (feeds the network "Student and
Family Experience → Suspensions" topline indicator),
`rpt_gsheets__school_metrics_extract`, and `rpt_deanslist__iready_lessons` — the
last of which ships **outbound to DeansList**. Paterson currently has 21 AY2026
incidents and zero suspensions, so nothing has moved yet.

## Out of scope, decided

**`Uniform` and `Dress Code` stay excluded, on evidence rather than deferral.**
Neither is normed — each is a single school. `Uniform` is Lanning Square Primary
only (2,123 `In Uniform`, 44 `Out of Uniform`, 559 students, 27 staff): a
roster-based daily compliance sweep, local to that school. `Dress Code` is Rise
only, 2 rows by 1 staff member on 1 day.

Uniform corrections are already captured network-wide as a behavior inside
`Tier 1 - Corrective Behaviors` — 12 of 19 schools, 49 instances. So AY2025's
`School Uniform` corrective (5,067 instances) has a direct AY2026 successor in
the same `Corrective` bucket and `# Corrective Behaviors per Student per Day`
stays comparable. DeansList config cleanup for `Dress Code` belongs with #4858.

`System Behaviors` and `Reflection Period` stay excluded, unchanged from today.

## Out of scope, tracked

**`BEAT Exemplary` changes what BEAT points mean.** Through AY2025 `Values` was
exactly 1 point per row; in AY2026 `BEAT Exemplary` sits inside it at 5 points,
so Newark reads 397,235 rows against 441,927 points. It stays in `BEAT` and in
`total_points`, broken out as its own member. No code change, but
`SO - Leaderboard - Points` shifts meaning between years.

**All 4 Home Instruction worksheets pin `academic_year` to 2025** and go blank
for AY2026 regardless of this work. Workbook-side.

**Eight Entry Analysis worksheets may carry a saved `2025-26` year filter** on
the `Academic Year (Display)` calc. Plausible, unconfirmed — worth checking at
republish, because someone verifying "corrective behaviors appear for AY2026" on
that tab would see the old taxonomy.

**`Weekly Incentive [LOD]` and `Monthly Incentive [LOD]`** test
`behavior = 'Earned Weekly/Monthly Incentive'`, which the category filter makes
unreachable. Both always return 0, and `Weekly Incentive [LOD]` is live on
`LP - Tree Data - BEAT Points` as `% Earning Weekly Incentive` — a landing-page
tile currently reading 0%.

**Miami `behavior` resolves to null** for `Big Reminders` and
`Written Reminders`, 43,263 AY2025 rows: the Miami branch regexes the category,
which holds no parenthetical. History only.

**The `behavior` regex truncates names containing `/`, `-`, or `&` before a
parenthetical** — `Off Task/Not Following Directions (Tier 1)` would become
`Not Following Directions`. No current behavior name has both, so nothing is
wrong today. Hardening, not a defect.

**`referral_tier` exists twice and the copies have drifted.** See #4747. The
shared column in `int_deanslist__incidents` also inverts Miami's tiers.

**The stopped-Miami-feed problem is not bounded to the 3 OKRTS extracts.**
`int_topline__suspension_weekly` has the identical defect: it left-joins
`int_deanslist__incidents__penalties` onto the enrollment-weeks spine with no
code-location handling, so every Miami AY2026 student-week reads
`is_suspended_y1_all_running = 0` structurally, diluting the network "Student
and Family Experience → Suspensions" topline indicator. This pre-dates this
branch and is tracked as
[#5064](https://github.com/TEAMSchools/teamster/issues/5064).

## Validation

### AY2025 is unchanged, blocking

Filtered to `behavior_category = 'Values'`, AY2025 BEAT totals must be identical
to production per region and per school. Same for AY2025 `Corrective` counts.

Unfiltered, AY2025 BEAT points rise **8.7% in Newark and 6.1% in Camden** as
`Values (10 Point Bonus)` starts flowing. Confirm the delta matches those
figures rather than exceeding them. (These are post-join numbers; the raw
staging figures are 9.6% and 6.7%.)

### Miami's AY2025 is unchanged, including column values

Row counts alone are insufficient. Assert that Miami AY2025 `is_week_ytd` has
the same true/false distribution before and after — this is the check that
catches the window-function regression.

### AY2026 renders

`category_type = 'Corrective'` returns non-zero rows for Newark, Camden, and
Paterson. `Habits of Excellence` returns rows for the 8 schools that log it and
nothing for the other 11. `category_type is null` returns zero rows.

### Extract counts track staging

For each newly admitted category, compare the extract row count against the raw
`stg_deanslist__behavior` count and confirm the difference is only the
out-of-calendar-week rows. Checking against zero would pass on one surviving
row.

### Paterson appears

Paterson behavior rows reach the extract and both incentive columns populate.

### Fan-out is contained

`school_enrollment_by_week` is unchanged — it is
`count(distinct co.student_number)`. The incentive flags still resolve, since
the workbook wraps them in `FIXED` level-of-detail expressions with `MAX`, and
`days_in_session` is consumed through `MAX` and `AVG`. What does move is
`SUM(behavior_count)` on 5 current-year sheets: `EA - Behaviors - Lines`,
`EA - Behaviors - Roster`, `EA - Behaviors - Staff`, `SO - Behaviors - Lines`,
`SO - Behaviors - Roster`. `EA - Behaviors - Staff` matters most — it ranks
staff by entry volume, and `Values (5)` is a bulk award emitting 4 rows per
click.

### Build

```bash
uv run dbt build --project-dir <worktree>/src/dbt/kipptaf \
  --select rpt_tableau__okrts_behavior rpt_tableau__okrts_referrals \
           rpt_tableau__suspension_over_time
```

Naming all three is required. `rpt_tableau__okrts_behavior` is a leaf — nothing
in `src/dbt/` refs it but the exposure — so `+` selects nothing extra and the
other two changed models would go unbuilt, with contracts enforced.

## Ship sequence

1. Sheet edits. **Done 2026-08-28.**
1. One PR: macro and var, 3 models, 1 yml, 1 exposure. Scope is `kipptaf` only.
1. Prod materializes on the models' own dbt automation conditions
   (`dbt_table_automation_condition` / `dbt_view_automation_condition`), not on
   the `okrts_dashboard` schedule — that schedule only refreshes the Tableau
   extract.
1. Workbook republish by the dashboard owner. All four data sources are
   **embedded `.hyper` extracts**, so a new warehouse column does not appear in
   the field list until the data source is refreshed in Desktop and republished.
   In the same pass: remove the 2 `Exclude Paterson (TEMP)` filters, add the
   `Habits of Excellence` member and a parallel measure on
   `LP - Tree Data - BEAT Points`, and add the `behavior_category = 'Values'`
   filter to the 5 sheets above plus any year-over-year view.

**Ordering hazard.** Between steps 3 and 4 the live dashboard shows AY2025 BEAT
points up 8.7%/6.1% and AY2026 counts inflated by `Values (5)`, and the workbook
cannot filter it back until `behavior_category` exists in the extract. If that
window is unacceptable, split the PR: ship `behavior_category` first, let the
owner add the filters, then ship the allowlist expansion.

## Corrections from review

The first draft asserted these. All four are false and are fixed above.

1. "There are no datasource-level or extract-level filters." Two exist, both
   excluding Paterson. The original scan only inspected `<datasource>` and
   `<extract>` elements, never the workbook-level `<shared-views>` block.
1. "The model has no enforced contract... the yml is a column list." Contracts
   are enforced by inheritance from `extracts`.
1. "The 4 AM extract refresh does not wait for it." `deps` are lineage edges,
   not an execution gate.
1. "Prod materializes through the existing `okrts_dashboard` schedule." Models
   materialize on their own automation conditions.

Two more were understated: the Miami exclusion is not "a single predicate per
model" (it breaks `is_week_ytd`), and the AY2025 bonus delta is 8.7%/6.1%, not
9.6%/6.7%.
