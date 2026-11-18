# Alchemer Archive Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frozen Alchemer survey tables once with a real `round_rn`,
a resolved 2022 family student, and the rated person, then archive them again.

**Architecture:** Revive `int_surveys__alchemer_submissions` and
`int_surveys__alchemer_responses` (archive pattern in reverse), add one pivot
CTE over the frozen `base_alchemer__survey_results` answers, rank in the model,
pad the live union, have the user rebuild in prod, then re-archive.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** `docs/superpowers/specs/2026-10-26-alchemer-archive-rebuild-design.md`

Worktree:
`/workspaces/teamster/.claude/worktrees/cbini/feat/claude-alchemer-archive-rebuild`
(below, `<wt>`). Every git call uses `git -C <wt>`; every dbt call uses
`uv run dbt ... --project-dir <wt>/src/dbt/kipptaf`. Invoke `dbt-local-dev`
before the first dbt build. Run
`uv run dbt deps --project-dir <wt>/src/dbt/kipptaf` once, in its own call,
first.

## Global Constraints

- New columns on `int_surveys__alchemer_submissions`:
  `respondent_student_number` (INT64, `contains_pii: true`) and
  `subject_employee_number` (INT64).
- `round_rn`: `row_number()` partitioned by
  `survey_id, academic_year, term_code, rank_respondent, subject_employee_number`,
  ordered by `date_submitted desc, survey_response_id desc`.
- `rank_respondent` =
  `coalesce(cast(respondent_student_number as string), respondent_identifier, survey_response_id)`.
  The last fallback makes a submission with no identity rank alone.
- 2022 family survey is Alchemer survey `6829997`, question `student_number`.
  Prefix `8400` only when the submission has a non-null, non-blank answer to any
  question whose shortname starts `miami_`. Answers not matching `^\d{5,6}$`
  resolve to null.
- Rated person is the `subject_df_employee_number` answer, `safe_cast` to INT64.
- Archive arm: `subject_employee_number` from
  `int_surveys__manager_survey_details.subject_df_employee_number`;
  `round_rn = 1` (its response id already encodes respondent, subject, term).
- `--target prod` builds go to the user. `--target dev` builds need no
  authorization.
- GitHub (commits, PR body, comments) gets counts only, never row values.

## Review Focus

- A Self and Others respondent who rated 5 colleagues once each: all 5 rows must
  keep `round_rn = 1`. Covered by Task 2 Step 4 check (a).
- A 2022 family submission with a student number but empty `miami_*` answers:
  must resolve as typed, not prefixed. Covered by Task 2 Step 4 check (c).
- A family submission with no student number and no email: must get
  `round_rn = 1` on its own. Covered by Task 2 Step 4 check (d).
- Two submissions with identical `date_submitted`: exactly one gets 1. Covered
  by the uniqueness test in Task 2 Step 1.
- The live union keeps its column order after the pad, so no two same-typed
  columns swap. Covered by Task 3 Step 3.

---

### Task 1: Revive the archived models

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__alchemer_submissions.yml`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__alchemer_responses.yml`
- Modify: `src/dbt/kipptaf/models/surveys/sources-bigquery.yml`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_submissions.sql:115`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql:62`

**Interfaces:**

- Produces: both models enabled; live models read them by `ref()`.

- [ ] **Step 1:** Remove `enabled: false` from both models' `config:` and from
      their `data_tests` configs.
- [ ] **Step 2:** In `sources-bigquery.yml`, add `config: enabled: false` to the
      `int_surveys__alchemer_submissions` and `int_surveys__alchemer_responses`
      tables. Model and source share a Dagster asset key, so both cannot be
      enabled.
- [ ] **Step 3:** Swap `source("surveys", "int_surveys__alchemer_submissions")`
      and `source("surveys", "int_surveys__alchemer_responses")` to `ref(...)`
      in the two live models.
- [ ] **Step 4:** Run
      `uv run dbt parse --no-partial-parse --project-dir     <wt>/src/dbt/kipptaf 2>&1 | tail -n 20`.
      Expected: no errors, no duplicate-node error.
- [ ] **Step 5:** Commit:
      `refactor(surveys): revive the Alchemer archive     models for a rebuild`
      with `Refs #6125`.

### Task 2: Rank and resolve in `int_surveys__alchemer_submissions`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__alchemer_submissions.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__alchemer_submissions.yml`

**Interfaces:**

- Consumes: Task 1.
- Produces: columns `respondent_student_number` (INT64),
  `subject_employee_number` (INT64), and a real `round_rn` (INT64), in that
  position after `round_rn`'s current slot:
  `..., survey_response_link, round_rn, respondent_student_number, subject_employee_number, respondent_identifier, survey_submission_key`.

- [ ] **Step 1: Write the test.** Add a model-level
      `dbt_utils.unique_combination_of_columns` on
      `survey_id, academic_year,     term_code, rank_respondent, subject_employee_number`
      with `config: where: round_rn = 1, severity: error`. Expose
      `rank_respondent` only if the test cannot take the expression; otherwise
      pass the `coalesce(...)` from Global Constraints as the column entry. Add
      a `not_null` on `round_rn` with `severity: error`.
- [ ] **Step 2: Run it against the old frozen data to see it fail.** Run the
      test SQL's equivalent read-only through BigQuery MCP against
      `kipptaf_surveys.int_surveys__alchemer_submissions`. Expected: `round_rn`
      has nulls (archive arm) and duplicate partitions exist.
