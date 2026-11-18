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
- `run --comparison` replaces each named comparison's latest result (section
  3a); `review` refuses while a comparison has no result or a stale one.
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

## Revision 2026-11-14: skip, don't stop

Decided by the owner while reviewing the plan. The validator was stopping a
whole run over one comparison's problem; problems now stay with the analyst
while the rest of the work goes on.

- **`compare` skips a comparison instead of refusing the run** when it has no
  `rebuild_check`, its sheet query changed since it, it maps a member Cube
  lacks, or its workbook changed since it. A changed `also_facts` table skips
  only the comparisons whose Cube SQL reads it. Skips print before any spend
  with their reasons, and a skipped comparison keeps its previous result. The
  run refuses only when every comparison is skipped.
- **Still stops:** spend caps, and anything that would put a student or staff
  value where it should not go.
- **`ask-owner` posts what is ready.** Questions with a proven cause go to the
  owner as before. Items still in `investigate`, and comparisons that are
  missing, stale or skipped, are listed in a "Still with the analyst" section
  with masked counts and the trace's lead, so the owner can say if one looks
  familiar. They are not questions: `record-answers` never reads them. The issue
  body is rendered again as more items settle.
- This replaces the anti-goal "a formula difference closes as `deliberate`
  without the owner seeing it" only in wording: unsettled items are now shown to
  the owner, never decided for them.

## Revision 2026-11-18: after the fresh DDI run

The first live run of the reshaped validator, a fresh DDI Suite validation
(#6415), posted 13 comments on PR #6402 holding 15 findings. 12 are confirmed in
the code. The owner chose to fix the bugs and add 3 of the proposals in this PR,
with the core fix done properly rather than disclosed. The faster trace is
#6437, out of scope here.

### Intent and why

The validator promised that a differing cell closes only on proven rows. On the
3 goal comparisons, the dashboard and Cube compute the goal differently. That
difference creates no unmatched row; it only moves the cell's number. Every
differing cell also held unmatched rows from other causes, so no cell was ever
filed as a formula difference, and once those row causes were decided, every
cell closed. Both safety nets in _Design_ section 2 failed: no cell was free of
row causes, and decided causes come back every run. It surfaced only because the
owner already knew the goals were wrong. A validator that can close a wrong cell
this way cannot be trusted, so the fix comes before merge.

### Goals

1. A cell whose number still differs once every unmatched row is left out is a
   formula difference, whether or not it also holds row causes.
2. When that cannot be checked, the cell says so, and the owner sees it.
3. The 9 confirmed bugs are fixed as verified below, each with a test.
4. Only worksheets people can open are validated, unless a comparison opts in.
5. Filter values that cannot identify a person are shown.
6. An explanation is written once per dashboard model and cause, not once per
   comparison.

### Anti-goals

- A cell closes, or is called a formula difference, on a guess.
- A student or staff value reaches GitHub through any new line.
- The formula check spends without being priced and capped first.

### Approaches (the formula check)

- **Recompute each differing cell on matched rows only (chosen).** Both sides'
  numbers are recomputed with every unmatched row left out. A remaining gap is
  the formula. Exact for any measure, additive or not, because both sides see
  the same rows.
- **Disclose only.** Label cells closed by coverage alone as "formulas not
  compared" and always ask the formula question when `definitions:` differ.
  Rejected as the fix: it discloses the gap but never detects it. It survives as
  the fallback below.
- **Put the formula's per-row part in `rows.values`.** For the goal, pair the
  dashboard's goal column with Cube's, so a goal difference shows as
  `value_differs` rows. Rejected as the fix: it depends on the analyst thinking
  of it for every formula. It stays available as ordinary configuration.

### Design

#### 1. The formula check (in `sort`)

- **Which cells:** every differing cell of a comparison with `rows` that
  coverage can place (not unplaceable) and that has at least one group in it. A
  cell with no group is already a formula difference.
- **Dashboard side:** the comparison's sheet query over its `{rows}` with every
  unmatched grain key left out (an anti-join against the comparison's saved
  unmatched rows in `cube_validation_scratch`, both sides' unmatched rows, every
  bucket), grouped by the comparison's dims and cut, at the comparison's own
  moment.
- **Cube side:** Cube's compiled SQL for the cell query, with the fact reference
  rewritten to the fact minus the same unmatched grain keys, read as of the
  comparison's moment. This works only when each grain column maps to a column
  on the fact.
- **Verdict per cell:** if the two recomputed values still differ at the
  comparison's `decimals`, the cell joins the comparison's `<id>:formula` item,
  with its row groups still listed. If they agree, coverage decides the cell as
  today.
- **When the Cube side cannot be rewritten** (a grain column is an expression,
  not a fact column, or the rewrite is refused), the cell closes by coverage as
  today but is labeled "formulas not compared: <why>". `ask-owner` lists it
  under "Still with the analyst". Never silent.
- **Where and when:** in `sort`, after stored explanations re-run, because the
  saved rows exist then. Its queries are priced in `sort`'s up-front total and
  capped. One query per side per affected comparison, not per cell.
- **Results:** the formula item's evidence names the cells, masked like every
  other count. The formula decision (`formula: true`) covers these cells too.
- **Runbook:** explain that a formula difference can sit under row causes, and
  that "formulas not compared" means the check could not run.

**Precise rules (from the builder check):**

- **Matched rows means the rows the reconcile matched, not "everything minus the
  unmatched".** Both sides keep only grain keys that the reconcile saw on both
  sides with equal values: a semi-join on the reconcile's own row sets (the
  dashboard's after `rows.dashboard_scope`, `rows.reduce` and cuts; Cube's after
  `scope`), minus the saved unmatched keys. Rows the reconcile never saw, such
  as out-of-scope or non-latest daily rows, are never in either side, so they
  can never be read as a formula difference. It rebuilds the reconcile's row
  sets inside the query at the comparison's moment rather than storing matched
  keys.
