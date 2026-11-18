---
name: cube-validation
description:
  'Use when asked to validate Cube, check whether Cube matches the dashboard,
  sort (triage) a validation run, pick up the answers on a validation issue
  ("pick up the answers on #N"), or when working in `src/cube/validation/` or
  `scripts/cube_validation/`.'
---

# cube-validation

The validator compares a Cube view's measures with the dashboards that show
them: rebuild the sheet in SQL, compare it with Cube, explain each difference,
ask the owner. Each view's validation file is `src/cube/validation/<view>.yml`;
the code is `scripts/cube_validation/`. Cube loads only `src/cube/model/`, so
these files never reach the semantic layer.

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
  the result you post) shows counts under 10 as `<10`, and hides any count that
  would give one away; mask a terminal count the same way before posting it.
- Nothing committed names a person or holds an email. Pass `--email` (a
  network-grant address) or set `CUBE_VALIDATION_EMAIL`.
- **Check every decision reason for a student's or staff member's name before
  `decide` or `record-answers` writes it.** Both refuse an email or an ID-like
  number; neither can detect a name.
- A sorted item's `stub` holds the group's real values. It may reach the
  analyst's chat, never GitHub.
- Validation-file changes, explanation files under
  `src/cube/validation/explanations/` included, go in their own commits, apart
  from tool changes, with each file staged by name.
- Tableau writes go only to the `TEMP-CB` project.

## Running a command

