---
name: carat-dashboard
description: >-
  Use when any question or task touches the CARAT dashboard (College Admission
  Readiness Assessments Tracker) or its lineage. Triggers: adding Illuminate
  practice SAT/ACT assessments for a new administration, generating or auditing
  raw-to-scale-score rows for the practice conversion or scaffold sheets, a
  practice score not appearing on the dashboard, goal thresholds not matching, a
  request to change a goal percentage or target line, QA or a KIPP Forward
  summary after new official scores load, academic-year rollover, or working on
  int_assessments__college_assessment_practice,
  int_tableau__college_assessment_roster_scores,
  rpt_tableau__college_assessment_dashboard_current, or _benchmark_calcs and
  their upstream models.
---

# CARAT Dashboard Data Model

## Always read first

**Read the first two sections of
[`docs/models/carat-dashboard-data-model.md`](../../../docs/models/carat-dashboard-data-model.md)
before answering anything** — _What is CARAT?_ and _How it fits together_,
stopping at `## Terms`. Not optional, and not only for deep questions. They
establish what the dashboard reports and which models feed it. Without that, it
is easy to answer confidently about the wrong pipeline: CARAT has two, official
and practice, and confusing them is the most common source of wrong answers.

The doc is the manual for the shipped models: key ideas (attempts, benchmarks,
goals, seasons, growth), what each dashboard view shows, the supporting models,
the Google Sheets, and decisions and known issues. Read the section a route
below names. It is authoritative over the design spec, which several things
landed differently from.

Also relevant:

- Design spec:
  [`docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md`](../../../docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md)
  — authoritative for the designation/conversion split, the two-section SAT
  total, and which pre-existing defects were deliberately left unfixed
- Exposure: `college_admission_readiness_assessments_tracker_carat`

## Route by task

Read the one file for your task. Every sheet change also follows _Handing sheet
rows to the user_, below.

| Task                                                                                                    | Read                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Change a goal percentage ("the Foundation moved the target, update Tableau")                            | [references/goals.md](references/goals.md) — a sheet edit, never code                                                                                                              |
| Goal thresholds, cut scores, or the strategy doc's topline goals                                        | [references/goals.md](references/goals.md)                                                                                                                                         |
| Counting attempts, or hunting duplicate kippadb records                                                 | [references/goals.md](references/goals.md)                                                                                                                                         |
| Add practice SAT/ACT assessments for a new administration                                               | [references/practice-assessments.md](references/practice-assessments.md)                                                                                                           |
| Audit conversion-tab rows, or a practice score is not appearing                                         | [references/practice-assessments.md](references/practice-assessments.md)                                                                                                           |
| Add PSAT 8/9 or PSAT 10 practice conversions                                                            | [references/practice-assessments.md](references/practice-assessments.md), then [references/practice-psat-scoring-tables.md](references/practice-psat-scoring-tables.md) for Step 3 |
| Add or check scaffold-tab rows                                                                          | [references/practice-assessments.md](references/practice-assessments.md)                                                                                                           |
| Rebuild the Expected Assessments seasons tab                                                            | [references/expected-assessments.md](references/expected-assessments.md)                                                                                                           |
| QA official scores after a College Board ID crosswalk paste (hand-off from `collegeboard-id-crosswalk`) | [references/official-scores-qa.md](references/official-scores-qa.md)                                                                                                               |
| Add a new metric, or a threshold that isn't on the Scaffold (e.g. PSAT 10 Math ≥ 450)                   | a design change, not a sheet edit: doc _Benchmarks_ and the view's SQL; ask about an issue and brainstorming first                                                                 |
| An official PSAT or AP score is missing for a student                                                   | the `collegeboard-id-crosswalk` skill — usually an unmapped College Board ID                                                                                                       |
| An official SAT or ACT score is missing for a student                                                   | kippadb (Salesforce), not a crosswalk: CARAT reads SAT and ACT from kippadb only; KIPP Forward enters them                                                                         |
| Editing a CARAT model, or a result looks wrong and nothing above fits                                   | [references/gotchas.md](references/gotchas.md)                                                                                                                                     |

### Why did this number change

