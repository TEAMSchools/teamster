# Performance Bands Dimension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Illuminate and Focus Assessments score in Cube its band
set, cut points and a mastery-relative level (At/Above, Approaching, Below, Far
Below), and prove the level against the DDI Suite DKI View.

**Architecture:** The Focus package's band numbering moves into its own model. A
kipptaf domain intermediate unions Illuminate and Focus bands at band grain and
derives the level; `dim_performance_bands` reads it, the scores fact gains
`performance_band_key`, and a new Cube cube joins in. The validator compares the
level against 2 DKI sheets.

**Tech Stack:** dbt (BigQuery) in `src/dbt/focus` and `src/dbt/kipptaf`; Cube
YAML in `src/cube/model`; `scripts/cube_validation`.

**Spec:**
`docs/superpowers/specs/2026-11-05-performance-bands-dimension-design.md`

**Worktree:**
`/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-band-set-dimension`
(branch `cristinabaldor/feat/claude-band-set-dimension`). Every git call uses
`git -C <worktree>`; every dbt, Python and pytest call uses `uv run` from the
worktree, except the validator runner (Task 7).

## Global Constraints

- Source literals: `illuminate` and `apex`, exactly as
  `int_assessments__response_rollup.source` spells them.
- `performance_band_key` =
  `generate_surrogate_key([source, performance_band_set_id, band_number])` on
  both the dim and the fact. The fact wraps it in
  `if(<band number> is not null, ..., cast(null as string))`.
- `mastery_level` values, exactly: `At/Above`, `Approaching`, `Below`.
- Level rule: At/Above = `band_number >= mastery_band_number`; Approaching =
  `band_number = mastery_band_number - 1`; Below = lower. `is_far_below` =
  `band_number = 1 and not is_mastery`.
- A set that breaks a level assumption (mastery not contiguous to the top band,
  `band_number` out of `minimum_score` order, or mastery starting below band 3)
  gets null `mastery_level` and null `is_far_below` on every band. Its guard
  test runs at `warn` (spec revision 2026-11-05).
- Focus mastery: `Level 3` and above on every Focus set.
- Only band sets used by internal scores (`int_assessments__response_rollup`,
  `is_internal_assessment`) are in the union and the dim.
- Below and Far Below shares are percents of distinct students
  (`student_enrollment_key`), over students with a banded score.
- Cut values are percent correct, 0 to 100.
- Every new or changed dbt column and Cube member has a `description:`; a
  one-column Cube member's description equals its dbt column's, registered in
  `TWINS`.
- No movement column and no Cube text about movement beyond `mastery_level`'s
  `ai_context` (spec, Cube section).

## Review Focus

1. A score with a band number but no band set (merged split standards) gets a
   null key, never a placeholder hash. Test: Task 4 FK-population query.
2. A standard on a different band set from its assessment keys to its own set.
   Test: Task 4 query comparing the fact key's set to the rollup row's set.
3. Focus set 4 spells 2 bands "Low Level 1". Band identity is the band number,
   never the label. Test: Task 3 unit test row with a duplicate label.
4. The fact's band number is `numeric` and the Focus band number is `int64`;
   both must hash to the same string. Test: Task 4 FK-population query returns 0
   orphans.
5. A new Illuminate set breaks a level assumption (mastery at band 2, a gap).
   Its bands get a null level instead of a wrong one, and nothing stops
   refreshing. Test: Task 3 unit-test set E.

---

