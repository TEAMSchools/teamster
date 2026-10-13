# Shared Benchmark Score Union Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `int_assessments__benchmark_scores`, 1 table that unions the
iReady, Star and DIBELS benchmark sources, and repoint the 3 kipptaf union sites
to it with zero change in their output.

**Architecture:** A positional `union all` of 3 enumerated selects, 1 per
source, then 1 left join to the vendor subject crosswalk, materialized as a
table. Each site replaces its per-source CTEs with a read of the shared model,
filtered by `score_source`, and keeps its own filters and dedupes. Each task
proves its site unchanged with a full-row `EXCEPT DISTINCT` against prod.

**Tech Stack:** dbt (BigQuery), kipptaf project, BigQuery MCP
`execute_sql_readonly` for the comparisons.

**Spec:**
[docs/superpowers/specs/2026-09-28-shared-benchmark-score-union-design.md](../specs/2026-09-28-shared-benchmark-score-union-design.md).
Its _Columns_ table, _Hash inputs_ and _Per-site changes_ table are
authoritative. This plan does not repeat them.

## Global Constraints

- Blocked on #5366. Do not start Task 1 until #5366 is merged to `main`.
- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-shared-benchmark-score-union`,
  branch `cbini/refactor/claude-shared-benchmark-score-union`. Every `git` call
  uses `git -C <worktree>`. Every dbt call uses
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf`.
- Invoke the `dbt-local-dev` skill before the first build. Read
  `src/dbt/kipptaf/CLAUDE.md` and `src/dbt/kipptaf/models/marts/CLAUDE.md` with
  the Read tool before editing.
