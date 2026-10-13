# Apex Assessment Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Miami Apex (Focus) results flow through the shared assessment
pipeline, so they appear wherever Illuminate results do, with no change to NJ
numbers.

**Architecture:** 2 source `int_` models in the `focus` package (built in
`kippmiami`) do all Apex-only logic: latest session, overall and per-standard
scores, bands, and mastery. kipptaf reads them through `sources-kippmiami.yml`
plus `union_relations` passthroughs. A `source` column (`illuminate` / `apex`)
joins every assessment key in the kipptaf intermediates, which first get
conformed column names. Apex rows then enter members → canonical → scaffold →
rollup as a parallel branch, and every downstream consumer picks them up.

**Tech Stack:** dbt (BigQuery), dbt unit tests, BigQuery MCP for verification,
AppSheet, Google Sheets exposure.

**Spec:** `docs/superpowers/specs/2026-10-13-apex-assessment-results-design.md`

## Global Constraints

- Every NJ row in every changed model is identical before and after (count +
  key-plus-value fingerprint against prod). Illuminate surrogate keys in the
  marts do not move.
- `source` values are exactly `'illuminate'` and `'apex'`. The marts carry it as
  `assessment_type` (`'illuminate'` / `'apex'`), not as a `source` column.
- The key for any assessment is (`source`, `assessment_id`); for a canonical
  group, (`source`, `canonical_assessment_id`). No join on either id alone.
- Mastery: labels `Level 3`, `Level 4`, `Level 5` → true; `Level 1`, `Level 2`,
  `Low 1`, `Low 2`, `Mid 1`, `High 1`, `High 2` → false; any other label, or no
  band set → null. Never apply the `is_default` band set.
- `performance_band_label_number` = 1..N by `min_score` within the band set.
- Ignore `stg_focus__apex_sessions.passed`.
- Session pick: latest `completed_at` among
  `completed and not discarded and not excused` sessions on non-deleted
  assignments, per student × assessment.
- Overall: `score_actual` / `score_max` of the picked session. Standard: sum of
  responses with `score_actual is not null`, per standard (a response tagged to
  2 standards counts for both). `percent_correct` 0–100, rounded to 1 place as
  in the rollup.
- Apex branch filters `academic_year >= 2026` (Focus `syear`).
- Apex `student_id` = `student_number`.
- Rename map (scope in the spec): `powerschool_student_number` →
  `student_number`; `illuminate_subject_area` → `subject_area`;
  `illuminate_grade_level_id` → `grade_level_id`; `illuminate_academic_year` →
  `academic_year`; rollup/scaffold grain `illuminate_student_id` → `source` +
  `student_number` (Illuminate id kept as a nullable passthrough). `rpt_`, mart,
  and Cube output column names never change.
- Never run warehouse DDL/DML. Draft it; the user runs it.
- Student-level Apex models: `contains_pii: true` (model level on passthroughs,
  column level on package models: `student_number`, scores, dates taken).
- Run `uv run dbt ...` only; `--project-dir` an absolute worktree path.

## Review Focus

1. **Band set id collision.** The rollup's final join to
   `int_illuminate__performance_band_sets` on `performance_band_set_id` would
   give Apex rows Illuminate bands where ids overlap. Apex rows must take band
   fields from `int_focus__apex_results` only (test in Task 7).
2. **Canonical id collision.** 12 Apex ids equal Illuminate ids, so a canonical
   join on `canonical_assessment_id` alone merges them in
   `assessments_canonical`, `score_anchors`, `resolved_section_enrollments`, and
   the fact (test in Task 5).
3. **Ambiguous sections.** A student in 2 core sections of a subject on the test
   date gets null section with `section_match_method = 'multiple'`, not an
   arbitrary pick (test in Task 6).
4. **Untagged Apex assessment.** No AppSheet row → null module/scope; it must
   still reach the rollup and the assessment dashboard, and not break
   `regions_assessed_array` unnests (test in Task 6).
5. **Mixed-subject assessment.** Standards from 2 subject categories → null
   `subject_area`, not a fan-out (test in Task 1).

---

## PR 1 — Pipeline (Tasks 1–9)

Single PR with the cross-project staging workflow (`src/dbt/kipptaf/CLAUDE.md` →
_Single-PR cross-project workflow_).

