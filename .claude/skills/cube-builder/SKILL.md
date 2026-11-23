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
pieces in tiers, and builds them as pull requests, each checked against the
dashboard (a rebuild check, then `compare`) before it merges. One GitHub issue
per dashboard, titled "Build <dashboard> in Cube", is the hub: it holds the
inventory, the disagreements and the plan, and every builder PR refs it.

The commands live in `scripts/cube_validation/`. `members`, `rebuild-sheet` and
`compare` need credentials: run them through the `cube-validation` skill's
"Running a command" runner. `inventory-workbook` and `inventory` need none:
`uv run python -m scripts.cube_validation <command> ...` from the checkout that
holds the package. Keep the builder's working files in
`~/.cache/cube-validation/<slug>/`, never in git.

## Rules

- Claude posts and edits only what the analyst approved: the build issue, Asana
  edits, pull requests.
- Asana mirrors the approved build plan: the dashboard task holds the plan's PR
  tasks, its `Already in Cube` task, deferred rows and Validate task (_Plan_
  step 3). Show each change in the build issue first; make it after the analyst
  approves.
- GitHub text carries field and member names and counts, never a student's or
  staff member's name, number or row; counts under 10 read `<10`.
- A new student-level column (a tier, a bucket, a flag) is PII: tag it
  `config.meta.contains_pii: true` in its dbt YAML
  (`.claude/rules/ferpa-pii.md`).
- Tableau calls share one token with other sessions: make one Tableau call at a
  time, never in parallel.

## Inventory

1. Read the dashboard's domain skill when one exists (DDI Suite: `ddi-stack`,
   which covers buckets and DDI tiers).
2. `members` writes `~/.cache/cube-validation/members.json`: each member's name,
   view, description, compiled SQL and fact.
3. Download the workbook's XML through the runner, with the `download_twb`
   snippet from the `cube-validation` runbook step 2 in place of its `cli.main`
   call, and write it to `~/.cache/cube-validation/<slug>/<slug>.twb`. It
   downloads without the extract, so no student data lands on disk.
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
   the rows tagged `measure` or `dimension` under its PR tasks and its
   `Already in Cube` task, the deferred rows directly under it, and its retired
   notes; for a dashboard not laid out yet (_Plan_ step 3), its blocked-by
   builds and their open field subtasks. Rows an earlier-due dashboard's PR
   ships sit under that dashboard: find them with `search_tasks` on this
   dashboard's gid, which their `Used by:` line names. Write `asana.json` as
   `[{"field": ..., "status": ...}]` with status `open` or `deferred`; leave
   retired items out.
7. Find the catalog file holding the dashboard's section:
   `rg -l '<slug>' docs/superpowers/plans -g '2026-10-02-cube-gap-catalog-*.md'`
   (the glob skips the index file, which names every slug) (DDI Suite:
   `2026-10-02-cube-gap-catalog-assessments.md`, slug `ddi_suite`).
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
   | 1    | Nothing new: a comparison and its rebuild check         |
   | 2    | New Cube members over columns a mart already has        |
   | 3    | New columns on an existing fact or dimension, then 2    |
   | 4    | A new cube over an existing mart                        |
   | 5    | A new fact table: a new dbt mart, then everything above |

   Before placing a field in tier 2, confirm a mart has its column:
   `rg -n '<column>' src/dbt/kipptaf/models/marts`, plus words from its meaning,
   since a mart may have renamed it. A catalog `mart-ready` is not proof. A
   column found only in an `rpt_` or `int_extracts__` model is tier 3 or deeper:
   its logic moves into the domain `int_` both read (A12), and it goes on the
   fact or dimension whose grain it varies at (`dbt-marts.md` _Grain_). Moving a
   default or a mapping changes counts, so the domain owner confirms it. A dbt
   PR adds the column, a Cube PR adds the dimension, and a comparison slices an
   existing measure by it.

   The catalog's `mart-missing` `nj_student_tier`, for one, is in the marts as
   `ela_bucket` and `math_bucket` on `dim_student_enrollment_status`.

2. Search open issues for "Build <dashboard> in Cube"; reuse one that exists.
   Otherwise draft it: the `inventory` table, each disagreement with the
   analyst's decision, each duplicate verdict, the plan by tier, and the Asana
   changes _Plan_ step 3 will make. Show the draft; post only after approval.
3. Lay the approved plan out under the dashboard's Asana task (design:
   `docs/superpowers/specs/2026-11-23-asana-dashboard-build-plans-design.md`):
   - A build belongs to the earliest-due dashboard that needs it; on a tie, the
     dashboard whose build issue opened first. A build an earlier dashboard owns
     is not planned again.
   - Each PR is a subtask `PR (<dbt|Cube>): <what it builds> · <table>` with an
     owner. Only the dashboard task carries a due date. The tables after the `·`
     (comma-separated) are the table tasks its rows came from; the sync reads
     the type and `scripts/asana_migrate.py` matches on the tables. A dbt PR
     blocks the Cube PR that reads its columns. An open decision goes in the
     notes of the PR task it blocks, or on the hub issue; never its own task.
   - A `Validate <dashboard> in Cube` task blocked by every PR task, never by
     rows (Asana caps a task at 30 dependencies plus dependents).
   - Move the hub issue's synced `#NNNN |` task under the dashboard.
   - Move each row to the PR that ships its Cube member (the Cube PR when a dbt
     PR comes first). A deferred row moves directly under the dashboard; a row
     already live in Cube moves under the dashboard's `Already in Cube` task.
     Keep its `measure` or `dimension` tag, its `Use:` and `Used by:` lines and
     its member names. Remove its links to the table's `mart:`, `cube:` and
     `view:` stages. A stage with work left becomes a PR task; a table task is
     deleted when it has no open rows and no open stages.
   - Ask the analyst to run
     `uv run --with requests python scripts/asana_sync.py --only <dashboard gid>`
     in their terminal (it needs their own `ASANA_PAT`), and fix every row in
     its "Rows with no kind tag" list.

