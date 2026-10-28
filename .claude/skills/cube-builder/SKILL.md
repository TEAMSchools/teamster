---
name: cube-builder
description:
  'Use when asked to build a dashboard in Cube, add a dashboard field, measure
  or dimension to Cube, or find what Cube lacks for a dashboard: "build
  <dashboard> in Cube", "add <field> to Cube", "what''s missing from Cube for
  <dashboard>", or a gap catalog row marked `mart-ready`, `mart-missing` or
  `workbook-only`.'
---

# cube-builder

The builder inventories what a dashboard needs from Cube, plans the missing
pieces in tiers, and builds them as pull requests, each proven against the
dashboard before it merges. One GitHub issue per dashboard, titled "Build
<dashboard> in Cube", is the hub: it holds the inventory, the disagreements and
the plan, and every builder PR refs it.

The commands live in `scripts/cube_validation/`. `members`, `prove`, `check-api`
and `run` need credentials: run them through the `cube-validation` skill's
"Running a command" runner. `inventory-workbook` and `inventory` need none:
`uv run python -m scripts.cube_validation <command> ...` from the checkout that
holds the package. Keep the builder's working files in
`~/.cache/cube-validation/<slug>/`, never in git.

## Rules

- Claude posts and edits only what the analyst approved: the build issue, Asana
  edits, pull requests.
- Asana changes only for a miss: a measure no field subtask names, or a
  dependency the blocked-by list lacks. Show each in the build issue first; make
  it after the analyst approves.
- GitHub text carries field and member names and counts, never a student's or
  staff member's name, number or row; counts under 10 read `<10`.
- A new student-level column (a tier, a bucket, a flag) is PII: tag it
  `config.meta.contains_pii: true` in its dbt YAML
  (`.claude/rules/ferpa-pii.md`).
- `count_students` means the enrollment headcount and nothing else. A measure
  that counts any other set of students is named for that set
  (`count_students_with_attendance`).
- A `.twbx` holds extracts with student data. Keep only its `.twb` XML and
  delete the `.twbx` in the same step.
- Tableau calls share one token with other sessions: make one Tableau call at a
  time, never in parallel.

## Inventory

1. Read the dashboard's domain skill when one exists (DDI Suite: `ddi-stack`,
   which covers buckets and DDI tiers).
2. `members` writes `~/.cache/cube-validation/members.json`: each member's name,
   view, description, compiled SQL and fact.
3. Download the workbook with the Tableau MCP's `download-workbook`, then
   `unzip -p <file>.twbx '*.twb' > ~/.cache/cube-validation/<slug>/<slug>.twb`
   and delete the `.twbx`.
4. `inventory-workbook <twb> > ~/.cache/cube-validation/<slug>/review.json`
   lists every field: caption, role (`measure`, `cut`, `filter`, `parameter`),
   formula with code groups expanded, sheets, and `presentation`.
5. Dispatch one fresh reviewer subagent with the `.twb`, `review.json` and
   `members.json` paths only: never the gap catalog, the Asana task, or your own
   guesses, so it is not anchored on them. It reports fields the JSON misses or
   gives the wrong role, and sorts each field into one group:
   - in Cube under another name: reuse it;
   - a plain `rpt` column Cube lacks;
   - a workbook calculation with business logic;
   - presentation only (a parameter, a URL, a permission field): ignored.

   Add the fields it found to `review.json` with the same keys, and show the
   analyst where it and the command disagree.

6. Read the dashboard's task in the Asana project "Data Marts + Semantic Layer":
   its blocked-by builds, their open field subtasks, and its deferred and
   retired notes. Write `asana.json` as `[{"field": ..., "status": ...}]` with
   status `open` or `deferred`; leave retired items out.
7. Find the catalog file holding the dashboard's section:
   `rg -l '<slug>' docs/superpowers/plans/2026-10-02-cube-gap-catalog*.md` (DDI
   Suite: `2026-10-02-cube-gap-catalog-assessments.md`, slug `ddi_suite`).
8. `inventory <catalog file> <slug> --review review.json --asana asana.json`
   prints a markdown table (field, kind, member, sources, disagreement), then
   JSON. The member column is today's Cube; a catalog status is only where the
   catalog stood. The analyst decides every row with a disagreement.

## No duplicates

Run these before the plan calls anything missing.

1. An empty member cell is not yet "missing". `/meta` shows views only, so a
   member on a cube no view exposes never reaches `members.json`. Search
   `src/cube/model/**/*.yml` for the field's name, its column and words from its
   meaning: `rg -n -i '<term>' src/cube/model`.
