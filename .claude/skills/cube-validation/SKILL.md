---
name: cube-validation
description:
  "Use when asked to validate Cube, check whether Cube matches the dashboard, or
  when working in `src/cube/validation/` or `scripts/cube_validation/`."
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
- Tableau writes go only to the `TEMP-CB` project.
- Source anchors are entered by hand under `anchors:` with `measure`, `value`,
  `source`, `as_of`, `date_range` and `filters`. Judge each difference in
  triage; there is no threshold, and an exact match is not expected.
- A measure whose strongest check is "consistent only" is never reported as
  validated.

## Running a command

Tableau and `CUBE_API_SECRET` come only from the pytest secrets fixture, and
only the MAIN checkout's devcontainer template holds the Cube secret. So
`discover`, `prove`, `check-api` and `run` go through a throwaway
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

`review` needs no credentials: run it from any checkout with
`uv run python -m scripts.cube_validation review ...`. Exit 0 is done, 1 is a
refusal (stderr says why), 2 is a usage error. A refusal is an answer: fix its
cause, do not retry around it.

## Runbook

1. List the measures. Ask the analyst which measures and which view; a file
   needs `time_dimension` whenever it has `rows` or anchors.
2. `discover <file> --measure <name>` ranks workbook fields. Show the analyst
   the candidates. A name-alike field can mean something else, so no comparison
   is written until the analyst confirms it.
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
     `gt`, `gte`, `lt` and `lte` (exactly 1 number), or `set` (not null).
   - `definitions: {dashboard: ..., cube: ...}`: what each side counts, in a
     sentence or a code list. The review issue shows both for a comparison with
     a domain-owner question. It goes to GitHub: never name a person.

   Comparisons that repeat a block (one sheet, several fields) take it from a
   YAML anchor under a top-level `shared:` key: `<<: *roster`, then the keys
   that differ. Identities take numbers as well as measures
   (`right: 1 - pct_ontime`).

4. `prove <file> --comparison <id>` exports the sheet from a `TEMP-CB` copy and
   writes `proof` when the probe reproduces every cell at `decimals`. Repeat
   `--comparison` to prove several at once: comparisons on one sheet share one
   export, and one refusal does not stop the rest. A failed proof (cells
   mismatch) means the probe or the mapping is wrong: check the probe, then the
   dims, cuts, filters, `sheet_field` and `split_rows`; never loosen `decimals`.
   It prints a count per reason and 5 samples; the full list is in the local
   cache. A "cannot export" or "7 days" refusal is not a failed proof: retry
   after the refresh. The proof records the cuts its export covered, and the
   sheet's cuts and filters with no Cube member (by caption; filter values are
   never read).
5. `check-api <file>` once per view, before the first `run`. A disagreement
   means Cube's API and its compiled SQL differ, so `run` results are not
   trustworthy until it is explained.
6. `prove <file> --check` before every `run`. `run` never reads the workbook, so
   only this catches a dashboard owner's edit; re-prove each proof it lists.
   `run` warns when a proof is more than 7 days old.
7. `run <file>` (add `--moment <ISO time>` for a build within the last 7 days).
   It prices queries first and stops over `--max-usd`. A proof with no recorded
   cuts is listed under "Cuts to prove in the browser" for a re-prove.
8. Triage every open group, and every missing cut and filter, into one of 4
   calls, then record it (step 9). A missing cut or filter is a sheet field Cube
   has no member for: Cube cannot make that cut, so the owner decides whether
   the measure needs it. Map a field Cube does have under `filters:` instead of
   recording a decision.
   - `deliberate`: the difference is intended. Say what the Cube member counts
     in its `description:`; reasoning stays in the decision.
   - `fix_dashboard`: the workbook or its view is wrong. Task: the domain's
     Asana dashboard-fix task.
   - `fix_cube`: the Cube model is wrong. Task: the domain's GitHub Cube-fix
     issue.
   - `domain_owner`: the owner decides what is right. Task: the review issue
     from step 10. Anchor differences are judged here too.
9. Add a `decisions:` entry with `id` (unique), `comparison`, `group`, `call`,
   `reason`, `task` (required for all but `deliberate`) and the `fingerprints`
   `{cube, dashboard}` that `run` printed for that comparison. `reason` goes to
   GitHub in the review issue: never name a student or staff member in it.
   `task` is an `https://` link or `#<issue>`; the loader refuses other text.
   `group` is a mapping: `column` is the Cube member name the triage line shows
   (such as `regions_region_name`), and `values` are compared as text: quote
   values exactly as the triage line shows them. YAML rewrites an unquoted
   `9.50`, `010` or `no`, so the loader refuses one. A decision covers its group
   only while both fingerprints hold; do not copy fingerprints from another run.
   A missing cut or filter takes `missing_cut: <caption>` or
   `missing_filter: <caption>` in place of `group`, with no `comparison` and no
   `fingerprints`: it covers the field across the view.
10. `uv run python -m scripts.cube_validation review <files> --domain <domain>`
    prints the issue body. Show the draft to the analyst. Post it with
    `mcp__github__issue_write` only after approval, using the repo's issue
    template.

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
