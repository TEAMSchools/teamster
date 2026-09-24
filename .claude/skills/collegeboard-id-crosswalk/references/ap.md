# AP — ingest, crosswalk match, and pipeline check

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
This file is the runbook; that doc is the "why." PII and the reasons IDs go
missing are in [SKILL.md](../SKILL.md).

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

Compile
[`src/dbt/kipptaf/analyses/collegeboard_ap_codes_completeness.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_codes_completeness.sql)
(`uv run dbt compile --select "path:analyses/collegeboard_ap_codes_completeness.sql" --project-dir src/dbt/kipptaf --target prod`)
and run the compiled SQL
(`target/compiled/kipptaf/analyses/collegeboard_ap_codes_completeness.sql`) via
the BigQuery MCP.

If it returns any rows: for each missing code, look up its meaning by fetching
(reading the actual document, not trusting a search-result summary) the current
College Board "AP Student Datafile for Schools and Districts [Year] Layout
Format" PDF at `apcentral.collegeboard.org`. Hand the user the missing code, its
looked-up description, and the direct sheet URL:
`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`
(tab `src_collegeboard__ap_codes`) so they can add it manually — no Sheets write
access here.

## Phase 3: AP course tagging check

Compile
[`src/dbt/kipptaf/analyses/collegeboard_ap_course_tagging.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_course_tagging.sql)
(`uv run dbt compile --select "path:analyses/collegeboard_ap_course_tagging.sql" --project-dir src/dbt/kipptaf --target prod`)
and run the compiled SQL via the BigQuery MCP.

Any row returned is a PowerSchool course-setup gap — flag it unconditionally
(regardless of whether it happens to matter to this cycle's matching). If found,
identify the owning region/district with the follow-up query in that file's
comments, and hand the finding to whoever owns PowerSchool course setup for that
region. No write access to PowerSchool here.

## Phase 4: Pre-audit summary

Get cheap counts before running anything expensive. "The relevant admin year" is
the `enrollment_school_year` of whatever raw file Phase 1 just confirmed is
fresh — if you didn't just ingest a specific file this run (e.g. you're
re-running the audit later), use the most recent `enrollment_school_year`
present in `stg_collegeboard__ap`. Don't guess a year from ambient context
without checking one of these two sources first.

- Total raw students: `stg_collegeboard__ap` row count for that admin year.
- Total exam scores: `int_collegeboard__ap_unpivot` row count for the same year.
- Gap count:
  `select count(*) from kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`.
  **This count has no year filter** — the underlying audit table carries no year
  column, so it's a global count of every currently-unresolved gap across all
  admin years, not scoped to the year above. Say so explicitly rather than
  implying it's year-scoped like the other two counts.

Present as: "The raw AP file has _N_ students resolving to _M_ exam scores for
[year]. Separately, _G_ College Board IDs are unresolved in the crosswalk across
all years." Then ask: "Ready for me to run the matching audit against
PowerSchool?" **Don't proceed without confirmation.**

## Phase 5: Run the tiered match

Once approved, compile
[`src/dbt/kipptaf/analyses/collegeboard_ap_tiered_crosswalk_match.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_tiered_crosswalk_match.sql)
(`uv run dbt compile --select "path:analyses/collegeboard_ap_tiered_crosswalk_match.sql" --project-dir src/dbt/kipptaf --target prod`)
and run the compiled SQL via the BigQuery MCP. This already includes the Tier
C/D corroboration checks (gender hard-gate, course-enrollment informational
annotation) — see the comments in that file for the full tier/corroboration
logic.

## Phase 6: Tier breakdown

Present counts per tier (how many resolved at Tier A/B, C, D, via tiebreak), how
many `flagged_for_review` (gender mismatch), and how many `no_match`. Ask:
"Ready to start copy-pasting matches into the sheet?" **Don't proceed without
confirmation.**

## Phase 7: Delivery

Write every `resolved` row to one tab-separated file in the session scratchpad,
`College_Board_ID<tab>PowerSchool_Student_Number`, no header, and hand it over
per _Handing rows to the user_ in [SKILL.md](../SKILL.md): destination
`src_collegeboard__ap_id_crosswalk`, appended below the last filled row. If any
row is Tier C/D, show a small markdown review table in chat first (tier tag,
course-enrollment note) — for eyeballing, not for pasting.

Present `flagged_for_review` rows (if any) separately as a markdown table (CB
first/last/gender vs. PS first/last/gender) for the user to decide on
individually — these never go in the paste file.

Present `no_match` rows (if any) as a single markdown table (CB first/last/DOB)
— see Phase 12.

## Phase 8: User pastes

The user pastes the file into the sheet. No tool here can write to Sheets
directly.

## Phase 9: Post-paste reconciliation

Once the file is pasted, watch
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

Once the sheet reconciles cleanly, compile and run (via the BigQuery MCP)
[`src/dbt/kipptaf/analyses/collegeboard_ap_downstream_lineage_summary.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_downstream_lineage_summary.sql):

```bash
uv run dbt compile --select "path:analyses/collegeboard_ap_downstream_lineage_summary.sql" \
  --project-dir src/dbt/kipptaf --target prod \
  --vars '{current_academic_year: <target_year>}'
```

(omit `--vars` to default to the network's current cycle) and present the
before/after count summary across crosswalk sheet →
`int_collegeboard__ap_unpivot` → dashboard.

If counts don't reconcile, compile and run
[`collegeboard_ap_downstream_lineage_missing_rows.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_downstream_lineage_missing_rows.sql)
(same `--vars` pattern) to find exactly which rows are missing, then
[`collegeboard_ap_downstream_lineage_root_cause.sql`](../../../../src/dbt/kipptaf/analyses/collegeboard_ap_downstream_lineage_root_cause.sql)
-- passing the missing student numbers it surfaced via
`--vars '{missing_student_numbers: [...], current_academic_year: <target_year>}'`
-- to distinguish a PowerSchool tagging gap from the known dashboard
join-structure limitation, tracked in
[#4391](https://github.com/TEAMSchools/teamster/issues/4391).

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
   noise), that's a signal a new tier belongs in
   `collegeboard_ap_tiered_crosswalk_match.sql` — the same way Tiers C and D
   were derived during design. Genuinely one-off cases (student really isn't in
   PowerSchool) stay manual.

This is diagnostic, not a promise to keep expanding tiers forever — the goal is
a small manual-review bucket and evidence-based future additions.

## Phase 13: Pipeline QA and the KIPP Forward summary

Run _Pipeline QA after a crosswalk update_ in [SKILL.md](../SKILL.md).
