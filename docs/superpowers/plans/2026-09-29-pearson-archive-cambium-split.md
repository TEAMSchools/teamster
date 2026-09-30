# Pearson Archive and Cambium Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze Pearson New Jersey state scores in the district projects, move
the Cambium mapping into the `cambium` package, and serve both through a new
kipptaf `int_assessments__state_nj_scores` under neutral column names.

**Architecture:** Two PRs. PR 1 adds `int_cambium__all_assessments` to the
`cambium` package and disables the district Pearson score models, leaving their
tables frozen in place. PR 2 adds `int_assessments__state_nj_scores` in kipptaf
over the frozen district Pearson tables and the district Cambium tables, then
repoints the 10 readers of `int_pearson__all_assessments` and disables it.

**Tech Stack:** dbt (BigQuery), `dbt_utils.union_relations`, Dagster dbt assets,
BigQuery MCP (`execute_sql_readonly`) for verification.

**Spec:**
`docs/superpowers/specs/2026-09-29-pearson-archive-cambium-split-design.md` (the
column map, the reader table and the verification list live there; this plan
does not repeat them).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-split-pearson-cambium`
  (PR 1). PR 2 gets its own worktree, created in Task 4. Every call uses
  `git -C <worktree>` and absolute paths; dbt runs as
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/<project>`.
- Run `uv run dbt deps --project-dir <worktree>/src/dbt/<project>` once per
  project before its first dbt command, in its own Bash call.
- Column names follow the spec's map exactly. 25 renames; every other column
  keeps its current name.
- Retire by disable, never delete. Disabling a model does not disable its tests:
  disable each test by its generated name too.
- SQL follows `.claude/rules/dbt-sql.md`: enumerated positional `union all`, no
  `select *` in union branches, no `qualify`, no `group by all`, no `order by`.
- Every verification query reports counts only. No row values from student-level
  columns go into commits, PR bodies or comments.
- `--target staging` builds and `dbt clone --target staging` are shared writes:
  hand them to the user or get their consent in the turn before, one command per
  Bash call.
- New and modified models carry a description on the model and every column. PII
  tags use column-level `config.meta.contains_pii: true`, tiers 1-3 of
  `.claude/rules/ferpa-pii.md` (names, ids, scores, demographics).
- Before each push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Review Focus

1. Paterson has no `stg_cambium__njgpa` or `stg_cambium__eoc`: the package model
   must compile and build there with only `stg_cambium__njsla`. Task 1 builds it
   in Paterson.
2. AY2025 NJGPA exists in both vendors: the second grain test must run on the
   union in `int_assessments__state_nj_scores`, not per vendor. Task 4 runs it.
3. `_dbt_source_relation` on Cambium rows must keep today's values, or the
   `%cambium%`-scoped tests and `_dbt_source_project` break silently. The
   package model produces it with `dbt_utils.union_relations` (including the
   NJGPA branch), and Task 1's `EXCEPT DISTINCT` covers it.
4. The prelim gates must keep turning off for Cambium years: Task 5 compares
   both gated models row for row against prod.
5. Dagster: kipptaf's `kipp*_pearson.int_pearson__all_assessments` sources point
   at district asset keys that stop existing after PR 1. The kipptaf code
   location must still load. Task 3 checks the PR 1 branch deployment, and Task
   8 checks PR 2's.

---

### Task 1: `int_cambium__all_assessments` in the `cambium` package

**Files:**

- Create: `src/dbt/cambium/models/intermediate/int_cambium__all_assessments.sql`
- Create:
  `src/dbt/cambium/models/intermediate/properties/int_cambium__all_assessments.yml`
- Modify: `src/dbt/cambium/dbt_project.yml` (`vars:`)
- Modify: `src/dbt/kipppaterson/dbt_project.yml` (`vars:`)
- Source to port:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
  CTEs `cambium_njsla` through `cambium` (lines 72-491)

**Interfaces:**

- Produces: relation `<district>_cambium.int_cambium__all_assessments` in
  Newark, Camden and Paterson, one row per `student_test_uuid`. Its columns are
  the Cambium branch of today's model under the spec's new names, plus
  `_dbt_source_relation`. It has no `_dbt_source_project` and no crosswalk
  (kipptaf adds both in Task 4).
- Produces: package var `cambium_state_assessment_relations`, which defaults to
  `[stg_cambium__njsla, stg_cambium__eoc, stg_cambium__njgpa]`. Paterson
  overrides it to `[stg_cambium__njsla]`.

