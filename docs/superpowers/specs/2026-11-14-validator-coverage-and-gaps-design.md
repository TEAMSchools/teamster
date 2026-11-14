# Validator: close every known gap, then validate DDI and Attendance fresh

Issues: #6410 (main), #6346, #6343, #6181 (items 1, 7, 8, 12, 14), #6411
(superseded). Branch:
`cristinabaldor/fix/claude-validator-second-fact-time-dims`, PR #6402. Closed as
not planned while scoping: #6212, #6224, #6230.

This builds on `2026-11-13-validator-saved-rows-resume-design.md` (saved rows,
resume) in the same PR, and replaces Task 13 of its plan: the live check becomes
the fresh DDI validation below.

## Intent and why

The owner wants a validator, at the end of this work, that covers every gap
found so far, and then a fresh, timed validation of the DDI Suite on production,
with nothing carried over from earlier validations. Attendance gets the same
fresh start after.

Two things shape the work:

- **Cells cannot keep up with dashboard math.** `triage confirm --cells` closes
  a differing cell only when it can rebuild the cell's number from its rows.
  Each new calculation shape (a share at a level, a % of total across bars, a
  distance to a goal, a day-weighted rate) needs a new rebuild rule, and no
  validation file has ever recorded a cell-set decision. The rule changes to
  coverage: a cell closes when every unmatched row in it is proven, and a cell
  that differs while every row matches is a formula difference for the owner.
- **The validator carries steps nobody uses.** Anchors and identities (1
  identity block, ever), `check-api` (pre-aggregations are out of scope), and a
  separate `prove --check` step that a run can do itself.

## Goals

1. Every differing cell either closes by coverage, or reaches the owner as a
   formula difference, or stays in `investigate` because a row in it is
   unproven. No cell needs a rebuild rule.
2. `run` refuses before spending: on a workbook changed since its proof, and on
   a priced total over `--max-usd` or the daily cap.
3. `run --comparison` runs a chosen subset, and the rest of the validator reads
   the result.
4. Long steps show progress while they run, with elapsed time and spend.
5. A sheet filter with no Cube mapping says whether Cube offers the field, lacks
   it, or it is workbook-only, even when it filters no rows.
6. The trace gets past a model it cannot read, and says where it stopped.
7. A comparison whose dashboard stores daily rows, where Cube stores one row per
   period, can have rows.
8. The validator, its skills and its messages are smaller and say "validation
   file".

## Non-goals

- Pre-aggregations. `check-api` goes; whether Cube's API serves a rollup that
  matches the raw SQL is not checked.