### Task 1: Focus package band levels model

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__apex_band_levels.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__apex_band_levels.yml`
- Modify:
  `src/dbt/focus/models/intermediate/int_focus__apex_results.sql:141-190` (drop
  the `band_levels` CTE; join the new model)

**Interfaces:**

- Produces `int_focus__apex_band_levels`, 1 row per band: `band_set_id int64`,
  `band_set_name string` (from `stg_focus__apex_band_sets.name`),
  `label string`, `label_number int64`, `min_score` (as staged), `upper_bound`
  (next band's `min_score`, top band 1000000), `is_mastery bool`
  (`min_score >= ` the set's `Level 3` `min_score`; null when the set has no
  `Level 3`).

- [ ] **Step 1: Snapshot today's output.** Record `count(*)` and
      `count(distinct format('%T', t))` of
      `kippmiami_focus.int_focus__apex_results` (BigQuery MCP).
- [ ] **Step 2: Write the model and properties.** Move the CTE's logic as is,
      add the `band_sets` join and `is_mastery`. Properties: every column with
      `data_type` and description; `dbt_utils.unique_combination_of_columns` on
      `[band_set_id, label_number]` at `severity: error`.
- [ ] **Step 3: Repoint `int_focus__apex_results`** to join
      `ref("int_focus__apex_band_levels")` on the same predicates, reading
      `is_mastery` from it. Output columns unchanged.
- [ ] **Step 4: Build in dev.** Invoke `dbt-local-dev` first. Run
      `uv run dbt build --select int_focus__apex_band_levels int_focus__apex_results --project-dir src/dbt/kippmiami`.
      Expected: both build, tests pass.
- [ ] **Step 5: Prove no change.** On the dev relation vs prod:
      `select * from <prod> except distinct select * from <dev>` and the reverse
      both return 0 rows; counts match Step 1.
- [ ] **Step 6: Commit.** `git add` the 3 files by name;
      `refactor(dbt): move Focus Assessments band numbering into its own model`.

### Task 2: Expose Focus band levels to kipptaf

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` (add
  `int_focus__apex_band_levels` after `int_focus__apex_results`, same
  `config.meta.dagster` shape, asset key
  `[kippmiami, focus, int_focus__apex_band_levels]`)
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__apex_band_levels.sql`
  (the same `union_relations` passthrough as `int_focus__apex_results.sql` in
  that folder)
- Create or modify: that folder's properties file for the wrapper (description
  only, no uniqueness test, per the union-view exception)

**Interfaces:**

- Consumes: Task 1's model.
- Produces: kipptaf `int_focus__apex_band_levels` with Task 1's columns plus
  `_dbt_source_relation`, `_dbt_source_project`.

- [ ] **Step 1: Add the source entry and wrapper.**
- [ ] **Step 2: Compile against staging.**
      `uv run dbt compile --select int_focus__apex_band_levels --project-dir src/dbt/kipptaf --target staging`
      fails until Step 3 (no `zz_stg` relation); that confirms the gap.
- [ ] **Step 3: Seed the staging copy (shared write, user's OK required in the
      turn before).** In its own Bash call:
      `uv run dbt build --select int_focus__apex_band_levels --project-dir src/dbt/kippmiami --target staging`.
- [ ] **Step 4: Compile again.** Same command as Step 2. Expected: the compiled
      SQL lists every Task 1 column.
- [ ] **Step 5: Commit.**
      `feat(dbt): expose Focus Assessments band levels to kipptaf`.

### Task 3: Band union with the level rule

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__performance_band_union.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__performance_band_union.yml`
- Test: unit test and the guard test, both in the properties file

**Interfaces:**

- Consumes: `int_illuminate__performance_band_sets` (`performance_band_set_id`,
  `description`, `label`, `label_number`, `minimum_value`, `is_mastery`); Task
  2's wrapper; `int_assessments__response_rollup` (`source`,
  `performance_band_set_id`, `is_internal_assessment`).
- Produces `int_assessments__performance_band_union`, 1 row per band of a used
  set: `performance_band_key string`, `source string`,
  `performance_band_set_id int64`, `performance_band_set string`,
  `band_label string`, `band_number int64`, `band_count int64`,
  `minimum_score numeric`, `maximum_score numeric` (next band's minimum, null
  for the top band), `is_mastery bool`, `mastery_band_number int64`,
  `mastery_minimum_score numeric`, `mastery_level string`, `is_far_below bool`.

- [ ] **Step 1: Write the unit test** `test_performance_band_union_levels`
      (`format: sql` inputs). Fixtures and expected rows:
  - Illuminate set A, 5 bands, mastery from band 4: bands 1-5 →
    `Below, Below, Approaching, At/Above, At/Above`; `is_far_below` true only on
    band 1; `mastery_band_number` 4; `band_count` 5.
  - Illuminate set B, 5 bands, mastery from band 3: →
    `Below, Approaching, At/Above, At/Above, At/Above`; far below on band 1.
  - Focus set C, 8 bands, `Level 3` at band 6, bands 1 and 4 both labeled
    `Low Level 1`: → bands 1-4 `Below`, 5 `Approaching`, 6-8 `At/Above`; 8
    distinct keys.
  - An unused set D in the Illuminate input: absent from the output.
  - Illuminate set E, 5 bands, mastery from band 2: every band's `mastery_level`
    and `is_far_below` null; `is_level_rule_valid` false.
  - `maximum_score` of each top band is null; of every other band, the next
    band's `minimum_score`.
- [ ] **Step 2: Run it to see it fail.**
      `uv run dbt test --select test_type:unit,int_assessments__performance_band_union --project-dir src/dbt/kipptaf`.
      Expected: fails (model missing).
- [ ] **Step 3: Write the model.** Union Illuminate and Focus at band grain with
      the source literal, keep sets in the rollup's used set, then derive
      set-level columns with windows. Add a set-level `is_level_rule_valid bool`
      (true when all 3 assumptions in Global Constraints hold for the set;
      intermediate only, not in the dim), and the level with this rule:

  ```sql
  case
      when not is_level_rule_valid then null
      when band_number >= mastery_band_number then 'At/Above'
      when band_number = mastery_band_number - 1 then 'Approaching'
      else 'Below'
  end as mastery_level,
  ```

  `is_far_below` is null when `not is_level_rule_valid`.

