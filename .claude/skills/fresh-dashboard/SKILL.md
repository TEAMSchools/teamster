---
name: fresh-dashboard
description: >-
  Use when any question or task touches the FRESH dashboard's data model or its
  lineage. Triggers: explaining the scaffold/goals pipeline, debugging a count
  that doesn't match Finalsite, adding a new school/grade/year cycle,
  troubleshooting a student's status looking wrong, or working on
  int_finalsite__enrollment_scaffold, int_finalsite__goals_scaffold,
  rpt_tableau__fresh_dashboard_progress_to_goals, or
  rpt_tableau__fresh_dashboard_aggregated and their upstream models.
---

# FRESH Dashboard Data Model

## Always read first

- Reference doc:
  [`docs/reference/fresh-dashboard-data-model.md`](../../../docs/reference/fresh-dashboard-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md`](../../../docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md`](../../../docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md)

**Key facts to confirm before touching anything:**

- `academic_year` is start-year form (AY2026-2027 = `2026`).
- Miami is **always** 100% sheet-sourced, regardless of
  `finalsite_scaffold_source` — a deliberate, temporary carve-out (Miami's SIS
  moved to Focus, not ready yet as a scaffold source). Don't "fix" this by
  trying to onboard Miami schools into `stg_powerschool__schools` — ask first.
- `grade_level = -1` means "whole-school total row" in this scaffold's
  convention — never conflate with PowerSchool's own use of negative grade
  levels (pre-registration/pre-K).
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

2. **Adding a new grade or school mid-cycle?** Ask an engineer to run the `-1`
   candidate-row generator and the goals gap-row generator (below) — don't
   hand-type full rows from scratch.

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

## Rollover / maintenance generators

Both are ad hoc BigQuery queries, run on demand — not persistent dbt models.
Both end with the same verify-and-confirm step: after the analyst pastes rows
into the sheet, rematerialize `int_finalsite__enrollment_scaffold` (or the goals
sheet's consumers) and confirm the change reached prod before telling them it's
done — the same rematerialize-then-verify workflow used throughout this
project's own build (compare row counts / a value sample against the prod table
via a BigQuery MCP query or `bq`, and check `__TABLES__.last_modified_time` for
staleness).

### `-1` candidate-row generator (scaffold sheet)

Lists every currently-existing, non-Miami school missing its `grade_level = -1`
row in `stg_google_sheets__finalsite__school_scaffold` for the current academic
year — Miami needs its full spine, not just this generator's output (see the
Miami note above).

```sql
select distinct
  2026 as academic_year, -- finalsite year toggle: see skill
  ps.region,
  ps.abbreviation as school,
  ps.school_number as schoolid,
  -1 as grade_level,
  'KTAF' as org,
from `teamster-332318`.kipptaf_powerschool.stg_powerschool__schools as ps
left join `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__school_scaffold as s
  on ps.school_number = s.schoolid
  and s.grade_level = -1
  and s.academic_year = 2026 -- finalsite year toggle: see skill
where
  ps.state_excludefromreporting = 0
  -- extract_region logic inline since this is an ad hoc query, not a dbt model:
  and initcap(regexp_extract(ps._dbt_source_project, r'kipp(\w+)')) != 'Miami'
  and s.schoolid is null
