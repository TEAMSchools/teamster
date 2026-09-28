# Shared State Score Union Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `int_assessments__state_scores`, 1 table that unions the New
Jersey and Florida state score models, and repoint the 8 kipptaf union sites to
it with zero change in their output.

**Architecture:** A positional `union all` of 2 enumerated selects, 1 per
source, then 1 left join to the vendor subject crosswalk, materialized as a
table. Each site replaces its per-source CTEs with a read of the shared model,
filtered by `score_source`. Each task proves its site unchanged with a full-row
`EXCEPT DISTINCT` against prod.

**Tech Stack:** dbt (BigQuery), kipptaf project, BigQuery MCP
`execute_sql_readonly` for the comparisons.

**Spec:**
[docs/superpowers/specs/2026-09-28-shared-state-score-union-design.md](../specs/2026-09-28-shared-state-score-union-design.md).
The column table, the hash inputs and the per-site table there are
authoritative. This plan does not repeat them.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-shared-state-score-union`,
  branch `cbini/refactor/claude-shared-state-score-union`. Every `git` call uses
  `git -C <worktree>`. Every dbt call uses
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf`.
- Before the first dbt command:
  `uv run dbt deps --project-dir <worktree>/src/dbt/kipptaf`, in its own Bash
  call.
- Invoke the `dbt-local-dev` skill before the first build. Read
  `src/dbt/kipptaf/CLAUDE.md` and `src/dbt/kipptaf/models/marts/CLAUDE.md` with
  the Read tool before editing.
