---
name: cube-validation
description:
  'Use when asked to validate Cube, check whether Cube matches the dashboard,
  triage a validation run, pick up the answers on a validation issue ("pick up
  the answers on #N"), or when working in `src/cube/validation/` or
  `scripts/cube_validation/`.'
---

# cube-validation

The validator compares a Cube view's measures with the dashboards, source
anchors and identities that check them. Per-view files live in
`src/cube/validation/<view>.yml`; the code is `scripts/cube_validation/`. Cube
loads only `src/cube/model/`, so these files never reach the semantic layer.

## Rules

- Time travel reaches back 7 days. A moment older than that is refused: pick a
  newer fact build.
- Dashboard rows are rebuilt as of the fact build's start; Cube's answer is as
  of its end. A difference a dimension rebuild explains is named in the result,
  not a finding.
- The tool never posts anything: not to Slack, not to GitHub, not to Asana.
  Claude posts, and only what the analyst approved.
- Row-level output stays local. Never paste rows into an issue, a comment or a
  commit; GitHub text shows counts under 10 as `<10`.
- Nothing committed names a person or holds an email. Pass `--email` (a
  network-grant address) or set `CUBE_VALIDATION_EMAIL`.
- **Check every decision reason for a student's or staff member's name before
  `add-decisions` or `record-answers` writes it.** Both refuse an email or an
  ID-like number; neither can detect a name.
- A triage item's `stub` holds the group's real values. It may reach the
  analyst's chat, never GitHub.
- Validation-file changes go in their own commits, apart from tool changes, with
  each file staged by name.
- Tableau writes go only to the `TEMP-CB` project.
- Source anchors are entered by hand under `anchors:` with `measure`, `value`,
  `source`, `as_of`, `date_range` and `filters`. Judge each difference in
  triage; there is no threshold, and an exact match is not expected.
- A measure whose strongest check is "consistent only" is never reported as
  validated.

## Running a command

Tableau and `CUBE_API_SECRET` come only from the pytest secrets fixture, and
only the MAIN checkout's devcontainer template holds the Cube secret. So
`discover`, `prove`, `check-api`, `run` and `triage` go through a throwaway
`tests/test_zz_cube_validation.py` in `/workspaces/teamster`, never a worktree
copy:

1. Write the runner, filling in the worktree path, the URL (the Cube Cloud REST
   base ending `/cubejs-api/v1`; never commit it) and the arguments:

   ```python
   import importlib.util
   import sys

   PKG = "<worktree>/scripts/cube_validation"


   def test_cube_validation(monkeypatch):
       monkeypatch.setenv("CUBE_REST_URL", "<url>")
       spec = importlib.util.spec_from_file_location(
           "cube_validation", f"{PKG}/__init__.py", submodule_search_locations=[PKG]
       )
       assert spec and spec.loader
       module = importlib.util.module_from_spec(spec)
       sys.modules["cube_validation"] = module
       spec.loader.exec_module(module)
       from cube_validation import cli

       assert cli.main(["prove", "<worktree>/src/cube/validation/<view>.yml",
                        "--comparison", "<id>"]) == 0
   ```

2. Run `uv run pytest tests/test_zz_cube_validation.py -s --tb=short`, then
   delete the file.

`review`, `add-decisions`, `reapply`, `record-answers` and `preflight` need no
credentials: run them from the checkout that holds the validation files with
`uv run python -m scripts.cube_validation <command> ...`. Exit 0 is done, 1 is a
refusal (stderr says why), 2 is a usage error. A refusal is an answer: fix its
cause, do not retry around it.

## Runbook

1. List the measures. Ask the analyst which measures and which view; a file
   needs `time_dimension` whenever it has `rows` or anchors.
2. `discover <file> --measure <name>` ranks workbook fields: calculated fields
   and aggregated raw fields (`SUM(Membership)`). Pass
   `--caption "<name the dashboard shows>"` to rank that field first, and
   `--all` (or `--limit N`) to see past the top 5. A formula that uses a code
   group prints its codes. Each listed sheet's shape follows: shelves, long or
   wide export, displayed decimals, and filters. A filter on any field outside
   the reference columns prints "chosen values hidden": decide with the analyst
   whether the probe needs it, and never look up or copy its values. A filter on
   a code group (a bin such as Discipline) is listed the same way; the probe
   applies it, or `shelves: {clear_filters: [...]}` clears it. Show the analyst
   the candidates. A name-alike field can mean something else, so no comparison
   is written until the analyst confirms it. With the workbook already on disk,
   `--twb <path>` reads it instead of downloading and signs in to no Tableau
   (Cube still compiles the measure); `prove` always exports.
   `prove <file> --comparison <id> --headers` prints each cut's export headers
   (and a long export's field names) without probing, to find `sheet_field`
   before the first proof.

   Then `preflight <file> --twb <path> --sheet <sheet>` reads the chosen sheet
   offline (it needs `members.json` from `members`, and prints no filter or
   parameter value): each shelf field and its Cube member, table calcs and what
   they run along, every filter's kind (context, code group, relative date,
   parameter-driven) and whether other sheets share it through `filter-group`,
   the parameters the sheet reads, and whether `sheet_field` is on the sheet.
   Use it instead of reading the workbook XML by hand. Without `--sheet` it
   checks every comparison's sheet. `--twb` is required, since preflight never
   signs in to Tableau: download the workbook once through the runner, with this
   in place of its `cli.main` call, and reuse that file:

   ```python
   import pathlib

   with cli.tableau_session() as tbl:
       twb = tbl.download_twb("<workbook luid>")
   pathlib.Path("<scratchpad>/<name>.twb").write_text(twb, encoding="utf-8")
   ```

3. Write the comparison into the view file with `confirmed: true` and
   `proof: null`. Required: `workbook`, `sheet`, `dashboard_view`, `probe` (or
   `probe_sql`, never both), `decimals`, `dims`, `filters`, `defaults`, `cuts`,
   `rows` grain and values. Use the exact keys in `config.py`. Optional keys:
   - `sheet_field`: the field to compare, by its exported caption. In a long
     export (`Measure Names` / `Measure Values` columns) it is a `Measure Names`
     value; otherwise a column header. Required when the export has more than
     one value column.
   - `split_rows: sum`: adds export rows that share every mapped dim, for a
     sheet split by a field Cube lacks (a homeroom, a teacher). Use it only for
     a field that adds up (a sum or a count), never an average or a rate.
   - `dashboard_filters`: a sheet filter Cube has no member for, applied to the
     dashboard side only (`{dashboard: enroll_status, values: [0]}`). The run
     result names it, since rows it drops read as Cube-only. Use it instead of
     writing the filter into `probe_sql`.
   - `scope` and `dashboard_filters` take `equals` (the default), `not_equals`,
     `gt`, `gte`, `lt` and `lte` (exactly 1 number), or `set` (not null). A
     dashboard filter compares a date to the coming Sunday (Tableau's
     `TODAY() + 8 - weekday`) with `days_from_week_end: <days after it>` and a
     compare operator in place of `values`; it runs at the run's moment (see
     _Gotchas_ for the Saturday-evening window).
   - `parameters: {<caption>: <member>}`: a field the sheet shows only behind a
     parameter value (Chronic Absenteeism under "Attendance Metric"). The proof
     copy carries that value, so the REST export shows the field. Put the
     parameter here, never in `cuts`: a cut takes only `filters:` captions.
   - `shelves: {drop: [<caption>], add: {rows: [<caption>]}}`: the sheet's rows
     or columns hold a field Cube cannot map (a combined calc, a week, an id).
     The proof copy drops it and adds mapped fields (each under `dims`), and
     Tableau recomputes the measure, so an average stays right where
     `split_rows` cannot. The proof then covers the reshaped grain, not the
     sheet's own; tell the analyst, and the run result says so. A dropped
     field's sorts, formats and any table calc along it leave the copy (that
     calc's column leaves the export); its filters stay. `prove --headers` names
     the removed table calcs and the kept ones that now recompute along the new
     rows or columns; a compared field among them needs the analyst's call.
     `clear_filters: [<caption>]` resets that sheet's filter on each caption to
     every member (the analyst's call to validate past it, such as all subjects,
     not ELA).
   - `definitions: {dashboard: ..., cube: ...}`: what each side counts, in a
     sentence or a code list. The review issue shows both for a comparison with
     a domain-owner question. It goes to GitHub: never name a person.

   Comparisons that repeat a block (one sheet, several fields) take it from a
   YAML anchor under a top-level `shared:` key: `<<: *roster`, then the keys
   that differ. Identities take numbers as well as measures
   (`right: 1 - pct_ontime`).