- [ ] **Step 4: Write the properties.** `materialized: table` with the
      assessment star's cron tick (copy `dim_assessments`'
      `automation_condition`). `unique` on `performance_band_key` at
      `severity: error`. Every column described.
- [ ] **Step 5: Write the guard test** as a column test on
      `is_level_rule_valid`: `accepted_values: [true]` at `severity: warn` (it
      passes nulls, so pair it with `not_null` at `warn`). Its description names
      the source (Illuminate or Focus band-set setup), the 3 assumptions, and
      that a failing set's scores load with no level until the set is fixed or
      the rule is decided. No singular test file.
- [ ] **Step 6: Build and test.**
      `uv run dbt build --select int_assessments__performance_band_union --project-dir src/dbt/kipptaf`
      (with the `dbt-local-dev` defer flags). Expected: unit test, `unique` and
      the guard test pass (no warning today); 94 sets
      (`count(distinct format('%T|%T', source, performance_band_set_id))`).
- [ ] **Step 7: Commit.**
      `feat(dbt): union Illuminate and Focus band sets with a mastery level`.

### Task 4: Dimension and fact key

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_performance_bands.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_performance_bands.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
  (internal CTE selects `rr.performance_band_set_id`; the internal branch adds
  the key; the state and vendor branches add
  `cast(null as string) as performance_band_key`)
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`
  (new column, `config.meta.foreign_key` to `dim_performance_bands`)
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml` (add
  `ref("dim_performance_bands")`)
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml`
  (`title` description adds: for state tests, the test name, such as NJSLA,
  NJGPA, FAST or EOC)

**Interfaces:**

- Consumes: Task 3's columns.
- Produces: `kipptaf_marts.dim_performance_bands` with every Task 3 column
  except `source` and `performance_band_set_id` (plumbing, R8); fact column
  `performance_band_key string`.

- [ ] **Step 1: Write the dim** selecting Task 3's columns; properties copy
      `dim_assessments`' table config and PK constraint shape; descriptions
      match the spec's column table.
- [ ] **Step 2: Add the fact key** per Global Constraints.
- [ ] **Step 3: Build.**
      `uv run dbt build --select dim_performance_bands fct_assessment_scores_enrollment_scoped dim_assessments --project-dir src/dbt/kipptaf`.
      Expected: all pass; fact row count equals prod's.
- [ ] **Step 4: Check the key (Review Focus 1, 2, 4).** On the dev fact:
      `countif(performance_band_key is null and performance_band_label_number is not null)`
      = 0,
      `countif(performance_band_key is not null and performance_band_label_number is null)`
      = 0, and a left join to the dev dim leaves 0 unmatched non-null keys. Then
      for 2026-27 standard rows, the dim set behind each key equals the rollup
      row's `performance_band_set_id` on a 1,000-row sample.
- [ ] **Step 5: Check the cut values.** For 10 Illuminate and all 4 Focus sets,
      `mastery_minimum_score` equals the source's lowest mastery band minimum.
- [ ] **Step 6: Regenerate the marts reference.**
      `uv run scripts/generate_marts_reference.py`.
- [ ] **Step 7: Commit.**
      `feat(dbt): add dim_performance_bands and the scores fact's band key`.

### Task 5: Cube members, measures and text

**Files:**

- Create:
  `src/cube/model/cubes/student_assessments/student_performance_bands.yml`
  (`sql_table: kipptaf_marts.dim_performance_bands`; the domain-prefix rule
  names it `student_performance_bands`, after `student_assessments`)
- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml` (join
  `student_performance_bands` many-to-one on `performance_band_key`; measures
  below; text on `performance_band_label_number` and `is_mastery` names the new
  members)
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
  (new `join_path` block, every dim member except the key and `is_mastery`,
  which the fact already exposes; a `Performance band` folder; the 2 public
  measures)
- Modify: `src/cube/model/cubes/student_assessments/student_assessments.yml`
  (`title` description, twin of Task 4's)
- Modify: `src/cube/mcp/project_knowledge/assessment-cube-reference.md` (delete
  both interim band-set tables and text routing to them)
- Modify: `tests/cube/test_cube_schema.py` (`TWINS` for every one-column member
  of the new cube and `title`; `PHRASES` for the new `ai_context`)

**Interfaces:**

- Consumes: Task 4's dim and fact column.
- Produces view members: `performance_band_set`, `band_label`, `band_number`,
  `band_count`, `minimum_score`, `maximum_score`, `mastery_band_number`,
  `mastery_minimum_score`, `mastery_level`, `is_far_below`; measures
  `pct_students_below` and `pct_students_far_below` (hidden helpers
  `_count_students_banded`, `_count_students_below`,
  `_count_students_far_below`: `count_distinct` of
  `{student_section_enrollments.student_enrollment_key}` with filters on
  `{CUBE}.performance_band_key IS NOT NULL`,
  `{student_performance_bands.mastery_level} = 'Below'`,
  `{student_performance_bands.is_far_below}`).

- [ ] **Step 1: Write the cube, join, measures, view block and folder.**
      `mastery_level`'s `ai_context`: compares across assessments, band numbers
      do not; to see whether a student moved between bands on 2 assessments,
      compare `mastery_level` and name both assessments. Leave the new members
      and measures out of the `proficiency_rollup` pre-aggregation.
- [ ] **Step 2: Update the text and twins; delete the reference tables.**
- [ ] **Step 3: Run the schema tests.** `npm ci` in `src/cube` once, then
      `uv run pytest tests/cube/ 2>&1 | tail -n 15`. Expected: all pass, 0
      skipped.
- [ ] **Step 4: Smoke-test on a local Cube** (`cube-ops` skill; a model copy
      under the session scratchpad with the 2 `sql_table`s pointed at the dev
      dataset, a relative `CUBEJS_SCHEMA_PATH`, `CUBEJS_REFRESH_WORKER=false`).
      Query `pct_students_below` and `pct_students_far_below` by `mastery_level`
      for 1 2026-27 module. Expected: both return; the `Below` row's share
      matches a hand count on the dev fact.
- [ ] **Step 5: Commit.**
      `feat(cube): add performance band members and below/far-below shares`.

### Task 6: Pull request

- [ ] **Step 1: Lint** the touched SQL, YAML and markdown with
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- [ ] **Step 2: Push and open the PR** from `.github/pull_request_template.md`,
      `Closes #5573`, `Refs #6192`. Note in Reviewer Notes the shared
      `zz_stg_kippmiami_focus` seed and that the kippmiami model must build in
      prod before kipptaf's wrapper reads it.
- [ ] **Step 3: Offer CI watch and `claude-review` handling** (root CLAUDE.md).

### Task 7: Validate against the DKI View

Runbook: the `cube-validation` skill. Validation files go on
`cristinabaldor/test/claude-ddi-cube-validation`, in its own worktree, never in
the builder PR.

**Files:**

- Modify (validation branch):
  `src/cube/validation/student_assessment_scores_view.yml` (2 comparisons)
- Create (validation branch): the proof file `triage confirm` writes

- [ ] **Step 1: Worktree and merge.** Invoke `resuming-a-branch`; add a worktree
      for the validation branch and merge `origin/main`.
- [ ] **Step 2: Add comparison `levels-dki-mastery-bars`** on "DKI - Assessment
      Mastery Bars": `dims` map Performance Bands - 3 Level to `mastery_level`;
      the measure is the share of students per level; `rows:` block at student x
      assessment grain; filters and cuts copied from the existing
      `mastery-dki-school` comparison's shared block.
- [ ] **Step 3: Add comparison `far-below-dki-mastery-table`** on "DKI -
      Assessment Mastery Table", `sheet_field: AVG(Is Far Below)`, measure
      `pct_students_far_below`, same `rows:` grain.
- [ ] **Step 4: Preflight.** `preflight <file> --twb <ddi_suite.twb>`; settle
      the "Before prove" list with Cristina.
- [ ] **Step 5: Prove, check, run** through the runner with
      `--fact-dataset zz_<user>_kipptaf_marts` and a local Cube over Task 5's
      model: `prove --comparison` for both, `check-api`, `prove --check`, `run`.
- [ ] **Step 6: Triage.** Every open item should land on an existing cause or
      the new one. Write the new proof: cells where the workbook's school-level
      guess (`HS`: band >= 3, else band >= 4) disagrees with the band set's
      `mastery_level`. `triage confirm` it; 0 `UNEXPLAINED`.
- [ ] **Step 7: Commit the validation files** on the validation branch, each
      staged by name, and report the result to Cristina.

### Task 8: After merge

- [ ] **Step 1:** Confirm prod built
      `kippmiami_focus.int_focus__apex_band_levels` before kipptaf's next
      assessment tick; launch it in Dagster if not.
- [ ] **Step 2:** Re-run Task 7 Step 5 without `--fact-dataset` against Cube
      Cloud and update the PR description.
- [ ] **Step 3:** Close the Asana subtasks on `dim_assessments`: State test code
      / name (pointer to `module_code` and `title`) and QBL (retired
      2026-09-30).
