# Google Forms Latest Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every survey report keeps one latest Google Forms submission per
respondent, per subject, per administration, and Miami Re-Commitment families
resolve to students.

**Architecture:** A new domain model, `int_surveys__submission_subjects`, holds
every subject rule. `int_surveys__survey_submissions` joins it and re-ranks
`round_rn`. The facts filter `round_rn = 1`. The renewal feed, the Manager
Survey details and the SCD report read the shared subject instead of their own
copies.

**Tech Stack:** dbt (kipptaf project) on BigQuery; dbt unit tests; BigQuery MCP
for prod checks.

**Spec:**
`docs/superpowers/specs/2026-10-26-google-forms-latest-submission-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/feat/claude-google-forms-latest-submission`.
  Run every command from `<worktree>/src/dbt/kipptaf`, and use
  `git -C <worktree>` for git.
- Always `uv run dbt`. Dev builds use
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
  (the main checkout's prod manifest, absolute path). Never `--target staging`
  or `--target prod`.
- Every new or modified column gets a `description:`. Student numbers, employee
  numbers, `rank_respondent` and `rank_subject` get
  `config.meta.contains_pii: true`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  carry `Refs #5978`. No PII values in commits, PR text or comments: counts
  only.
- SQL rules that bite here:
  - S1: no `qualify`.
  - S9: cast once, in a CTE.
  - S10: `where`/`on` plain comparisons only.
  - S17: union branches list the same columns in the same order.
  - S20: comment every business-rule literal.
- Before each commit:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
  Fix lint findings; formatting is the commit hook's.
- The Alchemer archive
  (`source("surveys", "int_surveys__alchemer_submissions")`) is frozen. Do not
  edit it.

## Review Focus

1. A Google Forms submission with a null `term_code` must get `round_rn = 1`,
   including several from one respondent. Pinned by the Task 2 unit test row
   `no_term_a` / `no_term_b`.
2. One approver rating two staff in one term must keep two latest rows. Pinned
   by the Task 2 rows `approver_subject_1` / `approver_subject_2`.
3. A family submission with no email must rank by student, not alone. Pinned by
   the Task 2 rows `family_old` / `family_new`.
4. A non-numeric or 4-digit family answer must give a null student, not
   `8400`-prefixed junk. Pinned by Task 1 row `family_bad`.
5. A Manager Survey or Renewal row whose subject answer has no bracketed number
   must give a null subject and still rank, on respondent alone. Pinned by Task
   1 row `no_bracket`.

---

### Task 1: Shared subject model

**Files:**

- Create: `models/surveys/intermediate/int_surveys__submission_subjects.sql`
- Create:
  `models/surveys/intermediate/properties/int_surveys__submission_subjects.yml`

**Interfaces:**

- Consumes: `ref("int_google_forms__form_responses")` (question grain; columns
  `form_id`, `response_id`, `info_title`, `item_abbreviation`, `text_value`).
- Produces: `int_surveys__submission_subjects`, one row per
  `survey_id, survey_response_id`. Columns:
  - `survey_id` string
  - `survey_response_id` string
  - `subject_employee_number` int64
  - `respondent_student_number` int64

  Rows exist only for submissions with at least one subject question answered.

- [ ] **Step 1: Confirm the keys in prod.** Query
      `kipptaf_google_forms.int_google_forms__form_responses` (BigQuery MCP).
      Count submissions per `info_title` where `item_abbreviation` is in
      `('subject_employee_number', 'employee_name', 'family_respondent_number')`.
      Expected: Manager Survey 8,285; Renewal Approval Tool Processing 12,664;
      Performance Management Score Change Request Form 53; the Re-Commitment
      title 2,257, give or take new submissions. If an abbreviation is missing,
      stop and ledger it.

- [ ] **Step 2: Write the yml with the unit test first.**
  - Model description, column descriptions and PII tags.
  - A model-level `dbt_utils.unique_combination_of_columns` on
    `survey_id, survey_response_id` at `severity: error`.
  - Unit test `test_int_surveys__submission_subjects_rules`. Mock
    `int_google_forms__form_responses` with `format: sql` (a select of literal
    rows), with these rows:

  | row          | info_title                                                         | item_abbreviation          | text_value          | expect subject | expect student |
  | ------------ | ------------------------------------------------------------------ | -------------------------- | ------------------- | -------------- | -------------- |
  | `manager`    | Manager Survey                                                     | `subject_employee_number`  | `Person A (123456)` | 123456         | null           |
  | `renewal`    | Renewal Approval Tool Processing                                   | `employee_name`            | `Person B (234567)` | 234567         | null           |
  | `no_bracket` | Renewal Approval Tool Processing                                   | `employee_name`            | `Person C`          | null           | null           |
  | `family`     | KIPP Miami Re-Commitment Form & Family School Community Diagnostic | `family_respondent_number` | `12345`             | null           | 840012345      |
  | `family_bad` | KIPP Miami Re-Commitment Form & Family School Community Diagnostic | `family_respondent_number` | `1234`              | null           | null           |
  | `other`      | Support Survey                                                     | `q1`                       | `5`                 | (no row)       | (no row)       |

- [ ] **Step 3: Run it to watch it fail.**
      `uv run dbt test --select int_surveys__submission_subjects,test_type:unit --target dev`
      Expected: FAIL. The model SQL does not exist, or the compile error names
      the missing model.

- [ ] **Step 4: Write the model.**
  - Filter to the three abbreviations.
  - Group by `form_id, response_id`. Take `max(if(...))` per rule:
    - Bracket rule: `regexp_extract(text_value, r'\((\d{6})\)')`, then
      `safe_cast` to int64 in a later CTE (S8/S9).
    - Family rule: only when `info_title` is the Re-Commitment title and
      `regexp_contains(text_value, r'^\d{5,6}$')`.
  - Comment the `8400` literal (Miami's PowerSchool-to-Focus prefix) and the
    Re-Commitment title literal (S20).
  - Alias `form_id as survey_id`, `response_id as survey_response_id`.

- [ ] **Step 5: Run the unit test and build.** Run:

  ```bash
  uv run dbt build --select int_surveys__submission_subjects --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
  ```

  Expected: the unit test passes, the model builds, and the uniqueness test
  passes. Spot-check the dev table: the non-null counts per title match Step 1
  within 2 per title. Task 2's subject counts were 12,662 renewal, 8,285 manager
  and 2,254 family.

- [ ] **Step 6: Lint and commit** as
      `feat(surveys): add shared submission subject model`.

### Task 2: Re-rank Google Forms submissions

**Files:**

- Modify: `models/surveys/intermediate/int_surveys__survey_submissions.sql`
- Modify:
  `models/surveys/intermediate/properties/int_surveys__survey_submissions.yml`

**Interfaces:**

- Consumes: Task 1's `int_surveys__submission_subjects`.
- Produces: `int_surveys__survey_submissions` gains `rank_respondent` (string)
  and `rank_subject` (string), output from both arms. `subject_employee_number`
  and `respondent_student_number` are now populated on Google Forms. `round_rn`
  has new semantics. The column order is otherwise unchanged; append the two new
  columns after `respondent_identifier` in both union branches.

- [ ] **Step 1: Write the unit test first** in the yml:
      `test_int_surveys__survey_submissions_round_rn`.
  - Mock every ref and the Alchemer source with `format: sql`. The subjects
    model is new and has no warehouse relation, and the source needs zero rows.
  - Mock the terms sheet with one SURVEY window per title.
  - Mock the staff roster history so emails resolve to employee numbers. Mock
    the directory addresses with zero rows.
  - Expected `round_rn` per row:

  | row                  | title             | term | respondent | subject | submitted | expect `round_rn` |
  | -------------------- | ----------------- | ---- | ---------- | ------- | --------- | ----------------- |
  | `approver_subject_1` | Renewal (in term) | R1   | staff X    | 111111  | day 2     | 1                 |
  | `approver_subject_2` | Renewal (in term) | R1   | staff X    | 222222  | day 3     | 1                 |
  | `approver_repeat`    | Renewal (in term) | R1   | staff X    | 111111  | day 1     | 2                 |
  | `family_new`         | Re-Commitment     | F1   | no email   | —       | day 5     | 1                 |
  | `family_old`         | Re-Commitment     | F1   | no email   | —       | day 4     | 2                 |
  | `no_term_a`          | Candidate Offer   | none | staff Y    | —       | day 1     | 1                 |
  | `no_term_b`          | Candidate Offer   | none | staff Y    | —       | day 2     | 1                 |
  - `family_new` and `family_old` are the same student (840012345 via the
    subjects mock).
  - Assert `survey_response_id`, `round_rn`, `respondent_student_number` and
    `subject_employee_number` on every row.

- [ ] **Step 2: Run it to watch it fail.**
      `uv run dbt test --select int_surveys__survey_submissions,test_type:unit --target dev`
      Expected: FAIL. `round_rn` mismatches on `approver_subject_2`,
      `family_old` and `no_term_b` under today's `dense_rank`.

- [ ] **Step 3: Change the Google Forms arm.**
  - Left join the subjects model on `survey_id, survey_response_id`.
  - Add a cast CTE and a keyed CTE, mirroring
    `int_surveys__alchemer_submissions` lines 234-263:
    - `rank_respondent` = coalesce(student string, `respondent_identifier`,
      `survey_response_id`).
    - `rank_subject` = subject employee number string.
  - `round_rn`:
    `if(term_code is null, 1, row_number() over (partition by survey_title, academic_year, term_code, rank_respondent, rank_subject order by date_submitted desc, survey_response_id desc))`.
  - Comment the null-term branch: "no administration: never ranked".
  - Drop the `TODO(#5978)` nulls.
  - Add `rank_respondent`, `rank_subject` to both union branches. The source has
    both.

- [ ] **Step 4: Update the yml.**
  - Rewrite the `round_rn`, `respondent_student_number` and
    `subject_employee_number` descriptions to match the new behavior. Drop "null
    on Google Forms".
  - Add the two new columns with PII tags.
  - Add a model-level `dbt_utils.unique_combination_of_columns` on
    `survey_title, academic_year, term_code, rank_respondent, rank_subject` with
    `config: where: "round_rn = 1 and term_code is not null"` and
    `severity: error`.
  - If `dbt-layer-check` flags A5 at commit, add
    `config.meta.standard_exempt: {A5: latest submission per respondent, subject and administration is the business rule}`.

- [ ] **Step 5: Run the unit test and build** with
      `--select int_surveys__submission_subjects int_surveys__survey_submissions`
      and the dev flags. Expected: unit test PASS, both builds succeed, and the
      new uniqueness test passes. Then, against the dev table, count
      `round_rn = 1` per title for the six titles in the spec's counts table.
      Expected: within 2% of the spec's figures.

- [ ] **Step 6: Lint and commit** as
      `feat(surveys): rank Google Forms submissions per respondent and subject`.

### Task 3: Facts keep only the latest submission

**Files:**

- Modify: `models/marts/facts/fct_survey_submissions.sql`
- Modify:
  `models/surveys/intermediate/properties/int_surveys__manager_submission_subjects.yml`
  (disable)

**Interfaces:**

- Consumes: Task 2's `round_rn` and `subject_employee_number` on
  `int_surveys__survey_submissions`.
- Produces: no column change to `fct_survey_submissions`. It now has fewer rows.
  `int_surveys__manager_submission_subjects` is disabled.

- [ ] **Step 1: Record the prod baseline.** In prod
      `kipptaf_marts.fct_survey_submissions`, count rows by `respondent_type`.
      Also count rows in `fct_survey_responses`.

- [ ] **Step 2: Edit the fact.**
  - Add `and sg.round_rn = 1` to the `where` of all four arms.
  - Manager arm: replace `mso.subject_employee_number` with
    `sg.subject_employee_number` and drop the
    `int_surveys__manager_submission_subjects` join.
  - Family arm: replace the `TODO(#5978)` comment with: "family forms identify
    the student, not the contact".

- [ ] **Step 3: Disable the subjects model.** Set
      `int_surveys__manager_submission_subjects` to `config: enabled: false`.
      Then grep for leftovers:
      `rg "int_surveys__manager_submission_subjects" models tests`. Expected:
      only its own yml and sql.

- [ ] **Step 4: Build.** Build
      `int_surveys__submission_subjects int_surveys__survey_submissions fct_survey_submissions fct_survey_responses`
      with the dev flags. Expected: all build and all tests pass.
  - Manager rows: within 1% of baseline.
  - Family rows drop by about 300 (2,257 to about 1,964).
  - Staff and student rows: within 1%.
  - `fct_survey_responses` drops only by the family and manager rows removed.
  - Ledger the counts.

- [ ] **Step 5: Lint and commit** as
      `feat(surveys): keep latest submission in survey facts`.

### Task 4: Renewal feed and Manager Survey details read the shared subject

**Files:**

- Modify: `models/surveys/intermediate/int_surveys__renewal_responses_feed.sql`
- Modify: `models/surveys/intermediate/int_surveys__manager_survey_details.sql`

**Interfaces:**

- Consumes: Task 1's `int_surveys__submission_subjects`.
- Produces: no column or row change to either model.

- [ ] **Step 1: Record baselines.** In prod, count rows for both models. Also
      count distinct `subject_employee_number` for the renewal feed and distinct
      `subject_df_employee_number` for the Google Forms arm of the details
      model.

- [ ] **Step 2: Swap the renewal feed's regex.** Replace it with a left join to
      the subjects model on `fr.survey_id, fr.survey_response_id`. Keep
      `rn_approval`, `rn_level_approval` and the inner join to the roster as
      they are.

- [ ] **Step 3: Swap the Manager Survey details regex.** Replace the
      `safe_cast(regexp_extract(...))` on question `315a6c37` with an inner join
      to the subjects model on `fr.form_id, fr.response_id`. Keep the
      `fr.question_id = '315a6c37'` filter so the grain stays one row per
      submission before the dedup. Keep its `dbt_utils.deduplicate` unchanged.

- [ ] **Step 4: Build both models** with the dev flags, Task 1's model selected
      too. Expected: builds pass, and row counts and distinct subject counts
      equal the Step 1 baselines exactly. Any difference: stop and debug. The
      spec requires identical counts.

- [ ] **Step 5: Lint and commit** as
      `refactor(surveys): read subjects from the shared model`.

### Task 5: SCD report uses the shared student and the latest submission

**Files:**

- Modify: `models/extracts/tableau/rpt_tableau__school_community_diagnostic.sql`
- Modify: its properties yml under `models/extracts/tableau/properties/`

**Interfaces:**

- Consumes: Task 2's `int_surveys__survey_submissions.respondent_student_number`
  and `round_rn` on `int_surveys__survey_responses`.
- Produces: same columns; a grain test.

- [ ] **Step 1: Find the grain in prod.** Count rows against distinct
      `survey_id, survey_response_id, question_shortname` on prod
      `kipptaf_extracts.rpt_tableau__school_community_diagnostic`. If they
      differ, try adding `survey_title`. Ledger the key that gives zero
      duplicates. If none does, stop and ledger it.

- [ ] **Step 2: Add the grain test.** Put
      `dbt_utils.unique_combination_of_columns` on that key in the yml at
      `severity: error`.

- [ ] **Step 3: Edit the SQL.**
  - Delete the `family_responses` CTE.
  - Left join `int_surveys__survey_submissions as ss` on
    `sr.survey_id, sr.survey_response_id`.
  - Point `se2` at `ss.respondent_student_number` and `ss.academic_year`.
    Replace `fr.respondent_number` in the `respondent_number` coalesce with
    `ss.respondent_student_number`.
  - Add `and sr.round_rn = 1` to the first arm's `where`. Leave the PowerSchool
    InfoSnap arm alone.

- [ ] **Step 4: Build** the model with the dev flags, Tasks 1-2 models selected
      too. Expected: build passes and the grain test passes.
  - Re-Commitment rows with a non-null `region` rise from the prod baseline. The
    `8400` prefix now resolves about 1,087 of 1,116 (2023) and 1,112 of 1,141
    (2024).
  - Ledger the before and after counts of non-null `region` by `survey_title`.

- [ ] **Step 5: Lint and commit** as
      `fix(surveys): resolve Miami family students in the SCD report`. Check the
      model off on #5990 after the PR merges.

### Task 6: Pre-PR checks the spec requires

**Files:** none (verification only; results go in the ledger and PR body)

- [ ] **Step 1: The 67 windowed submissions with no term.** Against the dev
      `int_surveys__survey_submissions`, list rows whose title has a SURVEY
      window but whose `term_code` is null. Count how many share `survey_title`,
      `rank_respondent`, `rank_subject` and school year (from `date_submitted`)
      with another row. Expected: a count. If it is above 0, **stop and bring
      the count to the user before opening the PR.**

- [ ] **Step 2: Survey completion.** Compare row counts of
      `rpt_tableau__survey_completion` in prod and in a dev build (dev flags,
      Task 2 models selected). Ledger both.

- [ ] **Step 3: Workbook filter.** Using the Tableau MCP, find the workbook
      whose exposure depends on `rpt_tableau__survey_responses`
      (`models/exposures/tableau.yml`). Report whether any of its views filter
      on `round_rn`. Ledger the answer for the PR body.

- [ ] **Step 4: Full selection build.** Build all modified models and their
      children with `<models>+`, using the dev flags. Expected: no errors. Any
      warnings must already be in prod.