4. Run `preflight <file> --twb <path>` again and settle its "Before prove" list
   with the analyst; prove only when it reads "nothing blocks" or each item left
   is a decision the analyst made. `prove <file> --comparison <id>` exports the
   sheet from a `TEMP-CB` copy and writes `proof` when the probe reproduces
   every cell at `decimals`. Repeat `--comparison` to prove several at once:
   comparisons on one sheet share one export, and one refusal does not stop the
   rest. A failed proof (cells mismatch) means the probe or the mapping is
   wrong: check the probe, then the dims, cuts, filters, `sheet_field` and
   `split_rows`; never loosen `decimals`. It prints a count per reason and 5
   samples; the full list is in the local cache. A "cannot export" or "7 days"
   refusal is not a failed proof: retry after the refresh. The proof records the
   cuts its export covered, and the sheet's cuts and filters with no Cube member
   (by caption; filter values are never read).
5. `check-api <file>` once per view, before the first `run`. A disagreement
   means Cube's API and its compiled SQL differ, so `run` results are not
   trustworthy until it is explained.
6. `prove <file> --check` before every `run`. `run` never reads the workbook, so
   only this catches a dashboard owner's edit; re-prove each proof it lists.
   `run` warns when a proof is more than 7 days old.
7. `run <file>` (add `--moment <ISO time>` for a build within the last 7 days).
   It prices queries first and stops over `--max-usd`. Every run on this machine
   also shares a daily cap, `--max-usd-per-day` (UTC day), and view versions
   found in BigQuery's job history are cached in the local cache, so a repeat
   run does not pay to look them up again. A proof with no recorded cuts is
   listed under "Cuts to prove in the browser" for a re-prove. Prove every
   comparison in the file before the first `run`, then run once: a `run`
   re-queries every comparison, so proving them one at a time and running after
   each multiplies the cost. Run again only for a new build, a changed Cube
   model or dashboard, or new comparisons; decisions are re-applied offline.
   `--fact-dataset zz_<user>_kipptaf_marts` (on `prove`, `check-api`, `run` and
   `triage`) reads the fact from a dbt dev build instead of the file's `fact:`,
   to prove a mart change before it merges; give `triage` the same dataset as
   the `run` it reads.
