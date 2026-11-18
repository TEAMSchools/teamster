# KIPP Forward Early Apps Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four `rpt_gsheets__kfwd_early_apps_*` models that feed a
daily-refreshing Google Sheet tracking current seniors' early-application goals
from Overgrad data.

**Architecture:** Three domain intermediates in `models/students/` hold every
rule: an application-grain model, a senior-grain rollup, and a senior ×
criterion scaffold. Four thin `rpt_` models shape them for the sheet's 4 tabs.
An exposure in `google-sheets.yml` names the source sheet.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Connected Sheets.

**Spec:** `docs/superpowers/specs/2026-10-29-kfwd-early-apps-tracker-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/CGibson17/feat/claude-kfwd-early-apps-tracker`
  (`WT` below). Every `git` call is `git -C <WT>`; every dbt call passes
  `--project-dir <WT>/src/dbt/kipptaf`. Always `uv run`.
- Invoke the `dbt-local-dev` skill before the first dbt command (dev schema,
  `--defer --state`, and the prod manifest path). Run
  `uv run dbt deps --project-dir <WT>/src/dbt/kipptaf` in its own Bash call
  first.
- Never write a `--target staging` or `--target prod` object. Dev builds only.
- No student values in git, the PR, or the issue. Unit-test fixtures use
  `Student A`-style names and `Example College`-style colleges.
- Current seniors: `graduation_year = {{ var("current_academic_year") + 1 }}`.
- The 3 high schools, by Overgrad `school__name`:
  `KIPP Cooper Norcross High School`, `KIPP Newark Collegiate Academy`,
  `KIPP Newark Lab High School`.
- Early `due_date__type`: `early_action`, `early_action_2`, `early_decision`,
  `early_decision_2`, `single_choice_early_action`. ED = `early_decision*`; EA =
  the other 3.
- Submitted `status`: `Applied`, `Accepted`, `Denied`, `Deferred`, `Waitlisted`,
  `Enrolled`.
- URM rate: `stg_kippadb__account.adjusted_6_year_minority_graduation_rate`, on
  `nces_id = cast(university__ipeds_id as string)`. Null rate never qualifies
  and is never near the bar.
- Full need: column `is_full_need`, always `true`.
- Every join between `int_overgrad__students` and `int_overgrad__admissions`
  includes `_dbt_source_project` (rule A10).
- Counts are distinct `university__id`.
- SQL follows `.claude/rules/dbt-sql.md`; YAML follows
  `.claude/rules/dbt-yaml.md`. Every model and column has a `description:`.
  `rpt_` tests set `config: severity: error`.
- PII tags (tiers 1 to 3 from `.claude/rules/ferpa-pii.md`, column level):
  student name, GPA, GPA band, criterion statuses, and every application list.
  The Summary model is untagged (aggregate).
- `overgrad_student_id` is the grain key in every student-level model. It stays
  in the model for tests and is left out of the Connected Sheets column picks.
- Lint every changed SQL, YAML, and markdown file before pushing:
  `cd <WT> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.

## Review Focus

1. A flagged senior with no GPA: band `No GPA`, every criterion `N/A`, still in
   N. Test in Task 2.
2. An early application whose college has no URM rate: never qualifying, never
   near the bar. Test in Task 3.
3. A flagged senior whose only early application is `Withdrew`: counted as not
   submitted, so Section A. Test in Task 2.
4. URM exactly on a bar (80.0 qualifies; 75.0 is near the bar; 74.9 is neither).
   Test in Task 3.
5. A GPA band with 0 seniors at 1 school: Summary shows `-`, not a divide error.
   Test in Task 5.

---

### Task 1: Application-grain intermediate

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__early_applications.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__early_applications.yml`

**Interfaces:**

- Consumes: `ref("int_overgrad__admissions")`, `ref("stg_kippadb__account")`.
- Produces: 1 row per Overgrad admission whose `due_date__type` is early, every
  year and school. Columns: `_dbt_source_project`, `admission_id`,
  `overgrad_student_id` (`student__id`), `university_id`, `university_name`,
  `due_date_type`, `application_type` (`ED` or `EA`), `due_date`
  (`due_date__date`), `application_status`, `is_submitted` (bool),
  `urm_graduation_rate` (numeric, nullable), `is_full_need` (bool, always true),
  `updated_at`.