Tableau and `CUBE_API_SECRET` come only from the pytest secrets fixture, and
only the MAIN checkout's devcontainer template holds the Cube secret. So
`find-field`, `rebuild-sheet`, `compare`, `sort`, `explain` and `members` go
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

       assert cli.main(["rebuild-sheet", "<worktree>/src/cube/validation/<view>.yml",
                        "--comparison", "<id>"]) == 0
   ```

2. Run it from `/workspaces/teamster`, where the secrets load, with the
   validator worktree's environment, so the branch's sqlglot is used:
   `uv run --project <worktree> pytest tests/test_zz_cube_validation.py -s --tb=short`.
   Then delete the file.

`ask-owner`, `decide`, `reapply`, `record-answers`, `read-sheet` and `describe`
need no credentials: run them from the checkout that holds the validation files
with `uv run python -m scripts.cube_validation <command> ...`. Exit 0 is done, 1
is a refusal (stderr says why), 2 is a usage error, an old command or flag name
included (it prints the new one). A refusal is an answer: fix its cause, do not
retry around it.

Every command that reads a run reads the latest run of one fact: with
`--fact-dataset zz_<user>_kipptaf_marts` (on `rebuild-sheet`, `compare`, `sort`
and `explain`) that dbt dev build's, otherwise the validation file's `fact:`
(production). A dev build's results are kept apart from production's, so give
every command of one check the same flag. `decide`, `reapply`, `ask-owner` and
`record-answers` take no `--fact-dataset`, so they read production's. A command
refuses when the view's only run read another fact.

## Runbook

1. List the measures. Ask the analyst which measures and which view; a file
   needs `time_dimension` whenever it has `rows`.
2. `find-field <file> --measure <name>` ranks workbook fields: calculated fields
   and aggregated raw fields (`SUM(<column>)`). Pass
   `--caption "<name the dashboard shows>"` to rank that field first, and
   `--all` (or `--limit N`) to see past the top 5. A formula that uses a code
   group prints its codes. Each listed sheet's shape follows: shelves, long or
   wide export, displayed decimals, and filters. A filter on any field outside
   the reference columns prints "chosen values hidden": decide with the analyst
   whether the sheet query needs it, and never look up or copy its values. A
   filter on a code group (a bin over a code column) is listed the same way; the
   sheet query applies it, or `shelves: {clear_filters: [...]}` clears it. Show
   the analyst the candidates. A name-alike field can mean something else, so no
   comparison is written until the analyst confirms it. With the workbook
   already on disk, `--twb <path>` reads it instead of downloading and signs in
   to no Tableau (Cube still compiles the measure); `rebuild-sheet` always
   exports. `rebuild-sheet <file> --comparison <id> --headers` prints each cut's
   export headers (and a long export's field names) without querying, to find
   `sheet_field` before the first rebuild.

   Then `read-sheet <file> --twb <path> --sheet <sheet>` reads the chosen sheet
   offline (it needs `members.json` from `members`, and prints no parameter
   value and a filter's values only for a field on the allowlist): each shelf
   field and its Cube member, table calcs and what they run along, every
   filter's kind (context, code group, relative date, parameter-driven) and
   whether other sheets share it through `filter-group`, the parameters the
   sheet reads, and whether `sheet_field` is on the sheet. It refuses a text
   measure (compare the numeric measure it is built from) and marks a sheet on
   no published dashboard (step 3, `unpublished`). A sheet filter that keeps
   non-null values only is marked: it needs a `dashboard_filters` entry with
   `operator: set`. Use it instead of reading the workbook XML by hand. Without
   `--sheet` it checks every comparison's sheet, and names a comparison whose
   cells cannot be covered ("Cells cannot be covered: <why>", step 6). `--twb`
   is required, since `read-sheet` never signs in to Tableau: download the
   workbook once through the runner, with this in place of its `cli.main` call,
   and reuse that file:

   ```python
   import pathlib

   with cli.tableau_session() as tbl:
       twb = tbl.download_twb("<workbook luid>")
   pathlib.Path("<scratchpad>/<name>.twb").write_text(twb, encoding="utf-8")
   ```

3. Write the comparison into the validation file with `confirmed: true` and
   `rebuild_check: null`. Required: `workbook`, `sheet`, `dashboard_view`,
   `sheet_query` (or `sheet_query_sql`, never both), `decimals`, `dims`,
   `filters`, `defaults`, `cuts`, `rows` grain and values. Use the exact keys in
   `config.py`. Give every comparison `rows`: without it, or when a cell dim is
   part of the row grain rather than a column the row groups split by, its
   differing cells cannot be covered and stay open. Optional keys:
   - `unpublished: true`: compare a sheet that is on no published dashboard.
     Without it, `read-sheet` and `rebuild-sheet` refuse that sheet and
     `compare` skips it
     (`... not on a published dashboard; set unpublished: true to compare it anyway`).
   - `sheet_field`: the field to compare, by its exported caption. In a long
     export (`Measure Names` / `Measure Values` columns) it is a `Measure Names`
     value; otherwise a column header. Required when the export has more than
     one value column.
   - `split_rows: sum`: adds export rows that share every mapped dim, for a
     sheet split by a field Cube lacks. Use it only for a field that adds up (a
     sum or a count), never an average or a rate.
   - `dashboard_filters`: a sheet filter Cube has no member for, applied to the
     dashboard side only (`{dashboard: <status column>, values: [<value>]}`).
     The result names it, since rows it drops read as Cube-only. Use it instead
     of writing the filter into `sheet_query_sql`.
   - `rows.dashboard_scope`: the dashboard's half of a `scope`, for the row
     reconcile only (`[{dashboard: <status column>, values: [<value>]}]` beside
     a `scope` on the Cube member it matches). Without it, every row of the
     other status reads dashboard-only. Not a `dashboard_filters` entry: that
     one filters the sheet query too, which loses every cell with no rows in
     scope while the sheet still shows it blank.
   - `rows.reduce: {rule: latest, by: <date column>}`: for a dashboard that
     stores one row per key per day where Cube stores one per period. Before the
     reconcile it keeps, within each cut, each grain key's row with the latest
     value of `by`; the key is the `rows` grain. Rows tied on the latest value
     all stay and show as duplicates. With `dashboard_filters`, a row every
     filter keeps outranks one a filter drops, then the latest `by` wins.
   - `scope`, `dashboard_filters` and `rows.dashboard_scope` take `equals` (the
     default), `not_equals`, `gt`, `gte`, `lt` and `lte` (exactly 1 number), or
     `set` (not null). A dashboard filter compares a date to the coming Sunday
     (Tableau's `TODAY() + 8 - weekday`) with
     `days_from_week_end: <days after it>` and a compare operator in place of
     `values`; it runs at the run's moment (see _Gotchas_ for the
     Saturday-evening window).
   - `parameters: {<caption>: <member>}`: a field the sheet shows only behind a
     parameter value (one of several measures a parameter picks between). The
     `TEMP-CB` copy carries that value, so the REST export shows the field. Put
     the parameter here, never in `cuts`: a cut takes only `filters:` captions.
   - `shelves: {drop: [<caption>], add: {rows: [<caption>]}}`: the sheet's rows
     or columns hold a field Cube cannot map (a combined calc, a week, an id).
     The `TEMP-CB` copy drops it and adds mapped fields (each under `dims`), and
     Tableau recomputes the measure, so an average stays right where
     `split_rows` cannot. The rebuild check then covers the reshaped grain, not
     the sheet's own; tell the analyst, and the result says so. A dropped
     field's sorts, formats and any table calc along it leave the copy (that
     calc's column leaves the export); its filters stay.
     `rebuild-sheet --headers` names the removed table calcs and the kept ones
     that now recompute along the new rows or columns; a compared field among
     them needs the analyst's call. `clear_filters: [<caption>]` resets that
     sheet's filter on each caption to every member (the analyst's call to
     validate past it, such as every member instead of one).
   - `definitions: {dashboard: ..., cube: ...}`: what each side counts, in a
     sentence or a code list. The review issue shows both for a comparison with
     a domain-owner question, a formula difference included. It goes to GitHub:
     never name a person.

   Comparisons that repeat a block (one sheet, several fields) take it from a
   YAML anchor under a top-level `shared:` key: `<<: *roster`, then the keys
   that differ. A merge-key item may open with `<<:`; the writers find its
   `id:`.

4. Run `read-sheet <file> --twb <path>` again and settle its "Before
   rebuild-sheet" list with the analyst; rebuild only when it reads "nothing
   blocks" or each item left is a decision the analyst made. `rebuild-sheet`
   refuses a text measure and an unpublished sheet the same way. It skips blank
   cells, `*` total rows and dual-axis repeats; it prints how many total rows
   and blank cells it skipped, but not how many repeats. If a sheet keeps
   non-null values only and its rebuild check was written before the
   `dashboard_filters` entry existed, run `rebuild-sheet` again.
   `rebuild-sheet <file> --comparison <id>` exports the sheet from a `TEMP-CB`
   copy and writes `rebuild_check` (with `matched_at` and
   `sheet_query_fingerprint`) when the sheet query reproduces every cell at
   `decimals`. Repeat `--comparison` to rebuild several at once: comparisons on
   one sheet share one export, and one refusal does not stop the rest. A failed
   match (cells differ) means the sheet query or the mapping is wrong: check the
   sheet query, then the dims, cuts, filters, `sheet_field` and `split_rows`;
   never loosen `decimals`. It prints a count per reason and 5 samples; the full
   list is in the local cache. A "7 days of warehouse history" refusal is not a
   failed match: rebuild after the next refresh. The rebuild check records the
   cuts its export covered, and the sheet's cuts and filters with no Cube member
   (by caption; filter values are never read).

   The Tableau token is shared with Dagster's scheduled Tableau refreshes (and
   any Tableau MCP call), and Tableau keeps 1 session per token: any other
   sign-in ends the validator's, as a 401 mid-run. Each call then signs in again
   once and is retried; a second 401 in a row, or a fourth new sign-in in one
   session, stops `rebuild-sheet`. Each comparison it finished is already
   written, and the refusal prints the `rebuild-sheet ... --comparison` command
   for the rest: run that, not the whole list. A token used by the validator
   alone removes the clash; issuing one is the analyst's call.

5. `compare <file>` (add `--moment <ISO time>` for a build within the last 7
   days). Before any query that bills it checks every confirmed comparison:
   - It skips a comparison with a problem, printing `Skipping <id>: <why>.`, and
     compares the rest: a missing `dashboard_view` or `decimals`, no rebuild
     check, a sheet query changed since its rebuild check, a member Cube's model
     lacks, a workbook changed since its rebuild check or one Tableau errs on,
     SQL that cannot be built today or at the run's moment, a sheet on no
     published dashboard without `unpublished: true`, a pre-aggregation refusal
     (Cube answered from a pre-aggregation: add a Cube-only `scope` on a
     never-null member the rollup does not carry, such as the fact's primary
     key, with `operator: set`), or a dry run that fails. A republished workbook
     whose sheet formulas and filters and datasource connection and filters are
     unchanged is kept, and said so. After the price, it also skips a comparison
     whose Cube SQL reads an `also_facts` table, or whose 2 sides' rows read a
     table, that changed during the build, and one whose query fails in BigQuery
     (its spend stays counted). A BigQuery reason names the job id and reason
     code, never BigQuery's message: look the job up for the message. A failed
     dry run has no job (`job ?`): run that dry run again by hand to see the
     message. A skipped comparison keeps its previous result. Fix what each
     reason names (most say to run `rebuild-sheet` again). Of BigQuery errors in
     a comparison's own dry run or queries, only a cap stops the run; `compare`
     refuses when every comparison is skipped.
   - It names each comparison it will compare and why: `never compared`,
     `its entry or rebuild check changed`, `Cube's SQL changed` or
     `the dashboard SQL changed` (the sheet query or the dbt views it reads). A
     plain `compare` compares only those; `--comparison <id>` (repeatable)
     compares the ones named, and `--all` every one. Changed data alone does not
     make a result stale: to re-validate after a data change, run
     `compare --all`. A dbt table model is read as data, so a plain `compare`
     cannot see a change to its SQL either: after one, run `compare --all`
     (#6158 tracks catching it in CI). With nothing stale, a plain `compare`
     prints "Every comparison's latest result is current" and compares nothing;
     that is not a failure.
   - It dry-runs every query and fingerprint scan it will send and prints one
     total, `Compare: N queries, $X (dry run)`, plus the save script's reads of
     its temp table, which the dry run cannot price and BigQuery caps per query.
     It refuses past `--max-usd` or what is left of the daily cap,
     `--max-usd-per-day` (UTC day, shared by every run on this machine). View
     versions found in BigQuery's job history are cached in the local cache, so
     a repeat run does not pay to look them up again.

   As each comparison finishes it prints a progress line,
   `[HH:MM:SS UTC +<elapsed>] compare <id>: $<spent> spent`, and keeps the
   result as that comparison's latest. Then it prints "<id>: totals not matched"
   for a comparison whose rebuild check skipped the export's total rows or
   records no count, and "Comparison <id>: its cells cannot be covered (<why>)"
   for one without `rows` or whose dims sit in the row grain. A skipped
   comparison keeps its totals line, since the result it keeps leaves the same
   total rows unchecked, but gets no cells line. A validation is each
   comparison's latest result, each at its own moment; `run.json` is composed
   from them. To add a comparison, `rebuild-sheet` it, then
   `compare --comparison <id>`: the others keep their results. Decisions are
   re-applied offline, with no new `compare`. To check a mart change before it
   merges, pass `--fact-dataset zz_<user>_kipptaf_marts` (see _Running a
   command_).

   `compare` saves each comparison's unmatched rows to a table in
   `teamster-332318.cube_validation_scratch` (Data Team only; each table expires
   on its own) for `explain` and `sort` to classify; the rows never reach the
   cache. It checkpoints each comparison in the run folder as it finishes, so a
   stopped `compare` loses at most the comparison in progress. Started again, it
   resumes on its own when the last checkpoint is under 24 hours old ("Resuming
   the unfinished run of ..."); from 24 hours to 7 days it refuses until you
   pass `--resume` (finish at the old moment) or `--restart` (start fresh); past
   7 days only `--restart` works. A plain `compare --comparison <id>` also
   resumes an unfinished run folder, at its old moment. `--moment` resumes that
   moment's unfinished run whatever its age. A comparison whose entry or SQL
   changed since its checkpoint is compared again. `cost_usd` adds every
   process's spend.

6. `sort <file>` reads the latest run and writes `triage.json` beside its
   `run.json`. It first names each confirmed comparison that was never compared,
   is stale, or that the run skipped (`not compared: <why>`), as
   `<view>: comparison <id> <why>; compare it, then sort.` Such a comparison
   waits: `ask-owner` lists it under "Still with the analyst" until it is
   compared. Then `sort` puts every open item (row groups, cell sets, formula
   differences, missing cuts and filters) into one pile (a formula difference
   can sit under row causes, so the check below runs on matched rows):
   `map_filters`, `filters_nothing`, `cause`, then `investigate`, each with its
   label and its evidence. It lists 25 items per pile; `triage.json` holds them
   all. Run `sort` after every `compare`: `explain`, `decide` and `ask-owner`
   read only the sort beside the latest run and refuse one of another moment,
   one missing any of the run's open items, or one whose explanation changed
   since. Items in `investigate` do not block the rest: `decide` writes the
   others, and `ask-owner` asks what is ready.

   Nothing goes to the owner as a question without a cause explained row by row.
   A row group reaches `cause` only through a stored explanation (below),
   including one whose values differ on rows both sides hold
   (`--bucket value_differs`) and one whose rows both sides hold in different
   cells or cuts (`--bucket dims_differ`: the group's columns are Cube's cell,
   its `d:` columns the dashboard's). A missing cut or filter reaches it from
   the workbook (`sheet filter <caption>` or `sheet cut`), and rows a
   `dashboard_filters` entry drops ("dashboard filtered") from the run's own
   reconcile, as the cause `sheet filter <caption>`. A member description, a
   cell pattern or a trace count is a lead, never a cause.

   Differing cells close by coverage. A cell is covered when every row group
   with a row in it, under its cut, is in `cause` or decided; a covered cell
   needs no decision of its own, and a comparison's cell set closes once every
   cell in it is covered by decided groups. A cell with a group that is neither
   stays open. A cell whose rows all matched on both sides is a formula
   difference: the 2 sides compute the number differently. Each comparison's
   formula cells form one item, `<id>:formula`, which reaches `cause` on the
   run's own evidence ("N differing cells hold no unmatched row"), with no
   explanation file. Decide it with `formula: true`, usually `domain_owner`, and
   give the comparison `definitions:` so the owner sees both formulas. A
   comparison without `rows`, or whose cell dims sit in the row grain, cannot be
   placed: its cells stay open with that reason, and `read-sheet` and `compare`
   name it.

   The formula check recomputes each differing cell on rows both sides matched.
   It is priced with the explanations: the same dry run prints
   `Formula check: N queries, $X (dry run).`, under `--max-usd` and the daily
   cap. A cell it cannot check reads `formulas not compared: <why>`: the cell
   closes by coverage as before, the owner sees the comparison under "Still with
   the analyst", and `sort` and `ask-owner` still run. A check that ran is kept
   and reused, unpriced, while its result stands, including one whose cells read
   `no rows both sides hold` or
   `the rewrite does not reproduce the run's cells`: it runs again (and is
   priced again) only after the result changes (`compare` again) or after a
   validator update, so a cause outside both clears on the next `compare`. If
   that re-run cannot run, the kept verdicts stand. Any other reason (a cap, a
   BigQuery or Cube error) is never kept: fix it and `sort` again. `decide` and
   `ask-owner` refuse a triage written before the formula check existed; `sort`
   again.

   The trace leads. `sort` relaxes each step of the other side's SQL (WHERE and
   HAVING conjuncts, INNER JOINs, required LEFT JOINs, down 5 dbt models) and
   prints "lead: relaxing <step> brings back N of M rows" on each one-sided
   group; a row in the tables that no single step brings back reads "lead: no
   single step brings it back". A model whose SQL cannot run (a parse error, too
   long, `resourcesExceeded`, invalid) is skipped with its reason, "not traced:
   <model> skipped (<reason>)", and the trace goes on through the others. A
   bucket that stops, or ends with rows it could not attribute, prints its model
   chain: each model from the side's SQL down to where it stopped, with why. It
   prices level 0 first and each later query before it runs, under `--max-usd`
   and the daily cap; a cap, `--trace-max-minutes` (default 120) or a failed
   level-0 dry run stops only that bucket, keeping what it found. `--no-trace`
   skips it. It reads `src/dbt/kipptaf/target/prod/manifest.json` (`--manifest`
   for another) and, when compiled SQL is missing, refuses with the
   `dbt compile` command to run from the repository root. At 5 models deep, a
   live `sort` can refuse until models 4 and 5 levels below the side's table
   have compiled SQL: run the printed command, in a checkout whose dbt code
   built the tables, once for every view you sort. A comparison whose SQL
   changed since the run, or cannot be built today, waits: `sort` names it
   (above) and leaves its row groups out of the trace; `compare` it, then sort
   again. `sort` prints a progress line after each explanation and each trace
   level. Counts are exact in the terminal and `triage.json`; `ask-owner` quotes
   the masked copy (`evidence_posted`).

   Explain causes with the analyst, in short turns, not alone:
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
      side, one aggregate query: is the student there, is the event (an
      assessment, a day) or the other key there, is only a code different?
      Counts only. A whole key missing points straight at a cause.
   4. Then propose one hypothesis per cluster: its lead, the model predicate it
      names, and the one aggregate query that tests it. Run it once the analyst
      agrees. Queries return counts only; rows stay in BigQuery. Test each
      predicate of a `where` alone: one label can hide 2 causes.
   5. After 2 failed hypotheses on one cluster, or about $0.50 spent, stop and
      ask the analyst for context.
   6. Write the explanation: one query per comparison and bucket that reads
      `{unmatched}` and returns exactly `__row, cause`, one row per unmatched
      row. `{unmatched}` holds `__row`, `item_key`, `side`, the group-by
      columns, the grain under its Cube names, and `__rn` (past 1, a grain the
      other side holds twice). It also holds `__moved` and `__d_<col>`, NULL
      unless that column differs: read the dashboard's value of a column as
      `COALESCE(u.__d_x, u.x)`. A `CASE` in lineage order names each row's first
      failing predicate, copied literally from the model's SQL. The cause is ONE
      `CASE` whose every `THEN` is a quoted cause name (no `IF()`, nested `CASE`
      or column there) and which ends in `ELSE 'UNEXPLAINED'`, never in a cause:
      a later run's rows of a new cause must not be filed under an old one. A
      row the join misses must fall to `'UNEXPLAINED'` too: test the join first
      (or use `EXISTS`), and join a table at the row's grain, since a finer one
      repeats rows. Name each table as dbt compiles it, every part in its own
      backticks: `` `teamster-332318`.`kipptaf_marts`.`dim_schools` ``.
      `` `teamster-332318`.kipptaf_marts.dim_schools `` and
      `` `teamster-332318.kipptaf_marts.dim_schools` `` are refused, and
      `explain` warns of a table named with no project and dataset. Tables are
      read as of the run's moment: the build start, or the build end for a table
      only the Cube side reads, which is refused if it changed during the build.
      An explanation may open with its own `WITH`.

      ```sql
      SELECT u.__row,
        CASE
          WHEN r.record_id IS NULL THEN 'UNEXPLAINED'
          WHEN r.status = 'archived' THEN 'C1'
          WHEN r.status IS NULL AND r.source = 'import' THEN 'C2'
          ELSE 'UNEXPLAINED'
        END AS cause
      FROM {unmatched} AS u
      LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_records` AS r
        ON r.record_id = u.record_id
      ```

   7. `explain <file> --comparison <id> --bucket <cube_only|dashboard_only|value_differs|dims_differ> --sql <draft.sql> --cause C1=dashboard:<plain words> ...`
      (through the runner) needs a `--cause` for every cause literal the query
      returns. The tool counts the rows itself, joining the explanation back to
      `{unmatched}`, and refuses a row the explanation drops or repeats, a cause
      that is not that one `CASE` of quoted names ending in
      `ELSE 'UNEXPLAINED'`, any column but `__row` and `cause`, a grain or ID
      column as the cause, a literal compared with a column that names or
      reaches a person (the student column, a `_name` or `_email`,
      `student_number`, `employee_number`, a phone number, or a student's or
      staff member's id, key, number or identifier; the id of a thing, such as
      an assessment or a school, and a band or module number are fine), and an
      ID-like number or email in a comment or string. These checks catch the
      common mistakes, not every one: read the explanation yourself. It is
      priced and capped like any query. It saves the explanation to
      `src/cube/validation/explanations/<view>/<comparison>__<bucket>.sql`,
      under lint opt-outs and its `-- cause <bucket> = <side>: <words>` block,
      and moves each item it fully explains (no `UNEXPLAINED`) to `cause`. The
      rest stay, with "explanation <file> leaves N rows unexplained". It then
      links the comparison's cells again and prints each cell left open, with
      why; those lines are unmasked: keep them out of GitHub. `--items <ids>`
      narrows the printout only. After an edit, run it again without `--sql`. An
      explanation reads its comparison's unmatched rows from the table `compare`
      saved, so it never rebuilds both sides. A missing table, or one whose
      labels name another run or SQL, refuses and names the next step:
      `compare --comparison <id> --moment <m>` while the moment is within time
      travel, `compare --comparison <id>` at a new moment past it. Editing a
      comparison's entry after `compare` does the same: `compare` again, and
      only that comparison is compared again.

      Give each owner cause a count query the owner can run after time travel
      ends: a `-- reproduce <bucket>:` block in the explanation's header, the
      query as comment lines below it, ending at a blank line. It counts the
      cause's rows on today's tables with the cause's predicates (for example
      "Cube rows in AY2026 whose `status` is archived, by school"): aggregates
      and their GROUP BY columns only, no `{unmatched}` and no time travel.
      `explain` refuses one that names no cause of the explanation, returns a
      row, a grain or identifying column, or an ID-like literal, or fails its
      dry run, before the explanation runs. It is no part of the explanation's
      fingerprint, so adding one later re-opens nothing.

      ```sql
      -- cause C1 = dashboard: the dashboard drops archived records
      -- reproduce C1:
      --  SELECT r.school_abbreviation, COUNT(*) AS n_rows
      --  FROM `teamster-332318`.`kipptaf_marts`.`fct_records` AS r
      --  WHERE r.academic_year = 2026 AND r.status = 'archived'
      --  GROUP BY r.school_abbreviation
      ```

   8. Show the analyst the explanation file and the per-cause counts `explain`
      printed, and wait for an OK before the file is kept for commit. On a no,
      delete the file and run `sort --no-trace` again.
   9. Explained means 2 things: `UNEXPLAINED` is 0 for the item, and each
      bucket's rule is a literal model predicate, not a paraphrase of a doc. For
      the rows a predicate drops, a second aggregate shows the value (the date,
      the flag, the missing key).

   Comparisons that differ only in `dims`, `measure` or what shapes their cells
   (same `dashboard_view` and same `rows` grain and values; `filters`,
   `defaults`, `cuts`, `scope`, `dashboard_filters` and `dashboard_columns` may
   differ) usually reconcile the same rows. Explain one of them: its explanation
   also runs on the others' groups of that bucket, in `explain` (printed as
   "Also <comparison>: N of M items explained.") and in every `sort`, unless one
   has an explanation file of its own, which then wins, even when it fails. Each
   comparison runs it on its own rows, so a dim whose join drops or repeats rows
   shows as a refusal there. A shared explanation reads only `__row`, `side` and
   the grain: a group-by column one sibling lacks fails there. Delete a
   duplicate file to share. Work cause-first: explain a cause once, on the
   comparison that shows it most clearly, let it run on every comparison of that
   model, then work comparison by comparison on what is left.

   Every `sort` re-runs every stored explanation on the new run's rows first
   (`--no-explanations` skips them), then traces only what no explanation
   explains; an item with rows an explanation no longer explains returns to
   `investigate`. It dry-runs every explanation it will run and prints the total
   ("Explanations: N to run, $X (dry run)"); a total over `--max-usd` or the
   daily cap refuses before any runs. An explanation that cannot run (a failed
   check, its saved rows gone, BigQuery rejecting it) prints why and moves
   nothing; the rest still run. Each finished explanation's outcome is kept in
   `triage-progress.json` beside `run.json`, so a stopped `sort` started again
   reuses them ("reused from triage-progress.json"); an edited explanation or a
   changed set of open items runs it again. `--comparison <id>` (repeatable)
   runs, traces and prints only those comparisons; `triage.json` still holds
   every item. Re-sort a run whose leads are in hand with `--no-trace`; trace
   again only when new items appeared. The explanation files are the durable
   record: commit them with the decisions, in the validation-file commit. They
   hold SQL only: no values, no names. A formatting-only edit to one re-opens
   nothing.
   - Investigate: no explained cause yet. It is never asked as a question:
     `ask-owner` lists it under "Still with the analyst", with its masked count
     and the trace's lead.
   - Map under `filters:`: a `same values: map it under filters:` verdict. Once
     the analyst approves the batch, map the field under the comparison's
     `filters:` instead of recording a decision, then run `rebuild-sheet` again
     on the comparisons it sits on, since the rebuild check records the missing
     field. `same field, different coding` is not a map: the codes differ, and
     the item stays where `sort` put it.
   - A sheet filter with no Cube mapping, in any pile, opens its evidence with a
     label. "Cube offers it as `<member>`, unmapped: check before mapping it
     under `filters:`": a name match is a lead, so confirm the member is the
     same field, then map it. "Workbook-only field: no datasource column behind
     it": default call `deliberate`. "Cube has no member: a gap": default call
     `fix_cube`. A `filters_nothing` item takes its label's default call,
     quoting the evidence; with a candidate member, check it and map it instead.
   - A `cause` item is one of these (step 7 lists the calls):
     - Deliberate: the explained step is intended on that side.
     - Known issue: an open GitHub issue names the step. The call is the one
       that issue fixes (`fix_source` for source data, `fix_cube` for the Cube
       model), with the issue as `task`.
     - Owner: a question only the owner can settle about the explained step,
       such as which side's rule is intended, or which of 2 formulas is right (a
       formula difference). It becomes a `domain_owner` decision with an empty
       `task`, and only these become questions in `ask-owner`.

   `not compared: identifier column` means values were not compared, for
   privacy; never compare them by hand. An explained row group is decided on its
   causes, not its school: every group a cause explains shares one decision.
   `CUBE_VALIDATION_CACHE` points every command at another cache, such as a copy
   of a run to rework.

7. The calls:
   - `deliberate`: the difference is intended. Say what the Cube member counts
     in its `description:`; reasoning stays in the decision.
   - `fix_dashboard`: the workbook or its view is wrong. Task: the domain's
     Asana dashboard-fix task.
   - `fix_cube`: the Cube model is wrong. Task: the domain's GitHub Cube-fix
     issue.
   - `fix_source`: the source data is wrong. Task: the GitHub issue for that
     data's owner. The tool does not read GitHub: when that issue closes,
     `compare --all` again.
   - `domain_owner`: the owner decides what is right. Task: the validation issue
     from step 8, filled in after it is posted.

   Draft a reason for every item, so the analyst edits rather than writes: a
   close quotes the item's `evidence_posted` in `triage.json` (masked), never
   the terminal's exact counts, since the reason is committed, or names the
   issue; an owner item names the explained step and the question it leaves,
   which the owner's session shows them. Show the analyst one batch, numbered
   across piles in the order above, owner items last; each line has the label,
   the evidence, the call and the drafted reason. On "approve all" or "approve
   all but 2 and 6", the excluded items stay unrecorded until the analyst says
   where they go. Write the approved items, owner items included, to
   `approved.json` in the session scratchpad: a JSON list of
   `{"id", "call", "reason", "task", "item", "cause"}`, where `item` is the
   sorted item id, `id` a new decision id not already in the file, `task` empty
   for `deliberate` and `domain_owner`, and `cause` the cause's words, needed
   only on an item with several causes: give such an item one entry per cause,
   each with its own call. Map items, items in `investigate` and cell sets are
   not in it. Then `decide <file> <approved.json>`: an explained row group (a
   stored explanation's, or a sheet filter's) becomes one `cause:` decision per
   cause that has none yet, never a `group:` decision; a cause already decided
   keeps its decision, so give every entry on one cause the same call. An item
   is decided once every one of its causes is; approving it again changes
   nothing. A formula item becomes a `formula: true` decision; other items take
   their key fields from the stub. Fingerprints come from the latest run and the
   explanation. Items still in `investigate` wait while the rest are written;
   `decide` refuses an approved entry whose item is itself in `investigate`, or
   one that would close such an item. It writes the whole batch or nothing, then
   re-applies every decision to the saved run offline, so `ask-owner` reads it
   with no new `compare`. After a hand edit to `decisions:`, `reapply <file>`
   does the same.

   Before `ask-owner`, give the file a top-level `tasks:` block,
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
   view. A comparison's formula difference takes `formula: true` in place of
   `group`, with its `comparison` and `fingerprints`; in each run it covers only
   that comparison's differing cells that hold no unmatched row. The loader
   refuses a `cells:` decision and every renamed key, naming what to write
   instead. Never hand-write a `group:` decision for an item `sort` holds in
   `investigate`: `decide` and `ask-owner` refuse while one closes such an item.
   An explained cause takes `cause: {side, label}` in place of `group`, `label`
   being the explanation's words with each ID-shaped number written `<n>`, and
   `fingerprints` adds `explanation`, the explanation's. It names no group: each
   `sort` re-runs the explanations and marks an item `decided` when every one of
   its causes has a decision that still holds, so a run never closes one. A
   decision whose SQL or explanation changed decides nothing until re-approved
   through `decide`, never by pasting new fingerprints; one the owner answered
   (`answer:`) is never re-approved: delete it to ask again. `decide` writes
   these; do not hand-write one. A cause decision and a `group` decision on one
   group with different calls refuse, in `decide`, `reapply` and `ask-owner`,
   even after the `group` decision closed the group. That check reads the closed
   groups the latest `sort` classified, so run `sort --no-trace` after `explain`
   saves a new explanation and before the next `decide`.

8. `ask-owner <files> --domain <domain>` prints the validation issue's body: the
   numbered questions ready for the owner, each with the owner's hand checks,
   and a link to the questions JSON the owner's session reads. Items still in
   `investigate`, and comparisons never compared, stale or skipped, are listed
   under "Still with the analyst" with masked counts and the trace's lead (its
   count and scope only), so the owner can say if one looks familiar. They are
   not questions, and `record-answers` never reads them. Each comparison's
   moment shows in the issue; a question's moment is the earliest of its
   comparisons'. It runs twice. The first run writes the JSON to
   `reviews/<view>.json` beside the validation file (`reviews/<domain>.json`
   across views) and stops: commit it as a validation-file change and push. The
   next run links it at that commit and prints the body; it stops again whenever
   the questions changed or the file is not pushed as it stands. The JSON is
   masked like the body: read it before committing, as git keeps it. A hand
   check leaves out pinned SQL over 20,000 characters a side, giving its
   lengths. A cause question's example cell needs 10+ of the cause's own
   students in that cell and cut, as the explanations counted them: each
   explanation's counting query also counts distinct students per cause, cell
   and cut, and `sort` and `explain` keep the counts in `triage.json`
   (`cause_students`). A formula question's example is a formula cell. Each
   unanswered `domain_owner` cause is one question, across the comparisons it is
   explained on, with its words, per comparison the count of groups it decides
   and of the rows its explanation attributes to it, and the model-doc leads;
   the owner's answer records onto every decision it lists. Every other call
   (`deliberate`, a `fix_`) is listed under "Also decided (no answer needed)",
   one line per call, reason and task, so a cause and the missing sheet filter
   behind it, decided alike, print once: what it covers, the call, the reason
   and the task, masked like the questions and kept out of the JSON, so
   `record-answers` never reads one as an answer. Each cause question also gets
   a folded Reproduce block: each example cell as a Cube `load` query for Claude
   chat's Cube connector, each distinct `-- reproduce` count query once
   (numbered only when there are several, so "1" never reads as a count; labeled
   today's data), then per explanation file a branch link and the `explain` that
   re-explains it at the run's moment, and the `compare --all` plus `sort` after
   time travel ends. Commit and push the explanations before posting, or the
   link finds nothing. When the checks and Reproduce blocks would take the body
   past GitHub's 65,536-character cap, they move out of it into numbered comment
   files that stderr names: post the issue, then each file as a comment, in
   order (the linked JSON holds everything the owner's session reads). stderr
   names any question with no sort evidence: `sort` that view and render again
   before posting. The footnote promises that identifiers of students and staff
   are hidden, which holds only if no reason or definition names a person: read
   them first. Show the draft to the analyst, then post it with
   `mcp__github__issue_write`, titled "Validate <dashboard> in Cube", using the
   repo's issue template. That issue is the validation's hub. Then write
   `task: "#<issue>"` into each decision stderr lists; filling in a task needs
   no new `compare`. As more items settle, render `ask-owner` again and update
   the issue body. Tell the analyst the owner answers in their own Claude Code
   session by saying "walk me through issue #N" (the `cube-validation-answers`
   skill). When that session reports the pinned SQL expired, `compare --all`,
   `sort`, render `ask-owner` again, and update the issue body.
9. On "pick up the answers on #N", read only the comment the analyst names; if
   they name none, ask which, never take the latest. Save its body to a file in
   the session scratchpad and show the analyst its author's login. Check its
   notes for a student's or staff member's name; if one is there, the owner
   rewords it in a new comment. Run
   `record-answers <files> --comment <file> --author <login>` without `--yes`,
   show the analyst the printed changes, and on their confirmation run it again
   with `--yes`. It re-applies the decisions to each file's saved run offline; a
   file it prints as "not re-applied" needs `compare`. A refusal refuses the
   whole comment: tell the analyst why and ask the owner for a corrected
   comment; never edit the saved body to make it pass. The validation issue
   closes when every question has a decision, every fix has its issue, PR or
   Asana task, and nothing is left with the analyst.
10. Tell Cube's users why a number differs on purpose. Run `describe <files>`
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

What `read-sheet` cannot check:

- Which rows a dashboard holds: confirm an assumption ("one source system", "one
  region") in the data, not by reading SQL. A dashboard's source can carry rows
  its code never names.
- A Cube member's `description:` can drift from its data; check the claim before
  quoting it.
- Do not start a `compare` between 8 pm and midnight ET on a Saturday: the week
  can shift if Tableau Server's clock is not Eastern.
- A `% of Total` on a distinct count (`COUNTD`) divides by `TOTAL(COUNTD(...))`,
  which Tableau recomputes over the partition: the distinct entities there, not
  the sum of the marks. A sheet query that divides by `sum(n) over (...)` counts
  an entity at 2 marks twice. Divide by `count(distinct ...) over (...)`
  instead.

## Results

- A measure reads "validated" only when every cell passes and nothing is open.
  Otherwise it reads "differs", with its open items: open row groups, missing
  cuts or filters, and cell differences to sort. A measure of a comparison not
  compared yet reads "not compared yet".
- `scope` filters Cube's measure query, not only its rows: a scoped comparison
  checks a narrower number than an unscoped Cube query returns. Say so when
  reporting a scoped measure.
- A cut no rebuild check's export covered (a parameter cut, or one added since
  the check) is evaluated by the matched sheet query and listed under "Cuts to
  check in the browser".
- Sources read as they are now (Google Sheets externals) are named in the
  result; carry that caveat into the review issue.
