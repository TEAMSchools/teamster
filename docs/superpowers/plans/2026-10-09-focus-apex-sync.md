# Focus Apex Sync and Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 13 Focus `apex_*` tables on the existing Focus dlt intraday sync
and give each a contract-enforced `stg_focus__apex_*` model.

**Architecture:** PR 1 adds config entries to the probe-gated Focus dlt asset;
the intraday sensor loads the new tables on its first tick after deploy. PR 2,
opened only after the tables exist in prod, adds staging models in the `focus`
dbt package, built in `kippmiami`.

**Tech Stack:** Dagster + dlt (`src/teamster/libraries/dlt/focus/`), dbt on
BigQuery (`src/dbt/focus/`), trunk.

**Spec:** `docs/superpowers/specs/2026-10-09-focus-apex-sync-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/feat/claude-focus-apex-sync`,
  branch `cbini/feat/claude-focus-apex-sync`, issue #5828. Every git call is
  `git -C <worktree>`; every path is absolute under the worktree.
- PR 2 needs its own branch, created from `origin/main` after PR 1 merges,
  linked with
  `gh issue develop 5828 --name cbini/feat/claude-focus-apex-staging` and its
  own worktree.
- Every PR body carries `Refs #5828`.
- The 13 tables, all `cursor_column: updated_at`: `apex_assessments`,
  `apex_assigned_assessments`, `apex_assignment_students`, `apex_sessions`,
  `apex_session_responses`, `apex_assessment_items`, `apex_item_questions`,
  `apex_questions`, `apex_question_standards`, `apex_band_sets`,
  `apex_band_levels`, `apex_band_set_assessments`,
  `apex_assignment_gradebook_assignment`.
- No Python changes in PR 1. If the post-merge check (Task 2) trips, the
  fallback is the spec's option B, as a separate change.
- Never seed the tables from a branch deployment (spec, _Rollout_).
- Staging drops: `_dlt_id`, `_dlt_load_id`, `created_by_class`, `created_by_id`,
  `updated_by_class`, `updated_by_id`; `apex_session_responses.response`,
  `.feedback`; `apex_sessions.instructor_note`, `discarded_reason`,
  `excused_reason`, `tool_state_json`, `responses_json`;
  `apex_assessments.password`; `apex_questions.stimulus`.
- Soft delete `where deleted is not true`, dropping `deleted` and `deleted_at`,
  on exactly: `apex_assessments`, `apex_assigned_assessments`, `apex_questions`,
  `apex_band_sets`, `apex_band_levels`.
- `discarded`, `excused`, `pending_rescore` on `apex_sessions` are kept, not
  filtered.
- Cast every BIGNUMERIC column to `numeric`. Interval columns stay INT64
  microseconds. `audience_config` stays JSON.
- PII: column-level `config.meta.contains_pii: true` on `student_id` and on
  every student-level score or status column of `apex_sessions`,
  `apex_assignment_students`, and `apex_session_responses`.
- Tests: `unique` + `not_null` on `id` at `severity: error`; `not_null` at
  `error` on required foreign keys; no `relationships` tests.
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd in the worktree.
- PII never goes into commits, PR bodies, or comments: counts and column names
  only.

## Review Focus

1. **`deleted` landing as NULL instead of false.** `where deleted is not true`
   keeps NULL rows by design; Task 3 checks the landed null count so a NULL that
   means "deleted" in Apex would surface.
2. **BIGNUMERIC values that do not fit `numeric`** (scale above 9 or more than
   29 integer digits). The cast rounds or errors. Task 3 checks max scale and
   magnitude of every BIGNUMERIC column before the casts are written.
3. **`audience_config` and the Postgres `time` columns landing as STRING**
   instead of JSON and TIME. Task 3 records landed types; the staging contract
   uses what landed, not what the spec assumed.
4. **The first post-deploy tick loading all 13 tables at once**, including
   `apex_session_responses`. Task 2 inspects that specific run's duration and
   step-pod status.
5. **Intraday Focus run time creeping up over the year**, delaying the 13:15
   delivery's snapshot. Task 2 records the baseline the spec's fallback trigger
   compares against.

---

## PR 1: sync

### Task 1: Add the Apex tables to the Focus sync

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`
  (append after the `test_history_*` block)
- Modify: `src/teamster/libraries/dlt/focus/CLAUDE.md:118-143`
- Modify: `src/teamster/code_locations/kippmiami/CLAUDE.md:70-77`
- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py:36,52`

**Interfaces:**

- Produces: 13 assets `kippmiami/dlt/focus/apex_*`, each landing a table of the
  same name in `dagster_kippmiami_dlt_focus`. Task 3 onward reads these.

- [ ] **Step 1: Append the 13 entries** under a `# Apex` comment, in the order
      of the Global Constraints list, each `table_name: <name>` plus
      `cursor_column: updated_at`.

