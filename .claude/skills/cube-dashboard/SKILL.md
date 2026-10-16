---
name: cube-dashboard
description:
  Use when validating Cube against a Tableau dashboard, re-checking one after a
  Cube or workbook fix, mapping a dashboard's sheets to Cube members, adding a
  cause to a dashboard's rows layer, or reading a validation report. Triggers:
  "validate <dashboard> against Cube", "does Cube match Tableau", cube_validate,
  ZZ-REVIEW copies in TEMP-CB, or any file under
  .claude/skills/cube-dashboard/checks/.
---

# cube-dashboard

Both sides are captured once, inside the dashboard's evening window, into a
snapshot. Analysis reconciles rows first, then compares each exported number
with Cube's and explains gaps by the rows. Design:
`docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md`.

## Running a step that needs credentials

`plan`, `run`, `answers` and `close` need the Tableau PAT and `CUBE_API_SECRET`;
only the pytest secrets fixture provides them. Write this throwaway file, set
`ARGS`, run it, delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

ARGS = ["run", ".claude/skills/cube-dashboard/checks/<dashboard>.yml"]
PKG = Path(__file__).parents[1] / "scripts" / "cube_validate"


def test_step():
    spec = importlib.util.spec_from_file_location(
        "cube_validate", PKG / "__init__.py", submodule_search_locations=[str(PKG)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    from cube_validate import cli

    assert cli.main(ARGS) == 0
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback. `analyze` needs no secrets:
`uv run --with tableauhyperapi python -m scripts.cube_validate analyze <checks>`.

## When to run

The window is in the checks file and differs per dashboard. Attendance: 3:30 PM
to 6:00 AM New York time, after the 3:00 PM extract refresh and Cube's ~3:05 PM
rebuild. Re-check both times in Dagster before relying on them. `run` refuses
outside the window or when the extract predates this window's refresh. A run
that fails its preflight (window or cost cap) creates no snapshot.

- No Tableau MCP calls during a run: they sign in with the same token.
- A capture costs money; analysis is free and can be repeated.

## Snapshots and resuming

A snapshot is `~/.cache/cube-validate/<dashboard>/<YYYY-MM-DDTHHMM>/`. List that
folder to find the newest.

`run <checks> --snapshot <dir>` resumes an interrupted capture. It resumes only
inside the same window, with unchanged base tables and the same period, and
refuses otherwise.

## First validation of a dashboard

1. `plan <checks>`: downloads the workbook, writes `plan.yml` (sheets, extract
   columns, filter cards, parameters, drafted cuts). Fill `dashboards`,
   `datasource`, `sheets` (stubs) and `cuts`; list under `excluded_sheets`, with
   the reason, every sheet with no Cube counterpart, every sheet on another data
   source ("separate run"), and every sheet that blends 2 data sources
   ("blended, not checked"). Never list a sheet with a name or student-ID
   column. `filter_card_defaults` lists each card's starting value per
   dashboard; a list means the card starts on several values. Copy them into
   `defaults` (a value or a list) and skip `(All)`. A list reads as IN on the
   extract and Cube sides, and a cut's own filter on that card replaces it.
   Defaults differ by dashboard, so 1 checks file covers only the dashboards
   whose defaults match; give the others their own file.
2. Evening 1: `run <checks>`. Rows layer and exports are now frozen. Cells are
   mostly "mapping unproven" or "no Cube counterpart" until mapping.
3. Map from the exports in `<snapshot>/exports/` (see _Mapping a sheet_).
4. Same evening, still in the window: `answers <checks> --snapshot <dir>`. It
   refuses if any base table changed since capture.
5. Build causes from the first report's raw buckets (below), then `analyze`.
6. Work the hand checks (below). Then `close <checks>`; the analyst deletes the
   review copy in Tableau and runs `close` again until it reports none left.

## Mapping a sheet

Declare every column a sheet exports under that sheet: a dim (`dims`), a measure
(`measures`), or the student count (`students`). An undeclared column makes its
rows "no Cube counterpart".

- A dim needs `tableau`, `cube` and `cube_column`; without all three its cells
  read "mapping unproven".
- A measure with no Cube member is declared with `cube: null`.
- Each filter caption goes under `filters`.
- `defaults` holds the values the dashboard's filter cards start on. Every cut
  applies them first, then its own filters, so the default cut stays bare.
  Without them every cut selects rows the dashboard hides, and the student-count
  proof fails.
- A sheet without a student count is proven only by another sheet in the same
  cut that has one and the same filters; otherwise its cells read "mapping
  unproven".
- Cube's `rows.key` part order in the checks file is significant: file order is
  kept.

## Causes

The run starts with none. For each candidate, measure on this snapshot how many
rows it claims and what stays unexplained (`analyze` after adding it), then the
analyst approves it. Causes are SQL over table `rows`: `base`, `k_<key>`,
`t_<extract column>`, `c_<Cube column>`, `t__dup`, `c__dup`. Two causes claiming
one row stop the report; never order them to make it pass.

## Reading the report

- **Trust verdict first.** Trusted only when every invariant holds, including
  "capture completeness" (which `run` records), and every hand check agrees. A
  disagreeing hand check outranks pending ones. Findings stay held until then.
- **Row buckets:** match, value differs, dashboard only, Cube only, outside
  scope, outside period; each split by cause or "unexplained". Outside scope
  (schools Cube does not show this identity) and outside period (days the run
  did not capture) take no cause.
- **Cells:** pass, coincidental match, row gap, formula gap. Filter ignored,
  mapping unproven, no Cube counterpart and no captured rows are the tool's
  limits, never Cube findings.
- **Formulas not tested:** mapped measures with no cut whose rows all match.
  Their formulas are unproven either way.
- Counts under 10 show as `<10`, so the report can go to `#data_team`.

## Hand checks

`<snapshot>/analysis/hand_checks.md` lists 10 to 15 checks: one per verdict and
bucket, plus random passes. Tableau side in the review copy (same frozen
extract), Cube side against the captured value, rows against PowerSchool or
Focus. Cube's side is the captured answer at its recorded refresh time, never
today's Cube. Mark each result exactly `agree` or `disagree` in
`hand_checks.yml` (new checks start `pending`), then `analyze`. Any other value
stops `analyze` with an error naming the check's id.

## Last year

Once per year, after its logic last changed:
`run <checks> --period 2025-07-01:2026-06-30`. Its snapshot is tagged with the
year and kept until July.

## Rules

- Snapshots hold student-level rows: they stay in `~/.cache/cube-validate/`.
  `hand_checks.md` names students; keep it local.
- The checks file is committed, so it never holds a person's name.
- Review copies go to TEMP-CB only. The tool deletes nothing on Tableau.