- Row-level access (#6224, closed). The validator stays one network-wide caller.
- Comparing Cube with a source system. If needed later, it becomes its own
  skill.
- A weekly schedule (#5842) and a CI check (#6158).
- #6181 item 10 (2 sessions on one validation file): the owner will not run 2
  sessions on one file.
- #6181 items 9 (running against a local Cube is undocumented in this skill) and
  13 (`_MEASURE_PILL` edge shapes, no known case): not scoped in this round.

## Anti-goals (a failure even if it works)

- A cell closes because nobody could tell why it differs. Coverage closes a cell
  only on proven rows; a cell with an unproven row stays in `investigate`.
- A formula difference closes as `deliberate` without the owner seeing it.
- A student or staff value reaches GitHub through the new outcome, a progress
  line, or the trace's model chain.
- A check, guard or refusal is cut to make a step faster.

## Constraints

- One PR, #6402. Offline tests under DuckDB:
  `uv run --with duckdb pytest tests/scripts/cube_validation/ -q`.
- No parallel workers in `run` or `triage` (2026-11-13 spec, _Revision_).
- Live commands run through the `cube-validation` skill's runner; the owner
  approves each spend.

## Approaches

- **Remove first, then change, then add (chosen).** Cutting `check-api`, anchors
  and identities, cell sizing and the standalone `prove --check` first means the
  new code is written against what stays.
- **Add first, remove after.** Rejected: new code would be written, tested and
  then partly undone against parts already slated to go.
- **Split into several PRs.** Rejected: the owner keeps validator work in one
  PR, and the fresh validations need all of it.

## Design

### 1. Removals

- **`check-api`:** the command, `pipeline.check_api`, `_api_checks`, their
  constants and tests, and the runbook step in both skills.
- **Anchors and identities:** `checks.py`'s anchor and identity code, the
  `anchors:` and `identities:` keys in `config.py`, and their report text
  ("judge the anchor", "consistent only"). A measure's verdict is "validated"
  (every cell passes, nothing open), or "differs", with its open items. A
  validation file that still has either key is refused, naming the key and
  saying to delete the block.
- **Cell sizing:** `_SIGN`, `_counts_rows`, `_sizable`, `_rebuilt`,
  `_students_rebuilt`, `_reproduces`, the per-cell sums `run` keeps for them
  (`RunResult.cell_rows`, `cell_students`) except the per-cut row counts
  coverage needs (section 2), and `rows.cell` in `config.py`. A file with
  `rows.cell` is refused like the keys above. The per-cause student counts
  `review` uses to pick example cells (`cause_students`) are a separate thing
  and stay.
- **`prove --check` as a step:** its workbook check moves into `run` (section
  3). Its dry runs of stored cause proofs go if `triage`'s up-front pricing
  (#6410) already dry-runs every proof before spending; otherwise they move into
  `triage`. The builder confirms which from the code.
- **The skill's "Worked example (DDI)" table and its dead ends:** removed. Its
  lessons stay as generic guidance with no DDI names (test each flag of a
  `where` alone; a label like "week join" can hide 2 causes; an anchor year can
  be null).

### 2. Cells close by coverage

For each differing cell of a comparison with `rows`, `link_cells` finds the row
groups whose unmatched rows sit in that cell under that cut. Groups closed by a
decision count as well as open ones: a decided group's rows are explained. Then:

- **Every such group is in `cause` or decided:** the cell is covered. No size
  check.
- **Some such group is neither:** the cell stays open, as today.
- **No group has a row in the cell:** every row in it matched on both sides, so
  the difference comes from how each side computes the number. The cell is a
  **formula difference**.

Placing a group's rows in a cell must be exact, or coverage would close a cell
with no proven row in it:

- **Cuts.** `run` keeps, per group and cut, the count of its rows on each side
  (the `k{j}` cut flags the reconcile already computes). The sums `cell_rows`
  kept for sizing go; the row counts stay. A group with 0 rows under a cell's
  cut has no row in that cell.
- **Dims.** A cell's every dim must be a column the groups split by. When one is
  not (a dim that is part of the row grain), the cell cannot be placed, stays
  open, and its item says why. `preflight` and `run` name such comparisons
  before any spend.
- A comparison without `rows` cannot be covered either: same treatment.

Covered cells need no decision of their own. The comparison's cell-set item is
decided once every cell in it is covered by decided groups, the way a cause item
is decided once each of its causes is.

A formula difference is its own item and its own decision, never the
comparison's cell-set item:

- One item per comparison, `<id>:formula`, holding only its formula-difference
  cells. It reaches `cause` on the run's own evidence, like a dashboard-filtered
  row: "N differing cells hold no unmatched row". No proof file is needed, since
  the matching rows are the proof.
- Its decision claims `formula: true` for that comparison, not `cells: true`. It
  holds while the comparison's SQL fingerprints hold, and it covers only cells
  with no unmatched row in each new run: a cell that later gains an unproven row
  leaves the formula claim and is judged by coverage.
- Its call is usually `domain_owner`. The owner question shows both sides'
  definitions (`definitions:` on the comparison) and asks which formula is
  right.
- Its counts are masked on GitHub, like every other item's.
- `cells: true` decisions go with sizing: coverage needs none, and an old one is
  refused like `rows.cell`.

Known limit: a cell that holds both a proven row cause and a formula difference
closes by coverage. The formula difference still shows on every cell without a
row cause, and a fixed row cause leaves the cell differing with matched rows on
the next run, which flags it.

### 3. `run`

- **Workbook check, before any spend.** For each confirmed comparison, compare
  the workbook with its proof the way `prove --check` does today (sheet formulas
  and filters, datasource connection and filters), and refuse, naming the
  comparisons to re-prove. `run` now signs in to Tableau; the runner already
  loads those credentials.
- **Up-front price.** Before the first query that bills, dry-run every query the
  run will send, print the total, and refuse when it passes `--max-usd` or what
  is left of the daily cap. The per-query cap stays as a backstop. Whether a dry
  run prices the multi-statement save script as a whole is unverified: if not,
  price its statements one by one.
- **`--comparison <id>`, repeatable.** Runs only those comparisons, at the
  newest build or `--moment`. Each one's result replaces that comparison's
  latest result (section 3a).
- **Progress lines.** After each comparison, print one line and flush it: clock
  time, elapsed time, step, comparison, and spend so far. No row values.

### 3a. Each comparison keeps its own latest result

A validation is the latest result of each confirmed comparison, each at its own
moment, not one run at one moment. Time travel reaches back 7 days, so without
this, adding one comparison weeks later means comparing every comparison again.

- **Adding a comparison:** `rebuild-sheet` it, then `compare --comparison <id>`
  at the newest build. Every other comparison keeps its result.
- **Stale results.** Before any spend, `compare` checks each comparison's latest
  result against today's code and lists it as stale when any of these changed
  since it ran: Cube's SQL for its query, the dashboard side's SQL (the sheet
  query and the dbt models it reads), or its `rebuild_check`. A plain `compare`
  runs the stale and the never-run comparisons only; `--all` runs every one.
  Changed data alone does not make a result stale: the validation checks
  definitions.
- **`sort`, `decide`, `ask-owner`** read the latest result of every comparison.
  A comparison with no result, or a stale one, is named and blocks `ask-owner`,
  as an open item does today. Each comparison's moment shows in the owner's
  issue.
- **Explanations and decisions** stay tied to their comparison and its
  fingerprints, as now. An explanation runs against the saved rows of its
  comparison's own result.
- **Storage:** where each comparison's latest result and saved rows live, and
  how a run folder maps to them, is left to the builder, within the 2026-11-13
  spec's saved-rows and checkpoint design.

### 4. `triage`

- **Filters Cube might not offer (#6346).** For every sheet filter with no Cube
  mapping, whatever pile it lands in, look up candidate members in
  `members.json` (`triage._candidates`) and label the item:
  - "Cube offers it as `<member>`, unmapped": map it under `filters:`.
  - "Cube has no member: a gap": default call `fix_cube`, not `deliberate`.
  - "Workbook-only field": the proof's `missing_columns` shows no datasource
    column behind it, and no candidate member matches. Default call
    `deliberate`.
  - When a candidate matches, that label wins, even for a workbook calc. A name
    match is a lead, so the label says "check before mapping".
- **Trace (#6181 item 1).**
  - When a model's SQL fails (parse error, too long, `resourcesExceeded`,
    invalid), skip that model, note why, and keep descending the others.
  - When a bucket stops, print its model chain: each model from the side's table
    down to where it stopped, with why it stopped.
  - Raise `MAX_LEVELS` from 3 to 5, under the trace's existing spend cap and
    `--trace-max-minutes`.
  - Progress lines, as in `run`.

### 5. Rows for daily dashboard data (#6343)

A comparison's `rows` can reduce the dashboard side to one row per key before
the reconcile, by a named rule, never SQL in the YAML. The one rule now:
`latest`, which keeps each key's row with the latest value of a named date
column. For chronic absenteeism: key student and period, latest calendar date,
which is the row the workbook's `Is Chronic Absentee` reads. After the reduce,
the reconcile and coverage work as for any comparison. Truancy's day weighting,
if the sides differ on it, shows as a formula difference.

### 5a. Plainer names

The tool's job reads as one sentence: rebuild the sheet in SQL, compare it with
Cube, explain each difference, ask the owner. Names follow it. Sections above
use the old names where they point at today's code.

| Today                         | New                                 |
| ----------------------------- | ----------------------------------- |
| `discover`                    | `find-field`                        |
| `preflight`                   | `read-sheet`                        |
| `prove`                       | `rebuild-sheet`                     |
| `run`                         | `compare`                           |
| `triage`                      | `sort`                              |
| `triage confirm`              | `explain`                           |
| `add-decisions`               | `decide`                            |
| `review`                      | `ask-owner`                         |
| `probe` / `probe_sql`         | `sheet_query`                       |
| `proof:`                      | `rebuild_check:`                    |
| `proven_at`                   | `matched_at`                        |
| `probe_fingerprint`           | `sheet_query_fingerprint`           |
| cause proof, `proofs/` folder | explanation, `explanations/` folder |

`record-answers`, `describe`, comparison and decision keep their names. Old
names are refused with the new name, not aliased: no validation file in use
needs them.

### 6. Cleanup

- **#6181 item 12.** `tableau._nested_under` nests an added dimension into the
  last dimension item for any shelf whose ops are all `*`, not only exactly one.
  A shape it cannot reshape is refused, not written.
- **#6181 item 14.** One export-date helper in `tableau.py`, called by
  `tableau._key_text` and `pipeline._key`.
- **"Validation file"** replaces "view file" in both skills, CLI help, refusal
  messages and docstrings. File names stay `<view>.yml`: the name tells the
  validator which Cube view to check.
- **Skills:** the `cube-validation` runbook loses `check-api` and
  `prove --check`, gains `run`'s built-in checks, replaces cell sizing with
  coverage and the formula-difference outcome, and rewrites "Filters nothing".
  `cube-builder` drops its `check-api` and `prove --check` steps.

## Fresh validations (after the build)

1. **Cleanup batch, confirmed by the owner before anything is deleted:**
   - The validation branches `cristinabaldor/test/claude-ddi-cube-validation`
     and `cristinabaldor/test/claude-attendance-cube-validation`, and their
     worktrees.
   - The #6212 code branch
     `cristinabaldor/feat/claude-validator-code-group-cells`: 8 code commits
     exist only locally; the remote holds its spec and plan. Deleting a remote
     branch is the owner's step.
   - The local cache runs for both Attendance views.
   - Issues #6211 and #6341: closed or marked superseded by the fresh runs.
2. **DDI in a new Claude session** that has never seen an earlier validation:
   - New validation branch, based on #6402's branch, with an empty validation
     file. Production only: the deployed Cube, the prod marts, no
     `--fact-dataset`.
   - Off limits: the old validation branches, and old validation issues (#6211,
     #6341, and the DDI comments on #6181, #6410, #6411).
   - Allowed: domain docs (`docs/models/ddi-stack-data-model.md`, the
     `ddi-stack` skill) and the model SQL, as any analyst would read them.
   - Timed: every step's compute time, and one wall-clock total from the first
     `discover` to the drafted review issue. No timing code is built: the runner
     times each command with `time.monotonic()`, the progress lines give elapsed
     time inside `run` and `triage`, and the clean session keeps a timing table.
     It reports the table to the owner, and on #6410 once the owner approves the
     comment.
   - No forced stop-and-resume inside the timed run; a natural cap stop is the
     live test of resume.
3. **Attendance** the same way, in its own clean session.

## Decided by the owner

- Fold the DDI cell-sizing gap into #6410; no new issue.
- Coverage instead of sizing for every cell (Option A), with a
  formula-difference outcome for cells whose rows all match.
- Cut `check-api`, anchors and identities, and `rows.cell`; #6411 is superseded.
- `prove --check` folds into `run`; `run` prices up front.
- Build `run --comparison`, progress lines, #6346, the trace changes, the
  daily-rows reduce rule, #6181 items 12 and 14.
- Decline #6181 item 10. Close #6212, #6224 and #6230.
- Fresh DDI and Attendance validations in clean sessions; domain docs allowed;
  the worked example deleted.
- Each comparison keeps its own latest result, with a stale list, so a new
  comparison runs alone.
- The renames in section 5a, `rebuild_check:` included.

## Calls made in the design (owner to check)

- An old validation file with `anchors:`, `identities:` or `rows.cell` is
  refused with a message to delete the block, not silently ignored.
- A formula difference reaches `cause` without a proof file; the matching rows
  are its evidence.
- `run --comparison` replaces entries in a run at the same moment; `review`
  refuses a run that lacks a confirmed comparison.
- The reduce rule is named `latest`; more rules are added only when a dashboard
  needs one.
- Trace depth 5.
- Coverage places rows exactly: `run` keeps per-group, per-cut row counts, and a
  cell whose dims the groups do not split by stays open.
- Groups closed by a decision count toward coverage.
- Covered cells need no decision; a formula difference has its own item and
  `formula: true` decision; `cells: true` decisions are retired.
- A candidate member beats "workbook-only" for an unmapped sheet filter.
- A plain `compare` runs only stale and never-run comparisons; `--all` runs
  every one.
- Old command and key names are refused with the new name, not kept as aliases.
- Timing is kept by the runner and the clean session, not built into the
  validator.

## Runs saved before this change

The fresh validations start new runs, so older `run.json` files need no
migration. A reader that meets an old run's per-cell sums ignores them.

## After merge

- Close #6411 as superseded by coverage, with a comment.
- Comment on #6181: items 1, 7, 8, 12, 14 done; 10 declined; 9 and 13 left open.
- #6346, #6343 and #6410 close with the PR.

## Left to the builder

- Exact YAML keys for the reduce rule.
- Whether `prove --check`'s proof dry runs are already covered by `triage`'s
  up-front pricing.
- How a dry run prices the multi-statement save script.
- The progress line's exact format.
- Which tests to delete with the removed code, and which to rewrite for
  coverage.