- **Self-check first.** Each side's rewritten query is also run with nothing
  removed. If it does not reproduce the run's own value for the cell at
  `decimals`, the cell is "formulas not compared: the rewrite does not reproduce
  the run's cells". This catches a missed fact reference or a wrongly wrapped
  sheet query. It doubles the queries; they are priced like the rest.
- **Which tables the Cube side filters:** every table Cube's SQL reads (the
  view's `fact` and any `also_facts`) that carries every grain column. A table
  without the grain columns, such as a goals table at school and grade grain, is
  a lookup and is left as is. If no table Cube reads carries the grain columns,
  the cells are "formulas not compared".
- **Empty sides:** a cell with no matched rows on either side is "formulas not
  compared: no rows both sides hold". Matched rows exist on both sides by
  definition otherwise.
- **Every other failure is the same fallback, with its reason and next step:**
  saved rows gone or past time travel ("compare it again"), a BigQuery or Cube
  error (job id and reason code only), a Cube side that cannot be rewritten.
  None refuses `sort`, makes the comparison stale, or blocks `ask-owner`.
- **What "formulas not compared" means for the result:** the cell set closes by
  coverage as before. A measure with differing cells is never "validated" in any
  case, so the verdict does not change. The label is a disclosure, listed under
  "Still with the analyst"; no decision clears it, and re-running `sort` after
  its cause is fixed replaces it.
- **Pricing and scope:** the formula check's queries join the explanations'
  up-front batch in `sort`, so one refusal comes before anything runs. Under
  `sort --comparison`, it runs only for the comparisons named.

#### 2. Bugs (each with a test)

- **`read-sheet` and the COUNTD caption:** add `distinct count` to
  `read_sheet._AGG_PREFIX`, so `sheet_field: Distinct count of <field>` is
  found.
- **A comparison opening with a YAML merge key:** `config.write_rebuild_check`
  (and the decision writer) find a comparison by an `id:` line anywhere in its
  list item, allowing a trailing comment. `rebuild-sheet` finds the item before
  the export, so an unwritable file refuses before any spend.
- **Text measures:** `read-sheet` and `rebuild-sheet` refuse a text measure up
  front: "text measures are not compared; compare the numeric measure it is
  built from". The number-format message no longer fires on letters. Full text
  comparison is not built (_Calls_ below).
