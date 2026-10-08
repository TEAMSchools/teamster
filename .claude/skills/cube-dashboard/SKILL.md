---
name: cube-dashboard
description:
  "Use when checking that Cube matches a Tableau dashboard for the measure rows
  in the Asana project 'Data Marts + Semantic Layer': validating cube-covered
  rows against the live dashboard at every grain, authoring or updating a
  dashboard's checks file, reading a validation report, or posting results to
  Asana. Triggers: 'validate <dashboard> in Cube', 'does Cube match Tableau', a
  mismatch tag, ~/asana-sync/validation, checks/<dashboard>.yml."
---

# cube-dashboard

Validate mode compares Cube with what a Tableau dashboard shows, at every grain
the dashboard's sheets use, for the dashboard's done measure rows in Asana
("Data Marts + Semantic Layer", gid `1213735218595734`). Design:
`docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`.

A row passes only if every cell at every grain is within tolerance: counts
exactly, rates within 0.1 point. A total can match while a school is far off;
that is the case this exists to catch (#5692).

Verdicts, strongest first: `fail` (a gap nothing explains), `incomplete` (a
grain errored, or a Tableau construct on the row's sheets is unaccounted),
`missing_member` (every gap is explained by a member Cube lacks), `pass`. Each
comment lists the missing Cube members, with the cells they explain and the
grains they block, so the user knows what to add.

## Validate a dashboard

1. Rows. Read the dashboard task's subtasks from Asana; keep the completed ones
   whose notes have `Status:`. Never touch Anthony's six checklist subtasks.
2. Checks. Open `checks/<dashboard>.yml`. For any done row with no entry, author
   one (below). Show new or changed entries to the user and wait for approval
   before running.
3. Run. Write `tests/test_zz_cube_dashboard_run.py` (template below), run
   `uv run pytest tests/test_zz_cube_dashboard_run.py -s -q --tb=short`, then
   delete it. The run downloads the workbook with its extracts and compares Cube
   with the dashboard's own extract, not the live warehouse view. First run with
   `--scope-only`. A `ScopeError` means the Cube identity sees less than the
   dashboard; a `TimingError` means the extract and the Cube fact are more than
   an hour apart (one of them did not refresh). Stop and tell the user either
   way.
4. Renders. For each tab in the entries' `renders:`, call
   `mcp__tableau__get-view-image` once per region (`viewFilters` set to that
   region) and at the worst failing cells. Compare the visible numbers to the
   report. A render that disagrees with the check SQL means the SQL is wrong:
   mark the row `incomplete` in your summary and fix the entry before posting
   anything. A render shows aliased labels (a school id shown as its name); map
   a label back to its value from the column's `<aliases>` in the `.twb` before
   comparing.
5. Review. Walk the user through
   `~/asana-sync/validation/<date>-<dashboard>-fixes.md`, the fix digest. "Add
   to Cube" lists each missing member that explains gaps, merged across rows,
   with what it is, where it lives and the suggested edit. "Investigate" lists
   each row's gaps nothing explains, with the breakdown by its `diagnose_by`
   field and the dashboard and Cube definitions side by side: enough to name the
   cube or model edit. Note any pre-aggregations on failed grains (a stale
   rollup is a different fix from a mart gap). "Unaccounted Tableau constructs"
   lists what the checks file must account for before the row can pass; "Not
   checked" lists what the check deliberately skips, with why.
6. Post. After the user agrees, post the digest once on the dashboard's Asana
   task, then each row's three-line `comment` from
   `~/asana-sync/validation/<date>-<dashboard>.json` verbatim, both with
   `mcp__claude_ai_Asana__add_comment`.
7. Tags. Tell the user to run `~/asana-sync/sync.py` (preview, then `--apply`).
   It reads `latest.json`: `fail` rows get the `mismatch` tag, and
   `missing_member` rows are unticked and tagged `cube-partial`. The skill never
   changes tags or ticks itself.

Run template:

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
EXTRA: list[str] = []  # e.g. ["--scope-only"] or ["--rows", "<gid>"]


def test_run() -> None:
    # The pytest fixture loads the secrets; the child process inherits them.
    # tableauhyperapi reads the extract and is not a project dependency.
    cmd = ["uv", "run", "--with", "tableauhyperapi", "scripts/cube_validate.py", "run"]
    cmd += [str(CHECKS), "--as", "<network-scoped email>", *EXTRA]
    print("exit", subprocess.run(cmd, cwd=ROOT).returncode)
```

## Author a check entry

1. Download the workbook to `.claude/scratch/cube-dashboard/<dashboard>.twb`
   with a throwaway pytest (`tableauserverclient`, `include_extract=False`; it
   appends the extension, so pass the stem).
2. Run `uv run scripts/cube_validate.py grains <twb> --dashboard "<view>" ...`
   with every published view name from `mcp__tableau__get-workbook`, then again
   with `--measure "<caption>"`. Keep its `grains` and each sheet's `formula`.
3. Translate the formula to BigQuery-dialect SQL over the extract's columns,
   which carry the same names as the `rpt_tableau__*` model behind the
   datasource; the run translates it to Hyper's dialect. `grains` resolves field
   copies and expands parameter branches, drill levels and subtotals into
   grains. Match what the dashboard counts, not what the Cube measure counts;
   comment on any deliberate difference.
4. Map every grain dimension in `dimensions:`; one with no Cube member gets
   `cube: null`. Its grains are not comparable, and the dimension is listed as a
   missing member. Also list each such grain without that dimension: the sheet's
   numbers roll up to it.
5. Constructs. `grains --measure` lists every construct on the measure's sheets
   under `constructs`, each with a `key`. Account for each one:
   - A group or bin: paste its `dimension` snippet, set `kind: relabel` (codes
     rolled into buckets) or `kind: rule` (a definition), and set `cube:` to a
     member whose values equal the bin labels, or leave it null. Values in no
     bin keep their own value; when the dashboard shows an Other bar instead,
     add `other: Other` to the group.
   - A filter, set or source filter: reproduce it in `hard_filters`,
     `cube_filters` or `truth_filters`, reading its mode (exclude, nulls,
     context), not just the field name.
   - An LOD: FIXED ignores every filter except context filters; translate it
     with only those inside.
   - Then list the key under the file's `handled:` with what reproduces it.
     Anything the check cannot reproduce (table calculations, viewer functions,
     a total that sums rows) goes under the row's `not_checked:` with `why`.

   Set the file's `dashboards:` to the published dashboard names and each
   metric's `tableau:` to its caption; without them the run cannot audit the row
   and marks it `incomplete`.

6. When the formula uses a field Cube lacks (a filter on homeroom, say), list it
   under the metric's `missing_members:` and add the same SQL without it as
   `sql_without` (or `num_without`/`den_without`). A cell Cube matches only
   without it is reported as explained by that member, not as a bug.
7. `count` for sums and distinct counts, `rate` with `num`/`den` for shares
   (within 0.1 point), `average` with `num`/`den` for a mean in its own units,
   such as a scale score (within 0.1 unit). Give a metric
   `diagnose_by: {cube, sql}` when one field explains most definition gaps (the
   attendance code for attendance counts), and describe each missing member
   under the file's `members:` (`what`, `lives_in`, `suggested_edit`) so the
   digest can say what to add.
8. Check the file loads (`load_checks`), then run the new row alone
   (`--rows <gid>`) so its SQL runs once against the extract.

## Rules

- Aggregates only. Never put student names or ids in a comment, the report, or
  chat. Comments already hide cells under 10 students.
- Render only tabs that show aggregates. A roster tab (one row per student)
  renders student names into the session; list it under `renders:` never.
- Never mark a construct handled that the check does not reproduce. A wrong
  `handled:` entry hides the gap the audit exists to show.
- The scratchpad can be wiped: workbooks go in
  `.claude/scratch/cube-dashboard/`, results in `~/asana-sync/validation/`,
  checks in this folder.
- Build mode (work a dashboard's blocking table tasks) plugs in later through
  two things only: append the row's entry here, then
  `run <checks> --rows <gid>`; a built row is done when that returns `pass`.
