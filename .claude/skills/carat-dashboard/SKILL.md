---
name: carat-dashboard
description: >-
  Use when any question or task touches the CARAT dashboard (College Admission
  Readiness Assessments Tracker) or its lineage. Triggers: adding Illuminate
  practice SAT/ACT assessments for a new administration, generating or auditing
  raw-to-scale-score rows for the practice conversion or scaffold sheets, a
  practice score not appearing on the dashboard, goal thresholds not matching, a
  request to change a goal percentage or target line, academic-year rollover, or
  working on int_assessments__college_assessment_practice,
  int_tableau__college_assessment_roster_scores,
  rpt_tableau__college_assessment_dashboard_current, or _benchmark_calcs and
  their upstream models.
---

# CARAT Dashboard Data Model

## Always read first

**Read the first two sections of
[`docs/models/carat-dashboard-data-model.md`](../../../docs/models/carat-dashboard-data-model.md)
before answering anything** — _What is CARAT?_ and _Models behind the workbook_.
Stop at the third `##` heading (about line 74; find it with
`grep -n '^## ' docs/models/carat-dashboard-data-model.md`). Not optional, and
not only for deep questions. Read further into the doc when a route below names
a section. Those two sections establish what the dashboard actually reports, who
reads it, and which models feed which view. Without that, it is easy to answer
confidently about the wrong pipeline: CARAT has two, official and practice, and
confusing them is the most common source of wrong answers.

It is also authoritative for the shipped models, which the design spec is not —
several things landed differently from the spec, and the doc records the
deviations.

Also relevant:

- Design spec:
  [`docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md`](../../../docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md)
  — authoritative for the designation/conversion split, the two-section SAT
  total, and which pre-existing defects were deliberately left unfixed
- Exposure: `college_admission_readiness_assessments_tracker_carat`

## Route by task

Read the one file for your task. Every sheet change also follows _Handing sheet
rows to the user_, below.

| Task                                                                         | Read                                                                                                                                                           |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Change a goal percentage ("the Foundation moved the target, update Tableau") | [references/goals.md](references/goals.md) — a sheet edit, never code                                                                                          |
| Goal thresholds, cut scores, or the strategy doc's topline goals             | [references/goals.md](references/goals.md)                                                                                                                     |
| Counting attempts, or hunting duplicate kippadb records                      | [references/goals.md](references/goals.md)                                                                                                                     |
| Add practice SAT/ACT assessments for a new administration                    | [references/practice-assessments.md](references/practice-assessments.md)                                                                                       |
| Audit conversion-tab rows, or a practice score is not appearing              | [references/practice-assessments.md](references/practice-assessments.md)                                                                                       |
| Add PSAT 8/9 or PSAT 10 practice conversions                                 | [references/practice-assessments.md](references/practice-assessments.md), then [references/psat-college-board.md](references/psat-college-board.md) for Step 3 |
| Add or check scaffold-tab rows                                               | [references/practice-assessments.md](references/practice-assessments.md)                                                                                       |
| Rebuild the Expected Assessments seasons tab                                 | [references/expected-assessments.md](references/expected-assessments.md)                                                                                       |
| Editing a CARAT model, or a result looks wrong and nothing above fits        | [references/gotchas.md](references/gotchas.md)                                                                                                                 |

### Why did this number change

These questions each have a documented answer in the reference doc with measured
figures. Cite the doc rather than re-deriving:

| Question                                               | Section                                              |
| ------------------------------------------------------ | ---------------------------------------------------- |
| An attempt count is lower than it was                  | _Why participation attempt counts change_            |
| A student's SAT attempts dropped by one                | same — 86 students, the Camden 2027 duplicate load   |
| An attempt count is higher than it was                 | same — counts are no longer scoped to enrolled years |
| The roster returns two rows for one student            | same — `test_type` is in the grain                   |
| A percent-met or benchmark total moved                 | _Why the benchmark dashboard's totals change_        |
| Two records for one sitting, or an inflated row count  | _Known issue — duplicate kippadb test records_       |
| A goal line moved, or does not match the strategy doc  | _The rebuilt goals tab — what shipped_               |
| `_over_time` shows two rows per student for one goal   | same — resolved by the `_over_time` goal columns     |
| An over-time percent-met moved                         | _Why the over-time dashboard's numbers change_       |
| PSAT 8/9 HS Grad-Ready rose for 2028 or 2029           | same — the 800 to 790 threshold, 10 students each    |
| A 2014, 2015 or 2022 cohort's percent-met rose         | same — the 27 restored scores                        |
| A score reads `No Data` in one view but not another    | _Known issue — `rn_highest = 1` discards scores_     |
| Every school shows the same goal line                  | _Why the current dashboard's numbers change_         |
| An attempts percentage roughly halved or doubled       | same — the attempts denominator is test takers       |
| The board metrics view lost its goal line              | same — Board is retired, goals are now uniform       |
| `_current` reports a year behind, or two years at once | same — four branches hardcoded AY2025                |