- [ ] **Step 3: Implement.**
  - New CTE `alchemer_answers` over
    `source("alchemer", "base_alchemer__survey_results")`, grouped by
    `survey_id, response_id`: the `subject_df_employee_number` answer, the
    `student_number` answer, and `logical_or` of a non-blank `miami_*` answer.
  - Join it into `api_submissions` on survey and response id; derive
    `respondent_student_number` per Global Constraints (only for survey
    `6829997`; null elsewhere) and `subject_employee_number`.
  - Archive arm: add `subject_df_employee_number` to `archive_source` and select
    it as `subject_employee_number`; `1 as round_rn`; null student.
  - Rank after the union in a `submissions_ranked` CTE (window over the union,
    per the ranked-column note in `.claude/rules/dbt-sql.md`). Comment the
    `8400` literal (S20): Miami's PowerSchool-to-Focus student number prefix.
  - Declare `standard_exempt: {A5: ...}` only if `dbt-layer-check` flags the
    `row_number()`; it is not filtered to 1 here, so it should not.
- [ ] **Step 4: Build to dev and check.**
      `uv run dbt build --select     int_surveys__alchemer_submissions --target dev --defer --state <prod     manifest> --project-dir <wt>/src/dbt/kipptaf 2>&1 | tail -n 30`.
      Expected: model and both tests pass. Then query the dev table:
  - (a) Self and Others rows with `round_rn > 1`: about 807. Alchemer Manager
    Survey (API arm): about 24. Archive arm: 0. Those baselines grouped by
    email; `rank_respondent` uses employee number first, so a small gap is
    expected. Report the actual counts and explain any gap over 5%.
  - (b) Row count equals the frozen table's (53,224) and no `survey_response_id`
    is gained or lost.
  - (c) Survey `6829997`: 2,002 non-null `respondent_student_number`, of which
    810 start with `8400`.
  - (d) Every submission whose `rank_respondent` fell back to
    `survey_response_id` has `round_rn = 1`.
- [ ] **Step 5:** Update the yml: model description (drop "built once on
      2026-09-15"; say it is rebuilt only to change frozen rows), `round_rn`
      description (the rank rule), and descriptions for the 2 new columns;
      `contains_pii: true` on `respondent_student_number`.
- [ ] **Step 6:** Commit:
      `feat(surveys): rank Alchemer submissions and     resolve 2022 family students`
      with `Refs #6125`.

### Task 3: Pad the live union

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_submissions.sql:70-117`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_submissions.yml`

**Interfaces:**

- Consumes: Task 2's column order.
- Produces: `int_surveys__survey_submissions` carries
  `respondent_student_number` and `subject_employee_number` (null on Google
  Forms until #5978).

- [ ] **Step 1:** In the Google Forms branch, add
      `cast(null as int64) as respondent_student_number` and
      `cast(null as int64) as subject_employee_number` after `round_rn`. In the
      Alchemer branch, select both by name in the same slot.
- [ ] **Step 2:** Update the yml: `round_rn` description (Alchemer now ranked
      per respondent, rated person, and term; no longer "Always 1" or null on
      the archive), plus descriptions for the 2 new columns, the student one
      tagged `contains_pii: true`.
- [ ] **Step 3: Check.**
      `uv run dbt build --select     int_surveys__alchemer_submissions int_surveys__alchemer_responses     int_surveys__survey_submissions int_surveys__survey_responses --target dev     --defer --state <prod manifest> --project-dir <wt>/src/dbt/kipptaf 2>&1 |     tail -n 30`.
      Expected: all pass, `survey_submission_key` unique. Query: Alchemer rows
      in dev `int_surveys__survey_submissions` have the same `survey_title`,
      `date_submitted`, and `respondent_identifier` as dev
      `int_surveys__alchemer_submissions` (0 mismatches), proving no positional
      swap.
- [ ] **Step 4:** Grep consumers that `select *` from
      `int_surveys__survey_submissions` under a contract:
      `rg -n "int_surveys__survey_submissions" <wt>/src/dbt/kipptaf/models`.
      Expected: none select `*`; if one does, add the 2 columns to its contract
      yml.
- [ ] **Step 5:** Lint:
      `/workspaces/teamster/.trunk/tools/trunk check --force     --no-fix <changed sql and yml> </dev/null`
      from `<wt>`. Fix findings.
- [ ] **Step 6:** Commit:
      `feat(surveys): carry the Alchemer student and rated     person through the live submissions model`
      with `Refs #6125`. Push. Open the PR as a draft from
      `.github/pull_request_template.md` with `Closes #6125`.

### Task 4: Prod rebuild and comparison

**Interfaces:**

- Consumes: Tasks 1-3 pushed.

- [ ] **Step 1:** Hand the user, in plain text:
      `uv run dbt build --select int_surveys__alchemer_submissions     int_surveys__alchemer_responses --target prod --project-dir     /workspaces/teamster/.claude/worktrees/cbini/feat/claude-alchemer-archive-rebuild/src/dbt/kipptaf`.
      Wait for their confirmation.
- [ ] **Step 2:** Rerun the design doc's drift comparison against the new prod
      table, and the Task 2 Step 4 checks against prod. Expected: same counts as
      dev; drift limited to the 46 accepted rows plus the new columns.
- [ ] **Step 3:** Post the comparison on the PR as counts only.

### Task 5: Re-archive

**Files:** the five files from Task 1.

- [ ] **Step 1:** Set `enabled: false` again on both models and their tests;
      remove `enabled: false` from the two source tables; swap the live models
      back to `source()`.
- [ ] **Step 2:**
      `uv run dbt parse --no-partial-parse --project-dir     <wt>/src/dbt/kipptaf 2>&1 | tail -n 20`.
      Expected: clean. Then compile `int_surveys__survey_submissions` and
      confirm the Alchemer branch reads
      `kipptaf_surveys.int_surveys__alchemer_submissions`.
- [ ] **Step 3:** Commit:
      `refactor(surveys): archive the rebuilt Alchemer     tables as sources`
      with `Refs #6125`. Push. Mark the PR ready.
