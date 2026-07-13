# College Board AP ID Crosswalk Gap Resolution — Design Spec

**Date:** 2026-07-13 **Issue:**
[#4390](https://github.com/TEAMSchools/teamster/issues/4390) **Status:**
Approved

## Problem

`stg_google_sheets__collegeboard__ap_id_crosswalk` maps College Board AP IDs
(`College_Board_ID`) to PowerSchool student numbers
(`PowerSchool_Student_Number`). New AP takers each year aren't in the sheet yet,
so their scores can't resolve to a student and are silently dropped from
`rpt_tableau__ap_assessment_dashboard`. The dbt test
`int_collegeboard__ap_unpivot__crosswalk_resolves` catches this
(`kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`
lists the unresolved `ap_number_ap_id` values), but resolving each one has been
a manual, one-student-at-a-time BigQuery lookup (plug in first name, last name,
and DOB, rerun, repeat) — 173 times for the 2025-2026 admin.

There's also an ingestion-side gap upstream of the crosswalk. Raw AP files
dropped to the Couchdrop/Google Drive folder land in the partitioned
`kipptaf/collegeboard/ap` asset, but `stg_collegeboard__ap`'s automation
condition currently includes a `school_year = N+1` partition in its range
(extending to `CURRENT_FISCAL_YEAR.fiscal_year + 1`), which is always
unmaterialized — that trips the condition's `not (any_deps_missing)` gate and
blocks `stg_collegeboard__ap` from auto-rebuilding after a new file lands. This
will recur every year until the automation condition itself is fixed (tracked
separately), so until then, someone has to notice new raw data sitting
unpicked-up and manually trigger the `stg_collegeboard__ap` materialization.

## Goals

- Detect when raw AP data has landed but `stg_collegeboard__ap` hasn't picked it
  up yet, and — with the user's explicit approval — trigger the materialization.
- Replace the one-at-a-time lookup with a single bulk query that matches most
  gaps automatically.
- Surface results as chat tables (batched, easy to copy/paste in the VS Code
  terminal) — no scratch files.
- Package the workflow as a reusable skill so this doesn't require re-deriving
  the query every year.

## Out of Scope

- Writing directly to the Google Sheet (no available tool can edit Sheet cells —
  Drive MCP only creates/reads files).
- Fuzzy/similarity name matching (edit distance, phonetic matching, etc.). Only
  deterministic transforms (case-fold, diacritic-strip, hyphen/space
  token-splitting, exact ±1-year day-count comparison) are used.
- Resolving a residual `no_match` case automatically — whatever's left after all
  tiers still needs a human to investigate. (For the validated 2025-2026
  backlog, that residual was zero — see below — but future years' causes may
  differ.)
- Detecting or flagging _why_ a given crosswalk gap exists (see below) on a
  per-row basis, and any Ops escalation or College Board account-merge workflow
  — the action taken (add a new `CB ID → student_number` row) is the same
  regardless of cause, so there's nothing to branch on.

## Why Crosswalk Gaps Happen

A `College_Board_ID` can be missing from the crosswalk sheet for two distinct
reasons:

1. **First-time tester** — the student has never taken an AP exam with a CB
   account before, so no ID existed to add previously.
2. **Duplicate CB account** — the student already has a crosswalk entry under a
   _different_ `College_Board_ID`, but somehow ended up with a second CB account
   (and therefore a second ID) for this admin. College Board's account-merge
   process is long and tedious enough that KTAF doesn't pursue it — the
   practical fix is just adding the new ID as another mapping to the same
   `student_number`.

Both cases resolve identically (add the row), so the skill doesn't need to
distinguish them to act — but the skill should say this explanation out loud
when it presents results, so the user understands what's happening and why,
rather than wondering if a "new" ID means something went wrong.

## Ingestion Refresh Design

Before touching the crosswalk at all, the skill checks whether
`stg_collegeboard__ap` actually reflects the latest raw drop:

1. Compare materialization timestamps: `get_asset_health` /
   `get_asset_materializations` on the raw `kipptaf/collegeboard/ap` partitions
   (per school × school_year) vs. the staging asset
   `kipptaf/collegeboard/stg_collegeboard__ap`.
2. If a raw partition materialized more recently than `stg_collegeboard__ap`'s
   last materialization, staging is stale — most likely blocked by the
   future-partition automation-condition gap described above.
3. **Always ask before launching anything.** Preview the run (`launch_run` with
   `confirm=False`) and explain to the user why it's needed (which partitions
   are newer, and that the automation condition is blocked by the unmaterialized
   future-year partitions) before firing it with `confirm=True`. Never trigger a
   production materialization without that explicit go-ahead, even though this
   is expected to recur annually.