```

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

- **`School` rows** (`grade_level = -1`) — keyed by `schoolid`. Copy that
  school's own existing `(goal_type, goal_name)` combo-set forward. Verified
  during design: this set is uniform across almost every school, with one real
  exception (Miami's MTH lacks the lottery-based categories — Accepted / Offers
  / Pending Offers — at `School` granularity) that a per-school copy-forward
  rule handles correctly without special-casing.
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

**Why this is hardcoded, not derived:** two separate attempts to compute "the
current Finalsite cycle" automatically were built and then reverted (see
`git log` on `int_tableau__finalsite_student_scaffold.sql` for both). Finalsite
can carry two concurrent academic years of live student data at once — students
and regions roll over on their own uncoordinated timeline — so there's no
reliable signal in the ingested data itself for "which year is current now."
Unlike PowerSchool's `var("current_academic_year")`, which bumps on a
predictable July 1 cadence, SRE's recruitment-cycle timeline is fluid — there is
no fixed date to key an automatic bump off of. **Always confirm the new year
with SRE (or by reading the goals sheet directly) before changing anything below
— don't infer it from a calendar date or from ingestion data.**

**Step 0 — pre-flight: confirm the sheets are actually ready for the new year.**
Toggling the literal before the source sheets carry the new year's data doesn't
error — it silently zeroes out or truncates the pipeline (an `inner join` scoped
to a year with no rows just returns nothing). Check both, and don't proceed
until both are resolved:

1. **`status_crosswalk` has config for the new year:**

   ```sql
   select count(*) as row_count
   from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__status_crosswalk
   where file_year = <new_year>
   ```

   If `0`, **stop** — the crosswalk sheet's detailed-status → category mapping
   is institutional judgment with no source of truth to derive it from (same
   reason its own rollover is a manual process, not a generator — see the note
   at the end of "Rollover / maintenance generators" above). An analyst must add
   the new year's rows to the sheet before the toggle proceeds; toggling first
   would make `latest_status_calc`'s `inner join` (and every other site below)
   silently return zero rows for the new year.

2. **`school_scaffold` has its `-1` rows for the new year, for every
   currently-existing non-Miami school:** run the `-1` candidate-row generator
   above, but with `<new_year>` substituted for `2026` in both places (the
   generator's own hardcoded year is a pre-toggle artifact — it's still pointed
   at the outgoing year until you do this substitution). For a brand-new
   academic year the sheet typically has **zero** rows yet, so this isn't a
   partial-gap check — the generator's full output _is_ the complete `-1` row
   set the new year needs. Since the PowerSchool builder can never produce `-1`
   rows (structural, not a gap that closes on its own), don't just report that
   gaps exist: **run the query now and hand the user its full result as a
   ready-to-paste block** (plain delimited rows in a fenced code block, one row
   per line, matching the "Goals-sheet gap-row generator" batch-delivery
   convention — not a markdown table), so they can paste it directly into
   `stg_google_sheets__finalsite__school_scaffold` before or alongside the
   toggle. Leaving this until "later" means every affected school's
   `School`-granularity goal rollup goes silently missing from the scaffold the
   moment the toggle lands.

Only once both checks are clean — status_crosswalk has real rows for
`<new_year>`, and the pasted `-1` rows are confirmed in the sheet — proceed to
the file edits below.

**Files to edit** — every occurrence is marked
`-- finalsite year toggle: see skill` (or the block-comment form) immediately
above or beside the literal:

- `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql`
  (2 occurrences — `powerschool_scaffold`'s `academic_year` literal and
  `gsheet_scaffold`'s `where` filter)
- `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql`
  (1 occurrence — `latest_status_calc`'s `where` filter)
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql`
  (2 occurrences — the `School` and `School/Grade Level` goal CTEs)
- `src/dbt/kipptaf/tests/test_int_finalsite__status_order_matches_crosswalk_ranking.sql`
  (1 occurrence — `crosswalk_ranking`'s `where` filter)
- This file (1 occurrence — the `-1` candidate-row generator query above)

In each, replace the old year literal with the new one (e.g. `2026` → `2027`).
None of these read from a shared var — each is an independent literal, by design
(see "Why this is hardcoded" above), so every site must be changed individually.
Grep to confirm you found them all:

```bash
grep -rn "finalsite year toggle" src/dbt/kipptaf .claude/skills/fresh-dashboard
```

Build and verify after all changes:

```bash
uv run dbt build \
  --select int_finalsite__enrollment_scaffold int_tableau__finalsite_student_scaffold \
    rpt_tableau__fresh_dashboard_progress_to_goals \
    test_int_finalsite__status_order_matches_crosswalk_ranking \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state target/prod
```

**When to make the change:** whenever SRE says the recruitment cycle has rolled
over — not on a fixed schedule. There is no "revert" step the way
gradebook-audit's summer toggle has; this is a one-directional bump forward each
time SRE's cycle advances.

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
