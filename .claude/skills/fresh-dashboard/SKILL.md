---
name: fresh-dashboard
description: >-
  Use when any question or task touches the FRESH dashboard's data model or its
  lineage. Triggers: explaining the scaffold/goals pipeline, debugging a count
  that doesn't match Finalsite, adding a new school/grade/year cycle,
  troubleshooting a student's status looking wrong, or working on
  int_tableau__fresh_enrollment_scaffold, int_tableau__fresh_goals_scaffold,
  rpt_tableau__fresh_dashboard_progress_to_goals, or
  rpt_tableau__fresh_dashboard_aggregated and their upstream models.
---

# FRESH Dashboard Data Model

## Always read first

- Reference doc:
  [`docs/models/fresh-dashboard-data-model.md`](../../../docs/models/fresh-dashboard-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md`](../../../docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md`](../../../docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md)

**Key facts to confirm before touching anything:**

- The scaffold's year column is `enrollment_academic_year`, in start-year form
  (AY2026-2027 = `2026`). The `rpt_tableau__fresh_dashboard_*` views alias it
  back to `academic_year` for Tableau, so the external column name is unchanged.
- **Miami is Focus-sourced, not sheet-sourced.** `int_focus__schools` (joined
  through `stg_google_sheets__people__locations` for the abbreviation and the
  PowerSchool-space `schoolid`) and `int_focus__student_enrollments` supply it.
  Don't "fix" Miami by onboarding it into `stg_powerschool__schools` — those
  rows are a frozen pre-migration snapshot and are excluded on purpose.
- **The scaffold is fully SIS-derived; the scaffold sheet is retired**
  (`enabled: false`). Nothing is hand-entered. See the retired-generator note
  below before offering to add sheet rows.
- `grade_level = -9` means "whole-school total row" in this scaffold's
  convention — never conflate with PowerSchool's own use of negative grade
  levels (pre-registration/pre-K). It is now derived, one row per school; `-1`
  is reserved for Pre-K everywhere downstream and never appears in the scaffold.
- `school_level` is banded per grade (`>= 9` HS, `>= 5` MS, else ES), NOT read
  from either SIS's per-school field. These are NJ bands, so **Miami grade 5
  reports `MS` here but `ES` on the goals sheet** — an accepted divergence, not
  a bug. Don't reconcile it.
- The goals sheet is a **live-read** Google Sheets external table — a number can
  change between two queries run seconds apart if someone is editing it. A
  mismatch against a materialized table doesn't necessarily mean a bug; check
  the sheet directly before assuming one.

---

## For a non-engineer: "why does this number look wrong?"

Start here if you're on the school/enrollment team, not an engineer.

1. **Is the whole school/region off, or one specific student?**
   - Whole category (e.g. all Inquiries for a school) → likely a
     `status_crosswalk` mapping gap. Ask an engineer to check whether the
     detailed statuses Finalsite has for that school/year are all mapped in the
     crosswalk sheet (see "Troubleshooting a count discrepancy" below).
   - One specific student showing the wrong status → check the FRESH Dashboard's
     Progress-to-Goals tab, **OPEN ROSTER** button (top right), for that
     student's current status. If it looks wrong and you set two statuses on the
     same day in Finalsite, use the **Reset Protocol™**:
     1. Put them in another status.
     2. Wait a day.
     3. Put them in the status you want.
   - Numbers look inflated → check whether a test/fake Finalsite record needs
     adding to the exclusion sheet
     (`stg_google_sheets__finalsite__exclude_ids`).
   - A cleanup you did late in your day isn't showing → ingestion has a lag (see
     the reference doc); it may show up the next day.
   - A number doesn't match what you just typed into a sheet → the sheet is read
     live, so give it a moment and re-check; if it's still wrong, ask an
     engineer to rematerialize the affected models and confirm.

2. **Adding a new grade or school?** Nothing gets hand-entered into a scaffold
   sheet any more — the school × grade spine builds itself from PowerSchool and
   Focus. A school appears once a student is enrolled in that grade in the SIS.
   For a grade you are **recruiting for but haven't enrolled anyone into yet**,
   enter it in **Finalsite** under the Finalsite academic year and tell the data
   team; it comes in when the Finalsite enrollment year rolls over. You still
   need **goals** for it either way — ask the data team to run the goals
   reconciliation (below) rather than hand-typing rows.

