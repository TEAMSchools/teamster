# Cube Validation

The Cube validator checks that a Cube measure gives the same numbers as the
Tableau dashboard it replaces. This guide is for 2 readers: the analyst who runs
a validation, and the dashboard owner who answers its questions. It explains
what each step does and why. The step-by-step runbooks are linked under
[Where to go next](#where-to-go-next).

**Jump to:** [Who does what](#who-does-what) ·
[What a validation checks](#what-a-validation-checks) · [The steps](#the-steps)
· [Reading a result](#reading-a-result) · [Decisions](#decisions) ·
[When a comparison is skipped](#when-a-comparison-is-skipped) ·
[The owner's side](#the-owners-side) · [What it costs](#what-it-costs) ·
[What stays private](#what-stays-private)

## Who does what

- The analyst runs the validator with Claude Code, explains each difference, and
  approves every decision.
- The dashboard owner (the domain owner) answers the questions only they can
  settle, in their own Claude Code session. The owner never runs the validator
  or edits its files.
- Claude runs the commands and drafts the text. The validator itself never posts
  anything to GitHub, Slack, or Asana. Claude posts only what the analyst
  approved.

To start, ask Claude Code to "validate `<view>` in Cube". The `cube-validation`
skill runs each command for you. Commands that need Tableau or Cube credentials
run through a short test file that Claude writes and deletes, so you do not run
them by hand.

Each Cube view has one validation file, `src/cube/validation/<view>.yml`. It
holds the comparisons (one sheet and one measure each), the decisions, and the
links to the review issue. Cube never loads these files.

## What a validation checks

A comparison checks one dashboard sheet against one Cube measure at 3 levels:

- Rows. The validator rebuilds the dashboard's rows in SQL and matches them, row
  by row, to the rows Cube counts. A row that only one side holds is an
  unmatched row.
- Cells. Each number the sheet shows (a cell) is compared with Cube's number for
  the same filters.
- Formulas. A cell can differ even when every row in it matched on both sides.
  That cell is a formula difference: the 2 sides compute the number differently.

A measure reads `validated` only when every cell matches and nothing is open.
Otherwise it reads `differs` and lists its open items. A measure whose
comparison has not run yet reads `not compared yet`.

A validation does not check everything:

- It checks the sheets and filter choices you configured, not every view of the
  dashboard. A filter choice that no export covered is listed under "Cuts to
  check in the browser", for you to check by hand.
- It checks one moment: the data as of one fact build in the last 7 days. New
  data alone does not make a result stale. Run `compare --all` to check again
  after a data change.
- A comparison with a `scope` checks a narrower number than a plain Cube query
  returns. Say so when you report that measure.
- A source read as it is now, such as a Google Sheet, cannot be pinned to the
  run's moment. The result names it.
- An identifier column reads `not compared: identifier column`. The validator
  does not compare its values, for privacy. Never compare them by hand.

## The steps

Each step below names the command Claude runs. Run `--help` on any command for
its options: `uv run python -m scripts.cube_validation <command> --help`.

1. Find the field: `find-field` ranks the workbook fields that could match a
   Cube measure. A field with a similar name can mean something else, so you
   confirm the right one before anything is written. It reads Tableau and Cube
   and runs no BigQuery query.
2. Read the sheet: `read-sheet` reads the chosen sheet from a downloaded
   workbook, offline. It lists the sheet's fields, filters, and table
   calculations, and anything that blocks the next step.
3. Write the comparison into the validation file, with Claude.
4. Rebuild the sheet: `rebuild-sheet` rebuilds the sheet in SQL and checks that
   the SQL reproduces every cell of the sheet's export. A match is saved as the
   comparison's rebuild check. Tableau changes go only to a copy in the
   `TEMP-CB` project.
5. Compare: `compare` compares each comparison with Cube at one fact build. It
   prices every query first. It saves each comparison's unmatched rows for the
   next steps.
6. Sort: `sort` puts every open item into a pile (see
   [The sort piles](#the-sort-piles)) and writes `sort.json` beside the run's
   `run.json`. Run `sort` after every `compare`.
7. Explain: `explain` saves an explanation, a SQL query that names a cause for
   each unmatched row. You and Claude write it together, one cluster of rows at
   a time. Explanations are saved under `src/cube/validation/explanations/`.
8. Decide: `decide` writes the batch of decisions the analyst approved into the
   validation file. See [Decisions](#decisions).
9. Ask the owner: `ask-owner` drafts the body of the review issue, "Validate
   `<dashboard>` in Cube". Claude posts it after the analyst reads it.
10. The owner answers in 1 comment on that issue. See
    [The owner's side](#the-owners-side).
11. Record the answers: `record-answers` reads that comment and writes each
    answer as a decision. It first prints the changes. It writes them only when
    run again with `--yes`.
12. Describe: `describe` drafts a sentence for each measure that differs on
    purpose. That sentence goes into the Cube member's `ai_context`, so Claude
    can tell Cube's users why the number differs from the dashboard.

After a hand edit to the decisions in a validation file, `reapply` applies them
to the saved run again, with no new `compare`.

### Example

The examples on this page are made up. Say the analyst validates `books_read` on
an invented Reading Club dashboard. `compare` finds 30 rows that only Cube
counts. `sort` traces them and prints a lead: relaxing the dashboard's
`status != 'archived'` filter brings back 30 of 30 rows. The analyst writes an
explanation that files those rows under one cause, "dashboard: the dashboard
drops archived records". That cause is a question only the owner can answer, so
`ask-owner` asks it: should archived records count?

## Reading a result

### The sort piles

`sort` puts every open item into exactly 1 pile. An item is a group of unmatched
rows, a set of differing cells, a formula difference, or a sheet filter or cut
that Cube does not have.

| Pile              | What it means                                                     | What you do                                                              |
| ----------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `map_filters`     | A sheet filter matches a Cube member with the same values         | Map the filter under the comparison's `filters:`, then rebuild the sheet |
| `filters_nothing` | A sheet filter with no Cube member keeps every value on the sheet | Decide it, usually with the call its label suggests                      |
| `cause`           | The difference has an explained cause                             | Decide it, or send it to the owner                                       |
| `investigate`     | No explained cause yet                                            | Explain it with Claude; it never goes to the owner as a question         |

Items in `investigate` do not block the rest. You can decide every other item
and ask the owner what is ready.

### A cause

A cause is the step that explains, row by row, why rows sit on one side only.
Only 3 things can supply a cause: a saved explanation, a filter in the workbook,
or a filter the comparison applies to the dashboard side. A trace lead, a Cube
member's description, or a pattern in the cells is a lead, not a cause.

A trace lead reads like `lead: relaxing <step> brings back 30 of 30 rows`. It
points at the SQL step to test next. It proves nothing on its own.

### A formula difference

Each comparison's formula cells form 1 item, `<comparison>:formula`. Its cause
reads one of 2 ways:

- `differing cells hold no unmatched row`: every row in those cells matched, so
  the 2 sides compute the number differently.
- `differing cells differ on matched rows`: the formula check recomputed the
  cells on the rows both sides hold, and they still differ.

A formula difference usually goes to the owner, who decides which calculation is
right. Give the comparison `definitions:` so the owner sees both formulas.

### "formulas not compared"

A cell reads `formulas not compared: <why>` when the formula check could not
recompute it. The cell still closes when the row groups in it close. The owner
sees that comparison under "Still with the analyst". A reason in the data or the
configuration clears on the next `compare`. A cap or a BigQuery or Cube error
needs a fix and another `sort`.

### "Still with the analyst"

This section of the review issue counts what the analyst has not explained yet,
per comparison. It also lists comparisons that were never compared, are stale,
or were skipped. Its items are not questions, and the owner does not answer
them. The owner can still say if one looks familiar. The items, one by one, are
in `reviews/<view>-still-with-analyst.md`, which the section links.

## Decisions

A decision closes a sorted item. It has a call and a reason. Claude drafts each
reason, and the analyst edits and approves them as a batch. A `map_filters` item
takes no decision: you map the filter instead. A set of differing cells takes
none either: it closes once the row groups in its cells close.

| Call            | What it means                              | Task it links                         |
| --------------- | ------------------------------------------ | ------------------------------------- |
| `deliberate`    | The difference is intended                 | None                                  |
| `fix_dashboard` | The workbook or its view is wrong          | The domain's Asana dashboard-fix task |
| `fix_cube`      | The Cube model is wrong                    | The domain's GitHub Cube-fix issue    |
| `fix_source`    | The source data is wrong                   | A GitHub issue for the data's owner   |
| `domain_owner`  | Only the owner can say which side is right | The review issue                      |

Only `domain_owner` decisions become questions for the owner. The other calls
are listed in the review issue under "Also decided (no answer needed)".

A decision holds while the SQL on both sides stays the same. When either side's
SQL or the explanation changes, the decision waits to be confirmed again. When
the analyst decides a whole comparison is not worth explaining further, 1
`deliberate` decision can close all of its open row groups.

## When a comparison is skipped

`compare` checks every comparison before it spends anything. A comparison with a
problem prints `Skipping <id>: <why>.` and keeps its previous result. The rest
are compared. Then `sort` names it as `not compared: <why>`, and the review
issue lists it under "Still with the analyst".

| The reason says                                                   | What to do                                                                            |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| No rebuild check, or the sheet query or workbook changed since it | Run `rebuild-sheet` again                                                             |
| A member that Cube's model lacks                                  | Fix the member name in the validation file, or the Cube model                         |
| The sheet is not on a published dashboard                         | Set `unpublished: true` only if you mean to compare that sheet                        |
| Cube answered from a pre-aggregation                              | Add a Cube-only `scope` on a never-null member the rollup lacks, with `operator: set` |
| A table changed during the build                                  | Compare again after the next build                                                    |
| The dims put 2 rows in the same cell                              | Fix the dims so each cell is 1 row                                                    |
| A BigQuery error, with a job id                                   | Look the job up in BigQuery for the message                                           |

A refusal about "7 days of warehouse history" is not a skip. The moment is older
than BigQuery keeps history, so pick a newer fact build or wait for the next
refresh. "Every comparison's latest result is current" is not a failure either:
nothing changed, so nothing needed comparing.

## The owner's side

The owner answers in their own Claude Code session. They say "walk me through
issue #N", and the `cube-validation-answers` skill takes over. The owner needs
no code.

1. Claude reads the questions from the file the review issue links.
2. Claude asks 1 question at a time, in policy words, such as "Should archived
   records count as books read?"
3. For each question, Claude shows both definitions side by side, who differs
   and by how much, and what the validator found.
4. Claude shows the owner's own checks: the dashboard cell to read, and SQL to
   paste into the BigQuery console, with its price. The owner runs them, not
   Claude.
5. The owner picks an answer.
6. At the end, the owner reads a summary of the answers. Claude posts it as 1
   comment on the review issue only after the owner confirms the text.

| The owner says            | The call it records |
| ------------------------- | ------------------- |
| The dashboard is right    | `fix_cube`          |
| Cube is right             | `fix_dashboard`     |
| Both are fine, on purpose | `deliberate`        |
| The source data is wrong  | `fix_source`        |
| Something else, in words  | `domain_owner`      |

The pinned SQL in a check stops working 7 days after the run, when BigQuery's
history ends. A cause question also carries reproduce queries on today's data,
which keep working. The owner can use those, or ask the analyst to run the
validation again.

The analyst then runs `record-answers` on the owner's comment. The review issue
closes when every question has a decision, every fix has its issue or task, and
nothing is left with the analyst.

## What it costs

The validator spends money only on BigQuery queries, and it prices them before
it runs them.

- `rebuild-sheet`, `compare`, `sort`, and `explain` dry-run every query first
  and print a total, such as `Compare: 12 queries, $0.40 (dry run)`. They refuse
  to run when the total is over a cap.
- `--max-usd` caps 1 command. `--max-usd-per-day` caps every run on your machine
  for the UTC day. Each command's `--help` shows the current defaults.
- `sort` traces unmatched rows down through the dbt models. The caps and
  `--trace-max-minutes` bound the trace, and `--no-trace` skips it.
- Work that already ran is reused, not paid for again. `sort` keeps finished
  explanations in `sort-progress.json`, a formula check that ran is kept while
  its result stands, and a plain `compare` runs only the comparisons that are
  new or changed.
- `find-field`, `read-sheet`, `decide`, `reapply`, `ask-owner`,
  `record-answers`, and `describe` run no BigQuery query.

When you explain a cluster with Claude, stop and ask for context after 2 failed
guesses or about $0.50 spent on that cluster.

## What stays private

A validation works with student-level rows, so the validator keeps them off
every shared surface.

- Row-level output stays local: the terminal, `sort.json`, and your local cache.
  Unmatched rows wait in a BigQuery dataset that only the Data Team can read,
  and each table there expires.
- Anything posted or committed shows a count under 10 as `<10`. A total that
  would give away a hidden count reads `10+`. Small counts can single out a
  student, so the owner's questions show every count as a bound.
- A sheet filter on a field outside the reviewed reference columns prints
  "chosen values hidden". The validator never reads or copies those values,
  because a filter's chosen values can name a student or a small group.
- Explanations hold SQL only. `explain` refuses a query that compares a literal
  value with a column that names or reaches a person, and an ID-like number or
  email in the query's text.
- `decide` and `record-answers` refuse an email or an ID-like number in a
  reason. Neither can detect a name, so read every reason and definition before
  it is written. The review issue promises that student and staff identifiers
  are hidden, and that promise holds only if no reason names a person.
- Example students the owner asks to see come from the owner's own BigQuery
  access and stay in the owner's chat. Nothing posted carries a student's name,
  number, or row.

## Where to go next

- The analyst's runbook, with every flag and edge case:
  [`.claude/skills/cube-validation/SKILL.md`](https://github.com/TEAMSchools/teamster/blob/main/.claude/skills/cube-validation/SKILL.md)
- The owner's runbook:
  [`.claude/skills/cube-validation-answers/SKILL.md`](https://github.com/TEAMSchools/teamster/blob/main/.claude/skills/cube-validation-answers/SKILL.md)
- The validator's code:
  [`scripts/cube_validation/`](https://github.com/TEAMSchools/teamster/tree/main/scripts/cube_validation)
- Building and testing Cube models: the [Cube](cube.md) guide