8. `triage <file>` reads the latest run and writes `triage.json` beside its
   `run.json`. It sorts every open item (row groups, cell differences, missing
   cuts and filters) into one pile: `map_filters`, `filters_nothing`, `cause`,
   then `investigate`, each with a masked label and its evidence. Start from the
   summary it prints first; a flood in one bucket means fix the grain. It lists
   25 items per pile; `triage.json` holds them all. Run `triage` after every
   `run`: `add-decisions` and `review` read only the triage beside the latest
   run and refuse one of another moment or one missing any of the run's open
   items.

   Every item must reach a proven cause before anything is recorded: a step (a
   filter, join or rule in either side's SQL, or in a model it reads) shown row
   by row to drop every one of the item's rows. `add-decisions` and `review`
   refuse while the view's latest triage holds an `investigate` item, per view
   file. Never present a guess as a cause: a member description or a cell
   pattern is a lead to trace, not a cause.

   The trace proves row groups. Before sorting, `triage` traces each one-sided
   row group of a comparison with `rows`: Cube-only rows through the dashboard
   side's SQL, dashboard-only rows through Cube's. The steps are WHERE and
   HAVING conjuncts, INNER JOINs and their non-key ON filters, and LEFT JOINs a
   later predicate requires; a row pick (QUALIFY, `rn = 1`) never is. At each
   level, by the grain:

   - A row 1 step alone brings back is attributed to it. A row several steps of
     one scope each bring back is attributed to them as one cause (`A / B`);
     across scopes it stays unattributed.
   - The rest are checked for presence: every step of the level and of every
     level above neutralized, row picks too, its tables unchanged. A present row
     is attributed to the 1 pair of steps in one scope that brings it back
     (`A + B`); 3 or more steps, steps in 2 or more scopes, or a row pick stay
     unattributed. A present row never descends.
   - Only a row missing from a table descends into it, through the table's dbt
     compiled SQL as of the run's moment, 3 tables deep.
   - A grain the other side holds twice is never attributed.

   A group whose rows are all attributed lands in `cause` with each cause and
   its rows; otherwise it stays in `investigate` with the counts and why the
   rest are unattributed. Counts that would let a small part be worked out read
   `masked`.

   - Cost: the level-0 total is printed before any trace query runs, then each
     later query's price before it runs, with a running total; each is refused
     past `--max-usd` or the daily cap. The daily cap's ledger stays in the
     default cache whatever `CUBE_VALIDATION_CACHE` says. A cap or
     `--trace-max-minutes` (default 120) hit partway stops the trace: what it
     found is kept, the rest say "trace stopped", and `triage.json` is still
     written, groups proven before the stop keeping their cause. A dry run that
     fails partway stops it the same way. No row leaves BigQuery; a failed query
     keeps only its job id and reason. `--no-trace` skips it and leaves every
     row group in `investigate`.
   - Compiled SQL: the trace reads `src/dbt/kipptaf/target/prod/manifest.json`
     in the checkout running the tool (`--manifest` for another). Before any
     trace query, `triage` refuses when the manifest or a model's compiled SQL
     is missing, and prints the `dbt deps` and
     `dbt compile --target prod --target-path target/prod` command; run it from
     the repository root, then `triage` again. It names every model the trace
     needs, because a compile drops the compiled SQL of every model it does not
     select. Compile in a checkout whose dbt code built the tables (`main` as of
     the run's moment): a table whose compiled SQL no longer runs is skipped and
     named ("below"), and rows its SQL returns unrelaxed are never attributed.
     Before triaging several views, compile once with every model their refusals
     name, or each view's compile strips the others'.
   - Its SQL must be the run's: `triage` refuses when either side's SQL changed
     since the run; `run` again first.
   - `CUBE_VALIDATION_CACHE` points every command at another cache, such as a
     copy of a run to rework without touching the live one.

   - Investigate: no proven cause yet. Read what the trace found, then work the
     unattributed rows by hand through the other side's SQL and the models it
     reads until one step accounts for every row. It never goes to the owner,
     and it leaves `investigate` only when `triage` files it under `cause`.
   - Map under `filters:`: a `same values: map it under filters:` verdict. Once
     the analyst approves the batch, map the field under the comparison's
     `filters:` instead of recording a decision, then re-prove the comparisons
     it sits on, since the proof records the missing field.
     `same field, different coding` is not a map: the codes differ, and the item
     stays where triage put it.
   - Filters nothing: `deliberate`, quoting the evidence.
   - A `cause` item is one of these (step 9 lists the calls):
     - Deliberate: the proven step is intended on that side.
     - Known issue: search open GitHub issues (`mcp__github__search_issues`, by
       measure, member, region and school words) for one that names the step.
       The call is the one that issue fixes (`fix_source` for source data,
       `fix_cube` for the Cube model), with the issue as `task`.
     - Owner: a question only the owner can settle about the proven step, such
       as whether WPP should count or which date anchors a score. It becomes a
       `domain_owner` decision with an empty `task`, and only these reach
       `review`.

   A missing cut or filter is a sheet field Cube has no member for. Unless it
   maps or filters nothing, the workbook carrying it is the proof: it lands in
   `cause` as the dashboard step `sheet filter <caption>` (or `sheet cut`), and
   the owner decides whether Cube needs it. "Cell differences" lists candidate
   causes (patterns, where they cluster, both definitions): leads to check, not
   findings, and cell sets stay in `investigate`. Rows a `dashboard_filters`
   entry drops read "dashboard filtered", not Cube-only: the reconcile proves
   each row, so the group lands in `cause` under that filter.
   `not compared: identifier column` means values were not compared, for
   privacy; never compare them by hand. `also covers:` lists the sibling groups
   the same decision would close: approve the item only if its cause is proven
   for each. Anchor differences are judged here too.

9. The calls:
   - `deliberate`: the difference is intended. Say what the Cube member counts
     in its `description:`; reasoning stays in the decision.
   - `fix_dashboard`: the workbook or its view is wrong. Task: the domain's
     Asana dashboard-fix task.
   - `fix_cube`: the Cube model is wrong. Task: the domain's GitHub Cube-fix
     issue.
   - `fix_source`: the source data is wrong. Task: the GitHub issue for that
     data's owner. The tool does not read GitHub: when that issue closes, `run`
     again.
   - `domain_owner`: the owner decides what is right. Task: the validation issue
     from step 10, filled in after it is posted.

   Draft a reason for every item, so the analyst edits rather than writes: a
   close quotes the evidence or names the issue; an owner item names the proven
   step and the question it leaves, which his session shows him. Show the
   analyst one batch, numbered across piles in the order above, owner items
   last; each line has the masked label, the evidence, the call and the drafted
   reason. On "approve all" or "approve all but 2 and 6", the excluded items
   stay unrecorded until the analyst says where they go. Write the approved
   items, owner items included, to `approved.json` in the session scratchpad: a
   JSON list of `{"id", "call", "reason", "task", "item"}`, where `item` is the
   triage item id, `id` a new decision id not already in the file, and `task`
   empty for `deliberate` and `domain_owner`. Map items are not in it. Then
   `add-decisions <file> <approved.json>`: it takes each decision's key fields
   from the item's stub and its fingerprints from the latest run, and writes the
   whole batch or nothing, then re-applies every decision to the saved run
   offline, so `review` reads it with no new `run`. After a hand edit to
   `decisions:`, `reapply <file>` does the same.

   Before `review`, give the file a top-level `tasks:` block,
   `{cube_fix: <the domain's Cube-fix issue>, dashboard_fix: <its Asana dashboard-fix task>}`:
   `record-answers` takes a `fix_cube` or `fix_dashboard` answer's task from it
   and refuses the comment without it.

   Edit a decision by hand only to change one. Its keys: `id` (unique),
   `comparison`, `group`, `call`, `reason`, `task` (required for every `fix_`
   call) and the `fingerprints` `{cube, dashboard}` from that comparison's run.
   `task` is an `https://` link or `#<issue>`; the loader refuses other text.
   `group` is a mapping: `column` is the Cube member name (such as
   `regions_region_name`), and `values` are compared as text, quoted exactly.
   YAML rewrites an unquoted `9.50`, `010` or `no`, so the loader refuses one. A
   decision covers its group only while both fingerprints hold; do not copy
   fingerprints from another run. A missing cut or filter takes
   `missing_cut: <caption>` or `missing_filter: <caption>` in place of `group`,
   with no `comparison` and no `fingerprints`: it covers the field across the
   view. A comparison's cell differences take `cells: true` in place of `group`,
   with its `comparison` and `fingerprints`. Rows a dashboard-only filter drops
   take `group: { column: dashboard_filter, values: [<its column>] }`.

10. `review <files> --domain <domain>` prints the validation issue's body: the
    numbered questions, each with the owner's hand checks, and a closing JSON
    block the owner's session reads. It refuses unless every file's view has a
    triage with nothing in `investigate`. stderr names any question with no
    triage evidence: `triage` that view and render again before posting. The
    footnote promises that identifiers of students and staff are hidden, which
    holds only if no reason or definition names a person: read them first. Show
    the draft to the analyst, then post it with `mcp__github__issue_write`,
    titled "Validate <dashboard> in Cube", using the repo's issue template. That
    issue is the validation's hub. Then write `task: "#<issue>"` into each
    decision stderr lists; filling in a task needs no new `run`. Tell the
    analyst the owner answers in his own Claude Code session by saying "walk me
    through issue #N" (the `cube-validation-answers` skill). When that session
    reports the pinned SQL expired, `run` again, render `review` again, and
    update the issue body.
11. On "pick up the answers on #N", read only the comment the analyst names; if
    they name none, ask which, never take the latest. Save its body to a file in
    the session scratchpad and show the analyst its author's login. Check its
    notes for a student's or staff member's name; if one is there, the owner
    rewords it in a new comment. Run
    `record-answers <files> --comment <file> --author <login>` without `--yes`,
    show the analyst the printed changes, and on their confirmation run it again
    with `--yes`. It re-applies the decisions to each file's saved run offline;
    a file it prints as "not re-applied" needs `run`. A refusal refuses the
    whole comment: tell the analyst why and ask the owner for a corrected
    comment; never edit the saved body to make it pass. The validation issue
    closes when every question has a decision and every fix has its issue, PR or
    Asana task.

## Gotchas

What `preflight` cannot check:

- Which rows a dashboard holds: confirm an assumption ("Illuminate only", "one
  region") in the data, not by reading SQL. A dashboard's source can carry rows
  its code never names.
- A Cube member's `description:` can drift from its data; check the claim before
  quoting it.
- Do not start a `run` between 8 pm and midnight ET on a Saturday: the week can
  shift if Tableau Server's clock is not Eastern.

## Results

- Only "matches a dashboard" with every cell passing reads "validated". An
  "anchored to a source" measure reads "judge the anchor": the analyst judges
  the difference in triage, and it is never reported as validated. Neither is
  "consistent only".
- "validated" covers cells. A measure line that adds "open row groups to triage"
  or "missing cuts or filters to triage" is not done until they are triaged.
- `scope` filters Cube's measure query, not only its rows: a scoped comparison
  checks a narrower number than an unscoped Cube query returns. Say so when
  reporting a scoped measure.
- A cut no proof's export covered (a parameter cut, or one added since the
  proof) is evaluated by the proven probe and listed under "Cuts to prove in the
  browser".
- Sources read as they are now (Google Sheets externals) are named in the
  result; carry that caveat into the review issue.