## Build

Build shallowest tier first, one PR type at a time. Each PR takes the root
CLAUDE.md no-issue branch form
(`git worktree add -b <branch> <path> origin/main`) and carries
`Refs #<build issue>`: a branch linked with `gh issue develop` closes the build
issue when its PR merges.

Comparisons, explanations and decisions go in the validation file
`src/cube/validation/<view>.yml` on the dashboard's own validation branch, never
in a builder PR. Base that branch on the branch that carries the validator:
`origin/main` once the validator has merged, else the validator's branch. The
runner's `PKG` is the `scripts/cube_validation` of that branch's checkout.

| PR type | What it changes                           | Reviewer           |
| ------- | ----------------------------------------- | ------------------ |
| YAML    | New measures over members already present | simple review      |
| Cube    | New dimensions, joins, a new cube         | analytics engineer |
| dbt     | New columns or a new mart                 | data engineer      |

**A dbt PR merges before the Cube PR that reads its column.**

Start each builder session for a dashboard with the sweep: find open PRs that
ref its build issue, and promote (step 9) any whose synced `#NNNN |` Asana task
is not under the dashboard yet. That covers PRs opened outside the builder.

1. dbt PR: invoke `dbt-local-dev`, then
   `uv run dbt build --select <model>+ --project-dir src/dbt/kipptaf --target dev`
   builds the column into `zz_<user>_kipptaf_marts`.
2. Start a local Cube over the PR's model, per _Testing a model variant locally_
   in the `cube-ops` skill: the copy comes from the PR's worktree, and the
   server runs from the main checkout's `src/cube`. `cube-ops` covers starting
   it in the background. Use a Cube Cloud Dev Mode deployment only when the
   analyst asks for it.
   - Start the server with a throwaway `CUBEJS_API_SECRET=<local value>`.
   - In the runner, `monkeypatch.setenv` `CUBE_API_SECRET` to that same value
     and `CUBE_REST_URL` to `http://localhost:4000/cubejs-api/v1`.
3. While the column exists only in the dev build, redirect the copy's
   `sql_table` to `zz_<user>_kipptaf_marts` (never the working tree) and pass
   `--fact-dataset zz_<user>_kipptaf_marts` to `rebuild-sheet`, `compare`,
   `sort` and `explain`: each reads that build's run, kept apart from
   production's.
4. Before relying on the local Cube, copy
   `~/.cache/cube-validation/members.json` aside, then run `members` against it:
   the new members must be listed before any query bills. For a new measure, a
   `same SQL: <new>, <other>` line means it is `<other>` under another name:
   confirm in `members.json`, drop the new one and reuse `<other>`. Keep the
   local `members.json` through step 6, since `read-sheet` reads it; then
   restore the copy, or rerun `members` against Cube Cloud, before any later
   `inventory`.
5. On the validation branch, add the comparison that checks the piece by the
   `cube-validation` runbook steps 2 and 3. A new dimension is checked by
   slicing an existing measure by it (the new dimension mapped under `dims`).
   Give the comparison a `rows:` block whose grain leaves out the new dimension:
   otherwise a differing cell can never be covered and stays open. Slicing an
   existing measure brings back that measure's known causes; read them in the
   view's validation file before calling a difference a bug in the new piece.
6. Run the `cube-validation` runbook steps 4 and 5: `read-sheet`,
   `rebuild-sheet`, then `compare --comparison <id>`.
7. The PR description says what was checked, the moment, the branch, and the
   `Cube:` and `Fact:` lines `compare` printed.
8. After a dbt PR merges and its production build lands, run
   `compare --comparison <id>` for the Cube PR without `--fact-dataset` and
   update its description.
9. Promote the PR's Asana task once the PR is open. The Zapier sync creates a
   top-level `#NNNN | <title>` task in TEAMster about a minute after the PR
   opens; wait for it. Move it under the dashboard, give it the planned PR
   task's due date and owner, move the planned task's rows and every blocked-by
   link that pointed at it, then close the planned task with a comment linking
   the synced one. Zapier completes the synced task at merge, and a task moved
   by hand keeps its parent through later syncs.

## Finish

1. When every tier has merged, open "Validate <dashboard> in Cube" and run the
   whole dashboard through the `cube-validation` runbook, `sort` included; the
   owner answers with the `cube-validation-answers` skill.
2. With the analyst's approval, record the validation result on the dashboard's
   task in the Asana project "Data Marts + Semantic Layer".
3. When a dashboard's due date moves, re-check who owns its builds (_Plan_ step
   3): a build's PR task moves to the dashboard that is now earliest.