Each of those carries the measured numbers, so an answer can cite them instead
of re-running a comparison. If a reconciliation disagrees with the documented
figures, read the last subsection of the participation section first — the
counting fix and the Salesforce cleanup cancel each other depending on which
landed first, which is the usual reason.

## Orientation

Two separate score pipelines feed CARAT, and confusing them is the most common
source of wrong answers:

| Pipeline | Hub model                                      | `test_type` | Source                                        |
| -------- | ---------------------------------------------- | ----------- | --------------------------------------------- |
| Official | `int_assessments__college_assessment`          | `Official`  | kippadb + collegeboard                        |
| Practice | `int_assessments__college_assessment_practice` | `Practice`  | Illuminate + the conversion and scaffold tabs |

Both pipelines meet in `int_assessments__all_college_assessments`, and
`rpt_tableau__college_assessment_dashboard_benchmark_calcs` reads that hub.
Thresholds are no longer hardcoded — they come from the scaffold sheet's
`hs_grad_ready_min_score` / `college_ready_min_score`, and `EA/ED-Ready` is
retired.

Practice **does** reach the benchmark view now, and what makes that safe is
`test_type` sitting in the partition of both
`rn_highest_benchmark_aligned_scope` and `benchmark_aligned_scope_max_score`.
Never remove it. Without it a practice score competes with an official one, can
win, and shifts reported college-ready attainment network-wide. The view also
joins `expected_test_type` to the hub's `test_type`, so a practice benchmark is
never satisfied by an official result.

**This generalises to every partition and dedupe key in the lineage**, because
Official and Practice share one `score_type` vocabulary by design — the same
string means a different sitting depending on `test_type`. `_current`'s
`benchmark_tier` shipped without it in review and would have let a practice
score raise the official row's readiness band; `_roster` joined the
participation roster on `rn_lifetime = 1` alone and duplicated every row for
students with practice data; `_current`'s own `attempts` CTE had the same
defect. **When you add a `partition by`, a dedupe, or a join to the roster or
either hub, ask whether `test_type` belongs in it — the answer has been yes
every time so far**, and the failure is silent in all three cases.

## Handing sheet rows to the user

Every CARAT sheet change reaches the user in one shape:

1. A **tab-separated** file. Google Sheets splits a paste into columns only on
   tabs; comma-separated text lands entirely in column A.
2. Written to the **session scratchpad**, handed over as a clickable path the
   user opens in VS Code, selects all, copies, and pastes. Never pasted into
   chat: the chat panel turns tabs into spaces.
3. Covering the **whole block** being replaced, with the paste anchor named (A1
   with a header row, A2 without one) — not a list of cells to edit by hand.
4. Built from the **live sheet**, not a `stg_*` model: staging may be reshaped
   (the goals model is unpivoted) or stale (it is a table that has not rebuilt).
   Read the Sheets external through ADC from Python; the BigQuery MCP cannot.

After the paste, re-read the live sheet and diff it against the file.

## Scripts

All in [`scripts/`](scripts/); run with `uv run python` from the repo root.

- `build_scale_score_rows.py` — practice conversion rows from Foundation pastes.
  See [references/practice-assessments.md](references/practice-assessments.md).
- `build_expected_assessment_rows.py` — the whole Expected Assessments tab from
  a calendar spec. See
  [references/expected-assessments.md](references/expected-assessments.md).
- `dump_goals_tab.py` — the whole live Goals tab, with `--set` edits applied.
  See [references/goals.md](references/goals.md).