- [ ] **Step 1: Write the comparison query (the failing test)**

  Save it to the session scratchpad as `cambium_compare.sql`. It runs one
  district at a time:
  - Left side: the dev relation
    `zz_<github_user>_<district>_cambium.int_cambium__all_assessments`,
    left-joined to
    `kipptaf_google_sheets.stg_google_sheets__pearson__student_crosswalk` on
    `student_test_uuid`, with `coalesce(x.student_number, student_number)` and
    `cast(state_student_id as string)`.
  - Right side: prod `kipptaf_pearson.int_pearson__all_assessments`, filtered to
    `_dbt_source_relation like '%<district>_cambium%'`, with every column except
    `_dbt_source_project` selected under its new name.
  - Output: `count(*)` of each `EXCEPT DISTINCT` direction, plus the row count
    by `_dbt_source_relation` on each side.

- [ ] **Step 2: Run it and confirm it fails**

  Run it through `execute_sql_readonly`. Expected:
  `Not found: Table ...int_cambium__all_assessments`.

- [ ] **Step 3: Write the model**

  - Port the 6 CTEs unchanged in logic, renaming output columns per the spec's
    map.
  - Build `relations` from the var the way
    `src/dbt/pearson/models/intermediate/int_pearson__all_assessments.sql` does
    (a `ref()` inside the loop, so only the listed relations enter the graph).
  - The NJSLA/EOC union takes the listed relations other than
    `stg_cambium__njgpa`.
  - Wrap the NJGPA branch, and its arm of the `cambium_aligned` `union all`, in
    `{% if "stg_cambium__njgpa" in var("cambium_state_assessment_relations") %}`.
  - Read NJGPA through
    `dbt_utils.union_relations(relations=[ref("stg_cambium__njgpa")])`, so it
    carries `_dbt_source_relation` like the other branch.
  - Keep the existing `test_status = 'completed'` filter and the existing casts.

- [ ] **Step 4: Write the properties YAML**

  - Description adapted from the Cambium half of today's
    `int_pearson__all_assessments.yml`, including the `test_status` rationale.
  - Model-level `unique_combination_of_columns(student_test_uuid)`.
  - Move today's Cambium-scoped tests with it. `test_grade` gets `not_null` with
    `where: raw_subject not in ('Algebra I', 'Algebra II', 'Geometry')`, plus
    `accepted_values [3, 4, 5, 6, 7, 8, 9, 11]`. `assessment_version` and
    `assessment_type` each get `not_null` and `accepted_values` limited to
    Cambium's values.
  - A description and a PII tag on every column.

- [ ] **Step 5: Add the vars**

  - `src/dbt/cambium/dbt_project.yml`: add `cambium_state_assessment_relations`
    with the 3-model default, and a comment that mirrors the `pearson` one.
  - `src/dbt/kipppaterson/dbt_project.yml`: override it with
    `[stg_cambium__njsla]`, next to `pearson_state_assessment_relations`.

- [ ] **Step 6: Build in all 3 districts**

  For each of `kippnewark`, `kippcamden` and `kipppaterson`, run in its own Bash
  call:
  `uv run dbt build --select int_cambium__all_assessments --defer --favor-state --state <worktree>/src/dbt/<district>/target/prod --project-dir <worktree>/src/dbt/<district> 2>&1 | tail -n 30`.
  Invoke the `dbt-local-dev` skill first for the `--state` path. Expected: model
  and tests PASS in all 3. Paterson compiles with no NJGPA branch.

- [ ] **Step 7: Run the comparison and confirm it passes**

  Run Step 1's query for each district. Expected: 0 rows in both directions. The
  counts by source table sum to 11893 `stg_cambium__njsla`, 813
  `stg_cambium__njgpa` and 504 `stg_cambium__eoc` across the 3 districts.

- [ ] **Step 8: Commit**

  `git -C <worktree> add` the 4 files by name, then commit
  `feat(dbt): add int_cambium__all_assessments to the cambium package`.

### Task 2: Freeze Pearson scores in the district projects

**Files:**

- Modify: `src/dbt/kippnewark/dbt_project.yml` (`models: pearson:`,
  `data_tests:`)
- Modify: `src/dbt/kippcamden/dbt_project.yml` (`models: pearson:`,
  `data_tests:`)
- Modify: `src/dbt/kipppaterson/dbt_project.yml` (`models: pearson:`,
  `data_tests:`)