### Task 1: `int_focus__apex_assessments` (package)

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__apex_assessments.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__apex_assessments.yml`
- Modify: `src/dbt/focus/models/intermediate/unit_tests.yml`

**Interfaces:**

- Produces, 1 row per `assessment_id`: `assessment_id` int64, `title`,
  `academic_year` int64 (= `syear`), `band_set_id` int64 (null if none live),
  `subject_area` string, `administered_at` date.

- [ ] **Step 1: Write unit tests** in `unit_tests.yml`:
  - `test_int_focus__apex_assessments_subject`: standards only in category
    `Mathematics (B.E.S.T.)(Focus)` → `'Mathematics'`; only
    `Language Arts (B.E.S.T.)(Focus)` → `'Text Study'`;
    `Science (Florida SC)(Focus)` → `'Science'`;
    `Social Studies (Florida SS)(Focus)` → `'Social Studies'`; 1 Math + 1
    Science standard → null; no standards → null.
  - `test_int_focus__apex_assessments_band_set`: band set row whose
    `stg_focus__apex_band_sets` parent is missing → `band_set_id` null.
  - `test_int_focus__apex_assessments_administered_at`: 2 assigned rows with
    `start_date` 2026-09-15 and 2026-09-08 → `2026-09-08`.
- [ ] **Step 2: Run**
      `uv run dbt test --select int_focus__apex_assessments --project-dir <wt>/src/dbt/kippmiami`
      → FAIL (model missing).
- [ ] **Step 3: Implement.** Subject: map category_1 title by prefix
      (`Language Arts` → `Text Study`, `Mathematics`, `Science`,
      `Social Studies`) over the assessment's questions' standards; null unless
      exactly 1 distinct mapped subject. `administered_at` = min `start_date` of
      its assigned assessments (my call per spec _Left to the builder_). Band
      set: live `band_set_assessments` joined to `band_sets` and
      `apex_assessments`. Properties: `unique` + `not_null` on `assessment_id`
      (severity error).
- [ ] **Step 4: Run** the same command → PASS, then
      `uv run dbt build --select int_focus__apex_assessments` (kippmiami, dev).
- [ ] **Step 5: Commit** `feat(focus): add int_focus__apex_assessments`.

### Task 2: `int_focus__apex_results` (package)

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__apex_results.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__apex_results.yml`
- Modify: `src/dbt/focus/models/intermediate/unit_tests.yml`

**Interfaces:**

- Consumes: `int_focus__apex_assessments.band_set_id`.
- Produces, 1 row per (`student_number`, `assessment_id`, `response_type`,
  `response_type_id`): `student_number` int64, `assessment_id` int64,
  `session_id` int64, `date_taken` date (`completed_at`, local tz),
  `response_type` (`'overall'` / `'standard'`), `response_type_id` int64
  (assessment id for overall, standard id for standard), `response_type_code`
  (`short_name`), `response_type_description` (`title`),
  `response_type_root_description` (category_1 title), `points` numeric,
  `points_possible` numeric, `percent_correct` float64,
  `performance_band_set_id` int64, `performance_band_label` string,
  `performance_band_label_number` int64, `is_mastery` bool.

- [ ] **Step 1: Write unit tests:**
  - `test_int_focus__apex_results_session_pick`: 3 sessions for 1 student ×
    assessment — completed 09-10, completed 09-12 but `discarded`, completed
    09-11 → picks the 09-11 session; a session on a deleted assignment is
    ignored.
  - `test_int_focus__apex_results_overall_uses_session_score`: session
    `score_actual` 6 / `score_max` 10, responses summing to 7 → overall
    `percent_correct` 60.0.
  - `test_int_focus__apex_results_standard_rollup`: responses (2/2 std A), (0/2
    std A and B), (null score std B) → A 50.0, B 0.0 over 2 possible.
  - `test_int_focus__apex_results_bands`: band set with levels `Level 1`
    0–39.99, `Level 2` 40–59.99, `Level 3` 60–100: overall 60.0 → `Level 3`,
    number 3, mastery true; standard 50.0 → `Level 2`, mastery false; a level
    labelled `Advanced` matched → mastery null; assessment with no band set →
    label, number, mastery all null.
- [ ] **Step 2: Run** `uv run dbt test --select int_focus__apex_results` → FAIL.
- [ ] **Step 3: Implement** per Global Constraints. Band match:
      `percent_correct between min_score and max_score`. Filter
      `academic_year >= 2026` here. Properties: grain test
      `dbt_utils.unique_combination_of_columns` on the 4 key columns; column
      `contains_pii` on `student_number`, scores, `date_taken`.
