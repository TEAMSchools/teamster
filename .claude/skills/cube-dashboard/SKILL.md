---
name: cube-dashboard
description:
  Use when validating Cube against a Tableau dashboard, re-checking one after a
  Cube or workbook fix, mapping a dashboard's sheets to Cube members, or filing
  or following up on the GitHub issues a validation drafted. Triggers: "validate
  <dashboard> against Cube", "does Cube match Tableau", "follow up on
  <dashboard>", cube_validate, ZZ-REVIEW copies in TEMP-CB, or any file under
  .claude/skills/cube-dashboard/checks/.
---

# cube-dashboard

Truth is what Tableau shows. A review copy of the workbook is published to
TEMP-CB, each state a person can reach is exported, Cube is compared with each
export, and SQL over the dashboard's own extract explains each gap. Design:
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`; its
last revision section is binding.

## Running a step that needs credentials

`open`, `export`, `close`, `map`, `compare` and `explain` need the Tableau PAT
or `CUBE_API_SECRET`. Only the pytest secrets fixture provides them. Write this
throwaway file, change `ARGS`, run it, and delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

CHECKS = ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
ARGS = ("cube_validate_snapshot", ["open", CHECKS])


def _load(name):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_step():
    script, argv = ARGS
    mod = _load(script)
    try:
        assert mod.main(argv) == 0
    except BaseException:
        # A failed open or export must not leave the copy unnoticed: close
        # prints its name and URL for the analyst to delete.
        if script == "cube_validate_snapshot" and argv[0] in ("open", "export"):
            mod.main(["close", CHECKS])
        raise
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback.

## When to run

Timing depends on the dashboard. Settle it before the first `open`.

- **Its extract refreshes.** Find the dashboard's
  `kipptaf__tableau__<dashboard>_extract_refresh_schedule` in
  `docs/reference/automations.md` (New York time). Every export must finish
  before the next one: `export` ends the session when the live workbook changes.
  DDI Suite refreshes at 1:00 AM, at 6:00 PM, and at 4:00 PM on Fridays, so its
  exports run weekdays between 9 AM and about 5 PM, never late Friday.
- **The shared token.** The tool signs in with the same PAT as Dagster's Tableau
  refreshes and the Tableau MCP; another sign-in ends the tool's session. It
  waits about a minute and signs in again, up to 5 times. Exports also pause
  during `tableau_quiet_minutes` (checks file, default `[0, 10]`), because the
  hourly refreshes in `automations.md` sign in just after each hour. Widen it if
  a run still loses its session at another minute.
- **No Tableau MCP calls during a run.** Each one signs in with the same token.
- **The nightly dbt build.** `explain` reads the live `rpt_` tables and Cube;
  finish `compare` and `explain` the same day as the export.
- **How long it takes.** On DDI (6 sheets): `open` with 49 cuts took about 25
  minutes and `compare` about 1.5 minutes per cut. Plan the descent so its
  exports also land before the next extract refresh; `compare` and `explain`
  need no Tableau and can run after it.

## Validating a dashboard

1. **Header.** Create `checks/<dashboard>.yml` with `workbook`, `workbook_luid`,
   `review_project_luid` (TEMP-CB, `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`),
   `dashboards`, `student_count`, `scope: {filter: <region caption>}` and
   `asana_task` (the dashboard's Asana task id).
2. **Plan.** `cube_validate_snapshot.py plan <checks>`. Show the analyst the
   trees, the borderline pairs, the must, optional and skipped states, and each
   dashboard's sheets. Save their edits as `trees`, `cross_cuts`,
   `accept_nesting` and `states`. List the sheets to compare under `sheets:` as
   stubs (`<sheet>: {datasource: <caption>}`). Never list a student-level sheet
   (one with a name column such as `Lastfirst`).
3. **Open the default view only.** `open <checks> --states <file>`, the file
   holding only the default state. Only the listed sheets and click sources are
   exposed on the copy. `open` refuses while an earlier copy of the workbook is
   still in TEMP-CB.
4. **Map.** `cube_validate.py map <checks>` writes `<snapshot>/map.yml`: each
   exported column with its workbook formula and candidate Cube members. Draft
   `sheets:` from it; the formula decides the SQL
   (`COUNT([x]) / TOTAL(COUNT([x]))` is a share of rows, not of students). The
   analyst approves the mapping. See _Mapping keys_.
5. **Compare the default view.** `compare <checks>`. Fix the mapping and run
   `compare --redo` until the default view's mismatches are real gaps.
6. **Asana rows.** List the dashboard task's measure rows from Asana (read
   only). Sort each into `rows:` (dashboard, sheet, and the measure or dimension
   caption, mapped on a listed dashboard) or `rows_deferred:` with a reason
   (unmapped, lives on an unlisted dashboard, or no Cube member). Map a gap, or
   add its dashboard, before exporting. Show the analyst both lists. Nothing in
   Asana is renamed or edited.
7. **Live checks**, the first time a workbook is validated: _Live checks_.
8. **Export the rest.** `export <checks>`, then `compare`, then one descent
   level: `export <checks> --states <snapshot>/next_states.yml` and compare
   again. Stop at two levels: they show where each gap sits. Drill a third level
   only after `explain`, and only under parents whose cells are still `fail`; an
   explained gap only repeats grade by grade.
9. **Close.** `close <checks>` prints the copy's name and URL. The analyst
   deletes it in Tableau; run `close` again until it says the copy is gone.
   Always, including after a failure. The tool deletes nothing on Tableau.
10. **Explain.** `cube_validate.py explain <checks>`. It saves `cells.jsonl` as
    each batch finishes, so a crash keeps the work done.
11. **Report.** `cube_validate.py drafts <checks>` (no secret). Read the digest
    and the coverage report.

## Live checks

On the default view, before the first full export of a workbook:

- An uncaptioned field filters by its raw name: export one value of
  `dibels_most_recent_composite` (DDI); its mapped sheets must change.
- A group bin name filters its group: `Subject Area (group)` = `Mathematics`.
- `vf(<caption>, "Null")` filters a blank (Is Foundations). Until it does, blank
  states stay optional.
- The high-school section key reproduces: after `compare` and `explain`, the
  Teacher sheet's HS cells are not `incomplete`.
- Both Cube routes run: the coverage report lists queries under "Cube routes".

A `filter_ignored` state means its check failed: fix the caption or value, then
`open --resume --retry-ignored`.

## Mapping keys

Under `sheets.<sheet>`: `datasource` (the extract's caption), `dims` and
`measures`, keyed by the column caption Tableau exports. Optional `cube_filters`
and `extract_filters` apply to that sheet only, on top of the top-level ones.

- **Dimension:** `cube` (a member; a list of members, joined with " - " to match
  `sql`; `{time: <member>, granularity: week}`; or none when Cube lacks it) and
  `sql`. `keys:` regexes tried in order, each with one group around the join
  key; anchor each so a label of another shape never matches, because the
  captured text is shown in every output. `values:` Tableau aliases to stored
  values. `attr: true` for a known attribute. `person: true` for a student
  column, or `person: a teacher` for staff; `load_checks` requires it when `sql`
  reads a name column.
- **Measure:** `cube`, then `sql` or `num` and `den`. `round: <n>` when the
  export shows a plain number rounded to n decimals. `scale` multiplies Cube's
  value. `table_calc: percent_of_total` or `running_sum`. `cube_filters` and
  `where`: Cube filters and an extract condition for this measure alone.
  `diff: [A, B]`: A minus B, two plain measures on the same sheet; no `cube:` or
  variants of its own. `missing_members` and `variants` explain gaps.

At the top level:

- `filters`: `{caption: {cube: member}}` for filter cards not shown as a column;
  `values:` maps extract values to Cube's; `sql:` gives a calculated card's
  extract expression; add `person:` here too.
- `cube_filters` and `extract_filters`: the dashboard's hard filters on each
  side, optionally per `datasource`. Mark test-record filters `private: true` so
  they never reach a draft.
- `param_filters` and `param_where`: what a parameter value filters, on each
  side. Leave a parameter out when it only changes what a sheet shows.
- `ignore_sheet_filters`: saved filters Cube cannot express. `compare` warns
  when an ignored filter would hide rows in a slice. A FIXED-LOD filter cannot
  be counted; link its issue in a comment.
- `rows`, `rows_deferred`, `asana_task`: the Asana rows (step 6).
- `tableau_quiet_minutes: [start, end]`: minutes past each hour when exports
  pause (see _When to run_).
- `mismatches`: below.

## Reading the results

- **`filter_ignored` state:** Tableau ignored the `vf` caption or value
  silently. Fix it, then export that state again.
- **`incomplete`, "extract SQL reproduces N%":** the mapping's SQL is wrong for
  some cells; the coverage report lists them. Fix the mapping. Never file this
  as a Cube issue.
- **`fail`:** a gap nothing explains yet, labelled **row gap** (Cube and the
  live table count different students) or **formula gap** (the same students, a
  different value). The digest's Investigate section prints the extract SQL and
  the same SQL on the live `rpt_` table, ready to run.
- **`cube-routes-disagree`:** Cube answers the same query differently with and
  without the student count, usually a rollup gap. Built in, `fix: cube`; give
  it `issue:` once filed.
- **Variants:** `sql`, `num` and `den`, or `where` on the dashboard side;
  `cube_filters` for "Cube without these rows". A cell is explained only when
  one variant accounts for its whole gap.
- **`fix:`** says who fixes a mismatch: `cube`, `dashboard` (add `where: rpt`
  for the model), `source`, `undecided` (the domain owner decides), or
  `accepted` (an owner ruled it will not be fixed; needs `issue:`; its cells
  pass with a note and the Asana row is not reopened).
- **Limit:** Cube reads its own fact table, not the `rpt_` table. A fail says
  Cube differs from the dashboard's formula on the live `rpt_` table; which dbt
  model is at fault is the analyst's next query. Both sides wrong the same way
  is out of scope by design.

## Filing

1. For each draft and each "Investigate" row, search the repo's issues, open and
   closed, with the GitHub MCP. List the matches beside it.
2. A match that is the same problem becomes the entry's `issue:`; a related one
   goes in `related:`.
3. Show the analyst the full list of drafts before filing anything. File only
   the ones they pick, with the title, labels and body from the draft.
4. Write each new `issue:` into the checks file and commit it. The analyst runs
   `~/asana-sync/sync.py`.

## Following up ("follow up on <dashboard>")

The analyst owns runs. A builder verifies their own fix with the draft's "Check
it yourself" block; the follow-up run confirms it.

1. Read each filed issue's state, labels and comments. A closed issue gets
   `closed_on`. On an undecided issue, the label `fix-cube` or `fix-dashboard`,
   or a comment starting with the word, sets `fix`; a ruling not to fix sets
   `fix: accepted`.
2. Open a new session (default view only), then
   `export <checks> --for <mismatch>` for each mismatch: it exports only the
   states behind that mismatch's cells.
3. `compare`, `explain`, `drafts`. `drafts` replaces every `latest.json` entry
   for the dashboard.

A `rows:` change needs `drafts` only. A new measure mapping needs no export when
its column was already exported: run `compare --measure "<caption>"` and
`explain --measure "<caption>"` (both repeatable, and `--sheet "<sheet>"` too).
They recompute only those cells, in every state, and leave the rest as they
were. A name the checks file does not map is an error.

## Timing

The extract is a snapshot; Cube reads current data. When Cube differs from
Tableau but equals the same SQL run on the live `rpt_` table, the gap is only
the extract's age: `explain` marks it `pass` with a timing note. When Cube's
data is older than the live table, the cell is `incomplete`: re-run `explain`
after Cube refreshes. `explain` reads BigQuery through ADC as well as Cube.

## Rules

- Snapshots hold student-level rows. They stay in `~/.cache/cube-validate/`.
  Never commit them, and never paste row values outside the terminal or
  `#data_team`.
- The checks file is committed, so `states:` never holds a person's name.
- Review copies go to TEMP-CB only, named `ZZ-REVIEW <date> <time> <workbook>`.
  The tool deletes nothing on Tableau; the analyst deletes each copy.