- Modify:
  `src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla.yml`,
  `int_pearson__njsla_science.yml`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces: `<district>_pearson.int_pearson__all_assessments` tables left frozen
  in all 3 districts. Task 4 reads them.

To disable, per district:

| District | Models                                                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Newark   | `int_pearson__all_assessments`, `stg_pearson__njgpa`, `stg_pearson__njsla`, `stg_pearson__njsla_science`, `stg_pearson__parcc`         |
| Camden   | same as Newark                                                                                                                         |
| Paterson | `int_pearson__all_assessments`, `stg_pearson__njsla`, `stg_pearson__njsla_science`, `int_pearson__njsla`, `int_pearson__njsla_science` |

Leave `stg_pearson__student_list_report`, `int_pearson__student_list_report` and
`stg_pearson__student_test_update` enabled.

- [ ] **Step 1: Capture the baseline node list**

  In each district, on `origin/main` (the main checkout is fine), run
  `uv run dbt ls --resource-type model test --output name` after a
  `dbt parse --no-partial-parse`. Save the output to the scratchpad as
  `nodes-<district>-main.txt`.

- [ ] **Step 2: Disable the models**

  Add `+enabled: false` for each model in the table, under the existing
  `models: pearson: staging:` and `pearson: intermediate:` blocks. For
  Paterson's own `int_pearson__njsla*`, set `config: enabled: false` in their
  properties YAML.

- [ ] **Step 3: Disable their tests**

  List the tests attached to each disabled model with
  `uv run dbt ls --resource-type test --select <model> --output name`, run on
  main. Add `+enabled: false` for each test name under `data_tests:`, following
  the existing Paterson `cambium: staging: properties:` block, with the same
  explanatory comment.

- [ ] **Step 4: Verify the diff of enabled nodes**

  Re-run Step 1 on the branch with `--no-partial-parse` and `diff` it against
  the baseline. Expected: only the table's models and their tests disappear;
  `int_pearson__student_list_report` is still listed.

- [ ] **Step 5: Commit**

  Commit `refactor(dbt): freeze Pearson state score models in the districts`.

### Task 3: Open PR 1 and hand off the between-PR steps

**Files:** none beyond Tasks 1-2.

- [ ] **Step 1:** Run trunk check on every changed file (see Global
      Constraints), push, and open the PR with
      `.github/pull_request_template.md`. Put `Refs #5591` in the body and the
      Task 1 and Task 2 verification counts in the "For Claude" fold. Watch CI,
      and process the `claude-review` findings per `pr-ci-review`.
- [ ] **Step 2:** Confirm the branch deployment's `dagster-cloud-deploy` check
      loads every code location. That covers Review Focus 5 for the district
      side.
- [ ] **Step 3: After merge**, confirm with
      `mcp__dagster__get_asset_materializations` that
      `<district>/cambium/int_cambium__all_assessments` has materialized in all
      3 districts. If it hasn't within a day, report that to the user rather
      than launching runs.
- [ ] **Step 4:** Hand the user the 3 staging clone commands from the spec (one
      per district), and wait for them to confirm they ran.

### Task 4: `int_assessments__state_nj_scores` in kipptaf

**Files:**

