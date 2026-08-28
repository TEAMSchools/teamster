# OKRTS behavior taxonomy retrofit: carrying two culture systems in one model

Refs [#5062](https://github.com/TEAMSchools/teamster/issues/5062). Adjacent:
[#4747](https://github.com/TEAMSchools/teamster/issues/4747),
[#4858](https://github.com/TEAMSchools/teamster/issues/4858).

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

The contract is narrower than it looks. 23 of 74 worksheets touch the taxonomy,
through two derived columns.

`category_type` is today 2-valued: `BEAT` and `Corrective`. Every
worksheet-level filter on it pins to `"BEAT"`. `Corrective` reaches the workbook
only through 3 calculated fields on `LP - Tree Data - BEAT Points`:
`# Corrective Behaviors`, `# Corrective Behaviors per Student`, and
`# Corrective Behaviors per Student per Day`.

`referral_tier` drives the referral worksheets. It still resolves under the new
policy — the `Tier 1 -`, `Tier 2 -`, and `Tier 3 -` category prefixes already
existed in AY2025 — so this spec leaves it alone.

Every `behavior` filter in the workbook is `level-members`, meaning show-all.
New behavior names flow through with no workbook edit. There are no
datasource-level or extract-level filters.

## Design

### The allowlist covers both taxonomies

The allowlist grows from 11 names to 15 rather than being replaced. Retaining
`Corrective Behaviors` and Miami's 9 legacy names is what keeps AY2025 intact.

Added:

| Category                                    | Maps to                | First seen |
| ------------------------------------------- | ---------------------- | ---------- |
| `Tier 1 - Corrective Behaviors`             | `Corrective`           | 2026-08-03 |
| `Tier 1 - Habits of Excellence Corrections` | `Habits of Excellence` | 2026-08-13 |
| `Values (5)`                                | `BEAT`                 | 2026-08-13 |
| `Values (10 Point Bonus)`                   | `BEAT`                 | 2024-12-06 |

None of the 4 exists in Miami, verified against production, so the allowlist
change cannot move a Miami number.

### `category_type` gains a third value

`Habits of Excellence` becomes a peer of `BEAT` and `Corrective`, not a fold
into `Corrective`. Only 8 of 19 schools log it, and it is middle- and
high-school only. Blending it into the corrective rate would inflate that rate
at exactly the schools that adopted it, and
`# Corrective Behaviors per Student per Day` is a headline number on the landing
page.

The 3 existing corrective calculated fields stay corrective-only. Any Habits of
Excellence measure is added alongside them.

### The raw category is exposed

A new `behavior_category` column carries the DeansList category verbatim. This
is the load-bearing piece of the design: it is what lets one model serve both a
year-comparable view and a progress-report-comparable view without combining
categories.

The column costs nothing structurally. `behavior_category` is already selected
and grouped in the `behavior_aggregation` CTE — it is simply not projected in
the final `select`. Adding it changes no grain.

### The two bonus categories come in, kept separable

`Values (5)` and `Values (10 Point Bonus)` have never been on the allowlist, so
their points have never appeared on this dashboard. They come in now, both
mapping to `BEAT`, and stay distinguishable through `behavior_category`.

The evidence:

- Excluded points run **109% of counted points** for AY2026 to date. 9,956 of
  10,164 students hold at least one `Values (5)` award. The dashboard currently
  shows a student with 82 points whose progress report reads 171.
- `Values (5)` is a bulk award. All 22,868 events grant all 4 values at once,
  worth exactly 20 points and 4 behavior rows each.
- `Values (10 Point Bonus)` swings hard year to year: 96% of base `Values`
  points in Newark AY2024, 9.6% in AY2025. Newark logged 1.42M bonus rows in
  AY2024 and 173K in AY2025.

Neither category tracks student behavior. Both track staff award practice. That
is why they must stay separable rather than merged into a single `BEAT` total —
the workbook filters `behavior_category = 'Values'` on any year-over-year view
and sums all 3 where it needs to match the progress report.

`Values (5)` also inflates `behavior_count`, not just `total_points`, at 4 rows
per event. The same filter fixes both.

### `TEAMwork` normalizes to `Teamwork`

The casing split is inside AY2026, not only across years. `Values` logs
`TEAMwork`; `Values (5)` and `Values (10 Point Bonus)` both log `Teamwork`.
Without normalization the BEAT breakdown shows both members side by side in the
current year.

No renamed or split behavior is mapped. `Off Task/Not Following Directions` does
not become `NFD/Off Task`, and `Late/Unauthorized Location` does not become
`Late to class`. Those members simply change between years, which the show-all
filters absorb. Deciding that two differently-named behaviors mean the same
thing is a culture-team call, not a modeling one.

### Miami leaves AY2026, keeps its history

Miami's DeansList feed stopped on 2026-06-25 for behavior and 2026-06-03 for
incidents. Miami students stay in the AY2026 enrollment spine, sourced from
Focus, so the left joins in the OKRTS models produce rows with zero behaviors
and zero referrals. The dashboard reads that as 5 schools with perfect conduct.

Miami is excluded from AY2026 forward in the 3 models that left-join from an
enrollment spine:

| Model                               | Join shape | Change      |
| ----------------------------------- | ---------- | ----------- |
| `rpt_tableau__okrts_behavior`       | left       | exclude     |
| `rpt_tableau__okrts_referrals`      | left       | exclude     |
| `rpt_tableau__suspension_over_time` | left       | exclude     |
| `rpt_tableau__home_instruction`     | inner      | none needed |

The cutover year is written as a literal, not read from
`var("current_academic_year")`. It marks a historical event and must not move
when the variable rolls over in July — the same reasoning the `exclude_frozen`
macro comment records for Miami's frozen PowerSchool.

Miami returns in quarter 2 once its replacement behavior platform is ingested.
The exclusion is a single predicate per model, with a comment naming the
DeansList cutover date and the planned reversal.

## Column contract

`rpt_tableau__okrts_behavior` gains 1 column. Nothing is removed or renamed.

| Column              | Type     | Note                                        |
| ------------------- | -------- | ------------------------------------------- |
| `behavior_category` | `string` | Raw DeansList category, new                 |
| `category_type`     | `string` | Gains a third value, `Habits of Excellence` |
| `behavior`          | `string` | `TEAMwork` normalized to `Teamwork`         |

`rpt_tableau__okrts_behavior.yml` gains `behavior_category`. The model has no
enforced contract and no tests, so the yml is a column list for the Tableau
extract.

## Exposure fix

The `okrts_dashboard` exposure lists 3 of the 4 datasources the workbook uses.
`rpt_tableau__home_instruction` is missing, so the 4 AM extract refresh does not
wait for it even though it drives a whole dashboard tab. Add
`ref("rpt_tableau__home_instruction")` to `depends_on`.

## Paterson, outside the repo

DeansList sends `Paterson Prep ES` and `Paterson Prep MS`. Neither string is in
`int_people__location_crosswalk`, which holds 12 other Paterson aliases. The
inner join in `rpt_tableau__okrts_behavior` drops all 23,652 Paterson behavior
rows. Paterson's 843 students are already in the enrollment spine, so 2 sheet
rows fix it.

Spreadsheet `1FCc28XWxFj3gSfItGGJ2tVU0C1fYD1JxKRxuSFqisMo`, owned by the
dashboard owner.

Tab `src_people__location_crosswalk_v2`:

| `Name`             | `Clean_Name`                      |
| ------------------ | --------------------------------- |
| `Paterson Prep ES` | `Paterson Prep Elementary School` |
| `Paterson Prep MS` | `Paterson Prep Middle School`     |

Tab `src_google_sheets__people__locations_v3`, column `Deanslist_School_ID`,
currently blank for both rows:

| `Name`                            | `Deanslist_School_ID` |
| --------------------------------- | --------------------- |
| `Paterson Prep Elementary School` | `966`                 |
| `Paterson Prep Middle School`     | `1070`                |

The crosswalk rows alone make Paterson's behaviors appear. The DeansList IDs are
what populate `is_earned_progress_to_quarterly` and
`is_earned_quarterly_incentive`, which key on `deanslist_school_id`. Doing the
first without the second leaves Paterson showing behaviors and no incentives,
which reads as a region that earns nothing.

About 20 models read `deanslist_school_id`. Two of them —
`int_deanslist__referral_suspension_rollup` and
`int_students__attendance_interventions` — currently exclude Paterson through
`location_deanslist_school_id is not null` filters and will start including it.
That is the intended outcome, and it is why the ID fill gets its own
verification step rather than riding along with the alias rows.

## Validation

### AY2025 is unchanged, blocking

The core requirement. Filtered to `behavior_category = 'Values'`, AY2025 BEAT
totals must be identical to production, per region and per school. Same for
AY2025 `Corrective` counts.

Unfiltered, AY2025 BEAT points rise by roughly 9.6% in Newark and 6.7% in Camden
because `Values (10 Point Bonus)` now flows. That is expected and reversible in
the workbook, but it means the default AY2025 number will not match a screenshot
taken last spring. Confirm the delta matches the predicted figure rather than
exceeding it.

### AY2026 renders

`category_type = 'Corrective'` returns non-zero rows for Newark, Camden, and
Paterson. `Habits of Excellence` returns rows for the 8 schools that log it and
nothing for the other 11.

### Paterson appears

After the sheet edits, Paterson behavior rows reach the extract and the 2
incentive columns populate. Before the sheet edits this check fails by design.

### Miami

Zero AY2026 rows in the 3 excluded models. AY2025 Miami row counts unchanged.

### Fan-out is contained

Adding `Values (5)` and `Values (10 Point Bonus)` multiplies behavior rows per
student-week. Confirm `school_enrollment_by_week` is unchanged — it uses
`count(distinct co.student_number)`, so it should be — and that the incentive
flags still resolve, since the workbook wraps them in `FIXED` level-of-detail
expressions that tolerate repetition.

### Build

`uv run dbt build --select rpt_tableau__okrts_behavior+` from the worktree.

## Ship sequence

1. Sheet edits by the dashboard owner, in parallel with the model work. Paterson
   validation depends on them.
1. One PR: model, yml, exposure. Scope is `kipptaf` only.
1. Prod materializes through the existing `okrts_dashboard` schedule.
1. Workbook republish by the dashboard owner: add the `Habits of Excellence`
   member, add a parallel measure on `LP - Tree Data - BEAT Points`, and add the
   `behavior_category = 'Values'` filter to year-over-year views.

## Out of scope

Tracked, not fixed here.

**`BEAT Exemplary` changes what BEAT points mean.** Through AY2025, `Values` was
exactly 1 point per row. In AY2026 `BEAT Exemplary` sits inside it at 5 points,
so Newark reads 397,235 rows against 441,927 points. It stays in `BEAT` and in
`total_points`, broken out as its own member. No code change, but
`SO - Leaderboard - Points` shifts meaning between years.

**`Uniform`, `Dress Code`, `System Behaviors`, `Reflection Period`** stay
excluded pending stakeholder review. `Uniform` is a compliance sweep — 2,123
`In Uniform` against 44 `Out of Uniform` — so mapping the category to
`Corrective` would count compliance as a correction.

**Home Instruction worksheets pin `academic_year` to 2025.** All 4 go blank for
AY2026 regardless of this work. Workbook-side fix.

**Two dead calculated fields.** `Weekly Incentive [LOD]` and
`Monthly Incentive [LOD]` test `behavior = 'Earned Weekly Incentive'`, which the
allowlist makes unreachable. Both always return 0.

**Miami `behavior` resolves to null** for `Big Reminders` and
`Written Reminders`, 43,263 AY2025 rows. The Miami branch regexes the category,
which holds no parenthetical. History only.

**`referral_tier` exists twice and the copies have drifted.** See
[#4747](https://github.com/TEAMSchools/teamster/issues/4747). The shared column
in `int_deanslist__incidents` also inverts Miami's tiers, mapping `T1` to `High`
and `T3` to `Low`. Confirm that inversion is deliberate before anyone
consolidates.