2. A same-named member on another cube or view is a candidate, not a match. Show
   the analyst what it counts (the key it counts, its table's grain, its
   filters) beside what the dashboard counts, and propose one verdict:
   - same population, already in the dashboard's view: reuse it, build nothing;
   - same population, on a cube the view does not include: add that cube to the
     view (tier 2), never a copy of the measure;
   - different population: a new measure, named for the students it counts,
     whose description says how it differs from the others.

   The analyst confirms each verdict before the plan is written.

Dimensions take both steps. A new measure also gets the same-SQL check in
_Build_ step 4.

## Plan

1. Put each missing piece in the shallowest tier that builds it. Deferred Asana
   items are listed, not planned.

   | Tier | What it needs                                           |
   | ---- | ------------------------------------------------------- |
   | 1    | Nothing new: a comparison and a proof                   |
   | 2    | New Cube members over columns a mart already has        |
   | 3    | New columns on an existing fact or dimension, then 2    |
   | 4    | A new cube over an existing mart                        |
   | 5    | A new fact table: a new dbt mart, then everything above |

   A column the catalog marks `mart-missing`, such as `nj_student_tier`, is tier
   3: a dbt PR adds the column, a Cube PR adds the dimension, and a comparison
   slices an existing measure by it.

2. Search open issues for "Build <dashboard> in Cube"; reuse one that exists.
   Otherwise draft it: the `inventory` table, each disagreement with the
   analyst's decision, each duplicate verdict, the plan by tier, and the Asana
   misses to fix. Show the draft; post only after approval.
3. Make the approved Asana edits.

## Build

Build shallowest tier first, one PR type at a time. Each PR follows the root
CLAUDE.md branch flow, is based on `origin/main`, and carries
`Refs #<build issue>`.

Comparisons, proofs and decisions go in `src/cube/validation/<view>.yml` on a
separate validation branch, stacked on
`cristinabaldor/feat/claude-cube-validation-and-build-skill` until #6160 merges,
never in a builder PR. The runner's `PKG` is always the validator worktree's
`scripts/cube_validation`.

| PR type         | What it changes                           | Reviewer           |
| --------------- | ----------------------------------------- | ------------------ |
| 1: YAML only    | New measures over members already present | simple review      |
| 2: Cube changes | New dimensions, joins, a new cube         | analytics engineer |
| 3: Fact changes | New columns or a new mart in dbt          | data engineer      |

**A type 3 PR merges before the type 2 PR that reads its column.**

1. Type 3: invoke `dbt-local-dev`, then `uv run dbt build --select <model>+`
   builds the column into `zz_<user>_kipptaf_marts`.
2. Start a local Cube over the PR's model, per the `CUBEJS_SCHEMA_PATH` copy in
   `.claude/rules/cube-authoring.md`: the copy comes from the PR's worktree, and
   the server runs from the main checkout's `src/cube`, since a worktree has no
   dotenv file. `cube-ops` covers starting it in the background. Use a Cube
   Cloud Dev Mode deployment only when the analyst asks for it.
   - Start the server with a throwaway `CUBEJS_API_SECRET=<local value>`.
   - In the runner, `monkeypatch.setenv` `CUBE_API_SECRET` to that same value
     and `CUBE_REST_URL` to `http://localhost:4000/cubejs-api/v1`.
   - Smoke-test one `check-api` before relying on the server.
3. While the column exists only in the dev build, redirect the copy's
   `sql_table` to `zz_<user>_kipptaf_marts` (never the working tree) and pass
   `--fact-dataset zz_<user>_kipptaf_marts` to `check-api`, `prove` and `run`.
4. After writing a new measure, copy `members.json` aside, then run `members`
   against the local Cube. A `same SQL: <new>, <other>` line means the new
   measure is `<other>` under another name: confirm in `members.json`, drop the
   new one and reuse `<other>`. Restore the copy, or rerun `members` against
   Cube Cloud, before any later `inventory`.
5. On the validation branch, add the comparison that proves the piece by the
   `cube-validation` runbook steps 2 and 3. A new dimension is proven by slicing
   an existing measure by it (the new dimension mapped under `dims`).
6. Run the `cube-validation` runbook steps 4 to 7: `prove`, `check-api`,
   `prove --check`, `run`.
7. The PR description says what was proven, the moment, the branch, and the
   `Cube:` and `Fact:` lines `run` printed.
8. After a type 3 PR merges and its production build lands, rerun `run` for the
   type 2 PR without `--fact-dataset` and update its description.

## Finish

1. When every tier has merged, open "Validate <dashboard> in Cube" and run the
   whole dashboard through the `cube-validation` runbook, triage included; the
   owner answers with the `cube-validation-answers` skill.
2. With the analyst's approval, move the dashboard's Asana stage subtasks from
   "Built in Cube" toward "Matches within tolerance", as far as the validation
   result supports.
