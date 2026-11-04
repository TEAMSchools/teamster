# Focus Apex: sync and staging design

Issue: [#5828](https://github.com/TEAMSchools/teamster/issues/5828). Reporting
on top of this data stays in
[#5821](https://github.com/TEAMSchools/teamster/issues/5821).

## Context

Miami gives its interim assessments in Apex, the assessment module inside Focus.
Apex has no usable report by section, grade, or school, and its staff exports
carry no assessment name or id. #5821 planned an intake built on those exports.

A probe on 2026-10-09 showed the exports are unnecessary. It ran from a pod in
the GKE cluster with the `op-focus-db-kippmiami` secret, so it used the same
database, user, and egress IP as the Focus dlt pipeline. It found:

- 131 `apex_*` tables in `kippfl_focus` (121 in `public`, 10 in `audit`), all
  readable by `kippfl_dataeng`. The server is the primary
  (`pg_is_in_recovery() = false`).
- None of them is in
  `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`.

The measurements behind this design are in the findings comment on #5821.

## Goal

Land 13 Apex tables in `dagster_kippmiami_dlt_focus` on the existing probe-gated
intraday sync, and give each a contract-enforced staging model in the `focus`
dbt package.

Out of scope: kipptaf models, intermediate models, any reporting output, and the
rules Miami still has to settle (denominator, retakes, mastery cutoff
confirmation).

## Tables

All 13 use `cursor_column: updated_at`. The probe found no null `updated_at` in
any of them.

| Table                                  | Role                                          | Rows (2026-10-09) |
| -------------------------------------- | --------------------------------------------- | ----------------- |
| `apex_assessments`                     | Assessment title, year, status                | 148               |
| `apex_assigned_assessments`            | Assignment: school, dates, audience           | 143               |
| `apex_assignment_students`             | Students rostered to an assignment            | 18,487            |
| `apex_sessions`                        | One student attempt: overall score, status    | 9,889             |
| `apex_session_responses`               | One question in an attempt: score             | 823,459 (264 MB)  |
| `apex_assessment_items`                | Items on an assessment                        | 2,711             |
| `apex_item_questions`                  | Questions in an item                          | 3,730             |
| `apex_questions`                       | Question type, DOK, Bloom's                   | 3,795             |
| `apex_question_standards`              | Question to Focus standard                    | 1,880             |
| `apex_band_sets`                       | Mastery band set                              | 5                 |
| `apex_band_levels`                     | Band level label and cut scores               | 28                |
| `apex_band_set_assessments`            | Band set assigned to an assessment            | 76                |
| `apex_assignment_gradebook_assignment` | Apex assignment to Focus gradebook assignment | 23                |

## Design

### Sync (PR 1)

Add the 13 entries to `focus.yaml`. Nothing else in the sync changes: the
intraday sensor probes every configured table every 15 minutes, and its first
tick after deploy finds no stored signature for the new tables and loads all 13.

Update the "79 tables" counts to 92 in `libraries/dlt/focus/CLAUDE.md`,
`code_locations/kippmiami/CLAUDE.md`, and the comments in
`code_locations/kippmiami/dlt/focus/schedules.py`.

**Known ceiling.** `apex_session_responses` is already about 2x the largest
Focus table we sync (`gradebook_assignments_join_course_periods`, 434k rows) and
grows all year. During test windows it changes on most ticks, and every change
is a full `replace`. The `dlt_focus_kippmiami` pool allows 1 run at a time, so a
slow reload delays every other Focus table, including the snapshot the 13:15
Finalsite-to-Focus delivery anti-joins against. Step-pod memory is not the
worry: peak memory scales with `FOCUS_CHUNK_SIZE` and extract workers, not table
size.

**Fallback (option B), if the ceiling is hit.** Add a per-table
`intraday: false` key to `focus.yaml`, default true. `dlt/focus/sensors.py`
passes the sensor only the intraday tables; `dlt/focus/schedules.py` adds the
flagged tables to the 04:00 target and raises its `dagster/max_runtime` from 900
to 1800. No library change is needed: the library sensor only probes the tables
it is handed. The step after that is incremental merge loads for
`apex_session_responses`, a new load mode for the library.

### Staging (PR 2)

One model per table: `src/dbt/focus/models/staging/stg_focus__apex_<table>.sql`,
a `sources-bigquery.yml` entry, and a properties file declaring every projected
column with a `data_type`. Built in `kippmiami`, the only consumer of the
package.

**Soft delete.** Apex uses a BOOL `deleted`, not the Focus `1`/NULL convention.
Filter `where deleted is not true` and drop `deleted` and `deleted_at` on
`apex_assessments`, `apex_assigned_assessments`, `apex_questions`,
`apex_band_sets`, and `apex_band_levels`. The probe found no scored response on
a deleted question and no session on a deleted assessment, so the filter drops
no results.

**Not filtered.** `apex_sessions.discarded`, `excused`, and `pending_rescore`
stay as columns. They are scoring decisions that reporting makes, not deletes.

**Dropped columns.**

| Column(s)                                                             | Why                                        |
| --------------------------------------------------------------------- | ------------------------------------------ |
| `_dlt_id`, `_dlt_load_id`, `created_by_*`, `updated_by_*`             | Package convention                         |
| `apex_session_responses.response`, `.feedback`                        | Student and teacher free text              |
| `apex_sessions.instructor_note`, `discarded_reason`, `excused_reason` | Free text about a student                  |
| `apex_assessments.password`                                           | Credential                                 |
| `apex_questions.stimulus`                                             | Question text; reporting does not use it   |
| `apex_sessions.tool_state_json`, `responses_json`                     | UI state; `responses_json` is always empty |

**Types.**

- Unbounded Postgres `numeric` lands as BIGNUMERIC through
  `widen_unbounded_numeric_adapter`. Cast scores, percent, points, and band
  `min_score`/`max_score` to `numeric` in staging.
- `interval` (`apex_sessions.elapsed_time`, the `time_limit` and
  `retake_elapse_time` columns) lands as INT64 microseconds through
  `interval_to_microseconds_adapter`. Keep the name and type.
- `audience_config` stays JSON.

**PII.** Column-level `config.meta.contains_pii: true`, tiers 1 to 3 of
`.claude/rules/ferpa-pii.md` (scope confirmed with the user):

- `student_id` on `apex_sessions` and `apex_assignment_students`. Focus
  `student_id` is the `8400`-prefixed student number, a direct identifier.
- Student-level score and status columns: `apex_sessions` (scores, `percent`,
  `passed`, `completed`, `graded`, `excused`, `discarded`, `pending_rescore` and
  the other per-attempt flags) and `apex_session_responses` (`score_actual`,
  `score_max`, `needs_grading`).

**Tests.** `unique` and `not_null` on `id` at `severity: error`. `not_null` at
`error` on the foreign keys every row must carry (`apex_sessions.assessment_id`,
`assignment_id`, `student_id`; `apex_session_responses.session_id`,
`question_id`; the join tables' two sides). No `relationships` tests: each table
loads in its own resource seconds apart, so cross-table orphans appear on
teacher activity (`src/dbt/focus/CLAUDE.md`).

## Rollout

Two PRs, both `Refs #5828`:

1. **PR 1, sync.** `focus.yaml` plus the count fixes.
2. **PR 2, staging.** Opened after PR 1's tables land in prod.

Do not seed the tables from a PR 1 branch deployment. Branch dlt runs write to
the prod dataset and the prod `_dlt_pipeline_state`, and the pool limit does not
span deployments, so a branch run can race a prod sensor run on that state row.
dbt Cloud CI does not build `focus` package models, so a single PR gains no CI
coverage.

## Verification

After PR 1 lands:

- All 13 tables exist with row counts near the probe's.
- Landed types: `deleted` BOOL, unbounded numerics BIGNUMERIC, intervals INT64,
  `audience_config` JSON. These decide the staging casts and filters.
- Focus intraday run durations for the first school days after merge, compared
  with the week before (Dagster run history for
  `kippmiami__dlt__focus__intraday_sensor`). A clear rise, or a step pod killed
  for memory, triggers the fallback.

Before PR 2 opens:

- `uv run dbt build --select stg_focus__apex_*` in `kippmiami` passes contracts
  and tests.
- From staging, the probe's two measurements come within a few points:
  - Standards coverage: 89.1% of scored responses (`score_actual is not null`)
    in completed, non-discarded sessions have a row in
    `stg_focus__apex_question_standards`.
  - Score reconciliation: in 94% of completed, non-discarded sessions, summed
    response `score_actual` and `score_max` equal the session's.
- `trunk check --force` passes on the new SQL and YAML.

## Facts for the reporting design (#5821)

Recorded here so the reporting spec does not re-probe:

- `apex_sessions.assignment_id` references `apex_assigned_assessments.id` (9,889
  of 9,889 match on assessment and roster). Its id space overlaps
  `apex_assignment_students.id`; a bare id match there is meaningless.
- `apex_session_responses.question_id` references `apex_questions.id`. About 83%
  of rows are blank placeholders (null score and null answer) or belong to
  in-progress sessions.
- 254 completed sessions have no response rows, nearly all imported scores in
  `Math - G1 - PET 1`, `Math - GK - PET 1`, and `Math - GK - QA1`: overall score
  only.
- 201 completed sessions do not reconcile; 91 are `pending_rescore`, 84 differ
  only in maximum points, about 60 are in `Math - G7 - PET2`. Use the session
  score for the overall result.
- 7 assessments carry no standards: 4 PSAT modules, `Civics - G7 - PET1`, 1
  Wonders selection test, 1 G6 science topic test. 4% of scored responses carry
  more than 1 standard.
- Band sets: PETs, MQQs, TPQs, EOCs, and K-4 QAs use Level 1-5 with Level 3 at
  70-79; 6-12 FAST QAs use an 8-level set with Level 3 at 75-79.
- `audience_config` is a JSON array of `{grouper, ids}` with groupers `school`,
  `grade_level`, `teacher`, `student`. No section grouper; derive section from
  `schedule` on the session date.
- Apex tags carry Bloom's levels and skills, no category. Subject and grade come
  from titles (`Subject - Grade - Type N - 2026 - 2027 FL`) plus a crosswalk for
  exceptions.
- About half of scored questions were edited after students tested. Only current
  standard links exist in `public`; the `audit` schema keeps history.