## For an engineer: troubleshooting a count discrepancy

Standard checks, roughly in order of likelihood:

1. **Missing crosswalk mapping**: pull
   `distinct detailed_status, enrollment_type` from
   `stg_finalsite__status_report` for the year in question, anti-join against
   `stg_google_sheets__finalsite__status_crosswalk`'s
   `(detailed_status, enrollment_type)` for that `_dagster_partition_key`.
   Anything present in Finalsite but absent from the crosswalk is silently
   dropped by `latest_status_calc`'s `inner join`.
2. **Invalid or QA-flagged rows**: for statuses that DO have a mapping, check
   `valid_detailed_status = false` or `qa_flag = true` — these are also silently
   excluded. `valid_detailed_status` specifically encodes "is this status
   legitimate for this enrollment_type (New vs. Returning)" — a `false` means a
   real data-entry mismatch upstream in Finalsite.
3. **Same-day status tie**: if one specific student's `latest_status` looks
   wrong (e.g. shows an in-progress status for a kid who actually
   withdrew/declined), check whether two statuses were set the same calendar day
   in Finalsite. This is a permanent, accepted Finalsite limitation, not a code
   bug — see the reference doc's "Known data model caveats" and use the Reset
   Protocol above, not a code fix.
4. **Fake/test student records**: check
   `stg_google_sheets__finalsite__exclude_ids` for the student in question — a
   test record not yet excluded inflates counts.
5. **Ingestion lag**: `stg_finalsite__status_report` is sensor/file-drop
   triggered (Couchdrop SFTP), not a fixed cron — a very recent Finalsite edit
   may not have landed yet.
6. **Live sheet edits**: for a goal-value discrepancy specifically, remember the
   goals sheet is read live (no caching) — the number may have simply changed
   between when a materialized table last built and now. Compare against the
   sheet directly (or against `int_google_sheets__finalsite__goals_pivot`, also
   a live read) before assuming a code bug.

## Sanity-checking the scaffold against SRE's target sheet

SRE maintains the workbook the goals ultimately come from, and its cover sheet
lists the schools they expect to recruit for. That makes it the outside check on
`int_tableau__fresh_enrollment_scaffold` — if a school SRE is recruiting for is
missing from the scaffold, or the scaffold carries one SRE doesn't recognize,
the spine is wrong.

**Workbook:** `26-27 KNJMIA Application Target Formulas`, id
`1YP8MR--r__7DpS-Al8C9fv0NLAuJI6S6IpW5mObZwdI`, owned by mventresca@. The school
list is on the `cover sheet` tab; per-school grade detail is on per-region tabs
(`KCNA`, `Newark`, …). SRE re-shares a new workbook each cycle, so confirm the
id before trusting it.

**How to read it:** use the Drive connector —
`mcp__claude_ai_Google_Drive__get_file_metadata` returns a content snippet
spanning several tabs, and `read_file_content` returns the body. **Do not reach
for the Sheets API** (`uv run --with google-api-python-client`): ADC here
authenticates as a service account that has no access to the workbook and
returns `403 The caller does not have permission`. The connector runs as the
signed-in user, which does.

**Two things will trip up a naive comparison:**

- **The workbook is KNJMIA — Newark, Camden, and Miami only. Paterson is
  absent.** Scope Paterson out, or its two schools (PPES, PPMS) read as spurious
  extras.
- **Abbreviations don't match and the sheet has no `schoolid`,** so this is a
  region + level + count check or a hand-mapped name comparison, never a join:

  | sheet | scaffold   |
  | ----- | ---------- |
  | KRA   | Royalty    |
  | KCA   | Courage    |
  | KMT   | Miami Tech |
  | KLE   | Legacy ES  |
  | KLM   | Legacy MS  |
  | NLHS  | NLH        |

As of AY2026 this check passes: 22 schools expected across the three regions, 22
produced (Newark 12, Camden 5, Miami 5), plus Paterson's 2 outside the
workbook's scope.