- Worktree: after PR 1 merges, create it with
  `gh issue develop 5591 --name cbini/refactor/claude-state-nj-scores`, then
  `git worktree add /workspaces/teamster/.claude/worktrees/cbini/refactor/claude-state-nj-scores cbini/refactor/claude-state-nj-scores`.
  Copy the spec and plan in, since they live on PR 1's branch; if PR 1 already
  merged them into `main`, they arrive with it.
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_nj_scores.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__state_nj_scores.yml`
- Modify: `src/dbt/kipptaf/models/cambium/sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kipppaterson.yml`

**Interfaces:**

- Consumes: Task 1's `int_cambium__all_assessments` and Task 2's frozen district
  `int_pearson__all_assessments` tables.
- Produces: `kipptaf_assessments.int_assessments__state_nj_scores`, a table. Its
  columns are today's 56 under their new names, in today's order. Every task
  after this one reads it.

- [ ] **Step 1: Write the comparison query (the failing test)**

  Save it to the scratchpad as `nj_compare.sql`:
  - Dev `int_assessments__state_nj_scores`, `EXCEPT DISTINCT` against prod
    `kipptaf_pearson.int_pearson__all_assessments` with old names aliased to
    new.
  - The same in the reverse direction.
  - Row counts split by vendor (`_dbt_source_relation like '%cambium%'`).

  Run it. Expected: `Not found`.

- [ ] **Step 2: Add the source entries**

  Add an `int_cambium__all_assessments` table to each
  `models/cambium/sources-kipp*.yml`, with a `meta.dagster` `group: cambium` and
  `asset_key: [<district>, cambium, int_cambium__all_assessments]`, matching the
  siblings.

- [ ] **Step 3: Write the model**

  - `pearson` CTE: move today's `pearson` CTE unchanged, including
    `source_column_name="_dbt_source_relation_2"` and the explicit `include`
    list.
  - `pearson_renamed` CTE: select every column, renaming per the spec's map.
  - `cambium` CTE: `dbt_utils.union_relations` over the 3
    `source("kipp*_cambium", "int_cambium__all_assessments")`, also with
    `source_column_name="_dbt_source_relation_2"` and an explicit `include`
    list.
  - `unioned` CTE: positional `union all` of the two, with enumerated columns in
    the same order.
  - Outer select: today's outer select (cast `state_student_id` to string,
    coalesce `student_number` from the crosswalk on `student_test_uuid`,
    `extract_source_project("u")`), written with enumerated columns rather than
    `* replace`.

- [ ] **Step 4: Write the properties YAML**

  - `config: materialized: table`.
  - Both grain tests from today's YAML, renamed: `(student_test_uuid)`, and
    `(student_number, academic_year, aligned_test_code, administration_round)`
    with `where: student_number is not null` and `severity: error`.
  - Move today's `assessment_version` and `assessment_type` tests with all
    values.
  - Descriptions ported and renamed, and PII tags per Global Constraints.

- [ ] **Step 5: Build and run the comparison**

  `uv run dbt build --select int_assessments__state_nj_scores --defer --favor-state --state <kipptaf prod state> --project-dir <worktree>/src/dbt/kipptaf 2>&1 | tail -n 30`.
  Expected: PASS, both grain tests included.

  Then run `nj_compare.sql`. Expected: 0 rows in both directions, 71208 Pearson
  rows and 13210 Cambium rows, or prod's current count if it has grown.

- [ ] **Step 6: Commit**

  Commit `feat(dbt): add int_assessments__state_nj_scores`.

### Task 5: Repoint the readers whose output doesn't change

**Files (modify):**

- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_scores.sql:1-45`
- `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__state_test_scores.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql` (CTE
  `state_nj_assessments`)
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
  (CTE `state_nj_administrations`)
- `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__state_assessments_demographic_comps.sql`
  (CTE `valid_prelim_assessments`)
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__state_assessments_dashboard.sql`
  (CTE `valid_prelim_assessments`)

**Interfaces:** Consumes Task 4's model. Every output column name of these 6
models stays as it is.

- [ ] **Step 1: Write the comparison query (the failing test)**

  Save a scratchpad query that, for each of the 6 models, counts full-row
  `EXCEPT DISTINCT` in both directions (via `to_json_string(t)`) between the dev
  and prod relations. It also counts the key-set `EXCEPT DISTINCT` of
  `assessment_score_key` between dev and prod
  `fct_assessment_scores_enrollment_scoped`.

  Run it before building: every dev relation is still missing or stale.

- [ ] **Step 2: Make the edits**

  In each file, swap `ref("int_pearson__all_assessments")` for
  `ref("int_assessments__state_nj_scores")` and rename the columns it reads per
  the spec's reader table. In `int_assessments__state_scores`, the New Jersey
  branch then selects the columns under their shared names, and keeps `season`
  from `administration_round`. Update the prelim-gate comment text that names
  the old model.

- [ ] **Step 3: Build the models and run the comparison**

  `uv run dbt build --select int_assessments__state_scores rpt_deanslist__state_test_scores dim_assessments dim_assessment_administrations int_tableau__state_assessments_demographic_comps rpt_tableau__state_assessments_dashboard fct_assessment_scores_enrollment_scoped --defer --favor-state ...`.
  Expected: PASS.

  Then run Step 1's query. Expected: 0 rows in every direction for every model.

- [ ] **Step 4: Commit**

  Commit
  `refactor(dbt): read NJ state scores from int_assessments__state_nj_scores`.

### Task 6: `int_students__graduation_pathway_scores` and its unit tests

**Files (modify):**

- `src/dbt/kipptaf/models/students/intermediate/int_students__graduation_pathway_scores.sql`
  (alias `n` in CTE `scores`)
- `src/dbt/kipptaf/models/students/intermediate/properties/int_students__graduation_pathway_scores.yml`
  (fixtures near lines 242 and 419)

- [ ] **Step 1: Rewrite the fixtures, then run them and confirm they fail**

  In both unit-test fixtures, change `input:` to
  `ref('int_assessments__state_nj_scores')` and rename the mocked columns:
  `localstudentidentifier`, `testscalescore`, `testcode` and
  `testscorecomplete`. `discipline`, `assessment_name` and `assessment_version`
  keep their names. Run
  `uv run dbt test --select "test_type:unit,int_students__graduation_pathway_scores" ...`.
  Expected: FAIL, because the model still reads the old ref.

- [ ] **Step 2: Make the model edit**

  Swap the ref and the 4 column names in the model.

- [ ] **Step 3: Run the tests and confirm they pass**

  Re-run Step 1's unit tests (expected PASS). Then build the model with
  `--defer`, and run a full-row `EXCEPT DISTINCT` in both directions against
  prod. Expected: 0 and 0.

- [ ] **Step 4: Commit**

  Commit
  `refactor(dbt): read graduation pathway scores from the NJ state score union`.

### Task 7: Tests, analysis, YAML references and the retirement

**Files (modify):**

- `src/dbt/kipptaf/tests/test_incorrect_student_number_pearson.sql`, and its
  `meta.dagster.ref.name` in `src/dbt/kipptaf/tests/properties.yml:266`
- `src/dbt/kipptaf/tests/stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources.sql`
- `src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql` (CTE
  `gaps`)
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml:76,86`
  and `int_assessments__resolved_section_enrollments.yml:55,77,87`