- [ ] **Step 1: Write the unit test**
      `test_int_students__early_applications_classification` in the properties
      YAML. Given 6 admissions: `early_decision`/`Applied`,
      `early_decision_2`/`Will Apply`, `single_choice_early_action`/`Accepted`,
      `early_action`/`Withdrew`, `regular`/`Applied`, `priority`/`Applied`, and
      2 accounts (one with rate 80.0, one with null rate). Expect 4 rows, with
      `application_type` `ED`, `ED`, `EA`, `EA`; `is_submitted` true, false,
      true, false; the rate joined for the matching IPEDS id and null otherwise;
      `is_full_need` true on every row.
- [ ] **Step 2: Run it and see it fail**
      `uv run dbt test --select "int_students__early_applications,test_type:unit" --project-dir <WT>/src/dbt/kipptaf`
      Expected: FAIL (model does not exist).
- [ ] **Step 3: Write the model.** Filter to the early types in Global
      Constraints. Left join the account on IPEDS id.
- [ ] **Step 4: Add the grain test** `dbt_utils.unique_combination_of_columns`
      on `_dbt_source_project`, `admission_id`. It also catches an IPEDS id on 2
      Salesforce accounts, which would fan out rows.
- [ ] **Step 5: Run the unit test.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(dbt): add int_students__early_applications`.

### Task 2: Senior-grain rollup

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__early_applications_rollup.sql`
- Create: `.../properties/int_students__early_applications_rollup.yml`

**Interfaces:**

- Consumes: `ref("int_overgrad__students")`, Task 1's model.
- Produces: 1 row per current senior at the 3 high schools, with or without
  applications or a flag. Columns: `_dbt_source_project`, `overgrad_student_id`,
  `student_name` (`last_name, first_name`), `high_school`, `counselor_name`
  (`first last`), `unweighted_gpa` (numeric: cast to `numeric` before
  `round(..., 2)`, so a float 3.745 cannot round down), `gpa_band` (`3.75+`,
  `3.50-3.74`, `3.00-3.49`, `Below 3.00`, `No GPA`), `is_ed_ea_flagged`
  (`is_ed_ea = 'Yes'`), `submitted_early_count` (int),
  `submitted_early_applications` (string), `will_apply_early_applications`
  (string), `earliest_will_apply_due_date` (date), `latest_overgrad_updated_at`
  (timestamp: the latest `updated_at` of the student and their early
  applications).
- List formats, alphabetical by college, joined with `, `: submitted
  `Example College (ED) 77%` (rate rounded to whole number; `no rate` when
  null); will-apply `Example College (EA)`.

- [ ] **Step 1: Write unit test**
      `test_int_students__early_applications_rollup`. Given 5 current seniors at
      the 3 schools plus 1 at `KIPP MS Completers (Newark)` and 1 with
      `graduation_year` of next year. Cases: Student A flagged, GPA 3.96, 2
      submitted applications to 2 colleges; Student B flagged, null GPA, 0
      applications; Student C flagged, GPA 3.10, 1 `Withdrew` application and 1
      `Will Apply` due 2026-11-01; Student D unflagged, GPA 3.50, 1 submitted
      application; Student E GPA 3.745. Override
      `vars: {current_academic_year: 2026}`. Expect 5 rows (the MS Completers
      and next-year seniors excluded). Student B band `No GPA`, count 0. Student
      C count 0, will-apply list populated, earliest date 2026-11-01. Student E
      `unweighted_gpa` 3.75, band `3.75+`.
- [ ] **Step 2: Add a second unit test**
      `test_int_students__early_applications_rollup_distinct_colleges`: 1 senior
      with 2 submitted rows for the same `university_id`. Expect
      `submitted_early_count` = 1.
- [ ] **Step 3: Run both and see them fail.**
- [ ] **Step 4: Write the model.** Spine from `int_overgrad__students`; left
      join Task 1 on `overgrad_student_id` and `_dbt_source_project`.
- [ ] **Step 5: Grain test** on `_dbt_source_project`, `overgrad_student_id`.
- [ ] **Step 6: Run the unit tests.** Expected: PASS.
- [ ] **Step 7: Commit**
      `feat(dbt): add int_students__early_applications_rollup`.