- Build command, used by every task (`<sel>` is the task's selection):
  `uv run dbt build --select <sel> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir <worktree>/src/dbt/kipptaf 2>&1 | tail -n 30`.
  Run it in the foreground.
- Every task's selection includes `int_assessments__state_scores`. A narrower
  selection re-points the shared model to prod, where it does not exist.
- `assessment_score_key` and `assessment_administration_key` keep their exact
  input lists. Do not edit any `generate_surrogate_key` call.
- `academic_year` in the shared model is unshifted. Every `+ 1` stays in its
  site.
- No `select distinct`, `qualify row_number() = 1` or `dbt_utils.deduplicate`
  added anywhere. A duplicate is a finding, not something to mask.
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
type rejects `except distinct` (ARRAY, JSON), wrap each side as
`select to_json_string(t) from <rel> as t`. Before and after the query, read
`last_modified_time` from `<prod dataset>.__TABLES__` for the model and for
`int_pearson__all_assessments`' and `int_fldoe__all_assessments`' upstream
tables. If any changed in between, rebuild and rerun.

## Review Focus

1. The 1 Cambium row with a null `localstudentidentifier` must not get a new
   `student_identifier` in the fact. Task 2's equivalence check covers it, and
   its extra step counts it directly.
2. `rpt_tableau__academic_goals_rollup` grade-3 PM1 rows must keep their
   unshifted year. A wrong offset moves Reading and Math counts. Task 5 adds a
   per-branch count.
3. A New Jersey row whose `raw_subject` has no crosswalk row must pass through
   as `raw_subject`, not null. Task 1 counts nulls in `illuminate_subject_area`.
4. `scale_score` widens to float64 on Florida rows. A site that casts it, such
   as `rpt_gsheets__assessment_roster`, must produce the same value. The
   full-row checks in tasks 6 and 7 cover it.
5. The prelim branch of `rpt_tableau__state_assessments_dashboard` must keep
   reading `int_pearson__student_list_report`. Task 7 greps for the `ref()`.

---

### Task 1: The shared model

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_scores.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__state_scores.yml`

**Interfaces:**

- Consumes: `ref("int_pearson__all_assessments")`,
  `ref("int_fldoe__all_assessments")`,
  `ref("stg_google_sheets__assessments__vendor_subject_crosswalk")`.
- Produces: `ref("int_assessments__state_scores")`, with exactly the columns and
  names in the spec's _Columns_ table, in that order. `score_source` is
  `'state_nj'` or `'state_fl'`.

- [ ] **Step 1: Write the SQL.** CTEs `state_nj` and `state_fl`, each an
      enumerated select following the spec's column table. Pad New Jersey-only
      columns on the Florida side with
      `cast(null as <type of the pearson column>)`. Then `unioned` as
      `union all`, then the final select left-joins the crosswalk as `x` on
      `x.source_system = if(u.score_source = 'state_nj', 'pearson', 'fldoe') and x.raw_subject = u.raw_subject`,
      computing `illuminate_subject_area` as
      `coalesce(x.illuminate_subject_area, u.raw_subject)`.

- [ ] **Step 2: Write the properties file.** Model description, a description
      for every column, `config.materialized: table`,
      `config.meta.contains_pii: true`, and 1 model-level test:
      `dbt_utils.unique_combination_of_columns` over `_dbt_source_project`,
      `state_student_id`, `academic_year`, `administration_period`,
      `raw_subject`. Copy the file layout from
      `int_assessments__score_anchors.yml`, without its `automation_condition`
      block, since this model stays eager.

- [ ] **Step 3: Build.** Selection: `int_assessments__state_scores`. Expected:
      the model and its uniqueness test pass, `ERROR=0`.

- [ ] **Step 4: Check rows against the sources.**

```sql
select
    score_source,
    count(*) as n,
    countif(illuminate_subject_area is null) as null_subject,
    countif(state_student_id is null) as null_state_id,
from `<dev>.int_assessments__state_scores`
group by score_source
```

Expected: `state_nj` equals `count(*)` of prod
`kipptaf_pearson.int_pearson__all_assessments`, and `state_fl` equals prod
`kipptaf_fldoe.int_fldoe__all_assessments`, both counted in the same minute.
`null_subject = 0` and `null_state_id = 0` on both rows.

- [ ] **Step 5: Run the crosswalk coverage test.**
      `uv run dbt test --select stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir <worktree>/src/dbt/kipptaf 2>&1 | tail -n 15`.
      Expected: `PASS=1`.

- [ ] **Step 6: Lint and commit.** Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <both files> </dev/null`
      from the worktree. Expected: no issues. Commit as
      `feat(dbt): add int_assessments__state_scores`.

### Task 2: `fct_assessment_scores_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`,
  CTEs `state_nj`, `state_fl`, `state_all`, `state_union`

**Interfaces:**

- Consumes: `int_assessments__state_scores` from Task 1.
- Produces: an unchanged fact. The CTE keeps the name `state_union` and every
  column the downstream `su.` references read, including `student_identifier`
  and `illuminate_subject`.

- [ ] **Step 1: Capture the baseline.** Run the equivalence check's `n_prod`
      half now and record it. Also record
      `select count(*) from kipptaf_pearson.int_pearson__all_assessments where localstudentidentifier is null`.
      Expected: 1.

- [ ] **Step 2: Replace the 4 CTEs with 1 `state_union` CTE** over
      `int_assessments__state_scores`, per the spec's per-site table. Filter
      `scale_score is not null and (score_source = 'state_fl' or academic_year >= {{ var("current_academic_year") - 7 }})`.
      `student_identifier` is
      `coalesce(cast(student_number as string), if(score_source = 'state_fl', state_student_id, null))`.
      `illuminate_subject` reads `illuminate_subject_area`. `source_system` is
      `if(score_source = 'state_nj', 'pearson', 'fldoe')`. `title` reads
      `assessment_name`, `performance_band` reads `performance_level_label`,
      `performance_band_level` reads `performance_level`, `grade_level` reads
      `test_grade`, and `percent_correct` stays `cast(null as numeric)`.

- [ ] **Step 3: Build.** Selection:
      `int_assessments__state_scores fct_assessment_scores_enrollment_scoped`.
      Expected: `ERROR=0`. The contract passes with no properties change.

- [ ] **Step 4: Run the equivalence check** on the fact. Expected: pass.

- [ ] **Step 5: Commit** as
      `refactor(dbt): read state scores from the shared union in the fact`.

### Task 3: `int_assessments__score_anchors`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`,
  CTEs `state_nj_scores` and `state_fl_scores`

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: 1 CTE named `state_scores` with the same 9 columns in the same order
  as today's `state_nj_scores`, which the `scores` union reads by position.

- [ ] **Step 1: Replace the 2 CTEs with `state_scores`** and swap them in the
      `scores` union. Filter
      `test_date is not null and student_number is not null`. `source_system` is
      `if(score_source = 'state_nj', 'pearson', 'fldoe')` and `source_type` is
      `score_source`. `raw_subject` reads `raw_subject`. The `scores_resolved`
      crosswalk join stays.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__state_scores int_assessments__score_anchors`. Expected:
      `ERROR=0`.

- [ ] **Step 3: Run the equivalence check.** Expected: pass.

- [ ] **Step 4: Commit** as
      `refactor(dbt): read state scores from the shared union in score anchors`.

### Task 4: `int_extracts__student_enrollments_subjects`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql`,
  CTEs `prev_yr_state_test` and `prev_yr_state_test_resolved`

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: 1 CTE, `prev_yr_state_test_resolved`, keeping the columns the final
  join reads: `_dbt_source_project`, `statestudentidentifier`,
  `academic_year_plus`, `subject`, `is_proficient`,
  `state_test_aggregated_proficiency`.

- [ ] **Step 1: Replace the 2 CTEs** per the spec's per-site table.
      `statestudentidentifier` reads `state_student_id`, `subject` reads
      `illuminate_subject_area`, `state_test_aggregated_proficiency` reads
      `aggregated_proficiency`, and `academic_year_plus` is `academic_year + 1`.
      Drop the crosswalk join.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__state_scores int_extracts__student_enrollments_subjects`.
      Expected: `ERROR=0`.

- [ ] **Step 3: Run the equivalence check.** Expected: pass. Also run
      `select countif(state_test_proficiency != 'No Test') from <dev>` and
      confirm it equals prod's figure. It was 52851 on 2026-09-28.

- [ ] **Step 4: Commit** as
      `refactor(dbt): read state scores from the shared union in enrollment subjects`.

### Task 5: `rpt_tableau__academic_goals_rollup`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__academic_goals_rollup.sql`,
  the 3 state branches of `state_test_union` and `state_test_resolved`

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: `state_test_union` with the same columns in the same order. The STAR
  branch is untouched, and it keeps `source_system` null so
  `state_test_resolved` still passes its `subject` through.

- [ ] **Step 1: Replace the 3 state branches with 1 select.** Filter:

```sql
(
    score_source = 'state_nj'
    and assessment_name = 'NJSLA'
    and not (grade_level_when_assessed = 8 and raw_subject like 'Algebra%')
)
or (
    score_source = 'state_fl'
    and assessment_name = 'FAST'
    and scale_score is not null
    and (
        (administration_period = 'PM3' and test_grade != 3)
        or (administration_period = 'PM1' and test_grade = 3)
    )
)
```

`academic_year_plus` is
`academic_year + if(administration_period = 'PM1', 0, 1)`. `level` reads
`performance_level`. `assessment_type` is
`if(score_source = 'state_nj', assessment_name, 'FAST PM3')`. `source_system` is
`if(score_source = 'state_nj', 'pearson', 'fldoe')`. In `state_test_resolved`,
replace the crosswalk expression with `illuminate_subject_area`, carried through
this branch, and drop the join. Keep the `case` that maps `'Text Study'` to
`'Reading'`.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__state_scores rpt_tableau__academic_goals_rollup`.
      Expected: `ERROR=0`.

- [ ] **Step 3: Run the equivalence check.** Expected: pass. Also compare
      `select subject, count(*), countif(scale_score_state is not null) from <rel> group by subject`
      on dev and prod. On 2026-09-28 prod read Math 15852 / 7746 and Reading
      15393 / 7772.

- [ ] **Step 4: Commit** as
      `refactor(dbt): read state scores from the shared union in academic goals`.

### Task 6: `rpt_gsheets__assessment_roster`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__assessment_roster.sql`,
  CTEs `njsla` and `fast`

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: 1 CTE, `state_tests`, with the 12 columns `unioned` reads, in the
  column order of today's `njsla` CTE.

- [ ] **Step 1: Replace the 2 CTEs with `state_tests`** and swap it into
      `unioned`. Filter:
      `discipline in ('ELA', 'Math') and ((score_source = 'state_nj' and assessment_name = 'NJSLA' and academic_year = {{ var("current_academic_year") - 1 }}) or (score_source = 'state_fl' and student_number is not null and academic_year in ({{ var("current_academic_year") }}, {{ var("current_academic_year") - 1 }})))`.
      `assessment_source` is `if(score_source = 'state_nj', 'NJSLA', 'FAST')`.
      `administration_round` reads `administration_round`.
      `performance_band_label` reads `performance_level_label`.
      `performance_band_int` is `cast(performance_level as int)`. `scale_score`
      is `cast(scale_score as numeric)`.

- [ ] **Step 2: Build.** Selection:
      `int_assessments__state_scores rpt_gsheets__assessment_roster`. Expected:
      `ERROR=0`.

- [ ] **Step 3: Run the equivalence check.** Expected: pass.

- [ ] **Step 4: Commit** as
      `refactor(dbt): read state scores from the shared union in the assessment roster`.

### Task 7: `rpt_tableau__state_assessments_dashboard`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__state_assessments_dashboard.sql`,
  the pearson and fldoe branches of `assessment_scores`

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: `assessment_scores` with the same columns in the same order. The
  prelim branch is untouched.

- [ ] **Step 1: Replace the 2 branches with 1 select.** Filter:
      `scale_score is not null and (score_source = 'state_fl' or academic_year >= {{ var("current_academic_year") - 7 }})`.
      Mapping: `localstudentidentifier` reads `student_number`, `state_id` reads
      `state_student_id`, `score` reads `scale_score`, `performance_band` reads
      `performance_level_label`, `performance_band_level` reads
      `performance_level`, `admin` reads `administration_round`, `subject` reads
      `aligned_subject`, `test_code` reads `aligned_test_code`. Every other
      column keeps its name.

- [ ] **Step 2: Confirm the prelim branch.**
      `rg -c 'ref\("int_pearson__student_list_report"\)' <file>`. Expected: the
      same count as on `origin/main`.

- [ ] **Step 3: Build.** Selection:
      `int_assessments__state_scores rpt_tableau__state_assessments_dashboard`.
      Expected: `ERROR=0`.

- [ ] **Step 4: Run the equivalence check.** Expected: pass.

- [ ] **Step 5: Commit** as
      `refactor(dbt): read state scores from the shared union in the state dashboard`.

### Task 8: The 2 branch-keeping sites

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__state_assessments_demographic_comps.sql`,
  the pearson and fldoe branches of `scores`
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__state_assessments_weekly.sql`,
  both branches

**Interfaces:**

- Consumes: `int_assessments__state_scores`.
- Produces: both models unchanged, each branch structure kept.

- [ ] **Step 1: Repoint `int_tableau__state_assessments_demographic_comps`.**
      Each branch joins `int_assessments__state_scores` as `a`, adding
      `a.score_source = 'state_nj'` or `'state_fl'` to its join. Rename per the
      spec's column table: `a.localstudentidentifier` becomes
      `a.student_number`, `a.admin` becomes `a.administration_round`,
      `a.testscalescore` becomes `a.scale_score`. The Florida branch's
      `a.test_code` reads `a.aligned_test_code`. The New Jersey branch's
      `aligned_*` reads keep their names.

- [ ] **Step 2: Repoint `int_topline__state_assessments_weekly`.** The Florida
      join reads `fl.state_student_id` and `fl.administration_period`. The New
      Jersey join reads `p.state_student_id`. Add the `score_source` predicate
      to each join.

- [ ] **Step 3: Build.** Selection:
      `int_assessments__state_scores int_tableau__state_assessments_demographic_comps int_topline__state_assessments_weekly`.
      Expected: `ERROR=0`.

- [ ] **Step 4: Run the equivalence check on both models.** Expected: both pass.

- [ ] **Step 5: Confirm no site still unions the 2 sources.**
      `rg -l 'ref\("int_fldoe__all_assessments"\)' src/dbt/kipptaf/models` and
      the same for `int_pearson__all_assessments`. Expected: neither list
      contains any of the 8 sites. `int_assessments__state_scores` appears in
      both.

- [ ] **Step 6: Commit** as
      `refactor(dbt): read state scores from the shared union in comps and topline`.

### Task 9: Whole-branch check and PR

**Files:** none new.

- [ ] **Step 1: Rebuild everything in 1 selection.** Selection: the shared model
      plus all 8 sites, listed by name. Do not use
      `int_assessments__state_scores+`, which pulls in the whole Cube mart
      graph. A single run makes changed models that read each other, such as
      `rpt_tableau__academic_goals_rollup` reading
      `int_extracts__student_enrollments_subjects`, use each other's dev copies,
      which the per-task builds did not do. Expected: `ERROR=0`. Warnings on
      unrelated tests: count the same failure in prod before treating it as new.

- [ ] **Step 2: Rerun the equivalence check on all 8 sites** from this build.
      Expected: all pass.

- [ ] **Step 3: Lint every touched file.** Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
      from the worktree, listing every file from Tasks 1-8 plus this plan.
      Expected: no issues.

- [ ] **Step 4: Push and open the PR.** Invoke `pr-ci-review` first. Body from
      `.github/pull_request_template.md`, with `Closes #5366` and `Refs #5362`.
      The body reports the equivalence counts per site, and no row values. Check
      the returned title and body match intent.
