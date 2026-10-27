---
name: cube-validation
description:
  "Use when asked to validate Cube, check whether Cube matches the dashboard,
  add a Cube measure from a dashboard, or when working in `src/cube/validation/`
  or `scripts/cube_validation/`."
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

1. Set `CUBE_REST_URL` in the environment: the Cube Cloud REST base ending
   `/cubejs-api/v1`. Never commit it.
2. In the test, load the package by absolute path as top-level `cube_validation`
   (`importlib.util.spec_from_file_location` with `submodule_search_locations`,
   register in `sys.modules` before `exec_module`), from the checkout or
   worktree under test, then call `cube_validation.cli.main([...])` and assert
   the return is 0.
3. Run `uv run pytest tests/test_zz_cube_validation.py -s --tb=short`, then
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
   `rows` grain and values. Use the exact keys in `config.py`.
4. `prove <file> --comparison <id>` exports the sheet from a `TEMP-CB` copy and
   writes `proof` when the probe reproduces every cell at `decimals`. A failed
   proof (cells mismatch) means the probe or the mapping is wrong: check the
   probe, then the dims, cuts, filters and `--value-column`; never loosen
   `decimals`. A "cannot export" or "7 days" refusal is not a failed proof:
   retry after the refresh. After a workbook edit, `prove <file> --check` lists
   stale proofs; re-prove those.
5. `check-api <file>` once per view, before the first `run`. A disagreement
   means Cube's API and its compiled SQL differ, so `run` results are not
   trustworthy until it is explained.
6. `run <file>` (add `--moment <ISO time>` for an older build). It prices
   queries first and stops over `--max-usd`.
7. Triage every open group into one of 4 calls, then record it (step 8):
   - `deliberate`: the difference is intended. Say what the Cube member counts
     in its `description:`; reasoning stays in the decision.
   - `fix_dashboard`: the workbook or its view is wrong. Task: the domain's
     Asana dashboard-fix task.
   - `fix_cube`: the Cube model is wrong. Task: the domain's GitHub Cube-fix
     issue.
   - `domain_owner`: the owner decides what is right. Task: the review issue
     from step 9. Anchor differences are judged here too.
8. Add a `decisions:` entry with `id` (unique), `comparison`, `group` (a mapping
   with `column` and `values`), `call`, `reason`, `task` (required for all but
   `deliberate`) and the `fingerprints` `{cube, dashboard}` that `run` printed
   for that comparison. A decision covers its group only while both fingerprints
   hold; do not copy fingerprints from another run.
9. `uv run python -m scripts.cube_validation review <files> --domain <domain>`
   prints the issue body. Show the draft to the analyst. Post it with
   `mcp__github__issue_write` only after approval, using the repo's issue
   template.

## Results

- "Matches a dashboard" and "anchored to a source" can be reported as validated;
  "consistent only" cannot.
- A cut nobody exported is evaluated by the proven probe and labeled as such.
- Sources read as they are now (Google Sheets externals) are named in the
  result; carry that caveat into the review issue.
