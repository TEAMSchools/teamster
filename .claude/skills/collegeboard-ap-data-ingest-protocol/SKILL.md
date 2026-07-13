---
name: collegeboard-ap-data-ingest-protocol
description:
  Use when resolving gaps in the College Board AP ID crosswalk, when new AP
  scores aren't showing up on the AP assessment / CARAT dashboard, when
  stg_collegeboard__ap hasn't picked up a new AP score file drop, or when
  auditing the AP codes/course-crosswalk sheets for completeness.
---

# College Board AP Data Ingest Protocol

## Overview

Every AP admin year, new scores land in `stg_collegeboard__ap` but silently fail
to reach `rpt_tableau__ap_assessment_dashboard` (the CARAT dashboard) for one of
four reasons: the staging table hasn't picked up the new file, new students
aren't in the CB-ID-to-PowerSchool crosswalk sheet yet, the
codes/course-crosswalk sheets are missing an entry, or a crosswalk fix doesn't
fully propagate downstream. This skill walks all four, in order, with the human
approving every risky action and every batch of data before it moves.

**Full design rationale and validation evidence:**
`docs/superpowers/specs/2026-07-13-collegeboard-ap-pipeline-audit-design.md`.
This file is the runbook; that doc is the "why."

## PII — read this before running anything

Crosswalk-matching results (Phases 4-8) include student names, DOB, and gender.
**Never write these to any file that gets committed to git** — issue, PR, commit
message, or any file under version control. Chat/terminal output only. The
codes-completeness, AP-course-tagging, and downstream-lineage checks carry no
PII (codes, course names, aggregate counts) — no special handling needed for
those.

## Why crosswalk gaps happen (say this to the user)

A College Board ID can be missing from the crosswalk sheet for two reasons: a
first-time AP tester (no ID ever existed to add), or a student with a second CB
account for this admin (College Board's merge process is too tedious for KTAF to
pursue — the fix is just adding the new ID as another mapping to the same
`student_number`). Both resolve identically (add the row) — say this out loud
when presenting results so a "new" ID doesn't read as something having gone
wrong.

## Phase 1: Ingestion check

Compare materialization timestamps via `get_asset_health` /
`get_asset_materializations`: raw `kipptaf/collegeboard/ap` (partitioned by
school × school_year) vs. staging `kipptaf/collegeboard/stg_collegeboard__ap`.

