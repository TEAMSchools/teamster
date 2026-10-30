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
  commit. The terminal and local files (`triage.json`, the cache) show exact
  counts. Text bound for GitHub or a commit (the review issue, decision YAML,
  the run report you post) shows counts under 10 as `<10`, and hides any count
  that would give one away; mask a terminal count the same way before posting
  it.
- Nothing committed names a person or holds an email. Pass `--email` (a
  network-grant address) or set `CUBE_VALIDATION_EMAIL`.
- **Check every decision reason for a student's or staff member's name before
  `add-decisions` or `record-answers` writes it.** Both refuse an email or an
  ID-like number; neither can detect a name.
- A triage item's `stub` holds the group's real values. It may reach the
  analyst's chat, never GitHub.
- Validation-file changes, proof files under `src/cube/validation/proofs/`
  included, go in their own commits, apart from tool changes, with each file
  staged by name.
- Tableau writes go only to the `TEMP-CB` project.
- Source anchors are entered by hand under `anchors:` with `measure`, `value`,
  `source`, `as_of`, `date_range` and `filters`. Judge each difference in
  triage; there is no threshold, and an exact match is not expected.
- A measure whose strongest check is "consistent only" is never reported as
  validated.

## Running a command

Tableau and `CUBE_API_SECRET` come only from the pytest secrets fixture, and
only the MAIN checkout's devcontainer template holds the Cube secret. So
`discover`, `prove`, `check-api`, `run`, `triage` and `triage confirm` go
through a throwaway `tests/test_zz_cube_validation.py` in
`/workspaces/teamster`, never a worktree copy:

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

2. Run it from `/workspaces/teamster`, where the secrets load, with the
   validator worktree's environment, so the branch's sqlglot is used:
   `uv run --project <worktree> pytest tests/test_zz_cube_validation.py -s --tb=short`.
   Then delete the file.

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
   - `rows.dashboard_scope`: the dashboard's half of a `scope`, for the row
     reconcile only (`[{dashboard: iep_status, values: [No IEP]}]` beside
     `scope` on `is_iep`). Without it, every row of the other status reads
     dashboard-only. Not a `dashboard_filters` entry: that one filters the probe
     too, which loses every cell with no rows in scope while the sheet still
     shows it blank.
   - `scope`, `dashboard_filters` and `rows.dashboard_scope` take `equals` (the
     default), `not_equals`, `gt`, `gte`, `lt` and `lte` (exactly 1 number), or
     `set` (not null). A dashboard filter compares a date to the coming Sunday
     (Tableau's `TODAY() + 8 - weekday`) with
     `days_from_week_end: <days after it>` and a compare operator in place of
     `values`; it runs at the run's moment (see _Gotchas_ for the
     Saturday-evening window).
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

   The Tableau token is shared with Dagster's scheduled Tableau refreshes (and
   any Tableau MCP call), and Tableau keeps 1 session per token: any other
   sign-in ends the validator's, as a 401 mid-run. Each call then signs in again
   once and is retried; a second 401 in a row, or a fourth new sign-in in one
   session, stops `prove`. Each comparison it finished is already written, and
   the refusal prints the `prove ... --comparison` command for the rest: run
   that, not the whole list. A token used by the validator alone removes the
   clash; issuing one is the analyst's call.

5. `check-api <file>` once per view, before the first `run`. A disagreement
   means Cube's API and its compiled SQL differ, so `run` results are not
   trustworthy until it is explained.