- [ ] **Step 2: Replace the hard-coded table counts.** This departs from the
      spec's "79 to 92": `.claude/rules/comments.md` says to point at the file
      that owns a value, and a number drifts with the next table. Wording: "all
      79" becomes "every table in `config/focus.yaml`"; "the other 78" becomes
      "every other table"; in `schedules.py:52`, "(100s of rows, not 79)"
      becomes "(the count-only tables, not the whole config)". Bring each edited
      comment block up to `.claude/rules/comments.md`.

- [ ] **Step 3: Check the config parses and the sensor sees the new tables**

  Run:
  `cd <worktree> && uv run pytest tests/libraries/test_dlt_focus_sensors.py tests/libraries/test_dlt_focus_kippmiami_schedule_wiring.py -q 2>&1 | tail -n 5`
  Expected: all pass. Then
  `uv run python -c "import yaml; a = yaml.safe_load(open('src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml'))['assets']; print(len(a), sum(x['table_name'].startswith('apex_') for x in a))"`
  prints `92 13`.

- [ ] **Step 4: Lint and commit**

  Lint the four files. Commit `feat(focus): sync Apex assessment tables` with
  `Refs #5828`.

### Task 2: Open PR 1, then verify the landing

**Files:** none.

- [ ] **Step 1: Record the baseline before merge.** With
      `mcp__dagster-plus__list_runs` filtered to sensor
      `kippmiami__dlt__focus__intraday_sensor` over the last 7 days, record p50
      and max run duration for school-day runs (07:00-16:00 ET). Put the numbers
      in the PR body's _For Claude_ fold-out.

- [ ] **Step 2: Push and open the PR** from `.github/pull_request_template.md`,
      `Refs #5828`. Then follow `pr-ci-review`: watch CI and process
      `claude-review` findings. The user merges.

- [ ] **Step 3: After merge, confirm the first load.** Within about 30 minutes
      of the deploy, find the first sensor run selecting `apex_*` assets.
      Expected: SUCCESS, all 13 materialized. Record its duration and whether
      any step pod restarted.

- [ ] **Step 4: Confirm the tables landed**

  Query `dagster_kippmiami_dlt_focus.__TABLES__` for `table_id like 'apex%'`.
  Expected: 13 rows, row counts within a few percent of the spec's table.

- [ ] **Step 5: Compare durations after the first 3 school days.** Same query as
      Step 1. A clear rise in p50 or max, or any OOM-killed step pod, is the
      spec's trigger for option B: report it to the user instead of starting
      PR 2.

---

## PR 2: staging

Start only after Task 2, Step 4 passes. Create the PR 2 branch and worktree
(Global Constraints), then run
`uv run dbt deps --project-dir <worktree>/src/dbt/kippmiami` in its own call.
Invoke `dbt-local-dev` before the first build.

### Task 3: Profile the landed schema

**Files:** none. Output: a column table in the PR 2 body's _For Claude_
fold-out, which Tasks 4-6 use as their column source.

**Interfaces:**

- Produces: for each of the 13 tables, its landed columns and BigQuery types
  from `INFORMATION_SCHEMA.COLUMNS`, minus the Global Constraints drops.

- [ ] **Step 1: List landed columns and types** for `table_name like 'apex%'`.
      Record which columns are BIGNUMERIC, INT64 intervals (`elapsed_time`,
      `time_limit`, `retake_elapse_time`), JSON, TIME, and BOOL `deleted`.

- [ ] **Step 2: Check `deleted` nulls** on the 5 soft-delete tables:
      `countif(deleted is null)`. Expected 0. If not 0, stop and ask the user
      whether NULL means live.

- [ ] **Step 3: Check BIGNUMERIC fit.** For every BIGNUMERIC column, count rows
      where `cast(col as numeric) != col` (use `safe_cast` so overflow returns
      null and is counted). Expected 0. If not 0, keep that column BIGNUMERIC
      and note why in its description.

### Task 4: Stage the assessment structure

**Files:**

- Modify: `src/dbt/focus/models/staging/sources-bigquery.yml` (add all 13 Apex
  tables under an `# Apex` comment, same `config.meta.dagster.asset_key` shape
  as `test_history_scores`)
- Create, each with `properties/<model>.yml`: `stg_focus__apex_assessments`,
  `stg_focus__apex_assigned_assessments`, `stg_focus__apex_assessment_items`,
  `stg_focus__apex_item_questions`, `stg_focus__apex_questions`,
  `stg_focus__apex_question_standards`,
  `stg_focus__apex_assignment_gradebook_assignment`

**Interfaces:**

- Consumes: Task 3 column table.
- Produces: the 7 models above. No student-level columns, so no PII tags.

- [ ] **Step 1: Write the SQL** for each model: explicit column list from Task
      3, `cast(<col> as numeric) as <col>` for BIGNUMERIC, soft-delete filter on
      `apex_assessments`, `apex_assigned_assessments`, `apex_questions`. Follow
      `.claude/rules/dbt-sql.md` (S6 and S7 ordering) and
      `stg_focus__test_history_scores.sql` as the shape.

