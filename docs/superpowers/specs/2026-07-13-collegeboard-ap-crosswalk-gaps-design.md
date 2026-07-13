# College Board AP ID Crosswalk Gap Resolution — Design Spec

**Date:** 2026-07-13 **Issue:** none (direct branch, user declined an issue)
**Status:** Approved

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

## Goals

- Replace the one-at-a-time lookup with a single bulk query that matches most
  gaps automatically.
- Surface results as chat tables (batched, easy to copy/paste in the VS Code
  terminal) — no scratch files.
- Package the workflow as a reusable skill so this doesn't require re-deriving
  the query every year.

## Out of Scope

- Writing directly to the Google Sheet (no available tool can edit Sheet cells —
  Drive MCP only creates/reads files).
- Fuzzy/similarity name matching. Only deterministic transforms (case-fold,
  diacritic-strip) are used.
- Resolving the `no_match` bucket automatically — those need a human to
  investigate (DOB typo, name mismatch beyond diacritics, student not in PS).

## Matching Design

All matching is scoped per-gap to `academic_year = enrollment_school_year` (the
CB record's own year) against
`kipptaf_powerschool.base_powerschool__student_enrollments` — no manual year
parameter needed, so the same query works unchanged in future years.

1. **Tier A** — exact match on `date_of_birth` + `last_name` (case-folded).
2. **Tier B** — same DOB, but `last_name` compared with diacritics stripped on
   both sides via `REGEXP_REPLACE(NORMALIZE(x, NFD), r"\pM", "")` (handles CB's
   ASCII-only file format vs. accented PowerSchool names, e.g. `Peña` → `Pena`).
3. **Tiebreak** — when Tier A/B together yield more than one distinct
   `student_number`, narrow further using `first_name` (same case-fold /
   diacritic-strip logic).

Each gap buckets into:

| Bucket        | Meaning                                              | Validated count (2025-2026) |
| ------------- | ---------------------------------------------------- | --------------------------- |
| `resolved`    | Exactly one PS candidate after Tier A/B (+ tiebreak) | 157                         |
| `multi_match` | Still >1 candidate after the first-name tiebreak     | 3                           |
| `no_match`    | No PS candidate found at all                         | 13                          |

Query validated live against the current 173-gap backlog during design (see
conversation) — a single `WITH` query using the tiers above.

## Output Format

No files. Results are presented as markdown tables directly in chat:

- `resolved`: batched 20 rows at a time (`College_Board_ID`,
  `PowerSchool_Student_Number`) — ready to copy straight into the Google Sheet.
- `multi_match` and `no_match`: small enough (single digits to low teens) for
  one table each, including CB first/last name and DOB so the user can
  investigate.

## PII Handling

Results include student names and DOB (indirect/direct identifiers). Per repo
policy this stays in chat/terminal only — never pasted into a GitHub
issue/PR/comment, Slack, or Asana. The skill's documentation must repeat this
constraint explicitly since it's meant to be picked up by future sessions.

## Workflow

1. Query
   `kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`
   joined to `stg_collegeboard__ap` to get the current gap list.
2. Run the tiered match against
   `kipptaf_powerschool.base_powerschool__student_enrollments`.
3. Present `resolved` in batches of 20, then `multi_match`, then `no_match`.
4. User manually pastes `resolved` rows (and any manually-confirmed
   `multi_match` / `no_match` resolutions) into the Google Sheet.
5. User (or the agent, on request) re-runs the audit query to confirm the gap
   count dropped, and re-triggers `stg_collegeboard__ap` /
   `int_collegeboard__ap_unpivot` if the underlying data needs a rebuild.

## Skill Packaging

New skill: `.claude/skills/collegeboard-ap-crosswalk-gaps/SKILL.md`.

- **Triggers**: "resolve CB AP ID crosswalk gaps," "unmatched college board
  ids," "ap_id_crosswalk missing students," or any question about students
  missing from the AP score dashboard due to crosswalk gaps.
- **Contents**: the tiered SQL query (parameter-free, self-scoping by year), the
  bucket definitions, the chat-table output format (batches of 20 for
  `resolved`), the PII-stays-local reminder, and the paste-then-reverify
  workflow steps above.