**Corroboration worth knowing:** the per-region tabs band Sumner's own rows as
`MS,Sumner Academy,5` and `MS,Sumner Academy,6` while the cover sheet files
Sumner under Camden **ES**. SRE themselves treat grades 5-6 as MS at the grade
level and the school as ES at the school level — which is exactly the per-grade
banding the scaffold's `school_level` reproduces. Don't "fix" that split.

## Goals reconciliation — offer this at the start of FRESH work

**SRE does not always flag goal changes.** So before doing anything substantive
on the FRESH dashboard, and always when the user asks to update goals, ask:

> Do you want to run a goals reconciliation against SRE's sheet first?

If yes, run the loop below. If the user declines, note that goal-value
discrepancies are then out of scope for whatever you find.

### The reconciliation loop

1. **Ask for the workbook URL.** SRE issues a new one each cycle; don't reuse
   the id recorded above without confirming.
1. **Confirm goal names are unchanged.** The goals sheet joins on `goal_name`,
   so a rename silently stops matching rather than erroring. Compare SRE's goal
   labels against `distinct goal_name` in `stg_google_sheets__finalsite__goals`
   and surface any that don't appear.
1. **Compare.** Read the workbook via the Drive connector, compare against
   `stg_google_sheets__finalsite__goals` on
   `(region, schoolid, grade_level, goal_type, goal_name)`, and classify each
   difference as missing / extra / value-mismatch.
1. **Hand back a paste-ready block.** Plain delimited rows in a fenced code
   block, one row per line, column order matching the sheet — not a markdown
   table, which can't be pasted into Sheets.
1. **Re-run after they paste.** The goals sheet is a **live read**, so the next
   comparison sees their edits immediately — no rebuild needed. Repeat until
   there are no discrepancies.

Suggest the user drive this with `/loop` (no interval — self-paced) so each
round re-compares automatically after they finish a batch of edits. Stop the
loop when a comparison comes back clean, and say so explicitly rather than going
quiet.

**Mid-year goal updates** can optionally be applied through the Claude Chrome
extension instead of hand-pasting: generate a change-set prompt naming the
workbook, the tab, each target row keyed by
`(region, schoolid, grade_level, goal_type, goal_name)`, old value → new value,
and an explicit instruction to change nothing else. The user drops that into the
extension, which edits the sheet. **Then re-run the comparison** — the
extension's write is unverified from here, so the reconciliation query is what
confirms it landed.

## Rollover / maintenance generators

The generator below is an ad hoc BigQuery query, run on demand — not a
persistent dbt model. It ends with a verify-and-confirm step: after the analyst
pastes rows into the sheet, rematerialize the goals sheet's consumers and
confirm the change reached prod before telling them it's done (compare row
counts / a value sample against the prod table via a BigQuery MCP query or `bq`,
and check `__TABLES__.last_modified_time` for staleness).

### The `-9` candidate-row generator is retired — do not look for it

`stg_google_sheets__finalsite__school_scaffold` and its source entry are both
`enabled: false` — disabled rather than deleted, per the archive convention.
`int_tableau__fresh_enrollment_scaffold` now derives every row type that sheet
supplied: per-grade membership from PowerSchool and Focus, `grade_level = -9`
whole-school totals, and `schoolid = 0` region rollups. There is nothing to
hand-enter and nothing to generate — new schools and grades appear automatically
once the SIS has at least one enrolled student in them.

If someone asks for the `-9` generator, the answer is that the rows are computed
now. Do not re-add sheet rows or re-enable the model.

The Google Sheet itself still exists in Drive and Ops may still look at it; only
the dbt read of it is gone. Its BigQuery relations linger after the disable —
dbt never drops a relation — so they need a manual drop once this ships.

### Goals-sheet gap-row generator

Three patterns — see the reference doc's "Goal definitions" section for which
`goal_type`/`goal_name` combos are `School` vs. `School/Grade Level` vs.
`Region/Grade Level`. For each, project the most recent existing year's
combo-set for that `schoolid` (or `region`, for `Region/Grade Level` rows)
forward onto the current scaffold, and list any
`(academic_year, region, schoolid, school, grade_level, goal_granularity, goal_type, goal_name)`
combo present in the scaffold/region set but absent from the current year's
goals sheet. A genuinely new school/grade has no prior-year pattern to project —
flag it for the analyst to pick goal types manually rather than silently
skipping it.