### Task 3: Senior × criterion scaffold

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__early_application_criteria_scaffold.sql`
- Create: `.../properties/int_students__early_application_criteria_scaffold.yml`

**Interfaces:**

- Consumes: Tasks 1 and 2.
- Produces: 1 row per senior (any flag) × each criterion of their band. Seniors
  in `Below 3.00` or `No GPA` get no rows. Columns: `_dbt_source_project`,
  `overgrad_student_id`, `gpa_band`, `criterion_code`, `criterion_sort`,
  `criterion_label`, `required_count`, `urm_bar`, `qualifying_count`,
  `near_bar_count`, `is_met` (bool), `is_near_miss` (bool),
  `qualifying_colleges`, `near_bar_colleges`, `what_they_have`,
  `what_would_close_it`.

| `criterion_code`     | sort | band      | label                        | type  | bar | required |
| -------------------- | ---- | --------- | ---------------------------- | ----- | --- | -------- |
| `ed_80_full_need`    | 1    | 3.75+     | 1 ED, full need, 80%+ URM    | ED    | 80  | 1        |
| `ea_78`              | 2    | 3.75+     | 2 EA, 78%+ URM               | EA    | 78  | 2        |
| `early_80_full_need` | 3    | 3.50-3.74 | 1 ED/EA, full need, 80%+ URM | early | 80  | 1        |
| `additional_68`      | 4    | 3.50-3.74 | 2 additional early, 68%+ URM | early | 68  | 2        |
| `early_68`           | 5    | 3.00-3.49 | 3 early, 68%+ URM            | early | 68  | 3        |

- Qualifying: submitted, right type, `urm_graduation_rate >= bar`, and
  `is_full_need` for the 2 full-need rules. For `additional_68`, set aside the
  alphabetically first qualifying `early_80_full_need` college, then count the
  rest.
- Near bar: submitted, right type, `bar - 5 <= rate < bar`.
- `is_near_miss`: `not is_met` and either
  `required_count = 1 and near_bar_count >= 1`, or
  `required_count > 1 and (qualifying_count = required_count - 1 or qualifying_count + near_bar_count >= required_count)`.
- `what_they_have`: `Qualifying: <list>; Near the bar: <list>`, omitting an
  empty part; each item uses the Task 2 submitted format.
- `what_would_close_it`, only when `is_near_miss`: for a 1-school rule,
  `An <ED|ED or EA> college at <bar>%+ (closest: <college> at <rate>%, <gap> points short)`
  with the gap to 1 decimal; otherwise
  `<n> more <ED|EA|early> college(s) at <bar>%+` where
  `n = required_count - qualifying_count`.

- [ ] **Step 1: Unit test** `test_..._criteria_scaffold_3_75_band`. 2 seniors in
      `3.75+`. Senior A: ED at 95.8, EA at 79.1 and 88.8. Senior B: ED at 78.2,
      EA at 79.1 and 73.6. Expect Senior A `ed_80_full_need` and `ea_78` met,
      not near misses. Senior B both not met and both near misses;
      `ed_80_full_need` close text
      `An ED college at 80%+ (closest: <college> at 78.2%, 1.8 points short)`;
      `ea_78` close text `1 more EA college at 78%+`.
- [ ] **Step 2: Unit test** `test_..._criteria_scaffold_narrow_near_miss`. 2
      seniors in `3.00-3.49`. Senior C: 0 qualifying, 1 application at 65.0: not
      a near miss. Senior D: 2 qualifying and 1 at 63.0: near miss.
- [ ] **Step 3: Unit test** `test_..._criteria_scaffold_additional`. 1 senior in
      `3.50-3.74` with early applications at 92, 88, and 70. Expect
      `early_80_full_need` met; `additional_68` met with `qualifying_count` 2
      (88 and 70 count; the alphabetically first of 92 and 88 is set aside).
- [ ] **Step 4: Unit test** `test_..._criteria_scaffold_edges` (Review Focus 2
      and 4). 3.75+ senior with ED at 80.0 (met), a second 3.75+ senior with ED
      at 75.0 (near miss) and EA at null rate (not counted), a third with ED at
      74.9 (not met, not a near miss).
- [ ] **Step 5: Run all 4 and see them fail.**
- [ ] **Step 6: Write the model.** Criteria come from a literal `unnest` of
      structs matching the table above, joined to the rollup on `gpa_band`.
- [ ] **Step 7: Grain test** on `_dbt_source_project`, `overgrad_student_id`,
      `criterion_code`.
- [ ] **Step 8: Run the unit tests.** Expected: PASS.
- [ ] **Step 9: Commit** `feat(dbt): add early application criteria scaffold`.

### Task 4: Roster extract

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kfwd_early_apps_roster.sql`
- Create: `.../sheets/properties/rpt_gsheets__kfwd_early_apps_roster.yml`

