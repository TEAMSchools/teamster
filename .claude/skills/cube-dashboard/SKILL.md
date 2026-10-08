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

## Validate a dashboard

1. Rows. Read the dashboard task's subtasks from Asana; keep the completed ones
   whose notes have `Status:`. Never touch Anthony's six checklist subtasks.
2. Checks. Open `checks/<dashboard>.yml`. For any done row with no entry, author
   one (below). Show new or changed entries to the user and wait for approval
   before running.
3. Run. Write `tests/test_zz_cube_dashboard_run.py` (template below), run
   `uv run pytest tests/test_zz_cube_dashboard_run.py -s -q --tb=short`, then
   delete it. First run with `--scope-only`; a `ScopeError` means the Cube
   identity sees less than the dashboard, so stop and tell the user.
4. Renders. For each tab in the entries' `renders:`, call
   `mcp__tableau__get-view-image` once per region (`viewFilters` set to that
   region) and at the worst failing cells. Compare the visible numbers to the
   report. A render that disagrees with the warehouse SQL means the SQL is
   wrong: mark the row `incomplete` in your summary and fix the entry before
   posting anything.
5. Review. Summarize the verdicts for the user: rows that fail, the worst cell
   for each, any grain errors, any pre-aggregations on failed grains (a stale
   rollup is a different fix from a mart gap).
6. Post. After the user agrees, post each row's `comment` from
   `~/asana-sync/validation/<date>-<dashboard>.json` verbatim with
   `mcp__claude_ai_Asana__add_comment`.
7. Tags. Tell the user to run `~/asana-sync/sync.py` (preview, then `--apply`).
   It reads `latest.json` and adds or removes the `mismatch` tag; the skill
   never changes tags itself.

Run template:

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
EXTRA: list[str] = []  # e.g. ["--scope-only"] or ["--rows", "<gid>"]


def test_run() -> None:
    spec = importlib.util.spec_from_file_location("cube_validate", ROOT / "scripts/cube_validate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    print("exit", mod.main(["run", str(CHECKS), "--as", "<network-scoped email>", *EXTRA]))
```

## Author a check entry

1. Download the workbook to `.claude/scratch/cube-dashboard/<dashboard>.twb`
   with a throwaway pytest (`tableauserverclient`, `include_extract=False`; it
   appends the extension, so pass the stem).
2. Run `uv run scripts/cube_validate.py grains <twb> --dashboard "<view>" ...`
   with every published view name from `mcp__tableau__get-workbook`, then again
   with `--measure "<caption>"`. Keep its `grains` and each sheet's `formula`.
3. Translate the formula to SQL on the dashboard's `rpt_tableau__*` table.
   Resolve groups (`categorical-bin` columns in the `.twb`) and parameters.
   Match what the dashboard counts, not what the Cube measure counts; comment on
   any deliberate difference.
4. Map every grain dimension in `dimensions:`; one with no Cube member gets
   `cube: null` and is reported as not comparable, not as a mismatch.
5. `count` for sums and distinct counts, `rate` with `num`/`den` for averages.
6. Check the file loads (`load_checks`) and each total-grain SQL runs once in
   BigQuery.

## Rules

- Aggregates only. Never put student names or ids in a comment, the report, or
  chat. Comments already hide cells under 10 students.
- The scratchpad can be wiped: workbooks go in
  `.claude/scratch/cube-dashboard/`, results in `~/asana-sync/validation/`,
  checks in this folder.
- Build mode (work a dashboard's blocking table tasks) plugs in later through
  two things only: append the row's entry here, then
  `run <checks> --rows <gid>`; a built row is done when that returns `pass`.
