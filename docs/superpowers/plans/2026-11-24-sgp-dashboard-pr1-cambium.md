# SGP dashboard, PR 1 (cambium package) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage Cambium's `economic_disadvantage_status` and `nj_ml_status` in
the cambium package and carry both through `int_cambium__all_assessments`, so
kipptaf can build the SGP dashboard's student groups from the state file.

**Architecture:** 2 plain string columns added to `stg_cambium__njsla` and
`stg_cambium__njgpa` (both raw files carry them), passed through every branch of
`int_cambium__all_assessments`. No derivation here; PR 2 derives the booleans in
kipptaf. The kipptaf union wrappers pick the columns up after the district prod
rebuild.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, local dev builds through the
consuming districts `kippnewark`, `kippcamden`, `kipppaterson`.

**Spec:** `docs/superpowers/specs/2026-11-24-sgp-dashboard-design.md` (_Pull
request 1_). Same pattern as `docs/superpowers/plans/2026-11-05-cambium-sgp.md`.

## Global Constraints

- Worktree root `W` =
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-sgp-dashboard`.
  Every path and `--project-dir` is absolute under `W`; every git call is
  `git -C W`. Never edit `/workspaces/teamster/src/...`.
- Column names exactly `economic_disadvantage_status` and `nj_ml_status`,
  `data_type: string`, `config.meta.contains_pii: true` in every properties file
  that lists them.
- Values are passed through unchanged. Do not touch `multilingual_learner`,
  `lep_status`, or `aligned_ml_status` (#6481 owns those).
- Staging tests set `config: severity` explicitly.
- Every dbt command is `uv run dbt ...`. `--target dev` only; no
  `--target staging` or `--target prod` writes in this PR.
- `--state` is absolute: `/workspaces/teamster/src/dbt/<district>/target/prod`.
- No PII values in commits or the PR body: aggregates only.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The PR body ends
  with `🤖 Generated with [Claude Code](https://claude.com/claude-code)` and
  says `Refs #6279`, never `Closes`.

## Review Focus

1. A code Cambium adds later (for example `F5`) must not break the NJSLA build,
   which carries ELA, math, and Science together. The `accepted_values` tests
   are `warn`; Task 1 runs them against current data and expects a pass.
2. The NJGPA branch compiles only in Newark and Camden; Paterson disables
   `stg_cambium__njgpa`. Task 3 builds both paths.
3. The column add must not change the intermediate's row count. Task 4 compares
   dev and prod per district.
4. Both columns must reach the intermediate on every row that has them. Task 4
   reconciles non-null counts per `test_code` between staging and the
   intermediate.
5. A blank in the source stays blank (null), never an empty string. Task 4
   counts empty strings and expects 0.

---

### Task 1: both columns in `stg_cambium__njsla`

**Files:**

- Modify: `W/src/dbt/cambium/models/staging/stg_cambium__njsla.sql` (the `njsla`
  CTE's plain-column group, lines 14–31, alphabetical:
  `economic_disadvantage_status` after `black_or_african_american`,
  `nj_ml_status` after `native_hawaiian_or_other_pacific_islander`)
- Modify: `W/src/dbt/cambium/models/staging/properties/stg_cambium__njsla.yml`
  (2 column entries, inside the tested-columns block at the top since both carry
  tests)

**Interfaces:**

- Produces: `stg_cambium__njsla.economic_disadvantage_status` and
  `stg_cambium__njsla.nj_ml_status` (STRING, nullable). Task 3 reads them by
  name.

- [ ] **Step 1: Set up the worktree's dbt projects.** For each of `kippnewark`,
      `kippcamden`, `kipppaterson`, in its own Bash call:
      `uv run dbt deps --project-dir W/src/dbt/<district>`. Then re-stage your
      personal source copy, one district per call (serial; parallel runs hit a
      BigQuery quota):
      `uv run dbt run-operation stage_external_sources --args "select: cambium.src_cambium__njsla" --vars '{ext_full_refresh: true}' --target dev --project-dir W/src/dbt/<district>`.
      Expected: each run logs the external as created or replaced.

- [ ] **Step 2: Write the failing contract.** Add 2 yml entries:

  - `economic_disadvantage_status`: `data_type: string`, `contains_pii: true`,
    `accepted_values` `['Y', 'N']` with `config: {severity: warn}`, description:
    `Economic disadvantage status from the state file, Y or N. Blank where the state file has none.`
  - `nj_ml_status`: `data_type: string`, `contains_pii: true`, `accepted_values`
    `['Y', 'F1', 'F2', 'F3', 'F4']` with `config: {severity: warn}`,
    description:
    `NJDOE multilingual learner status from the state file. Y is a current learner; F1 to F4 is a former learner in their first to fourth year after exit. Blank for every other student.`

  Each test's description names Cambium as the source and says a new code needs
  a decision in `int_assessments__state_nj_scores` (kipptaf).

- [ ] **Step 3: Run the build and watch it fail.**
      `uv run dbt build --select stg_cambium__njsla --project-dir W/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 30`
      Expected: FAIL, contract error naming the 2 columns as missing.

- [ ] **Step 4: Add the 2 plain columns** at the positions under Files.

- [ ] **Step 5: Run the build and watch it pass.** Same command as Step 3.
      Expected: PASS, both `accepted_values` tests pass with 0 rows.

- [ ] **Step 6: Commit.** `git -C W add -u` then a commit
      `feat(dbt): stage economic disadvantage and NJ ML status from Cambium NJSLA`
      with `Refs #6279` and the Co-Authored-By line.

### Task 2: both columns in `stg_cambium__njgpa`

**Files:**

- Modify: `W/src/dbt/cambium/models/staging/stg_cambium__njgpa.sql` (its
  plain-column group, same alphabetical rule as Task 1)
- Modify: `W/src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml`
  (same 2 entries and tests as Task 1, with "NJGPA" for "the state file")

**Interfaces:**

- Produces: `stg_cambium__njgpa.economic_disadvantage_status`,
  `stg_cambium__njgpa.nj_ml_status` (STRING, nullable). Task 3 reads them.

- [ ] **Step 1: Re-stage the NJGPA source** in Newark and Camden only (Paterson
      disables it), one call each:
      `uv run dbt run-operation stage_external_sources --args "select: cambium.src_cambium__njgpa" --vars '{ext_full_refresh: true}' --target dev --project-dir W/src/dbt/<district>`.

- [ ] **Step 2: Write the failing contract** (the 2 yml entries).

- [ ] **Step 3: Run the build and watch it fail.** The Task 1 Step 3 command
      with `--select stg_cambium__njgpa`. Expected: FAIL, contract error naming
      both columns.

- [ ] **Step 4: Add the 2 plain columns.**

- [ ] **Step 5: Run the build and watch it pass.** Expected: PASS, both
      `accepted_values` tests pass.

- [ ] **Step 6: Commit**
      `feat(dbt): stage economic disadvantage and NJ ML status from Cambium NJGPA`
      with `Refs #6279` and the Co-Authored-By line.

### Task 3: carry both columns through `int_cambium__all_assessments`

**Files:**

- Modify:
  `W/src/dbt/cambium/models/intermediate/int_cambium__all_assessments.sql` at 4
  sites, each in the plain-column group beside `multilingual_learner` (line
  numbers before any edit): `njsla_aligned` (~108), `njgpa_aligned` (~222), the
  `aligned` loop's select list (~317), and the final select (~416)
- Modify:
  `W/src/dbt/cambium/models/intermediate/properties/int_cambium__all_assessments.yml`
  (2 entries beside `multilingual_learner`)

**Interfaces:**

- Consumes: the 4 staging columns from Tasks 1 and 2.
- Produces: `int_cambium__all_assessments.economic_disadvantage_status` and
  `.nj_ml_status` (STRING, nullable), on NJSLA and NJGPA rows alike. PR 2 reads
  them through the kipptaf union wrapper by those names.

- [ ] **Step 1: Write the failing contract.** 2 yml entries,
      `data_type: string`, `contains_pii: true`, descriptions
      `Economic disadvantage status (Y or N) as reported by Cambium.` and
      `NJDOE multilingual learner status (Y, or F1 to F4 for former learners) as reported by Cambium.`
      No tests (staging owns the values).

- [ ] **Step 2: Run the build and watch it fail.**
      `uv run dbt build --select stg_cambium__njsla stg_cambium__njgpa int_cambium__all_assessments --project-dir W/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 30`
      Expected: FAIL, contract error on `int_cambium__all_assessments`.

- [ ] **Step 3: Add both columns at the 4 SQL sites.**

- [ ] **Step 4: Run the Newark build and watch it pass.** Same command as
      Step 2. Expected: PASS for all 3 models and their tests.

- [ ] **Step 5: Run the Paterson build.**
      `--select stg_cambium__njsla int_cambium__all_assessments` with
      `kipppaterson` in `--project-dir` and `--state`. Expected: PASS. Paterson
      compiles without the NJGPA branch.

- [ ] **Step 6: Commit**
      `feat(dbt): carry economic disadvantage and NJ ML status through int_cambium__all_assessments`
      with `Refs #6279` and the Co-Authored-By line.

### Task 4: verify in all 3 districts and open PR 1

**Files:** none changed, unless lint finds something.

- [ ] **Step 1: Build Camden.** The Task 3 Step 2 command with `kippcamden`.
      Expected: PASS.

- [ ] **Step 2: Reconcile, per district** (`d` in `kippnewark`, `kippcamden`,
      `kipppaterson`), with the BigQuery MCP (`projectId: teamster-332318`):

  - Row count of `zz_anthonygwalters_<d>_cambium.int_cambium__all_assessments`
    equals prod `<d>_cambium.int_cambium__all_assessments`, queried in the same
    minute.
  - Per `test_code`, non-null counts of each new column in the dev intermediate
    equal those in the dev staging models where `test_status = 'completed'`.
  - `countif(economic_disadvantage_status = '' or nj_ml_status = '')` is 0.
  - For 2025-26 NJSLA rows, `nj_ml_status` in `F1`–`F4` count is about 244
    across the 3 districts (the raw count from the spec); report the exact
    number.

- [ ] **Step 3: Lint.** With cwd `W`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the 6 changed files> docs/superpowers/plans/2026-11-24-sgp-dashboard-pr1-cambium.md </dev/null 2>&1 | tail -n 30`.
      Fix any lint finding (formatting is the commit hook's job). Commit fixes
      with `git -C W add -u`.

- [ ] **Step 4: Push.** `git -C W push`.

- [ ] **Step 5: Open the PR.** Body from `W/.github/pull_request_template.md`,
      following `W/.github/PLAIN_LANGUAGE.md`. Title
      `feat(dbt): stage economic disadvantage and NJ ML status from Cambium`.
      Base `main`. The body must:

  - say `Refs #6279` and that the branch also carries the SGP dashboard design
    and plans;
  - list the local builds and the Step 2 results (counts only);
  - say in Reviewer Notes that dbt Cloud CI builds kipptaf only, so the local
    district builds are this PR's verification, and that the `accepted_values`
    tests are `warn` so a new Cambium code cannot stop the NJSLA build.

  Read the created PR back and confirm the title and body match.

After merge: PR 2 (`2026-11-24-sgp-dashboard-pr2-kipptaf.md`) waits for the
Dagster prod rebuild of `int_cambium__all_assessments` in all 3 districts.