**Interfaces:**

- Consumes: Tasks 2 and 3.
- Produces: 1 row per flagged senior. Columns: `overgrad_student_id`,
  `student_name`, `high_school`, `counselor_name`, `unweighted_gpa`, `gpa_band`,
  `met_all_for_band` (`Yes`/`No`/`N/A`), `submitted_early_count`, then for each
  `criterion_code` a `<code>_status` (`Yes`/`No`/`N/A`) and a `<code>_colleges`
  (qualifying list when `Yes`, else null), then `near_miss_count`,
  `submitted_early_applications`.

- [ ] **Step 1: Unit test** `test_rpt_gsheets__kfwd_early_apps_roster`: 3
      seniors (flagged 3.75+ meeting both; flagged `No GPA`; unflagged). Expect
      2 rows. First: `met_all_for_band` `Yes`, 3.50 and 3.00 statuses `N/A`.
      Second: every status `N/A`, `met_all_for_band` `N/A`, `near_miss_count` 0.
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Write the model.** Pivot the scaffold with `max(if(...))` per
      criterion; `met_all_for_band` = `logical_and(is_met)` over the band's
      rows, `N/A` when the senior has none.
- [ ] **Step 4: Grain test** `unique` and `not_null` on `overgrad_student_id`.
- [ ] **Step 5: Run it.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(dbt): add early apps roster extract`.

### Task 5: Summary extract

**Files:**

- Create: `.../sheets/rpt_gsheets__kfwd_early_apps_summary.sql` and its
  properties YAML.

**Interfaces:**

- Consumes: Tasks 2 and 3.
- Produces: 19 rows, 1 per `row_sort`. Columns: `row_sort`, `gpa_band`,
  `row_label`; display columns `cooper_norcross`, `newark_collegiate`,
  `newark_lab`, `all_schools`; numeric columns `<school>_met`,
  `<school>_denominator`, `<school>_pct` for the same 4; `data_as_of` (date of
  max `latest_overgrad_updated_at` over flagged seniors).
- Rows: 1 `N: flagged Is ED/EA = Yes`; 2 to 5 the band counts (`3.75+`,
  `3.50-3.74`, `3.00-3.49`, `Below 3.00 or no GPA`), display as the bare count;
  6 to 19 the 7 criteria (5 codes plus `3.75+ met both` and
  `3.50-3.74 met both`), each as `% of N` then `% of band`.
- Display:
  `format('%d%% (%d/%d)', cast(round(100 * met / denominator) as int64), met, denominator)`;
  `-` when the denominator is 0.
- Population: flagged seniors only.

- [ ] **Step 1: Unit test** `test_rpt_gsheets__kfwd_early_apps_summary`: Cooper
      Norcross with 2 flagged 3.75+ seniors (1 meets `ed_80_full_need`), Newark
      Collegiate with 1 flagged 3.00-3.49 senior, Newark Lab with 0 flagged
      seniors. Expect the `ed_80_full_need` `% of band` row: `cooper_norcross`
      `50% (1/2)`, `newark_collegiate` `-`, `newark_lab` `-`, `all_schools`
      `50% (1/2)`; the N row `all_schools` `3`.
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Write the model.**
- [ ] **Step 4: Grain test** `unique` on `row_sort`.
- [ ] **Step 5: Run it.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(dbt): add early apps summary extract`.

### Task 6: Not Submitted Yet extract

**Files:**

- Create: `.../sheets/rpt_gsheets__kfwd_early_apps_not_submitted.sql` and its
  properties YAML.

**Interfaces:**