- **`School` rows** (`grade_level = -9` in `stg_google_sheets__finalsite__goals`
  and the enrollment scaffold) — keyed by `schoolid`. Copy that school's own
  existing `(goal_type, goal_name)` combo-set forward. Verified during design:
  this set is uniform across almost every school, with one real exception
  (Miami's MTH lacks the lottery-based categories — Accepted / Offers / Pending
  Offers — at `School` granularity) that a per-school copy-forward rule handles
  correctly without special-casing.
- **`School/Grade Level` rows** — keyed by `(schoolid, grade_level)`, same
  copy-forward rule applied per grade in the new scaffold.
- **`Region/Grade Level` rows** (Inquiries, Applications, Deferred, Waitlisted,
  etc.) — keyed by `(region, grade_level)`, independent of the scaffold's
  `schoolid` dimension (no specific school), but **not** independent of
  `grade_level` — verified against real data: every active region carries one
  row per grade, not a single collapsed region-wide row.

`status_crosswalk`'s own annual rollover stays a documented manual process, not
a generated one — there is no source of truth to derive its content from (the
Finalsite-status → category mapping is institutional judgment, not computable).

## Procedure: Update the Finalsite recruitment year

**Trigger phrases:** "SRE's cycle has rolled over, update FRESH for the new
year", "bump the Finalsite recruitment year", "the goals sheet is now on [year],
update the dashboard"

**Why this is a dedicated, manually-bumped var, not derived:** the value lives
in `finalsite_recruitment_year` (`src/dbt/kipptaf/dbt_project.yml`), but that
var doesn't compute itself — two separate attempts to compute "the current
Finalsite cycle" automatically were built and then reverted (see `git log` on
`int_tableau__finalsite_student_scaffold.sql` for both). Finalsite can carry two
concurrent academic years of live student data at once — students and regions
roll over on their own uncoordinated timeline — so there's no reliable signal in
the ingested data itself for "which year is current now." Unlike PowerSchool's
`var("current_academic_year")`, which bumps on a predictable July 1 cadence,
SRE's recruitment-cycle timeline is fluid — there is no fixed date to key an
automatic bump off of. **Always confirm the new year with SRE (or by reading the
goals sheet directly) before changing anything below — don't infer it from a
calendar date or from ingestion data.**

**Step 0a — ask for the new SRE workbook.** Before anything else, ask the user:
_"Do you have a new SRE target sheet URL for this cycle?"_ SRE re-shares a new
workbook each cycle (the AY2026 one was
`26-27 KNJMIA Application Target Formulas`), so the id recorded in
"Sanity-checking the scaffold against SRE's target sheet" above is stale by
definition at rollover time. Get the new URL, read it via the Drive connector,
and use its cover sheet as the expected-school list for the post-toggle
verification. If the user doesn't have it yet, note that the rollover can still
proceed — the scaffold derives itself — but the sanity check is deferred until
they do, and say so rather than silently skipping it.

Update the recorded id in this skill once you have the new one.

**Step 0b — confirm SRE and the data team agree which Finalsite enrollment year
is active.** This is the real gate on the whole rollover, not a formality: the
two year vars diverging is what activates `finalsite_new`, which is how
not-yet-enrolled schools and grades enter the scaffold. Don't infer the year
from a calendar date or from ingestion data — ask.

**Step 0c — new schools or grades?** There is nothing to hand-enter. Ask SRE to
enter them **in Finalsite** under the new Finalsite academic year; the year bump
then brings them in through `finalsite_new`. If SRE hasn't entered them yet, the
bump will simply not include them, so it's worth confirming before proceeding.

**Step 0d — `status_crosswalk` partition key and columns.** Two things, both on
the sheet, both before the bump:

```sql
select distinct _dagster_partition_key, file_year, count(*) as row_count
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__status_crosswalk
group by 1, 2
```

- The **`_dagster_partition_key` (column A)** must match the new Finalsite
  enrollment year. It's a **replace, not an append** — the sheet holds exactly
  one year at a time, guarded by
  `test_stg_google_sheets__finalsite__status_crosswalk_single_year`. If the key
  still reads the outgoing year, `latest_status_calc`'s `inner join` returns
  zero rows for the new year and the dashboard goes empty with no error.