4. After the run succeeds, re-check asset health to confirm
   `stg_collegeboard__ap` picked up the new data. `int_collegeboard__ap_unpivot`
   does not need a separate manual trigger — it rematerializes on its own via
   the automation condition once `stg_collegeboard__ap` succeeds (observed
   behavior from the 2025-2026 fix).
5. Only once staging is confirmed fresh does the skill move on to the
   crosswalk-gap matching below.

## Matching Design

All matching is scoped per-gap to `academic_year = enrollment_school_year` (the
CB record's own year) against
`kipptaf_powerschool.base_powerschool__student_enrollments` — no manual year
parameter needed, so the same query works unchanged in future years.

1. **Tier A** — exact match on `date_of_birth` + `last_name` (case-folded).
2. **Tier B** — same DOB, but `last_name` compared with diacritics stripped on
   both sides via `REGEXP_REPLACE(NORMALIZE(x, NFD), r"\pM", "")` (handles CB's
   ASCII-only file format vs. accented PowerSchool names, e.g. `Peña` → `Pena`).
3. **Tier C** — same DOB, but `last_name` compared by token instead of whole
   string: split on hyphens/spaces on both sides (case-fold + diacritic-strip
   each token), match if any token is shared. Handles compound/hyphenated
   surnames recorded inconsistently between CB and PowerSchool — e.g. a CB
   single-word surname vs. a PS surname with a name-suffix (`Jr`, `II`, ...)
   appended, or a two-word surname where CB kept only one half and PS kept both
   (in either direction), or a hyphen on one side vs. a space on the other.
   Still a deterministic string transform, not similarity scoring.
4. **Tier D** — DOB exactly 365 or 366 days apart
   (`ABS(DATE_DIFF(...)) IN (365, 366)` — equivalent to "same month/day, year
   off by exactly one" accounting for leap years) **and** both `first_name` and
   `last_name` match exactly (post case-fold/diacritic-strip). Handles a
   DOB-year transcription mismatch between CB and PowerSchool. Requires both
   names to match (not just last name) since loosening the DOB itself raises
   collision risk more than Tier C does.
5. **Tiebreak** — when Tiers A-D together yield more than one distinct
   `student_number` for a gap, narrow further using `first_name` (same case-fold
   / diacritic-strip logic, plus stripping non-alphanumeric characters so an
   apostrophe in a name doesn't block the match either).

Each gap buckets into:

| Bucket     | Meaning                                             | Validated count (2025-2026) |
| ---------- | --------------------------------------------------- | --------------------------- |
| `resolved` | Exactly one PS candidate after Tiers A-D + tiebreak | 173                         |
| `no_match` | No PS candidate found at all                        | 0                           |

Query validated live against the full 173-gap backlog during design (see
conversation, PII redacted here per repo policy — real names/DOBs are not
committed to git). Tiers A/B alone resolved 157 directly + 3 via tiebreak (one
tiebreak pair was same-DOB/same-surname twins, correctly split by first name).
The remaining 13 all initially landed in `no_match`; reviewing each one by hand
surfaced two deterministic, generalizable causes (9 compound/ hyphenated-surname
cases → Tier C, 3 DOB-year-off-by-one cases → Tier D, 1 case that turned out to
already be covered by Tier C once re-checked carefully). Adding Tiers C and D
resolved all 13, and — verified by comparing old vs. new `student_number` for
every gap that already had a clean Tier A/B match — introduced zero regressions.

This is not a guarantee that every future year's backlog reaches 0 `no_match` —
see "Continuous Improvement" below.

## Continuous Improvement — No-Match Root Cause Review

Whatever remains in `no_match` after Tiers A-D is not a dead end. Before handing
that bucket to the user as "needs manual investigation," the skill should try to
characterize _why_ each one didn't match — the same process used during design
(with results discussed in chat, never written to a committed file, since it
necessarily involves real student names):

1. Loosen the DOB constraint (any academic_year, not just the gap's own year)
   and look for the same last_name/token — reveals students who exist in PS
   under a different year (e.g., withdrawn, or an enrollment-year mismatch).
2. Loosen the last_name constraint (same DOB, any last_name in the same year) —
   reveals a name that changed or was recorded very differently.
3. If a case reveals a new deterministic, generalizable pattern (not one-off
   noise), that's a signal to add another tier — the same way Tier C and D were
   derived from the 2025-2026 backlog. If it's genuinely one-off (e.g., the
   student really isn't in PowerSchool at all), it stays a manual case.

This step is diagnostic, not a promise to keep expanding tiers forever — the
goal is to keep the manual-review bucket small and to make future additions
evidence-based rather than speculative.

## Output Format

No files. Results are presented as markdown tables directly in chat, delivered
progressively rather than all at once (see Workflow) so the user doesn't lose
track of where they are:

- A one-line **pre-audit summary** (raw student count, exam-score count, gap
  count) before running the match.
- A **tier breakdown** (counts per Tier A/B/C/D + tiebreak + residual
  `no_match`) after running the match, before showing any data.
- `resolved`: one batch of 20 rows at a time (`College_Board_ID`,
  `PowerSchool_Student_Number`) — ready to copy straight into the Google Sheet.
  The skill waits for the user to confirm before showing the next batch.
- residual `no_match` (if any): a single table with CB first/last name and DOB
  so the user can investigate — small enough (single digits to low teens
  historically) not to need batching.

## PII Handling

Results include student names and DOB (indirect/direct identifiers). Per repo
policy this stays in chat/terminal only — never pasted into a GitHub
issue/PR/comment, Slack, or Asana. The skill's documentation must repeat this
constraint explicitly since it's meant to be picked up by future sessions.

## Workflow

1. **Ingestion check.** Check whether raw `kipptaf/collegeboard/ap` partitions
   materialized more recently than `stg_collegeboard__ap`. If so, explain why to
   the user and ask approval to launch a `stg_collegeboard__ap` run; only
   proceed once approved and the run succeeds.
2. **Pre-audit summary.** Before running the tiered match, get cheap counts:
   total students in the raw file for the relevant admin (`stg_collegeboard__ap`
   row count for the year), total exam scores (`int_collegeboard__ap_unpivot`
   row count for the year), and the gap count (from
   `kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`).
   Present as: "The raw AP file has _N_ students resolving to _M_ exam scores.
   Of those, _G_ aren't in the crosswalk yet." Ask: "Ready for me to run the
   matching audit against PowerSchool?" Don't proceed until the user confirms.
3. **Run the tiered match** (Tiers A-D + tiebreak) against
   `kipptaf_powerschool.base_powerschool__student_enrollments` once approved.
4. **Tier breakdown.** Present counts per tier (how many resolved at Tier A, B,
   C, D, via tiebreak, and how many remain `no_match`). Ask: "Ready to start
   copy-pasting matches into the sheet?" Don't proceed until confirmed.
5. **Batch-by-batch delivery.** Present `resolved` one batch of 20 at a time.
   After each batch, ask "Ready for the next batch?" and wait for confirmation
   before showing the next one — never dump all batches in a single message.
6. User manually pastes each batch's rows into the Google Sheet as they go (or
   after the last batch — whichever the user prefers).
7. **Post-paste reconciliation.** Once the last batch has been delivered,
   monitor for the Google Sheet's sync to land: watch
   `stg_google_sheets__collegeboard__ap_id_crosswalk`'s row count (via Dagster
   asset health / BigQuery) until it increases by the number of resolved rows
   generated. Once it does, tell the user explicitly that a reconciliation check
   is about to run, then compare the generated `resolved` list against the
   actual new rows in that table to catch:
   - **missing rows** — a generated pair that never made it in (paste error,
     lost row)
   - **duplicate rows** — the same `College_Board_ID` appearing more than once,
     possibly mapped to different student numbers
   - **incorrect rows** — a `College_Board_ID` present but with a different
     `student_number` than generated (transcription/copy-paste error)
8. User (or the agent, on request) re-runs the audit query to confirm the gap
   count dropped to the expected residual (0 for a fully-resolved run, or the
   remaining `no_match` count otherwise).
9. **No-match root-cause review** (if any remain) — see "Continuous Improvement"
   above.

## Skill Packaging

New skill: `.claude/skills/collegeboard-ap-crosswalk-gaps/SKILL.md`.

- **Triggers**: "resolve CB AP ID crosswalk gaps," "unmatched college board
  ids," "ap_id_crosswalk missing students," "new AP scores aren't showing up on
  the dashboard," "push the AP file to Dagster," or any question about students
  missing from the AP score dashboard due to crosswalk or ingestion gaps.
- **Contents**: the raw-vs-staging staleness check and approval-gated
  `stg_collegeboard__ap` run steps; the pre-audit-summary and tier-breakdown
  confirmation gates; the Tier A-D + tiebreak SQL (parameter-free, self-scoping
  by year); the "why crosswalk gaps happen" explanation to surface alongside
  results; the one-batch-at-a-time chat-table delivery (batches of 20, confirm
  between each); the post-paste reconciliation check against
  `stg_google_sheets__collegeboard__ap_id_crosswalk`
  (missing/duplicate/incorrect rows); the no-match root-cause review process;
  and the PII-stays-local reminder (including: never write real student
  names/DOBs into a committed file — chat/terminal only).