If a raw partition materialized more recently than staging's last
materialization, staging is stale — most likely blocked by
`stg_collegeboard__ap`'s automation condition, whose partition range extends to
`CURRENT_FISCAL_YEAR.fiscal_year + 1`, a partition that's always unmaterialized
and trips the condition's `not (any_deps_missing)` gate. This recurs every year
until that automation condition itself is fixed (separate issue, not this
skill's job).

**Always ask before launching anything.** Preview with
`launch_run(..., confirm=False)`, explain to the user why (which partitions are
newer, and that the automation condition is blocking the rebuild), then fire
with `confirm=True` only after explicit approval. Never skip the ask, even
though this is expected to recur annually.

After the run succeeds, re-check asset health. `int_collegeboard__ap_unpivot`
doesn't need a separate manual trigger — it rematerializes on its own via the
automation condition once `stg_collegeboard__ap` succeeds.

Only proceed to Phase 2 once staging is confirmed fresh.

## Phase 2: Codes completeness check

Run [`queries/01-codes-completeness.sql`](queries/01-codes-completeness.sql).

If it returns any rows: for each missing code, look up its meaning by fetching
(reading the actual document, not trusting a search-result summary) the current
College Board "AP Student Datafile for Schools and Districts [Year] Layout
Format" PDF at `apcentral.collegeboard.org`. Hand the user the missing code, its
looked-up description, and the direct sheet URL:
`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`
(tab `src_collegeboard__ap_codes`) so they can add it manually — no Sheets write
access here.

## Phase 3: AP course tagging check

Run [`queries/02-ap-course-tagging.sql`](queries/02-ap-course-tagging.sql).

Any row returned is a PowerSchool course-setup gap — flag it unconditionally
(regardless of whether it happens to matter to this cycle's matching). If found,
identify the owning region/district with the follow-up query in that file's
comments, and hand the finding to whoever owns PowerSchool course setup for that
region. No write access to PowerSchool here.

## Phase 4: Pre-audit summary

Get cheap counts before running anything expensive:

- Total raw students: `stg_collegeboard__ap` row count for the relevant admin
  year.
- Total exam scores: `int_collegeboard__ap_unpivot` row count for the same year.
- Gap count:
  `select count(*) from kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`.

Present as: "The raw AP file has _N_ students resolving to _M_ exam scores. Of
those, _G_ aren't in the crosswalk yet." Then ask: "Ready for me to run the
matching audit against PowerSchool?" **Don't proceed without confirmation.**

## Phase 5: Run the tiered match

Run
[`queries/03-tiered-crosswalk-match.sql`](queries/03-tiered-crosswalk-match.sql)
once approved. This already includes the Tier C/D corroboration checks (gender
hard-gate, course-enrollment informational annotation) — see the comments in
that file for the full tier/corroboration logic.

## Phase 6: Tier breakdown

Present counts per tier (how many resolved at Tier A/B, C, D, via tiebreak), how
many `flagged_for_review` (gender mismatch), and how many `no_match`. Ask:
"Ready to start copy-pasting matches into the sheet?" **Don't proceed without
confirmation.**

## Phase 7: Batch-by-batch delivery

Present `resolved` rows in batches of 20, **as a plain delimited block in a
fenced code block** (`College_Board_ID<tab>PowerSchool_Student_Number`, one pair
per line) — not a markdown table, so it pastes cleanly into two Sheet columns
without pipe/dash characters riding along. If a batch contains any Tier C/D
rows, put a small markdown review table (tier tag, course-enrollment note)
immediately above the paste block for eyeballing — not for pasting.

After each batch, ask "Ready for the next batch?" and wait — **never dump all
batches in one message.**

Present `flagged_for_review` rows (if any) separately, after all `resolved`
batches, as a markdown table (CB first/last/gender vs. PS first/last/gender) for
the user to decide on individually — these never go in a paste block.

Present `no_match` rows (if any) as a single markdown table (CB first/last/DOB)
— see Phase 12.

The Google Sheet itself:
`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`
(tab `src_collegeboard__ap_id_crosswalk`).

## Phase 8: User pastes

The user manually pastes each batch's rows into the Google Sheet — as they go,
or after the last batch, whichever they prefer. No tool here can write to Sheets
directly.

## Phase 9: Post-paste reconciliation

Once the last batch is delivered, watch
`stg_google_sheets__collegeboard__ap_id_crosswalk`'s row count (Dagster asset
health, or a direct BigQuery row count) until it increases by the number of
resolved rows generated. Tell the user explicitly that a reconciliation check is
about to run, then compare the generated `resolved` list against the actual new
rows in that table:

- **Missing rows** — a generated pair that never made it in.
- **Duplicate rows** — the same `College_Board_ID` appearing more than once,
  possibly with different student numbers.
- **Incorrect rows** — a `College_Board_ID` present with a different
  `student_number` than generated.

## Phase 10: Downstream lineage verification

Once the sheet reconciles cleanly, run
[`queries/04-downstream-lineage.sql`](queries/04-downstream-lineage.sql)
(substituting the target academic year) and present the before/after count
summary across crosswalk sheet → `int_collegeboard__ap_unpivot` → dashboard. If
counts don't reconcile, use the file's follow-up queries to find exactly which
rows are missing and why (a PowerSchool tagging gap vs. the known dashboard
join-structure limitation, tracked in
[#4391](https://github.com/TEAMSchools/teamster/issues/4391)).

## Phase 11: Final gap recount

Re-run the Phase 4 gap-count query to confirm it dropped to the expected
residual (0 for a fully-resolved run, or the remaining `no_match` count
otherwise).

## Phase 12: No-match root cause review

For whatever remains in `no_match`, don't just hand it over — characterize _why_
it didn't match, in chat only (never write real names/DOB to a committed file):

1. Loosen the DOB constraint (any academic_year, not just the gap's own year)
   and look for the same last_name/token — reveals students who exist under a
   different year.
2. Loosen the last_name constraint (same DOB, any last_name in the same year) —
   reveals a name recorded very differently.
3. If a case reveals a new deterministic, generalizable pattern (not one-off
   noise), that's a signal a new tier belongs in `03-tiered-crosswalk-match.sql`
   — the same way Tiers C and D were derived during design. Genuinely one-off
   cases (student really isn't in PowerSchool) stay manual.

This is diagnostic, not a promise to keep expanding tiers forever — the goal is
a small manual-review bucket and evidence-based future additions.