- [ ] **Step 4: Run** tests → PASS; build in dev. The school-level known answer
      is checked in Task 7.
- [ ] **Step 5: Commit** `feat(focus): add int_focus__apex_results`.

### Task 3: kipptaf sources and passthroughs

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__apex_assessments.sql`
  and `int_focus__apex_results.sql`, plus `properties/*.yml`

**Interfaces:**

- Produces: kipptaf `ref("int_focus__apex_assessments")`,
  `ref("int_focus__apex_results")` with Task 1/2 columns plus
  `_dbt_source_project`.

- [ ] **Step 1:** Add both tables to `sources-kippmiami.yml` (copy the
      `int_focus__courses` entry shape). Passthroughs copy
      `int_focus__courses.sql`. Properties: model-level `contains_pii: true` on
      results; no uniqueness test (lives on the package model).
- [ ] **Step 2:** Seed staging:
      `uv run dbt build --select int_focus__apex_assessments int_focus__apex_results --target staging --project-dir <wt>/src/dbt/kippmiami`
      (writes `zz_stg_kippmiami_focus`; ask the user first — shared relations),
      then
      `uv run dbt compile --select int_focus__apex_results --target staging --project-dir <wt>/src/dbt/kipptaf`
      and confirm the compiled SQL lists columns.
- [ ] **Step 3: Commit** `feat(kipptaf): expose apex results from kippmiami`.

### Task 4: Conformed column names (NJ-neutral refactor)

**Files:** the 6 intermediates in
`src/dbt/kipptaf/models/assessments/intermediate/` and their properties,
`int_assessments__score_anchors`, and every model that references a renamed
column
(`rg -l 'powerschool_student_number|illuminate_subject_area|illuminate_grade_level_id|illuminate_academic_year|illuminate_student_id' --glob '*.{sql,yml,md}' src/dbt/kipptaf`,
~47 SQL files). Out-of-scope models alias at the join (spec _Conformed names_).

**Interfaces:**

- Produces, on rollup and scaffold: `student_number`, `subject_area`,
  `grade_level_id`, `illuminate_student_id` (nullable passthrough). On
  course_enrollments: `student_number`, `subject_area`, `grade_level_id`,
  `academic_year`. On resolved_section_enrollments and score_anchors:
  `student_number`. Members/canonical: `illuminate_grade_level_id` →
  `tagged_grade_level_id` (it is the AppSheet value; `grade_level_id` already
  exists there). The AppSheet staging model keeps its column names; members
  aliases at the join. `rpt_appsheet__assessments` keeps its output names.

- [ ] **Step 1:** Rename. Rollup/scaffold window partitions and grain tests swap
      `illuminate_student_id` for `student_number` (1:1 in prod rollup, checked
      2026-10-13; re-check on the scaffold with a `count(distinct)` query and
      stop if not 1:1).
- [ ] **Step 2:**
      `uv run dbt build --select <changed models>+ --exclude rpt_tableau__miami_fast`
      in dev (defer per `dbt-local-dev`), tail 30.
- [ ] **Step 3: Verify NJ-neutral:** for each changed `int_` and every `rpt_` /
      mart downstream, `count(*)` and
      `bit_xor(farm_fingerprint(to_json_string(t)))` over the output with
      renamed columns aliased back, dev vs prod → equal. Record the table in the
      PR body.
- [ ] **Step 4:** `trunk check --force --no-fix` on changed files; commit
      `refactor(assessments): conform assessment intermediate column names`.

### Task 5: `source` key column (still NJ-neutral)

**Files:** members, canonical, scaffold, score_anchors,
resolved_section_enrollments, rollup (+ properties); `dim_assessments`,
`dim_assessment_administrations`, the 3 `bridge_assessment_*`, fact; rollup
consumers that join on `assessment_id` / `canonical_assessment_id`
(`rpt_deanslist__mod_*`, `rpt_gsheets__deanslist_mod_audit`,
`int_assessments__college_assessment_practice`).

**Interfaces:**

- Produces: `source` string on every model above at assessment or
  student-assessment grain. Every uniqueness test on `assessment_id` /
  `canonical_assessment_id` gains `source`. Marts: `'illuminate'` literals that
  are hashed or emitted as `assessment_type` become the row's `source`.
- Members join to AppSheet stays Illuminate-only until Task 10 (the table has no
  `source` column yet).

- [ ] **Step 1: Write a singular test**
      `src/dbt/kipptaf/tests/assessments/test_assessments_no_cross_source_canonical.sql`:
      returns every `int_assessments__assessments_members` row whose (`source`,
      `canonical_assessment_id`) has no member row with the same (`source`,
      `assessment_id`), i.e. a canonical pick from another source. Expected: 0
      rows now and after Task 6.
- [ ] **Step 2:** Add `'illuminate' as source` at the Illuminate entry points
      (members, scaffold branches) and carry it through; add `source` to every
      join, partition (`canonical_w` in members), dedup key, and grain test
      listed.
- [ ] **Step 3:** Rebuild and repeat Task 4 Step 3 fingerprints (excluding the
      new column) → equal; mart surrogate keys equal prod row-for-row.
- [ ] **Step 4:** Commit `refactor(assessments): key assessments on source`.

### Task 6: Apex rows into members, canonical, and scaffold

**Files:** members, canonical, scaffold (+ properties).

**Interfaces:**

- Consumes: Task 3 passthroughs.
- Produces: members rows with `source = 'apex'`,
  `is_internal_assessment = true`, `is_florida_assessment = true`,
  `academic_year` and `academic_year_clean` set to the values a 2026-27 NJ
  Illuminate member carries (query one; the two differ by an offset), own
  canonical group (the `source` partition does this). Scaffold Apex branch: 1
  row per tested student × Apex assessment, `region = 'Miami'`,
  `_dbt_source_project = 'kippmiami'`, `is_replacement = false`,
  `student_assessment_id` = `session_id`, `date_taken`, section fields
  (`cc_dcid`, `cc_source_project`, `discipline`, `powerschool_school_id`,
  `grade_level_id`) from the match below, and new `section_match_method`
  (`'single'`, `'none'`, `'multiple'`; null on Illuminate rows).
- Section match: `int_assessments__course_enrollments` rows for the student with
  `_dbt_source_project = 'kippmiami'`, `subject_area` = assessment subject,
  `cc_dcid is not null`, `cc_dateenrolled <= date_taken < cc_dateleft`. Exactly
  1 → take it; else null section fields. School and grade fall back to
  `int_extracts__student_enrollments` on the test date when no single section
  matches.

- [ ] **Step 1: Unit tests** on the scaffold: student with 1 matching Math
      section → `'single'` with its `cc_dcid`; 2 → `'multiple'`, null `cc_dcid`,
      school still set; 0 → `'none'`; untagged Apex assessment (no AppSheet row)
      still yields scaffold rows.
- [ ] **Step 2:** Run → FAIL. **Step 3:** implement. **Step 4:** run → PASS;
      Task 5 singular test → 0 rows; NJ fingerprints unchanged.
- [ ] **Step 5:** Commit `feat(assessments): add apex assessments and scaffold`.

### Task 7: Apex rows into the rollup

**Files:** `int_assessments__response_rollup.sql` (+ properties).

**Interfaces:**

- Consumes: scaffold Apex rows; `int_focus__apex_results`.
- Produces: rollup rows with `source = 'apex'`, `n_assessments = 1`,
  `is_multipart_assessment = false`, `assessment_ids = [assessment_id]`, band
  columns from `int_focus__apex_results`, terms as today; plus passthrough
  `cc_dcid`, `section_match_method`.

- [ ] **Step 1: Unit test** `test_int_assessments__response_rollup_apex_bands`:
      Apex row with `performance_band_set_id = 5` and an Illuminate band set 5
      fixture covering its percent → band label/mastery come from the Apex
      fixture, not Illuminate's.
- [ ] **Step 2:** Run → FAIL. **Step 3:** implement as a third `response_union`
      branch joined on (`student_number`, `assessment_id`); the `pbl` join adds
      `ru.source = 'illuminate'` and band columns coalesce per source with
      `if(source = 'apex', ...)`. **Step 4:** PASS.
- [ ] **Step 5:** Known answer from rollup:
      `Math - G3 - PET 1 - 2026 - 2027 FL`, `response_type = 'overall'`, school
      KIPP Royalty Academy → 130 rows, 60 with `is_mastery`. Every Apex row with
      non-null `is_mastery` has non-null `performance_band_set_id` (0
      violations). Commit `feat(assessments): roll up apex results`.

### Task 8: Consumers

**Files:** `rpt_tableau__assessment_dashboard`, `rpt_tableau__ddi_dashboard`,
`rpt_gsheets__deanslist_mod_audit`,
`int_assessments__college_assessment_practice`, `dim_assessments`,
`dim_assessment_administrations`, Cube `student_assessment_scores` (read only —
confirm no change needed).

- [ ] **Step 1:** Both dashboards: keep the PowerSchool join for
      `source = 'illuminate'`; add a second left join to
      `base_powerschool__course_enrollments` on `cc_dcid` +
      `_dbt_source_project` for `source = 'apex'`, and coalesce the section and
      teacher columns. Output columns unchanged.
- [ ] **Step 2:** Mod audit builds its Illuminate URL only when
      `source = 'illuminate'`. College practice filters `source = 'illuminate'`.
- [ ] **Step 3:** Build `int_assessments__response_rollup+` (exclude
      `rpt_tableau__miami_fast`); NJ fingerprints on every `rpt_`/mart equal
      prod; Apex rows present in the fact with `assessment_type = 'apex'` in the
      dims; no Apex row matches an Illuminate row on any consumer join (query:
      join each consumer's Apex rows to Illuminate members on `assessment_id`
      without `source` → confirm the consumer output carries 0 such pairs).
- [ ] **Step 4:** Commit `feat(assessments): surface apex in consumers`.

### Task 9: Ship PR 1

- [ ] **Step 1:** `trunk check --force --no-fix` on all changed files.
- [ ] **Step 2:** Push; open the PR (template). Body says plainly: Miami numbers
      are not valid until Apex assessments are tagged in AppSheet; include the
      NJ fingerprint table and the known answer. `Closes #5830` only if PR 2 and
      3 land on this branch; otherwise `Refs #5830` and use a no-issue branch
      (the linked branch closes the issue on merge).
- [ ] **Step 3:** Watch CI and process `claude-review` (CLAUDE.local.md).

## PR 2 — AppSheet (Task 10)

### Task 10: Source column in AppSheet

**Files:** `stg_google_appsheet__illuminate_assessments_extension` (+ yml),
`rpt_appsheet__assessments` (+ yml), members, `rpt_deanslist__mod_assessment`,
`rpt_deanslist__mod_standards_domains`, `rpt_gsheets__deanslist_mod_audit`.

- [ ] **Step 1:** Hand the user this DDL to run, and wait for confirmation:

```sql
alter table `teamster-332318.kipptaf_appsheet.illuminate_assessments_extension`
add column source string;

update `teamster-332318.kipptaf_appsheet.illuminate_assessments_extension`
set source = 'illuminate'
where source is null;
```

- [ ] **Step 2:** User changes the app key and the table reference to `source` +
      `assessment_id` in the AppSheet editor; confirm before Step 4.
- [ ] **Step 3:** Staging uniqueness test → (`source`, `assessment_id`); every
      join to it adds `source`.
- [ ] **Step 4:** `rpt_appsheet__assessments` unions Apex rows from
      `int_focus__apex_assessments` (title, academic year, band set;
      Illuminate-only fields null) and adds `source`. Contract updated.
- [ ] **Step 5:** Build, fingerprint NJ, tag 1 Apex assessment in the app with
      the user, rebuild, confirm module fields flow to the rollup. Ship as PR 1.

## PR 3 — Tracker tab (Task 11)

### Task 11: `rpt_gsheets__miami_assessment_tracker`

**Files:** Create
`src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__miami_assessment_tracker.sql`
(+ yml, contract); modify `models/exposures/google-sheets.yml`.

**Interfaces:**

- Produces, 1 row per (`school_name`, `grade_level`, `subject_area`,
  `assessment_title`): `n_tested`, `n_mastery`, `pct_mastery`, `n_enrolled`.
  Aggregate only; no student columns.
- Reads the fact/dims for tested and mastery (A2), filtered
  `assessment_type = 'apex'`, overall rows; `n_enrolled` from Miami core course
  enrollments in the subject on `administered_at`; grade = enrolled grade. No
  tag filter.

- [ ] **Step 1:** Singular test: known answer row (Royalty, grade 3, math,
      PET 1) = 130 tested, 60 mastery, 156 enrolled.
- [ ] **Step 2:** Implement; build; test PASS.
- [ ] **Step 3:** Exposure `miami_data_tracker_2627` with
      `url: https://docs.google.com/spreadsheets/d/1LPYJFgvi5Btkqf4Q2onmM7A90MykKcqFyzZLOcUr7mA`.
- [ ] **Step 4:** Compare with Miami's hand-filled grade 6–8 math cells (read
      via Sheets MCP); write each difference's cause in the PR. Ship.
