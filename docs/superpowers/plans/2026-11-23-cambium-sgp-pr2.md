# Cambium SGP, PR 2 (kipptaf NJ scores) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry `student_growth_percentile` from the kipptaf
`int_cambium__all_assessments` wrapper into `int_assessments__state_nj_scores`,
after the student crosswalk.

**Architecture:** The model is a positional `union all` of the Pearson and
Cambium branches, then a left join to the student crosswalk on
`student_test_uuid` that replaces only `student_number`. Add the column last in
both branches (a typed null on Pearson) and pass it through the final select. A
dbt unit test pins the union alignment and the crosswalk behavior.

**Tech Stack:** dbt (BigQuery), kipptaf project, dbt unit tests.

**Spec:** `docs/superpowers/specs/2026-11-05-cambium-sgp-design.md` (Design, "PR
2")

## Global Constraints

- Worktree root `W` =
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-cambium-sgp-nj-scores`.
  Absolute paths and `git -C W` on every call.
- Column `student_growth_percentile`, INT64, `config.meta.contains_pii: true`.
- `uv run dbt ... --project-dir W/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  No `--target staging` or `--target prod`.
- No PII values in commits or the PR. The PR says `Refs #6279`, never `Closes`.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; the PR body ends
  with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Review Focus

1. Positional `union all`: a column in a different position in either branch
   silently shifts values. The unit test pins it.
2. The crosswalk replaces `student_number` and must keep the row's SGP. The unit
   test pins it (crosswalked Cambium row).
3. Pearson rows must carry a null SGP. The unit test pins it.
4. Grain and row count must not change. The model's existing grain tests plus a
   dev-versus-prod row count pin it.
5. Descendants (`int_assessments__state_scores`, the NJ marts, the STAT and
   DeansList `rpt_` models) all list their columns, so the new column cannot
   reach or break them. dbt Cloud CI builds `state:modified+` for real; no local
   descendant build.

---

### Task 1: `student_growth_percentile` in `int_assessments__state_nj_scores`

**Files:**

- Modify:
  `W/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_nj_scores.sql`
  (3 sites: last column of the Pearson branch, last column of the Cambium
  branch, after `u._dbt_source_project,` in the final select)
- Modify:
  `W/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__state_nj_scores.yml`
  (column entry after `_dbt_source_project`; new `unit_tests:` block at the end
  of the file)

**Interfaces:**

- Consumes: kipptaf `int_cambium__all_assessments.student_growth_percentile`
  (INT64; present in prod and `zz_stg_kipptaf_cambium`).
- Produces: `int_assessments__state_nj_scores.student_growth_percentile` (INT64,
  null on Pearson rows). The future SGP `rpt_` reads it.

- [ ] **Step 1: Install packages.**
      `uv run dbt deps --project-dir W/src/dbt/kipptaf`, in its own call.
      Expected: `Installed` / `Up to date`.

- [ ] **Step 2: Write the failing unit test.** Append to the properties yml:

  ```yaml
  unit_tests:
    - name: test_int_assessments__state_nj_scores_student_growth_percentile
      description: >-
        Cambium SGP passes through the union and survives the crosswalk join;
        Pearson rows carry a null SGP.
      model: int_assessments__state_nj_scores
      given:
        - input: ref('int_pearson__all_assessments')
          rows:
            - { studenttestuuid: p1, localstudentidentifier: 100 }
        - input: ref('int_cambium__all_assessments')
          rows:
            - {
                student_test_uuid: c1,
                student_number: 200,
                student_growth_percentile: 57,
              }
            - {
                student_test_uuid: c2,
                student_number: null,
                student_growth_percentile: 12,
              }
        - input: ref('stg_google_sheets__pearson__student_crosswalk')
          rows:
            - { student_test_uuid: c2, student_number: 300 }
      expect:
        rows:
          - {
              student_test_uuid: p1,
              student_number: 100,
              student_growth_percentile: null,
            }
          - {
              student_test_uuid: c1,
              student_number: 200,
              student_growth_percentile: 57,
            }
          - {
              student_test_uuid: c2,
              student_number: 300,
              student_growth_percentile: 12,
            }
  ```

- [ ] **Step 3: Run it and watch it fail.**
      `uv run dbt test --select "int_assessments__state_nj_scores,test_type:unit" <dev flags>`.
      Expected: FAIL, because the model has no `student_growth_percentile`
      column.

- [ ] **Step 4: Add the column.**
  - Pearson branch, after `_dbt_source_project,`:
    `cast(null as int64) as student_growth_percentile,`
  - Cambium branch, after `_dbt_source_project,`: `student_growth_percentile,`
  - Final select, after `u._dbt_source_project,`: `u.student_growth_percentile,`
  - YAML column entry: `data_type: int64`, `contains_pii: true`, description
    "Student growth percentile, 1 to 99, from Cambium; see stg_cambium__njsla
    for which tests carry one. NULL on every Pearson row: the Pearson files had
    no SGP."

- [ ] **Step 5: Run the unit test and watch it pass.** Same command as Step 3.
      Expected: PASS.

- [ ] **Step 6: Build the model.**
      `uv run dbt build --select int_assessments__state_nj_scores <dev flags>`.
      Expected: PASS for the model, its data tests, and the unit test.

- [ ] **Step 7: Reconcile with the BigQuery MCP** (dev schema
      `zz_anthonygwalters_kipptaf_assessments`):
  - row count equals prod
    `kipptaf_assessments.int_assessments__state_nj_scores`;
  - non-null SGP rows equal the non-null SGP rows in prod
    `kipptaf_cambium.int_cambium__all_assessments`;
  - 0 non-null SGP rows where `_dbt_source_relation` names a pearson relation.

- [ ] **Step 8: Lint.** With cwd `W`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the 2 changed files> docs/superpowers/plans/2026-11-23-cambium-sgp-pr2.md </dev/null 2>&1 | tail -n 20`.
      Fix findings; formatting is the commit hook's job.

- [ ] **Step 9: Commit.** `git -C W add -u` plus the new plan file, then
      `feat(dbt): carry student_growth_percentile into int_assessments__state_nj_scores`
      with `Refs #6279` and the Co-Authored-By line.

### After the task

Final whole-branch review, then push and open the PR with `Refs #6279`. The PR
notes that CI reads the kipptaf wrapper from `zz_stg_kipptaf_cambium`, which
already has the column. If CI fails on a missing column, stop and ask before any
`zz_stg_*` write.