- **Blank cells:** `tableau.match_export` skips an export-only cell whose value
  is blank and a sheet-query-only cell whose value is NULL, and prints how many
  it skipped. A blank on one side with a value on the other still fails.
- **`*` total rows:** `rebuild._export_cells` treats `*` like `All` in the
  total-row check, with the same guard (only when the sheet query has no real
  `*` member), only for dims on rows or columns, and counts them in
  `totals_skipped`.
- **Dual-axis sheets:** `rebuild._export_cells` drops a repeated export row when
  it matches another on every column except table calcs and other measure
  columns. Two marks that differ in any other column still fail as "more than 1
  export row", so the `split_rows` signal survives.
- **Non-null filters:** `find_field.restricts` treats a quantitative filter with
  `included-values` of `non-null` or `null` as restricting and says "non-null
  values only". `read-sheet` points at `dashboard_filters` with `operator: set`.
  A rebuild check written before the fix may list the field outside
  `restricting_filters`; the runbook says to re-run `rebuild-sheet` for it.
- **A `dims_differ` explanation:** `explain.unmatched_sql` carries `__moved` and
  `__d_<col>` per dim. The runbook and docstring say `__d_<col>` is NULL unless
  that column differs, so an explanation reads `COALESCE(u.__d_x, u.x)` for the
  dashboard's value.
- **Pre-aggregation refusal:** the refusal names the remedy (a Cube-only `scope`
  on a never-null member the rollup does not carry, such as the fact's primary
  key, `operator: set`), and no skip line ends in a doubled period. The runbook
  says the same.

#### 3. Published worksheets only

- A worksheet is published when it sits on a dashboard in the workbook's layout
  (a dashboard zone) or Tableau Server lists it as its own view.
- `find-field` and `read-sheet` mark any other worksheet "not on a published
  dashboard". `rebuild-sheet` refuses it. `compare` skips it with that reason.
- A comparison opts in with `unpublished: true`. Its owner question then says
  the sheet is on no published dashboard.

#### 4. Safe filter values

- The explicit allowlist (`find_field.SHOWN_FILTER_FIELDS`) stays the rule;
  anything not on it stays hidden. It gains `response_type`, `module_type` and
  `is_normed_scope`.
- For an allowlisted field, `find-field` and `read-sheet` show the chosen
  values, a quantitative filter's bounds, and its include or exclude mode.
- A calculated-field filter is shown only when every column it reads is
  allowlisted.

#### 5. Shared explanations and the cause-first method

- An explanation is shared across every comparison on the same `dashboard_view`
  whose `rows` grain and values match, whatever their `filters`, `defaults`,
  `dashboard_columns`, `scope` and `cuts`.
- Each comparison runs it on its own unmatched rows, with its own check that
  every row gets exactly one label. A row it does not cover is `UNEXPLAINED`.
- `explain` prints "Also <comparison>" for each it ran on; the explanation file
  does not list them.
- Runbook: find a cause once, on the comparison that shows it most clearly, then
  let it run on every comparison of that model; work comparison by comparison
  only for what is left.

### Proving it live (owner's decision)

No live spend is part of this build. After it lands, the #6415 session merges
the updated #6402 branch into its validation branch and re-runs `sort`; the 3
goal comparisons should come out as formula differences. That spend is approved
there.

### Calls made in this revision (owner to check)

- Text measures are refused, not compared. The DDI text measure is validated
  through the numeric measure it is built from.
- The pre-aggregation remedy is named, not applied: `compare` does not add the
  scope by itself.
- The formula check runs in `sort`, not `compare`.
- The formula check's precise rules above: the semi-join on the reconcile's own
  row sets, the self-check, which tables Cube's side filters, empty sides, one
  fallback for every failure, no change to the verdict, and pricing in the
  explanations' batch.
- A calculated-field filter's values show only when every column it reads is
  allowlisted.

### Left to the builder

- How the Cube-side rewrite finds and replaces the fact reference in compiled
  SQL, and how it detects a grain column that is not a fact column.
- The exact wording of the new labels and refusals.
- Whether "published" reads Tableau Server's views list at `find-field` time or
  only at `rebuild-sheet` time.