- Description text in `int_assessments__state_scores.yml`,
  `dim_assessment_administrations.yml`,
  `stg_google_sheets__assessments__vendor_subject_crosswalk.yml`, and
  `models/cambium/staging/properties/stg_cambium__{njgpa,eoc,njsla}.yml`
- `src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml`

- [ ] **Step 1: Record the prod baseline**

  Record today's failing-row counts from prod for
  `test_incorrect_student_number_pearson` and the crosswalk-coverage test. Read
  them from the stored-failure views in the kipptaf `dbt_test__audit` dataset,
  or by compiling each test on main and counting its rows. Save the counts to
  the scratchpad.

- [ ] **Step 2: Make the SQL edits**

  Swap the ref and rename the columns in the 2 tests and the analysis, per the
  spec's reader table.

- [ ] **Step 3: Make the YAML edits**

  - Point the 4 `source_column` strings at
    `int_assessments__state_nj_scores.<col>`. Both columns keep their names.
  - Set the test's `meta.dagster.ref.name` to
    `int_assessments__state_nj_scores`.
  - Update the description text so it names the new models.

- [ ] **Step 4: Retire the old model**

  In `int_pearson__all_assessments.yml`, add `config: enabled: false` to the
  model and to every test on it: the 2 model-level tests and the column tests on
  `assessment_version`, `assessment_type` and `test_grade`.

- [ ] **Step 5: Verify**

  - The 2 tests return the same failing-row counts as the Step 1 baseline.
  - `uv run dbt compile --select analysis:state_assessment_tiered_crosswalk_match`
    compiles.
  - `rg 'int_pearson__all_assessments' <worktree>/src/dbt/kipptaf --glob '*.{sql,yml,md}'`
    finds only the disabled model's own 2 files and the 3
    `models/pearson/sources-kipp*.yml` entries.
  - A `dbt parse --no-partial-parse` diff of enabled nodes against main shows
    `int_pearson__all_assessments` and its tests gone, and
    `int_assessments__state_nj_scores` and its tests added.

- [ ] **Step 6: Commit**

  Commit `refactor(dbt): retire kipptaf int_pearson__all_assessments`.

### Task 8: Open PR 2

- [ ] **Step 1:** Run trunk check on every changed file, push, and open the PR
      with `Closes #5591` and the Task 4-7 verification counts in the "For
      Claude" fold.
- [ ] **Step 2:** Watch CI. Expect the wide `state:modified+` selection that
      #5366 warned about, and before blaming this change for a failure, count
      the same failure in prod.
- [ ] **Step 3:** Confirm `dagster-cloud-deploy` loads the kipptaf code location
      (Review Focus 5), and process the `claude-review` findings per
      `pr-ci-review`.
