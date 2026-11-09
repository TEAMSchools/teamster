# Cambium SGP, PR 1 (cambium package) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Cambium's `studentgrowthpercentile` as
`student_growth_percentile` (int64) in the cambium package's
`stg_cambium__njsla` and `int_cambium__all_assessments`.

**Architecture:** One cast in staging, a pass-through in the package
intermediate (null on the NJGPA branch), contract YAML for both. The kipptaf
union wrappers pick the column up after the district prod rebuild; PR 2 (a later
session) carries it into `int_assessments__state_nj_scores`.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, local dev builds through the
consuming districts `kippnewark`, `kippcamden`, `kipppaterson`.

**Spec:** `docs/superpowers/specs/2026-11-05-cambium-sgp-design.md`

## Global Constraints

- Worktree root `W` =
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-cambium-sgp`.
  Every path and `--project-dir` is absolute under `W`; every git call is
  `git -C W`. Never edit `/workspaces/teamster/src/...`.
- Column name `student_growth_percentile`, `data_type: int64`,
  `config.meta.contains_pii: true` in both properties files.
- Staging uses plain `cast(... as int)`, not `safe_cast` (spec, _Design_).
- Staging tests set `config: severity: error` explicitly.
- Every dbt command is `uv run dbt ...`. `--target dev` only; no
  `--target staging` or `--target prod` writes in this PR.
- `--state` is absolute: `/workspaces/teamster/src/dbt/<district>/target/prod`.
- No PII values in commits or the PR body: aggregates only.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The PR body ends
  with `🤖 Generated with [Claude Code](https://claude.com/claude-code)` and
  says `Refs #6279`, never `Closes`.

## Review Focus

1. A non-numeric or blank SGP in a future file fails `stg_cambium__njsla`, which
   carries ELA, Math, and Science together. Deliberate (loud over silent); the
   PR's Reviewer Notes must say so.
2. A value outside 1 to 99 fails the staging range test. Task 1 runs the test
   against current data and expects a pass.
3. The NJGPA branch compiles only in Newark and Camden; Paterson's var omits
   `stg_cambium__njgpa`. Task 2 builds both paths.
4. The column add must not change the intermediate's row count. Task 3 compares
   the dev and prod row counts per district.
5. SGP must reach the intermediate on every completed NJSLA row that has it.
   Task 3 reconciles non-null counts per `test_code` between staging and the
   intermediate.

---

### Task 1: `student_growth_percentile` in `stg_cambium__njsla`

**Files:**

- Modify: `W/src/dbt/cambium/models/staging/properties/stg_cambium__njsla.yml`
  (new column entry after `subject`, inside the tested-columns block)
- Modify: `W/src/dbt/cambium/models/staging/stg_cambium__njsla.sql:35` (new line
  after `state_student_identifier`)

**Interfaces:**

- Produces: column `student_growth_percentile` (INT64, nullable) on
  `stg_cambium__njsla`. Task 2 reads it by that name.

- [ ] **Step 1: Set up the worktree's dbt projects.** For each of `kippnewark`,
      `kippcamden`, `kipppaterson`, in its own Bash call:
      `uv run dbt deps --project-dir W/src/dbt/<district>`. Then re-stage your
      personal source copy, one district per call (serial; parallel runs hit a
      BigQuery quota):
      `uv run dbt run-operation stage_external_sources --args "select: cambium.src_cambium__njsla" --vars '{ext_full_refresh: true}' --target dev --project-dir W/src/dbt/<district>`.
      Expected: each run logs the external as created or replaced. The NJGPA
      source needs no re-stage: `--favor-state` resolves the unselected
      `stg_cambium__njgpa` to prod.

- [ ] **Step 2: Write the failing contract.** Add the column entry to the yml:
      `name: student_growth_percentile`, `data_type: int64`,
      `config.meta.contains_pii: true`, a `dbt_utils.accepted_range` test with
      `arguments: {min_value: 1, max_value: 99}` and
      `config: {severity: error}`, and this description:

      Student growth percentile, 1 to 99. Compares the student's score with
      students statewide who had similar prior scores. Null where Cambium
      reports none, including grade 3, Science and the end-of-course tests.

- [ ] **Step 3: Run the build and watch it fail.**
      `uv run dbt build --select stg_cambium__njsla --project-dir W/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 30`
      Expected: FAIL, contract error naming `student_growth_percentile` as
      missing from the model.

- [ ] **Step 4: Add the cast.** In the int-cast group of the `njsla` CTE, after
      `state_student_identifier`:
      `cast(studentgrowthpercentile as int) as student_growth_percentile,`

- [ ] **Step 5: Run the build and watch it pass.** Same command as Step 3.
      Expected: PASS, including
      `dbt_utils_accepted_range_..._student_growth_percentile`.

- [ ] **Step 6: Commit.** `git -C W add -u` then
      `git -C W commit -m "feat(dbt): add student_growth_percentile to stg_cambium__njsla" -m "Refs #6279" -m "<Co-Authored-By line>"`

### Task 2: carry the column through `int_cambium__all_assessments`

**Files:**

- Modify:
  `W/src/dbt/cambium/models/intermediate/properties/int_cambium__all_assessments.yml`
  (new column entry after `student_test_uuid`)
- Modify:
  `W/src/dbt/cambium/models/intermediate/int_cambium__all_assessments.sql` at 4
  sites (line numbers are before any edit):
  - `njsla_aligned`: plain column after `student_test_uuid,` (line 110)
  - `njgpa_aligned`: `cast(null as int64) as student_growth_percentile,` after
    `cast(null as boolean) as is_bl_fb,` (line 243), keeping the casts ahead of
    the `if()` calls (sqlfluff ST06)
  - the `aligned` loop's select list: after `student_test_uuid,` (line 331)
  - the final select: after `student_test_uuid,` (line 435)

**Interfaces:**

- Consumes: `stg_cambium__njsla.student_growth_percentile` (Task 1).
- Produces: `int_cambium__all_assessments.student_growth_percentile` (INT64,
  nullable, always null on NJGPA rows). PR 2 reads it through the kipptaf union
  wrapper by that name.

- [ ] **Step 1: Write the failing contract.** Add the yml entry:
      `data_type: int64`, `config.meta.contains_pii: true`, description
      `Student growth percentile from stg_cambium__njsla. NULL on NJGPA, which carries none.`
      No test (the staging range test owns the values).

- [ ] **Step 2: Run the build and watch it fail.**
      `uv run dbt build --select stg_cambium__njsla int_cambium__all_assessments --project-dir W/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 30`
      Expected: FAIL, contract error on `int_cambium__all_assessments` naming
      the missing column.

- [ ] **Step 3: Add the column at the 4 SQL sites listed under Files.**

- [ ] **Step 4: Run the Newark build and watch it pass.** Same command as
      Step 2. Expected: PASS for both models and all their tests. Newark
      compiles the NJGPA branch.

- [ ] **Step 5: Run the Paterson build.** Same command with `kipppaterson` in
      `--project-dir` and `--state`. Expected: PASS. Paterson compiles without
      the NJGPA branch.

- [ ] **Step 6: Commit.** `git -C W add -u` then a commit
      `feat(dbt): carry student_growth_percentile through int_cambium__all_assessments`
      with `Refs #6279` and the Co-Authored-By line.

### Task 3: verify in all 3 districts and open PR 1

**Files:** none changed, unless lint finds something.

- [ ] **Step 1: Build Camden.** The Task 2 Step 2 command with `kippcamden`.
      Expected: PASS.

- [ ] **Step 2: Reconcile, per district** (`d` in `kippnewark`, `kippcamden`,
      `kipppaterson`), with the BigQuery MCP (`projectId: teamster-332318`):
  - Row count: `count(*)` from
    `zz_anthonygwalters_<d>_cambium.int_cambium__all_assessments` equals
    `count(*)` from `<d>_cambium.int_cambium__all_assessments` (prod), queried
    in the same minute. A mismatch means investigate before going on.
  - Non-null SGP per `test_code` in the dev intermediate equals the non-null SGP
    per `test_code` in the dev staging model `where test_status = 'completed'`.
  - Non-null SGP appears only on `ELA04`–`ELA08` and `MAT04`–`MAT07`, and never
    on an `assessment_name = 'NJGPA'` row.

- [ ] **Step 3: Lint.** With cwd `W`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the 4 changed files> docs/superpowers/plans/2026-11-05-cambium-sgp.md </dev/null 2>&1 | tail -n 30`.
      Fix any lint finding (formatting is the commit hook's job). Commit fixes
      with `git -C W add -u`.

- [ ] **Step 4: Push.** `git -C W push`.

- [ ] **Step 5: Open the PR.** Body from `W/.github/pull_request_template.md`,
      following `W/.github/PLAIN_LANGUAGE.md`. Title
      `feat(dbt): add Cambium student growth percentile to the cambium package`.
      Base `main`. The body must:
  - say `Refs #6279`;
  - list the local builds and the Step 2 reconciliation results (counts only);
  - say in Reviewer Notes that dbt Cloud CI builds kipptaf only, so the local
    district builds are this PR's verification;
  - flag Review Focus item 1 (plain `cast` fails loudly on a bad value).

  Read the created PR back and confirm the title and body match.