- **Ask SRE whether columns D, H and I→P still make sense** for the new cycle.
  Use the table below to ask the question in their terms rather than by column
  letter — these encode funnel judgment and cannot be derived.

| col     | column                                                                                                                                              | question to put to SRE                                                                           |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **D**   | `detailed_status_ranking`                                                                                                                           | When a student hits several statuses, which wins? Has that priority changed?                     |
| **H**   | `qa_flag`                                                                                                                                           | Which statuses should be excluded from reporting as bad data this cycle?                         |
| **I-P** | `status_enrollment`, `status_group_numerator`, `status_group_denominator`, `conversion_metric_numerator_1..3`, `conversion_metric_denominator_1..2` | Which funnel bucket does each status roll into, and which conversion rates does it count toward? |

If D changes, the `status_order` CASE in `int_finalsite__status_report_unpivot`
must change with it —
`test_int_finalsite__status_order_matches_crosswalk_ranking` guards the pair and
will fail if they drift. Full column reference, including the columns SRE does
_not_ need to review, is in the reference doc.

**Step 0e — goals.** Get the new workbook URL from SRE, confirm goal names are
unchanged, and run the reconciliation loop in "Goals reconciliation" above until
it comes back clean.

There is **no scaffold-sheet pre-flight check** any more — the sheet is retired,
so the old `-9` row check is gone. Once the year is agreed, the crosswalk key is
updated and goals reconcile, proceed to the file edits below.

**Files to edit** — every dbt model/test site reads from one shared var:

- `src/dbt/kipptaf/dbt_project.yml` — bump `finalsite_recruitment_year` (e.g.
  `2026` → `2027`). This alone updates every site below; none of them hold their
  own literal any more.
  - `int_tableau__fresh_enrollment_scaffold.sql` (`school_directory`'s
    `enrollment_academic_year`, and `finalsite_new`'s `where` filter — which
    also carries the constant gate predicate
    `finalsite_recruitment_year != current_academic_year`, so bumping the var is
    what switches that CTE from zero rows to live)
  - `int_tableau__finalsite_student_scaffold.sql` (`same_day_status_dates`'s
    `where` filter and `enrollment_lookup`'s two branches)
  - `rpt_tableau__fresh_dashboard_progress_to_goals.sql` (the `School` and
    `School/Grade Level` goal CTEs)
  - `test_int_finalsite__status_order_matches_crosswalk_ranking.sql`
    (`crosswalk_ranking`'s `where` filter)

`rpt_tableau__fresh_dashboard_qc` is a descendant of
`int_tableau__finalsite_student_scaffold`, so it inherits the year change
without holding a literal of its own — but it IS a verification site. It is
enabled, contract-enforced, and wired into the `fresh_dashboard` exposure, and
it is the SRE-facing mismatch worklist, so a bump that quietly empties or
inflates it is worth catching. Make sure the build command below selects it.

The goals gap-row generator in this file is an ad hoc BigQuery query, not a dbt
model, so it can't read `{{ var(...) }}` — substitute the new year by hand each
time you run it.

Grep to confirm every model site reads the var and none reverted to a bare
literal:

```bash
grep -rn 'var("finalsite_recruitment_year")' src/dbt/kipptaf
```

Build and verify after all changes:

```bash
uv run dbt build \
  --select int_tableau__fresh_enrollment_scaffold+ int_tableau__finalsite_student_scaffold+ \
    test_int_finalsite__status_order_matches_crosswalk_ranking \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer \
  --favor-state \
  --state target/prod
```

`--favor-state` is required, not optional: without it `--defer` resolves
unselected upstreams to your `zz_<user>_*` dev schema and fails on anything you
haven't personally built (e.g. `int_focus__schools`). If it still fails to
resolve a recently-added upstream, the `target/prod` manifest is stale — refresh
it with:

```bash
uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod
```

**When to make the change:** whenever SRE says the recruitment cycle has rolled
over — not on a fixed schedule. There is no "revert" step the way
gradebook-audit's summer toggle has; this is a one-directional bump forward each
time SRE's cycle advances.

**Expect `enrollment_lookup`'s PS/FS quality-check columns to go null for a
while after this toggle.** `enrollment_lookup` (in
`int_tableau__finalsite_student_scaffold.sql`) scopes
`int_extracts__student_enrollments` to the Finalsite recruitment year, not
`var("current_academic_year")` -- these two only match once PowerSchool's own
rollover independently catches up to the new year, which happens later and on
its own schedule. Until then, PowerSchool has no real enrollment rows for that
year, so the whole CTE -- and every `enroll_status`/`is_enrolled_*` column it
feeds -- is empty/null network-wide. This is expected, not a bug, and not
fixable by any part of this toggle; it resolves on its own once PowerSchool
catches up, with no further action needed.

## The QC worklist and its hardcoded FDOS date

Two AY2026 decisions that are easy to undo by accident. Full detail in the
reference doc; this is what to know before editing
`int_tableau__finalsite_student_scaffold` or `rpt_tableau__fresh_dashboard_qc`.

**`is_enrolled_fdos` is computed here, off a hardcoded regional date.** Newark
and Paterson August 28, Camden August 24, Miami August 14 — month and day
hardcoded, year from `var("finalsite_recruitment_year")`, exposed as
`custom_fdos_date`. It deliberately does NOT pass through either SIS's own
`is_enrolled_fdos`: Focus computes one network-wide first day, which reported
`false` for nearly every Miami student at a later-starting school, and
PowerSchool's is per-school. **Do not "fix" this by repointing at the upstream
flag, and do not change `int_extracts__student_enrollments` or
`int_focus__student_enrollments`** — they keep their own versions for their
other consumers. When the enrollment team changes a first day, edit the `CASE`
in `custom_fdos_dates` and nothing else.

**`is_enrolled_fdos` is a bare comparison on purpose.** Its sibling flags use
`if(<cmp>, true, false)`; that form would report every student with no SIS
record as `false` instead of NULL. Wrapping it to match the siblings is a
regression, not a cleanup — the same trap that produced a wrong doc claim about
`is_grade_level_mismatch` / `is_school_mismatch`, which DO collapse NULL to
`false` because they are wrapped.

**The worklist has four flags, not five.** `is_same_day_status_tie` was deleted
at the AY2026 review and replaced by direction 3 of `is_enroll_status_mismatch`
(the pending-status set). The same-day tie still happens in the data and the
Reset Protocol is still the fix — it just no longer gets its own worklist row,
so don't re-add the flag when someone reports a wrong `latest_status`.

**`finalsite_expected_enroll_status` has three non-null values**, and the
direction-3 set is SRE-owned rather than derived: `Accepted`, `Assigned School`,
`Did Not Enroll`, `Campus Transfer Requested`, `Parent Declined`,
`Enrollment In Progress`. Two oddities that are NOT bugs — `Did Not Enroll` and
`Parent Declined` read as exits rather than pending states, and `Accepted`
matches no rows in current data. Confirm with SRE before changing the list.

**Retention is SRE's to resolve, not ours.** Grade repetition makes
`is_grade_level_mismatch` and `is_school_mismatch` fire on correctly recorded
students. This was raised and explicitly handed to SRE — do not build
suppression or labeling logic for it unless they come back asking.

## Verified facts (don't re-derive these — reference them)

- `stg_powerschool__schools.school_level` is a single value **per school**
  (based on `high_grade`), not per grade — Sumner is base-classified `ES`
  network-wide there; this scaffold's own per-grade `CASE` (not that field) is
  what correctly produces `MS` for Sumner grades 5/6. Do not "fix" Sumner by
  reading `stg_powerschool__schools.school_level` directly.
- `schoolid` domains fully align between `stg_powerschool__schools` (filtered)
  and `int_people__location_crosswalk` for every case that matters — verified
  during design (see the spec's "Verification" section).
- Adding a `CROSS JOIN` to a query that previously read from a single table
  makes every other unqualified column reference ambiguous (`sqlfluff/RF02`) — a
  real error hit while building this project. Qualify every column with its
  table alias when adding a cross join, not just the new filter predicates.
- `UNION ALL` in BigQuery matches columns **positionally, not by name** —
  reordering a column in one branch to satisfy a style convention (ST06) without
  checking the other branches' column order can silently break a `UNION ALL`, or
  (worse, if types happen to align) silently misalign data with no error at all.
  Also hit and fixed while building this project.