- Consumes: Task 2.
- Produces: Section `A` (flagged, `submitted_early_count = 0`) and section `B`
  (unflagged, `submitted_early_count > 0`). Columns: `overgrad_student_id`,
  `section`, `section_label` (`A. Flagged ED/EA, no early app submitted` /
  `B. Submitted early, but Is ED/EA flag is blank: fix the flag in Overgrad`),
  `student_name`, `high_school`, `counselor_name`, `gpa_band`,
  `will_apply_early_applications`, `earliest_will_apply_due_date`,
  `submitted_early_applications`.

- [ ] **Step 1: Unit test** with 4 seniors: flagged/0 submitted (A), flagged/1
      submitted (out), unflagged/1 submitted (B), unflagged/0 (out). Expect 2
      rows with the right sections.
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Write the model.**
- [ ] **Step 4: Grain test** `unique` and `not_null` on `overgrad_student_id`.
- [ ] **Step 5: Run it.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(dbt): add early apps not-submitted extract`.

### Task 7: Near Misses extract

**Files:**

- Create: `.../sheets/rpt_gsheets__kfwd_early_apps_near_misses.sql` and its
  properties YAML.

**Interfaces:**

- Consumes: Tasks 2 and 3.
- Produces: 1 row per flagged senior × criterion where `is_near_miss`. Columns:
  `overgrad_student_id`, `criterion_code`, `criterion_sort`, `student_name`,
  `high_school`, `counselor_name`, `gpa_band`, `criterion_label`,
  `what_they_have`, `what_would_close_it`.

- [ ] **Step 1: Unit test**: a flagged senior with 2 near-miss criteria, a
      flagged senior with 1 met criterion, and an unflagged near-miss senior.
      Expect 2 rows, both for the first senior.
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Write the model.**
- [ ] **Step 4: Grain test** on `overgrad_student_id`, `criterion_code`.
- [ ] **Step 5: Run it.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(dbt): add early apps near-misses extract`.

### Task 8: Build in dev and check against prod data

- [ ] **Step 1: Build** `int_students__early_applications+` into the dev schema
      per `dbt-local-dev` (`--target dev --defer --state <prod manifest>`).
      Expected: every model and test passes.
- [ ] **Step 2: N check.** Count current seniors at the 3 schools with
      `is_ed_ea = 'Yes'` straight from
      `kipptaf_overgrad.int_overgrad__students`; it equals the Summary N row
      `all_schools` and the Roster row count.
- [ ] **Step 3: Sum check.** For each Summary row, the 3 school `_met` and
      `_denominator` values sum to the `all_schools` values.
- [ ] **Step 4: Stakeholder check, terminal only.** Find the 2 seniors from the
      2026-10-29 report by name in the dev Roster. Expect one `Yes` on both
      3.75+ criteria; the other `No` on both, with 2 Near Misses rows.
- [ ] **Step 5: Lint** every new SQL and YAML file. Fix findings.
- [ ] **Step 6: Commit** any fixes.

### Task 9: Exposure, source sheet, and pull request

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/google-sheets.yml`

- [ ] **Step 1: Get the source sheet URL.** Ask the user to create a blank
      Google Sheet named `rpt_gsheets__kfwd_early_apps` in the IMPORTRANGE
      Sources folder (`docs/guides/google-sheets.md`) and paste its URL. Do not
      create it without that confirmation.
- [ ] **Step 2: Add the exposure.** `name: kfwd_early_apps_tracker`,
      `label: KIPP Forward Early Apps Tracker`, `type: application`,
      `owner.name: Data Team`, `url: <source sheet URL>`, `depends_on` the 4
      `rpt_gsheets__kfwd_early_apps_*` refs,
      `config.meta.dagster.kinds:     [googlesheets]`.
- [ ] **Step 3: Parse.**
      `uv run dbt parse --no-partial-parse --project-dir <WT>/src/dbt/kipptaf`.
      Expected: no errors.
- [ ] **Step 4: Lint and commit** `feat(dbt): add early apps tracker exposure`.
- [ ] **Step 5: Push and open the PR** from `.github/pull_request_template.md`,
      body `Closes #6190`. Put the post-merge sheet setup in Reviewer Notes: 4
      Connected Sheets tabs (`summary`, `roster`, `not_submitted`,
      `near_misses`) in the source sheet, a daily refresh, every column except
      `overgrad_student_id`; then a Reports sheet `Early Apps Tracker` with 4
      friendly-named tabs using `IMPORTRANGE` only.
