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
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`.

## Running a step that needs credentials

`open`, `export`, `close`, `compare` and `explain` need the Tableau PAT or
`CUBE_API_SECRET`. Only the pytest secrets fixture provides them. Write this
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
        # A failed open or export must not leave the review copy behind.
        if script == "cube_validate_snapshot" and argv[0] in ("open", "export"):
            mod.main(["close", CHECKS])
        raise
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback.

## Validating a dashboard

1. **Header.** Create `checks/<dashboard>.yml` with `workbook`, `workbook_luid`,
   `review_project_luid` (TEMP-CB, `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`),
   `dashboards`, `student_count` (the Cube student-count member) and
   `scope: {filter: <region caption>}`.
2. **Plan.** Run `cube_validate_snapshot.py plan <checks>` (credentialed; it
   downloads the workbook). Show the analyst the trees, the borderline pairs and
   the must, optional and skipped states as one table per dashboard. Save their
   edits as `trees`, `cross_cuts`, `accept_nesting` and `states`.
3. **Open.** `open <checks>`: sweeps stale copies, publishes the review copy,
   exports the planned states, downloads the extracts.
4. **Map.** From the exported CSV headers, draft `sheets:`: each column's Cube
   member (from Cube `meta`) and extract SQL. The analyst approves the mapping.
   See _Mapping keys_ below.
5. **Compare.** `cube_validate.py compare <checks>`. It writes `cells.jsonl` and
   `next_states.yml` in the snapshot. After changing a mapping, run
   `compare --redo`: a plain compare skips states it has already compared.
6. **Descend.** While `next_states.yml` is not empty:
   `export <checks> --states <snapshot>/next_states.yml`, then compare again.
7. **Close.** `close <checks>`, always, including after a failure. Confirm the
   output says the copy is gone.
8. **Explain.** `cube_validate.py explain <checks>`.
9. **Report.** `cube_validate.py drafts <checks>` (no secret). Read the digest
   and the coverage report.

## Mapping keys

Under `sheets.<sheet>`: `datasource` (the extract's caption), `dims` and
`measures`, keyed by the column caption Tableau exports.

- **Dimension:** `cube` (member, or none when Cube lacks it), `sql` (extract
  column or expression). Add `person: true` for a student column, or
  `person: a teacher` for staff: outputs and draft queries then show that label,
  never the value.
- **Measure:** `cube`, then `sql` or `num` and `den`. `round: <n>` when the
  export shows a plain number rounded to n decimals (without it, "36.24" must
  equal Cube exactly). `scale` multiplies Cube's value (100 when Cube returns a
  fraction the sheet shows as a whole number). `table_calc: percent_of_total` or
  `running_sum`. `missing_members` and `variants` explain gaps.

At the top level:

- `filters`: `{caption: {cube: member}}` for filter cards not shown as a column;
  add `person:` here too.
- `cube_filters` and `extract_filters`: the dashboard's hard filters on each
  side, optionally per `datasource`. Mark test-record filters `private: true` so
  they never reach a draft.
- `param_filters` (`{caption: {value: [cube filters]}}`) and `param_where`
  (`{caption: {value: sql}}`): what a parameter value filters, on each side.
  Leave a parameter out when it only changes what a sheet shows.

## Reading the results

- **`filter_ignored` state:** the `vf` caption is wrong (Tableau ignores an
  unknown field silently). Fix the caption, then export that state again.
- **`incomplete`, "extract SQL does not reproduce Tableau":** the mapping's SQL
  is wrong, not Cube. Fix the mapping. Never file this as a Cube issue.
- **`fail`:** a gap nothing explains yet. Find the cause with SQL over the
  extract, then add a `mismatches:` entry and a variant on the measure.
- **Variants:** `sql`, or `num` and `den`, or `where` (limits every aggregate of
  the measure's own formula) on the dashboard side; `cube_filters` for "Cube
  without these rows". A cell is explained only when one variant accounts for
  its whole gap.
- **`fix:`** says who fixes a mismatch: `cube`, `dashboard` (add `where: rpt`
  for the model), `source`, or `undecided` (the domain owner decides).

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

Read each filed issue's state, labels and comments. A closed issue gets
`closed_on`. On an undecided issue, the label `fix-cube` or `fix-dashboard`, or
a comment starting with the word, sets `fix`. Then open a new session for the
states those cells came from, compare, explain, and report again.

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