- [ ] **Step 2: Write the properties files.** Every column with `data_type` and
      a description. Tests: `unique` + `not_null` on `id`; `not_null` on
      `assessment_id` (`apex_assigned_assessments`, `apex_assessment_items`),
      `item_id` (`apex_assessment_items`, `apex_item_questions`), `question_id`
      (`apex_item_questions`, `apex_question_standards`), `standard_id`
      (`apex_question_standards`), `apex_assignment_id` and
      `gradebook_assignment_id` (`apex_assignment_gradebook_assignment`).
      Describe `audience_config` as a JSON array of `{grouper, ids}` targets
      (`school`, `grade_level`, `teacher`, `student`).

- [ ] **Step 3: Build**

  Run:
  `uv run dbt build --select stg_focus__apex_assessments stg_focus__apex_assigned_assessments stg_focus__apex_assessment_items stg_focus__apex_item_questions stg_focus__apex_questions stg_focus__apex_question_standards stg_focus__apex_assignment_gradebook_assignment --project-dir <worktree>/src/dbt/kippmiami 2>&1 | tail -n 20`
  Expected: 7 models OK, all tests PASS.

- [ ] **Step 4: Check the soft-delete filter.** Row count of each filtered model
      equals `countif(deleted is not true)` on its source. Lint and commit
      `feat(focus): stage Apex assessment structure tables`.

### Task 5: Stage the mastery bands

**Files:**

- Create, each with `properties/<model>.yml`: `stg_focus__apex_band_sets`,
  `stg_focus__apex_band_levels`, `stg_focus__apex_band_set_assessments`

**Interfaces:**

- Consumes: Task 3 column table; Task 4's source entries.
- Produces: the 3 models. `stg_focus__apex_band_levels.min_score` and
  `max_score` are `numeric`.

- [ ] **Step 1: Write SQL and properties.** Soft delete on band sets and band
      levels. Tests: PK as above; `not_null` on `band_set_id`
      (`apex_band_levels`, `apex_band_set_assessments`) and `assessment_id`
      (`apex_band_set_assessments`).

- [ ] **Step 2: Build** the 3 models as in Task 4, Step 3. Expected: 3 OK.

- [ ] **Step 3: Check the bands.** `stg_focus__apex_band_levels` holds 4 live
      sets: 3 with 5 levels and Level 3 at `min_score = 70`, and 1 with 8 levels
      and Level 3 at 75 (spec, _Facts for the reporting design_). Lint and
      commit `feat(focus): stage Apex mastery band tables`.

### Task 6: Stage the student-level tables

**Files:**

- Create, each with `properties/<model>.yml`:
  `stg_focus__apex_assignment_students`, `stg_focus__apex_sessions`,
  `stg_focus__apex_session_responses`

**Interfaces:**

- Consumes: Task 3 column table; Task 4's source entries.
- Produces: the 3 models; `stg_focus__apex_sessions.assignment_id` references
  `stg_focus__apex_assigned_assessments.id` (state this in its description).

- [ ] **Step 1: Write SQL** with the Global Constraints drops; no row filters.

- [ ] **Step 2: Write properties** with PII tags on `student_id` and every score
      and status column (`score_actual`, `score_max`, `percent`, `passed`,
      `completed`, `completed_at`, `graded`, `released`, `discarded`, `excused`,
      `pending_rescore`, `score_locked`, `attempts`, `elapsed_time`,
      `is_observational` on sessions; `score_actual`, `score_max`,
      `needs_grading` on responses; the per-student schedule and retake columns
      on assignment students). Tests: PK as above; `not_null` on
      `assessment_id`, `assignment_id`, `student_id` (sessions and assignment
      students) and `session_id`, `question_id` (responses). Describe the blank
      placeholder rows on responses and how to filter them.

- [ ] **Step 3: Build** the 3 models. Expected: 3 OK, tests PASS.

- [ ] **Step 4: Check no free text leaked.** `INFORMATION_SCHEMA.COLUMNS` on the
      dev relations contains none of `response`, `feedback`, `instructor_note`,
      `discarded_reason`, `excused_reason`. Lint and commit
      `feat(focus): stage Apex session and roster tables`.

### Task 7: Reproduce the probe measurements and open PR 2

**Files:** none.

- [ ] **Step 1: Standards coverage from dev staging.** Scored responses
      (`score_actual is not null`) in completed, non-discarded sessions, with a
      row in `stg_focus__apex_question_standards`. Expected: within a few points
      of 89.1%.

- [ ] **Step 2: Score reconciliation from dev staging.** Completed,
      non-discarded sessions whose summed response `score_actual` and
      `score_max` equal the session's, within 0.01. Expected: within a few
      points of 94%.

- [ ] **Step 3: Open PR 2** from the template, `Refs #5828`, with both numbers
      and the Task 3 table in the fold-out (counts and column names only).
      Follow `pr-ci-review`.
