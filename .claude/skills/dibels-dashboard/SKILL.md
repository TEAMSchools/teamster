---
name: dibels-dashboard
description: >-
  Use for ANY DIBELS work -- reading, explaining, querying, modelling, goal
  setting, Tableau views, or answering a question about the numbers. Not only
  code changes: invoke it before answering anything about DIBELS, because the
  reference document it points at carries decisions that are not recoverable
  from the SQL. Triggers: the DIBELS dashboard or Literacy Dashboard, the Bright
  Spots tracker (#4952), the PM/aimline migration (#3834), benchmark completion
  tracking (#4902), aimline categories, foundation or benchmark or PM goal
  setting, the Amplify DIBELS spreadsheet, or anything touching
  int_amplify__all_assessments, int_amplify__pm_met_criteria,
  int_amplify__pm_met_criteria_aimline, int_amplify__benchmark_student_summary,
  int_students__dibels_participation_roster, rpt_tableau__dibels_dashboard,
  rpt_gsheets__dibels_bm_goals_calculations,
  rpt_gsheets__dibels_pm_goal_setting, stg_google_sheets__dibels_* or their
  lineage.
---

# DIBELS Dashboard

## Why this skill exists

T&L's source doc gives goals as **ranges** ("62 - 66%") and, starting AY2025, as
**two-or-more side-by-side population blocks** (All Students, Students with
IEPs, and MLL, whose real goal values are still outstanding -- see _MLL
population -- shipped with placeholder values_ below). The existing single-value
staging table already required someone to collapse each range to one number by
hand, applying a rule nobody wrote down. That rule is now written down (below)
and encoded in a generator script instead of memory.

## The min/max rule (verified, not guessed)

Checked grade-by-grade against `stg_google_sheets__dibels_foundation_goals` for
every Newark/Camden row across AY2024 and AY2025, zero exceptions:

- **At/Above -> the LOW end** of the range
- **Well Below -> the HIGH end** of the range
- Holds identically for MOY and EOY. The rule is **goal_type-driven, not
  period-driven** -- do not reintroduce a MOY-vs-EOY branch.

## Where to look

This file routes. Read the one page your task needs, not the whole skill. Each
page opens with a contents list -- jump to the section you need rather than
reading the page end to end.

| If you are                                                                                         | Read                                                                 |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Rolling the expectations scaffold forward a year or a season, or entering PM rounds for a new year | [references/rollover.md](references/rollover.md)                     |
| Setting, generating or pasting goals of any kind                                                   | [references/goal-setting.md](references/goal-setting.md)             |
| Editing a Google Sheet source, a named range, or `sources-external.yml`                            | [references/sheets-and-sources.md](references/sheets-and-sources.md) |
| Answering what an aimline label means, or reporting a rate against the aimline                     | [references/aimline-method.md](references/aimline-method.md)         |
| Changing a model, a column, or a join in either PM chain                                           | [references/model-architecture.md](references/model-architecture.md) |
| Explaining a number that looks wrong, or verifying a change before reporting it                    | [references/diagnosing.md](references/diagnosing.md)                 |
| Finishing a change -- what to check, and what else must be updated                                 | [references/diagnosing.md](references/diagnosing.md)                 |

The data model itself — every column, its domain, and the decisions behind it —
lives in
[docs/models/dibels-dashboard-data-model.md](../../../docs/models/dibels-dashboard-data-model.md).
That page and this skill hold different things: it holds the model, this holds
the procedure and the traps. Do not copy facts between them.

## Four rules that apply before you touch anything

These are here because breaking one produces a plausible wrong answer rather
than an error.

1. **`assessment_type = 'PM'` is not a filter on its own.** It spans both
   methods, so any PM count must also filter `model_type`, or it double-counts.
   See [references/model-architecture.md](references/model-architecture.md).
2. **Slice on the `expected_*` columns, never on a scores-side column.**
   Filtering on a scores-side column silently drops the students who were never
   tested, which is usually the population the question is about. Same file.
3. **Hand over the whole sheet, never a patch.** See
   [references/sheets-and-sources.md](references/sheets-and-sources.md).
4. **Never verify a derived column by re-applying its own derivation.** The
   check then compares an expression to itself and passes unconditionally. Drive
   the check off the underlying flag instead. See
   [references/diagnosing.md](references/diagnosing.md).

## Before you finish: update this skill and the reference document

**Not optional, and not gated on the user asking.** Any session that changes a
DIBELS model, discovers something about how the data behaves, or settles a
question with academics updates BOTH:

- `docs/models/dibels-dashboard-data-model.md` — the published reference. It is
  in the mkdocs nav, so a wrong page here is a bug, not a stale note.
- this skill, for anything a future session needs BEFORE it opens a file.

The reason is specific to this domain. Most of what matters about DIBELS is not
recoverable from the SQL: which choices are T&L's and must not be 'corrected',
which are ours, what academics were asked and answered, and which apparent bugs
are recorded intent. On 2026-09-15 a session called a documented T&L rule a bug
and started changing it; the yml description is what stopped that. A session
that leaves its findings only in a PR body has lost them.

What to write down, beyond the change itself:

- A rule that looks wrong but is deliberate — say whose decision it is, and that
  it must not be corrected.
- A value or label rename — the old name, the new one, and the date, because
  academics will ask about a word they still use.
- Anything measured — row counts, category distributions, coverage rates — with
  the academic year, since the next reader cannot tell a real shift from a
  method change without it.
- A dead end: an MCP that cannot reach a source, a check that proves nothing.

Put column and model semantics in the model's properties yml, workflow and
reasoning here, and the narrative in the reference document. The repo's yml
conventions still apply to descriptions.

Covers the whole DIBELS dashboard suite. Documented below: the Bright Spots
tracker / foundation goals retrofit (#4952) -- benchmark-goal work, not
PM/aimline -- and the PM/aimline migration (#3834). As the other tracks land,
give each its own `##` section here rather than starting a separate skill:

- **Benchmark completion tracking (#4902)** -- not yet documented here.