6. `prove <file> --check` before every `run`. `run` never reads the workbook, so
   only this catches a dashboard owner's edit; re-prove each proof it lists.
   After a republish it compares the sheet's formulas and filters and its
   datasources' connection and filters with the proof's, and keeps a proof
   neither changed ("republished ..., sheet unchanged"). A proof saved before
   the datasource check is listed once ("re-prove once"). `run` warns when a
   proof is more than 7 days old.
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
   then `investigate`, each with its label and its evidence. It lists 25 items
   per pile; `triage.json` holds them all. Run `triage` after every `run`:
   `add-decisions` and `review` read only the triage beside the latest run and
   refuse one of another moment, one missing any of the run's open items, one
   with an item in `investigate`, or one whose proof file changed since.

   Nothing goes to the owner without a cause proven row by row. A row group
   reaches `cause` only through a stored proof (below), including one whose
   values differ on rows both sides hold (`--bucket value_differs`) and one
   whose rows both sides hold in different cells (`--bucket dims_differ`: the
   group's columns are Cube's cell, its `d:` columns the dashboard's). A missing
   cut or filter reaches it from the workbook (`sheet filter <caption>` or
   `sheet cut`), and rows a `dashboard_filters` entry drops ("dashboard
   filtered") from the run's own reconcile, as the cause
   `sheet filter <caption>`. A cell set reaches it when every differing cell's
   rows lie in groups in `cause` and the cell's size checks out, so a cell set
   needs `rows` on its comparison to be provable: add `rows` before `run`. For a
   count, the cell's difference must equal the groups' net rows. For a rate with
   1 value column, each side's cell rebuilt from its rows (the mean of the value
   column) must show the run's value. The run keeps the sums per cut when every
   caption the cuts set differently (a default all cuts share is skipped) is a
   `rows` column on both sides; otherwise a cell under a cut whose column the
   rows are not grouped by cannot be sized and stays open. A run saved before
   per-cell sums links without the rate check and says so: `run` again to check
   sizes. A member description, a cell pattern or a trace count is a lead, never
   a cause. A run saved before groups recorded their NULLs is refused ("this run
   predates NULL-aware groups"): `run --moment <its moment>` again.

   The trace leads. `triage` relaxes each step of the other side's SQL (WHERE
   and HAVING conjuncts, INNER JOINs, required LEFT JOINs, down 3 dbt models)
   and prints "lead: relaxing <step> brings back N of M rows" on each one-sided
   group; a row in the tables that no single step brings back reads "lead: no
   single step brings it back". It prices level 0 first and each later query
   before it runs, under `--max-usd` and the daily cap; a cap,
   `--trace-max-minutes` (default 120) or a failed dry run stops only that
   bucket. `--no-trace` skips it. It reads
   `src/dbt/kipptaf/target/prod/manifest.json` (`--manifest` for another) and,
   when compiled SQL is missing, refuses with the `dbt compile` command to run
   from the repository root; compile in a checkout whose dbt code built the
   tables, once for every view you triage. It refuses when either side's SQL
   changed since the run: `run` again. Counts are exact in the terminal and
   `triage.json`; `review` quotes the masked copy (`evidence_posted`).

   Prove causes with the analyst, in short turns, not alone:

   1. Show the analyst the clusters before any SQL: the summary's buckets
      (near-equal Cube-only and dashboard-only totals mean the grain fails to
      join, not lost rows), then the `investigate` groups counted by side and by
      each group-by column.
   2. Before any SQL, read each doc an item's `lead: read docs/models/...` line
      names (the docs that mention the comparison's dashboard model or Cube
      fact), and search open issues (`mcp__github__search_issues`). Member
      descriptions are not evidence: they have not explained a missing row. Then
      read the model SQL along the lineage, both sides.
   3. For each cluster, first split its rows by which pieces exist on the other
      side, one aggregate query: is the student there, is the assessment (or the
      other key) there, is only a code different? Counts only. A whole key
      missing points straight at a cause (C3 below).
   4. Then propose one hypothesis per cluster: its lead, the model predicate it
      names, and the one aggregate query that tests it. Run it once the analyst
      agrees. Queries return counts only; rows stay in BigQuery.
   5. After 2 failed hypotheses on one cluster, or about $0.50 spent, stop and
      ask the analyst for context.
   6. Write the proof: one query per comparison and bucket that reads
      `{unmatched}` and returns exactly `__row, cause`, one row per unmatched
      row. `{unmatched}` holds `__row`, `item_key`, `side`, the group-by
      columns, the grain under its Cube names, and `__rn` (past 1, a grain the
      other side holds twice). A `CASE` in lineage order names each row's first
      failing predicate, copied literally from the model's SQL. The cause is ONE
      `CASE` whose every `THEN` is a quoted cause name (no `IF()`, nested `CASE`
      or column there) and which ends in `ELSE 'UNEXPLAINED'`, never in a cause:
      a later run's rows of a new cause must not be filed under an old one. A
      row the join misses must fall to `'UNEXPLAINED'` too: test the join first
      (or use `EXISTS`), and join a table at the row's grain, since a finer one
      repeats rows. Name each table as dbt compiles it, every part in its own
      backticks: `` `teamster-332318`.`kipptaf_marts`.`dim_assessments` ``.
      `` `teamster-332318`.kipptaf_marts.dim_assessments `` and
      `` `teamster-332318.kipptaf_marts.dim_assessments` `` are refused, and
      `confirm` warns of a table named with no project and dataset. Tables are
      read as of the run's moment: the build start, or the build end for a table
      only the Cube side reads, which is refused if it changed during the build.
      A proof may open with its own `WITH`.

      ```sql
      SELECT u.__row,
        CASE
          WHEN r.assessment_id IS NULL THEN 'UNEXPLAINED'
          WHEN r.module_type = 'WPP' THEN 'C1'
          WHEN r.module_type IS NULL AND r.source = 'apex' THEN 'C2'
          ELSE 'UNEXPLAINED'
        END AS cause
      FROM {unmatched} AS u
      LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_assessments` AS r
        ON r.assessment_id = u.assessment_id
      ```

   7. `triage confirm <file> --comparison <id> --bucket <cube_only|dashboard_only|value_differs|dims_differ> --sql <draft.sql> --cause C1=dashboard:<plain words> ...`
      (through the runner) needs a `--cause` for every cause literal the query
      returns. The tool counts the rows itself, joining the proof back to
      `{unmatched}`, and refuses a row the proof drops or repeats, a cause that
      is not that one `CASE` of quoted names ending in `ELSE 'UNEXPLAINED'`, any
      column but `__row` and `cause`, a grain or ID column as the cause, a
      literal compared with a column that names a person (the student column, a
      `_number`, `_name` or `_email`, a student id or key;
      `assessment_id = 189131` is fine), and an ID-like number or email in a
      comment or string. These checks catch the common mistakes, not every one:
      read the proof yourself. It is priced and capped like any query. It saves
      the proof to
      `src/cube/validation/proofs/<view>/<comparison>__<bucket>.sql`, under lint
      opt-outs and its `-- cause <bucket> = <side>: <words>` block, and moves
      each item it fully explains (no `UNEXPLAINED`) to `cause`. The rest stay,
      with "proof <file> leaves N rows unexplained". `--items <ids>` narrows the
      printout only. After an edit, run it again without `--sql`. A proof whose
      query would pass 900K characters with both sides inline (BigQuery refuses
      past 1,024K) first freezes its bucket's unmatched rows in a BigQuery
      session temp table ("Froze ... unmatched rows"), which halves the query;
      the rows never leave BigQuery. A shorter proof runs inline, which is
      faster.

      Give each owner cause a live count the owner can run after time travel
      ends: a `-- reproduce <bucket>:` block in the proof's header, the query as
      comment lines below it, ending at a blank line. It counts the cause's rows
      on today's tables with the cause's predicates (for example "Cube rows in
      AY2026 whose `module_type` is WPP, by school"): aggregates and their GROUP
      BY columns only, no `{unmatched}` and no time travel. `confirm` refuses
      one that names no cause of the proof, returns a row, a grain or
      identifying column, or an ID-like literal, or fails its dry run, before
      the proof runs. It is no part of the proof's fingerprint, so adding one
      later re-opens nothing.

      ```sql
      -- cause C1 = dashboard: the dashboard drops WPP modules
      -- reproduce C1:
      --  SELECT r.school_abbreviation, COUNT(*) AS n_rows
      --  FROM `teamster-332318`.`kipptaf_marts`.`fct_assessment_scores` AS r
      --  WHERE r.academic_year = 2026 AND r.module_type = 'WPP'
      --  GROUP BY r.school_abbreviation
      ```

      `--cells --comparison <id>` confirms a cell set, or refuses with the count
      of cells outside proven groups and, for a count, the gap between the
      cells' differences and the proven rows; for a rate, how many cells do not
      rebuild from their rows or cannot be sized. Before refusing it prints each
      open cell: its dims, cut, both values, the groups it matched with their
      bucket and pile, and why it stayed open (with the rebuilt values for a
      rate). Those lines are unmasked: keep them out of GitHub.

   8. Show the analyst the proof file and the per-cause counts `confirm`
      printed, and wait for an OK before the file is kept for commit. On a no,
      delete the file and run `triage --no-trace` again.
   9. Proven means 2 things: `UNEXPLAINED` is 0 for the item, and each bucket's
      rule is a literal model predicate, not a paraphrase of a doc. For the rows
      a predicate drops, a second aggregate shows the value (the date, the flag,
      the missing key).

   Comparisons that differ only in `dims`, `measure` or what shapes their cells
   (same `dashboard_view`, `rows`, `filters`, `defaults`, `cuts`, `scope` and
   `dashboard_filters`) usually reconcile the same rows. Prove one of them: its
   proof also runs on the others' groups of that bucket, in `confirm` (printed
   as "Also <comparison> (same rows)") and in every `triage`, unless one has a
   proof file of its own, which then wins, even when it fails. Each run checks
   that comparison's own rows, so a dim whose join drops or repeats rows shows
   as a refusal there. Delete a duplicate file to share.

   Every `triage` re-runs every stored proof on the new run's rows first, priced
   and capped (`--no-proofs` skips them), then traces only what no proof
   explains; an item with rows a proof no longer explains returns to
   `investigate`. Re-triage a run whose leads are in hand with `--no-trace`;
   trace again only when new items appeared. The proof files are the durable
   record: commit them with the decisions, in the validation-file commit. They
   hold SQL only: no values, no names. A formatting-only edit to one re-opens
   nothing.

   Worked example (DDI). Cube-only rows were classified through the dashboard's
   `responses` CTE, dashboard-only rows through Cube's fact:

   | Bucket | Side      | Model predicate                                                               | Found through                                     |
   | ------ | --------- | ----------------------------------------------------------------------------- | ------------------------------------------------- |
   | C1     | dashboard | `r.module_type != 'WPP'`                                                      | The domain doc and a `TODO: Remove SY26` comment  |
   | C2     | dashboard | `module_type is null and source = 'apex'`: the `!=` drops a NULL              | The doc's "untagged assessments never appear"     |
   | C3     | dashboard | the rollup's `academic_year`: the administration date sits a year early       | Comparing `date_taken`, the canonical date, title |
   | C4     | dashboard | the join to a week row covering `administered_at`                             | One date before the first enrollment week         |
   | C5     | dashboard | `is_enrolled_week_end`, `enroll_status`, `not is_out_of_district`             | Testing each flag of the `where` alone            |
   | C6     | dashboard | the sheet's Exclude Future Assessments (`dashboard_filters`)                  | Already a dashboard-only filter                   |
   | D1     | cube      | `score_anchors`: `not sc.is_replacement`                                      | Reading `score_anchors`; a known issue            |
   | D2     | cube      | the resolver's `anchor_date >= cc_dateenrolled and anchor_date < cc_dateleft` | Sections in the subject exist, none spans it      |
   | D3     | cube      | the resolver's homeroom tier: no section on the date                          | The same resolver                                 |
   | D4     | cube      | `dim_student_section_enrollments` key with no `dim_student_enrollments` row   | A query on the dimension chain                    |

   Dead ends there: an "off-grade" guess over-matched until `is_replacement`
   named the rule; a "week join" label hid C4 until each flag was tested alone;
   filtering anchors by `academic_year = 2026` dropped every internal anchor,
   whose year is null.

   - Investigate: no proven cause yet. It never goes to the owner.
   - Map under `filters:`: a `same values: map it under filters:` verdict. Once
     the analyst approves the batch, map the field under the comparison's
     `filters:` instead of recording a decision, then re-prove the comparisons
     it sits on, since the proof records the missing field.
     `same field, different coding` is not a map: the codes differ, and the item
     stays where triage put it.
   - Filters nothing: `deliberate`, quoting the evidence.
   - A `cause` item is one of these (step 9 lists the calls):
     - Deliberate: the proven step is intended on that side.
     - Known issue: an open GitHub issue names the step. The call is the one
       that issue fixes (`fix_source` for source data, `fix_cube` for the Cube
       model), with the issue as `task`.
     - Owner: a question only the owner can settle about the proven step, such
       as whether WPP should count or which date anchors a score. It becomes a
       `domain_owner` decision with an empty `task`, and only these reach
       `review`.

   `not compared: identifier column` means values were not compared, for
   privacy; never compare them by hand. A proven row group is decided on its
   causes, not its school: every group a cause explains shares one decision.
   Anchor differences are judged here too. `CUBE_VALIDATION_CACHE` points every
   command at another cache, such as a copy of a run to rework.

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
   close quotes the item's `evidence_posted` in `triage.json` (masked), never
   the terminal's exact counts, since the reason is committed, or names the
   issue; an owner item names the proven step and the question it leaves, which
   his session shows him. Show the analyst one batch, numbered across piles in
   the order above, owner items last; each line has the label, the evidence, the
   call and the drafted reason. On "approve all" or "approve all but 2 and 6",
   the excluded items stay unrecorded until the analyst says where they go.
   Write the approved items, owner items included, to `approved.json` in the
   session scratchpad: a JSON list of
   `{"id", "call", "reason", "task", "item", "cause"}`, where `item` is the
   triage item id, `id` a new decision id not already in the file, `task` empty
   for `deliberate` and `domain_owner`, and `cause` the cause's words, needed
   only on an item with several causes: give such an item one entry per cause,
   each with its own call. Map items are not in it. Then
   `add-decisions <file> <approved.json>`: a proven row group (a stored proof's,
   or a sheet filter's) becomes one `cause:` decision per cause that has none
   yet, never a `group:` decision; a cause already decided keeps its decision,
   so give every entry on one cause the same call. An item is decided once every
   one of its causes is; approving it again changes nothing. Other items take
   their key fields from the stub. Fingerprints come from the latest run and the
   proof. It writes the whole batch or nothing, then re-applies every decision
   to the saved run offline, so `review` reads it with no new `run`. After a
   hand edit to `decisions:`, `reapply <file>` does the same.

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
   with its `comparison` and `fingerprints`. Never hand-write a `group:` or
   `cells:` decision for an item triage holds in `investigate`: `add-decisions`
   and `review` refuse while one closes such an item. A proven cause takes
   `cause: {side, label}` in place of `group`, `label` being the proof's words
   with each ID-shaped number written `<n>`, and `fingerprints` adds `proof`,
   the proof's. It names no group: each `triage` re-runs the proofs and marks an
   item `decided` when every one of its causes has a decision that still holds,
   so a run never closes one. A decision whose SQL or proof changed decides
   nothing until re-approved through `add-decisions`, never by pasting new
   fingerprints; one the owner answered (`answer:`) is never re-approved: delete
   it to ask again. `add-decisions` writes these; do not hand-write one. A cause
   decision and a `group` decision on one group with different calls refuse.

10. `review <files> --domain <domain>` prints the validation issue's body: the
    numbered questions, each with the owner's hand checks, and a closing JSON
    block the owner's session reads. Each unanswered `domain_owner` cause is one
    question, across the comparisons it is proven on, with its words, per
    comparison the count of groups it decides and of the rows its proof
    attributes to it, and the model-doc leads; the owner's answer records onto
    every decision it lists. Each cause question also gets a folded Reproduce
    block: each example cell as a Cube `load` query for Claude chat's Cube
    connector, each distinct `-- reproduce` count once (labeled today's data),
    then per proof file a branch link and the `triage confirm` that re-proves it
    at the run's moment, and the `run` plus `triage` after time travel ends.
    Commit and push the proofs before posting, or the link finds nothing. When
    the Reproduce blocks would take the body past GitHub's 65,536-character cap,
    they move out of it into numbered comment files that stderr names: post the
    issue, then each file as a comment, in order (the JSON in the body still
    holds everything the owner's session reads). If stderr still warns that the
    body is too long, review fewer views at a time. It refuses unless every
    file's view has a triage with nothing in `investigate`. stderr names any
    question with no triage evidence: `triage` that view and render again before
    posting. The footnote promises that identifiers of students and staff are
    hidden, which holds only if no reason or definition names a person: read
    them first. Show the draft to the analyst, then post it with
    `mcp__github__issue_write`, titled "Validate <dashboard> in Cube", using the
    repo's issue template. That issue is the validation's hub. Then write
    `task: "#<issue>"` into each decision stderr lists; filling in a task needs
    no new `run`. Tell the analyst the owner answers in his own Claude Code
    session by saying "walk me through issue #N" (the `cube-validation-answers`
    skill). When that session reports the pinned SQL expired, `run` again,
    render `review` again, and update the issue body.
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
12. Tell Cube's users why a number differs on purpose. Run `describe <files>`
    (no credentials, writes nothing): per measure, every `deliberate` decision
    (the analyst's, or an owner's answer) as what differs and its reason, and a
    draft `meta.ai_context` sentence ("Differs from <dashboard> on purpose:
    ..."). The MCP chat reads `ai_context`, so an analyst asking why Cube does
    not match the dashboard gets the answer. Show the analyst the draft and
    reword it with them: plain words, no student or staff value, under Cube's
    2,000-character cap. Then, on a branch of its own off `origin/main`, Read
    `.claude/rules/cube-authoring.md` and add the sentence to the member's
    `ai_context` (the view's, for a note on reading the whole view; a view
    override restates the member's own), keeping any text already there.
    `description:` takes it only when it defines the raw column. Run
    `uv run pytest tests/cube/`, open the PR (`Refs` the validation issue), and
    merge it with the validation PR or after it.

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