- Build command, used by every task (`<sel>` is the task's selection):
  `uv run dbt build --select <sel> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir <worktree>/src/dbt/kipptaf 2>&1 | tail -n 30`.
  Run it in the foreground.
- Every task's selection includes `int_assessments__benchmark_scores`. A
  narrower selection defers the shared model to prod, where it does not exist.
- Both vendor-branch `generate_surrogate_key` calls in
  `fct_assessment_scores_enrollment_scoped` keep their exact input lists. Do not
  edit any `generate_surrogate_key` call.
- Site filters stay at the site. The shared model filters only
  `assessment_type = 'Benchmark'` on the DIBELS branch.
- No `select distinct`, `qualify row_number() = 1` or `dbt_utils.deduplicate`
  added anywhere. The 2 existing `dbt_utils.deduplicate` calls (Star in the
  fact, DIBELS in the roster) stay exactly as they are. A duplicate is a
  finding, not something to mask.
- Never paste query rows into a commit, PR or issue. Report counts only. The
  scores are student-level PII.
- Commit messages: conventional commits, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Write each message
  to the session scratchpad and `git commit -F` it. Stage named files.

### The equivalence check

Every site task ends with this query, run through `execute_sql_readonly` on
project `teamster-332318`. `<dev>` is the dev relation, found with
`select table_schema from teamster-332318.region-us.INFORMATION_SCHEMA.TABLES where table_name = '<model>' and table_schema like 'zz_cbini_%'`.
`<prod>` is the same model's prod relation.

```sql
select
    (select count(*) from `<dev>`) as n_dev,
    (select count(*) from `<prod>`) as n_prod,
    (select count(*) from (select * from `<dev>` except distinct select * from `<prod>`)) as only_dev,
    (select count(*) from (select * from `<prod>` except distinct select * from `<dev>`)) as only_prod,
```

It passes when `n_dev = n_prod`, `only_dev = 0` and `only_prod = 0`. If a column
type rejects `except distinct`, wrap each side as
`select to_json_string(t) from <rel> as t`. Before and after the query, read
`last_modified_time` from `__TABLES__` for the model's prod relation and for
`kipptaf_iready.int_iready__diagnostic_results`,
`kipptaf_renlearn.stg_renlearn__star` and
`kipptaf_iready.int_iready__domain_unpivot`. If any changed in between, rebuild
and rerun.

## Review Focus

1. DIBELS sub-measure rows in the fact must keep their `response_type = 'group'`
   and their measure code and name. Task 2's equivalence check covers every
   hashed column.
2. Star same-day retests reach the fact undeduped from the shared model, and the
   fact's dedupe must still keep the best sitting. Task 2's check covers it.
3. The 130 iReady rows with a null `_dbt_source_project` must still reach
   `int_assessments__score_anchors`. Task 3 counts them directly.
4. Internal rows in `int_assessments__score_anchors` must keep `raw_subject`
   after the crosswalk join is removed. Task 3's unit test and check cover it.
5. A benchmark row whose `raw_subject` has no crosswalk row must fall back to
   `raw_subject`, not null. Task 1 counts nulls in `illuminate_subject_area`.

---

### Task 0: Rebase onto #5366

**Files:** none.

- [ ] **Step 1: Confirm #5366 is merged.** Its PR is merged and
      `git -C <worktree> log origin/main --oneline -- src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_scores.sql`
      prints at least 1 commit.
- [ ] **Step 2: Merge `origin/main`.** Invoke the `resuming-a-branch` skill
      first, then `git -C <worktree> merge origin/main`. Expected: no conflict,
      because this branch holds only the spec and this plan.
- [ ] **Step 3: Re-read the 2 shared files.** Read
      `fct_assessment_scores_enrollment_scoped.sql` and
      `int_assessments__score_anchors.sql` as they are after #5366, and their
      properties files. The benchmark CTEs this plan names should be unchanged;
      if #5366 moved one, follow the spec's intent, not this plan's CTE names.
- [ ] **Step 4:** `uv run dbt deps --project-dir <worktree>/src/dbt/kipptaf`, in
      its own Bash call.

### Task 1: The shared model

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__benchmark_scores.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__benchmark_scores.yml`

**Interfaces:**

- Consumes: `ref("int_iready__diagnostic_results")`,
  `ref("stg_renlearn__star")`, `ref("int_amplify__all_assessments")`,
  `ref("stg_google_sheets__assessments__vendor_subject_crosswalk")`.
- Produces: `ref("int_assessments__benchmark_scores")`, with exactly the columns
  and names in the spec's _Columns_ table, in that order. `score_source` is
  `'iready'`, `'star'` or `'dibels'`.

- [ ] **Step 1: Write the SQL.** CTEs `iready`, `star` and `dibels`, each an
      enumerated select following the spec's column table, padding missing
      columns with `cast(null as <type>)` (`discipline` string,
      `proficiency_level_int` int64, `is_proficient` bool, `rn_subj_day` and
      `rn_subj_round` int64, `assessment_id` string, `response_type_code` and
      `response_type_description` string). The DIBELS branch filters
      `where assessment_type = 'Benchmark'`, and its `response_type_code` and
      `response_type_description` are the fact's `case` expressions, copied.
      Then `unioned` as `union all`, then the final select left-joins the
      crosswalk as `x` on
      `u.source_system = x.source_system and u.raw_subject = x.raw_subject`,
      computing `illuminate_subject_area` as
      `coalesce(x.illuminate_subject_area, u.raw_subject)`.

- [ ] **Step 2: Write the properties file.** Model description, a description
      and `data_type` for every column, `config.materialized: table`,
      `config.meta.contains_pii: true`, and 1 model-level test:
      `dbt_utils.unique_combination_of_columns` over the spec's 10 grain
      columns. Copy the file layout from `int_assessments__score_anchors.yml`,
      without its `automation_condition` block, since this model stays eager.

- [ ] **Step 3: Build.** Selection: `int_assessments__benchmark_scores`.
      Expected: the model and its uniqueness test pass, `ERROR=0`.

- [ ] **Step 4: Check rows against the sources.**

```sql
select
    score_source,
    response_type,
    count(*) as n,
    countif(illuminate_subject_area is null) as n_null_subject,
from `<dev>`
group by score_source, response_type
```

Expected: `iready`/`overall` equals `count(*)` of
`int_iready__diagnostic_results`; `star`/`overall` equals `count(*)` of
`stg_renlearn__star`; `dibels`/`overall` and `dibels`/`group` equal the
`measure_standard = 'Composite'` and non-`Composite` counts of
`int_amplify__all_assessments` under `assessment_type = 'Benchmark'`, all read
from prod in the same query. `n_null_subject = 0` on every row.

- [ ] **Step 5: Commit.** `feat(dbt): add int_assessments__benchmark_scores`.

### Task 2: `fct_assessment_scores_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`,
  the CTEs `iready_scores_raw` through `vendor_resolved`.

**Interfaces:**

- Consumes: `ref("int_assessments__benchmark_scores")` from Task 1.
- Produces: no new columns. The contract YAML does not change.

- [ ] **Step 1: Rewrite the vendor CTEs.**
  - `iready_scores_raw` and `dibels_scores` become 1 CTE, `benchmark_scores`,
    reading the shared model with the spec's combined filter under
    `score_source`. It selects the 16 columns `vendor_all` enumerates today,
    plus `illuminate_subject_area as illuminate_subject`.
  - `star_scores_raw` reads the shared model where `score_source = 'star'` and
    the 3 existing not-null predicates, selecting the same columns plus
    `assessment_id` and `illuminate_subject_area as illuminate_subject`.
    `star_scores` (the `dbt_utils.deduplicate` and its comment) is unchanged.
  - `iready_domain_scores_raw` is unchanged. A new CTE, `iready_domain_scores`,
    left-joins it to the crosswalk the way `vendor_resolved` does today, adding
    `illuminate_subject`.
  - `iready_scores` goes. `vendor_all` unions `benchmark_scores`, `star_scores`
    and `iready_domain_scores`, and `vendor_resolved` goes. The final vendor
    `select` reads `vendor_all`, aliased `va`.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__benchmark_scores fct_assessment_scores_enrollment_scoped`.
      Expected: `ERROR=0`, contract passes.

- [ ] **Step 3: Run the equivalence check** on the fact. Expected: passes over
      every row, which covers both hashes.

- [ ] **Step 4: Commit.**
      `refactor(dbt): read benchmark scores from the shared model in the fact`.

### Task 3: `int_assessments__score_anchors`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml`,
  its model description and its 2 unit tests.

**Interfaces:**

- Consumes: `ref("int_assessments__benchmark_scores")` from Task 1, and #5366's
  `ref("int_assessments__state_scores")`.
- Produces: no new columns.

- [ ] **Step 1: Update the unit tests first.** In both tests, replace the
      `int_iready__diagnostic_results`, `stg_renlearn__star` and
      `int_amplify__all_assessments` inputs with 1
      `ref('int_assessments__benchmark_scores')` input, and drop the crosswalk
      input. `test_internal_collapses_to_one_row_per_canonical` gives it
      `rows: []`. `test_duplicate_vendor_rows_collapse` gives it the same 3
      iReady rows as `format: sql`, now with `score_source: 'iready'`,
      `raw_subject: 'Reading'`, `illuminate_subject_area: 'Text Study'`,
      `test_date` and `scale_score` instead of the source column names. Both
      `expect` blocks are unchanged.

- [ ] **Step 2: Run the unit tests to see them fail.**
      `uv run dbt test --select "int_assessments__score_anchors,test_type:unit" ...`
      with the build command's flags. Expected: FAIL, because the model does not
      yet ref `int_assessments__benchmark_scores`.

- [ ] **Step 3: Rewrite the SQL.** `iready_scores`, `star_scores` and
      `dibels_scores` become 1 CTE, `benchmark_scores`, reading the shared
      model. Its filter keeps each source's current predicates under
      `score_source`; DIBELS uses `response_type = 'overall'` in place of
      `measure_standard = 'Composite'`. It selects
      `illuminate_subject_area as     subject_area`. Every other branch also
      emits `subject_area` (internal: `subject_area`; state: #5366's
      `illuminate_subject_area`), `scores` unions `subject_area` in place of
      `raw_subject` and `source_system`, and `scores_resolved` goes.
      `scores_keyed` reads `scores`.

- [ ] **Step 4: Update the model description** to say state and benchmark
      subjects arrive already resolved from the 2 shared models, instead of
      through a crosswalk join here.

- [ ] **Step 5: Build.** Selection:
      `int_assessments__benchmark_scores int_assessments__score_anchors`.
      Expected: `ERROR=0`, both unit tests and the uniqueness test pass.

- [ ] **Step 6: Run the equivalence check** on `int_assessments__score_anchors`.
      Expected: passes.

- [ ] **Step 7: Count the null-project iReady rows.**
      `countif(source_type = 'iready' and _dbt_source_project is null)` on dev
      and prod. Expected: equal and non-zero.

- [ ] **Step 8: Commit.**
      `refactor(dbt): read benchmark scores from the shared model in score anchors`.

### Task 4: `rpt_gsheets__assessment_roster`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__assessment_roster.sql`,
  the `iready` and `dibels_filtered` CTEs.

**Interfaces:**

- Consumes: `ref("int_assessments__benchmark_scores")` from Task 1.
- Produces: no new columns. The contract YAML does not change.

- [ ] **Step 1: Rewrite the 2 CTEs.** `iready` reads the shared model where
      `score_source = 'iready'` plus its 3 current predicates, mapping
      `test_round`, `overall_relative_placement`,
      `overall_relative_placement_int` and `overall_scale_score` to
      `administration_period`, `proficiency_level`, `proficiency_level_int` and
      `scale_score`. `dibels_filtered` reads it where `score_source = 'dibels'`,
      `response_type = 'overall'` and the 2-year window. It keeps the column
      names `dibels_deduplicated` and `dibels` read today (`period`,
      `measure_standard_score`, `measure_standard_level`,
      `measure_standard_level_int`, `client_date`), aliased from the shared
      columns, except that `aggregated_measure_standard_level` is replaced by
      the shared `is_proficient`, and the `dibels` CTE reads that column in
      place of its `= 'At/Above'` comparison. Output literals stay.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__benchmark_scores rpt_gsheets__assessment_roster`.
      Expected: `ERROR=0`, contract passes.

- [ ] **Step 3: Run the equivalence check** on the roster. Expected: passes.

- [ ] **Step 4: Commit.**
      `refactor(dbt): read benchmark scores from the shared model in the assessment roster`.

### Task 5: Whole-branch check and PR

**Files:** none new.

- [ ] **Step 1: Confirm the 3 sites no longer read the sources.**
      `rg -n "int_iready__diagnostic_results|stg_renlearn__star|int_amplify__all_assessments"`
      over the 3 site files. Expected: no hits. Over the fact,
      `int_iready__domain_unpivot` and `vendor_subject_crosswalk` each appear
      exactly once, both in the domain branch. The crosswalk appears nowhere in
      `int_assessments__score_anchors`.

- [ ] **Step 2: Build all 4 together.** Selection:
      `int_assessments__benchmark_scores+1`. Expected: `ERROR=0`. Warnings on
      models this branch did not touch are checked against prod before they are
      attributed here.

- [ ] **Step 3: Lint.** `trunk check --force --no-fix` on every changed `.sql`,
      `.yml` and `.md` file, per the root CLAUDE.md. Expected: no issues.

- [ ] **Step 4: Push and open the PR.** Body from
      `.github/pull_request_template.md`, `Closes #5367`, `Refs #5362`. State
      the 1 exception from the spec (the fact's domain branch) and the 3
      equivalence results as counts. Then invoke `pr-ci-review`.