The 2026 rebuild's measured before/after figures are in
[references/rebuild-2026-changes.md](references/rebuild-2026-changes.md) (RC);
standing explanations are in the reference doc (doc). Cite them rather than
re-deriving:

| Question                                               | Where                                                                         |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| An attempt count is lower than it was                  | RC _Why participation attempt counts change_                                  |
| A student's SAT attempts dropped by one                | same — 86 students, the Camden 2027 duplicate load                            |
| An attempt count is higher than it was                 | same — counts are no longer scoped to enrolled years                          |
| The roster returns two rows for one student            | same — `test_type` is in the grain                                            |
| A percent-met or benchmark total moved                 | RC _Why the benchmark dashboard's totals change_                              |
| Two records for one sitting, or an inflated row count  | doc _Duplicate kippadb test records_                                          |
| A goal line moved, or does not match the strategy doc  | [references/goals.md](references/goals.md), and doc _Goals_                   |
| An over-time percent-met moved                         | RC _Why the over-time dashboard's numbers change_                             |
| PSAT 8/9 HS Grad-Ready rose for 2028 or 2029           | same — the 800 to 790 threshold, 10 students each                             |
| A 2014, 2015 or 2022 cohort's percent-met rose         | same — the 27 restored scores                                                 |
| A score reads `No Data` in one view but not another    | doc _`rn_highest = 1` hides some students' best scores_                       |
| Every school shows the same goal line                  | RC _Why the current dashboard's numbers change_                               |
| A current-view percentage doesn't match a count        | doc _Attempts_ — every bar divides by all students in the group               |
| The board metrics view lost its goal line              | RC _Why the current dashboard's numbers change_                               |
| `_current` reports a year behind, or two years at once | same — four branches hardcoded AY2025                                         |
| A SAT score disagrees with a College Board report      | [references/gotchas.md](references/gotchas.md) _CARAT's SAT is kippadb's SAT_ |
| Official growth is not official-to-official            | doc _Growth_                                                                  |
| Practice numbers on the roster dropped sharply         | RC _Roster scores: what the repointing changed_                               |

If a reconciliation disagrees with the documented figures, read the last
subsection of RC's participation section first — the counting fix and the
Salesforce cleanup cancel each other depending on which landed first, which is
the usual reason.

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

1. The **destination as a link plus tab name**. Every CARAT tab lives in one
   workbook,
   <https://docs.google.com/spreadsheets/d/12yqEOmyeNrvzOkmrOFnKOpsHU0L19G7zoG3b9f5cIpI>:
   `Goals`, `Expected Assessments`, `Scale Score Conversion`, `Scaffold`.
2. A **tab-separated** file. Google Sheets splits a paste into columns only on
   tabs; comma-separated text lands entirely in column A.
3. Written to the **session scratchpad**, handed over as a clickable path the
   user opens in VS Code, selects all, copies, and pastes. Never pasted into
   chat: the chat panel turns tabs into spaces.
4. Covering the **whole block** being replaced, with the paste anchor named (A1
   with a header row, A2 without one) — not a list of cells to edit by hand.
5. Built from the **live sheet**, not a `stg_*` model: staging may be reshaped
   (the goals model is unpivoted) or stale (it is a table that has not rebuilt).
   Read the Sheets external through ADC from Python; the BigQuery MCP cannot.

After the paste, re-read the live sheet and diff it against the file. A row
count that comes back short means the paste ran past the tab's named range
(`Goals`, `Expected Assessments` and `Scaffold` are read through named ranges),
and the rows beyond it are silently ignored.

## Scripts

All in [`scripts/`](scripts/); run with `uv run python` from the repo root.

- `build_scale_score_rows.py` — practice conversion rows from Foundation pastes.
  See [references/practice-assessments.md](references/practice-assessments.md).
- `build_expected_assessment_rows.py` — the whole Expected Assessments tab from
  a calendar spec. See
  [references/expected-assessments.md](references/expected-assessments.md).
- `dump_goals_tab.py` — the whole live Goals tab, with `--set` edits applied.
  See [references/goals.md](references/goals.md).
- `current_metrics_before_after.py` — the `_current` view's metrics before and
  after a score load, against goal. See
  [references/official-scores-qa.md](references/official-scores-qa.md).
