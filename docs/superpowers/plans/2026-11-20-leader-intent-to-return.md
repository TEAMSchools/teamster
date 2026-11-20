# Leader Intent to Return Survey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assign the leader intent to return survey to recruitment's leader
population, keep those leaders out of the staff intent to return survey and the
general reminder feed, and give recruitment a follow-up Sheet of leaders who
have not submitted.

**Architecture:** One new domain model holds the leader rule.
`rpt_tableau__survey_links` reads it for a new survey branch and to exclude
leaders from the staff branch; completion and the Survey Dashboard pick the new
branch up unchanged. A new Sheets extract reads the same model plus submissions.

**Tech Stack:** dbt on BigQuery (kipptaf project), dbt unit tests, Google Sheets
exposures.

**Spec:** `docs/superpowers/specs/2026-11-20-leader-intent-to-return-design.md`

## Global Constraints

- Survey title, everywhere it appears: `Leader Intent to Return Survey` (matches
  the form title and the `reporting__terms` name exactly).
- Term code: `LITR`. Leader question shortname: `litr_plans`.
- Job titles (22), departments (8), business units (5): exactly the lists in the
  spec's _Recruitment's rules_ section. Managing Director of Talent Acquisition
  and the Talent Acquisition department are NOT in them.
- Survey eligibility is the same expression as `eligible_roster` in
  `models/extracts/tableau/rpt_tableau__survey_links.sql:70-74` (active,
  primary, rehire or hire at least 3 weeks before `current_date()`).
- The reminder feed `rpt_extracts__survey_reminder` keeps one `email` column.
- All work happens in the worktree
  `/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-leader-intent-to-return`;
  run every `dbt` command with `uv run` from `src/dbt/kipptaf` there. Before the
  first build, invoke the `dbt-local-dev` skill for dev-target and `--defer`
  usage.
- Deploy before 2026-11-30.

## Setup values (owned by the user, outside code)

Tasks 1 to 5 do not need these. Task 6 does. Ask the user for them when Task 6
starts if they are not already in the ledger.

1. The leader form's responder URL (prefill form), after the form is created as
   a copy of the staff intent to return form, with the question text from
   recruitment's setup page minus the "LEADERS:" prefix. The copy must keep
   "collect verified email": completion resolves the respondent from their
   signed-in email.
2. Confirmation that the `reporting__terms` row exists: 2026, name
   `Leader Intent to Return Survey`, code `LITR`, type `SURVEY`, 2026-11-30 to
   2026-12-11.
3. Confirmation that the `form_items_extension` sheet has a row for the leader
   question on the new form with abbreviation `litr_plans`.
4. The follow-up Google Sheet URL.

## Review Focus

- Non-leaders' staff intent to return assignments do not change: Task 2's
  before/after comparison against prod must return 0 rows each way.
- The population matches the rule on today's roster (239 people on 2026-11-20:
  Newark 113, Camden 44, Miami 35, KTAF 29, Paterson 18, allowing for roster
  drift): Task 1 verification.
- A KTAF leader in an Out department (for example Director, Teacher Development)
  and the MD of Talent Acquisition stay out: Task 1 unit test.
- A leader with no manager on the roster still appears on the follow-up Sheet
  with blank manager columns: Task 4 unit test.
- No placeholder link or URL reaches `main`: Task 6 grep.

---

### Task 1: Leader population model

**Files:**

- Create:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__leader_intent_to_return_population.sql`
- Create:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__leader_intent_to_return_population.yml`

**Interfaces:**

- Produces: `int_surveys__leader_intent_to_return_population`, one row per
  `employee_number`, `academic_year`, `survey_round`. Columns: `employee_number`
  int64, `academic_year` int64, `survey_round` string, `is_current` bool,
  `preferred_name_lastfirst` string, `job_title` string, `department` string,
  `business_unit` string, `location` string, `mail` string,
  `report_to_employee_number` int64, `report_to_preferred_name_lastfirst`
  string, `report_to_mail` string.

- [ ] **Step 1: Write the YAML with the grain test and the unit test**

Model description: who gets the leader survey and why (recruitment's 3 lists
plus survey eligibility; the only place the rule lives). Grain test:
`dbt_utils.unique_combination_of_columns` on `employee_number`, `academic_year`,
`survey_round`, `severity: error`. Describe every column; tag
`contains_pii: true` on `employee_number`, `preferred_name_lastfirst`, `mail`,
`report_to_employee_number`, `report_to_preferred_name_lastfirst`,
`report_to_mail`.

Unit test `test_leader_population_rule`, `given` both inputs as `format: sql`
(hire dates must be relative to `current_date()`):

- `ref("int_people__staff_roster")` rows, all Active and primary unless noted,
  hired `date '2020-08-01'` unless noted:
  - 101: School Leader, School Leadership, TEAM Academy Charter School → in
  - 102: School Leader, Human Resources, TEAM Academy Charter School → out
  - 103: Director, Teaching and Learning, KIPP TEAM and Family Schools Inc. → in
  - 104: Director, Teacher Development, KIPP TEAM and Family Schools Inc. → out
  - 105: Managing Director of Talent Acquisition, Talent Acquisition, KIPP TEAM
    and Family Schools Inc. → out
  - 106: School Leader, School Leadership, KIPP Miami, hired
    `date_sub(current_date(), interval 1 week)` → out
  - 107: School Leader, School Leadership, KIPP Miami, `primary_indicator` false
    → out
- `ref("stg_google_sheets__reporting__terms")`: one row `name` =
  `Leader Intent to Return Survey`, `type` = `SURVEY`, `academic_year` 2026,
  `code` = `LITR`, `is_current` true; one row `name` =
  `Intent to Return Survey`, `code` = `ITR`, 2026.
- `expect`: exactly employees 101 and 103, each with `academic_year` 2026,
  `survey_round` `LITR`, `is_current` true.

- [ ] **Step 2: Run the unit test and confirm it fails**

Run:
`uv run dbt test --select "int_surveys__leader_intent_to_return_population,test_type:unit" --target dev`
Expected: error, model SQL does not exist.

- [ ] **Step 3: Write the model**

Read `int_people__staff_roster` (alias `sr`) in one CTE that computes
`is_survey_eligible` (the Global Constraints expression) and `is_leader_role`
(job title, `home_department_name`, `home_business_unit_name` each in its list),
per S10. Final select filters `where is_survey_eligible and is_leader_role` and
inner joins `stg_google_sheets__reporting__terms` on
`name = 'Leader Intent to Return Survey'` and `type = 'SURVEY'` (S11: in the
`on`). Column sources: `formatted_name`, `home_work_location_name`, `mail`,
`reports_to_employee_number`, `reports_to_formatted_name`, `reports_to_mail`;
`rt.code as survey_round`.

- [ ] **Step 4: Run the unit test and confirm it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Build in dev and check the population**

Run:
`uv run dbt build --select int_surveys__leader_intent_to_return_population --target dev`
plus the defer flags from `dbt-local-dev`. Expected: build and grain test pass.
Query the dev relation for `count(*)` by `business_unit`. Expected close to the
Review Focus counts; investigate any business unit off by more than a few.

- [ ] **Step 6: Commit**

`git -C <worktree> add` the 2 new files, commit
`feat(surveys): add leader intent to return population`.

### Task 2: Survey links branch and staff exclusion

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_links.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__survey_links.yml`

**Interfaces:**

- Consumes: Task 1's model and columns.
- Produces: rows with `survey = 'Leader Intent to Return Survey'`,
  `assignment = 'Complete Leader Intent to Return Survey'`,
  `survey_round = 'LITR'`. Task 6 replaces this branch's link.

- [ ] **Step 1: Add the leader branch**

New `union all` branch after the staff intent to return branch, same column
list.
`from eligible_roster as r inner join <population> as lp on r.employee_number = lp.employee_number`;
`academic_year`, `survey_round`, `is_current` come from `lp`. Link: the literal
`'TODO(#6251): leader form responder URL'` until Task 6.

- [ ] **Step 2: Exclude leaders from the staff branch**

In the `Intent to Return Survey` branch,
`left join <population> as lp on r.employee_number = lp.employee_number and rt.academic_year = lp.academic_year`
and add `and lp.employee_number is null` to its `where`. Rounds with no LITR row
(2025 and earlier) are unaffected because the join finds nothing.

- [ ] **Step 3: Update the YAML**

Add the leader survey to the `link` description (leaders get their own form) and
the `survey` description. No new columns.

- [ ] **Step 4: Build and compare with prod**

Build `rpt_tableau__survey_links` in dev (defer). Expected: grain test passes.
Then run 2 queries with `except distinct` on
`(employee_number, academic_year, survey_round)` for
`survey = 'Intent to Return Survey'`:

- prod minus dev: must equal the dev population model's rows for `academic_year`
  2026, and nothing else.
- dev minus prod: must return 0 rows.

Also check that the dev leader rows equal the population model's rows.

- [ ] **Step 5: Commit**

`feat(surveys): assign leader intent to return survey`.

### Task 3: Keep leaders' round out of the general reminder feed

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/surveys/rpt_extracts__survey_reminder.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/surveys/properties/rpt_extracts__survey_reminder.yml`

- [ ] **Step 1: Add the filter**

Add `and survey != 'Leader Intent to Return Survey'` to the `where`. Leaders
stay in the feed for their other incomplete surveys.

- [ ] **Step 2: Update the description**

Add that the leader survey is excluded because recruitment sends its own
reminders from the follow-up Sheet.

- [ ] **Step 3: Build in dev**

Build `rpt_tableau__survey_completion rpt_extracts__survey_reminder` in dev
(defer). Expected: the `email` unique test passes; the column list is still just
`email`.

- [ ] **Step 4: Commit**

`feat(surveys): leave leader survey out of general reminders`.

### Task 4: Follow-up Sheet extract

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__leader_intent_to_return_followup.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__leader_intent_to_return_followup.yml`
- Modify: `src/dbt/kipptaf/models/exposures/google-sheets.yml`

**Interfaces:**

- Consumes: Task 1's model; `int_surveys__survey_submissions`
  (`respondent_employee_number`, `academic_year`, `term_code`, `round_rn`).
- Produces: one row per leader in the current round with no submission. Columns,
  in order: `employee_number`, `preferred_name_lastfirst`, `job_title`,
  `department`, `business_unit`, `location`, `mail`,
  `report_to_preferred_name_lastfirst`, `report_to_mail`. `employee_number` is
  added beyond the spec's list as the grain key.

- [ ] **Step 1: Write the YAML with tests**

Contract columns with `data_type` and descriptions; `contains_pii: true` on
every column except `job_title`, `department`, `business_unit`, `location`.
`employee_number`: `unique`, `not_null`, `severity: error`.

Unit test `test_leader_followup_lists_non_submitters` (`format: sql` for the
population model, which does not exist in the warehouse yet; dict for
submissions):

- population: 201 current, 202 current, 203 current with null manager columns,
  204 with `is_current` false; all 2026 / `LITR`.
- submissions: 202 with `term_code` `LITR`, 2026, `round_rn` 1; 201 with
  `term_code` `ITR`, 2026, `round_rn` 1.
- `expect`: 201 and 203 (203 with null `report_to_*`). 201 stays because a staff
  form submission does not count.

- [ ] **Step 2: Run the unit test and confirm it fails**

Expected: error, model SQL does not exist.

- [ ] **Step 3: Write the model**

From the population model `where is_current`, `left join` submissions on
employee number, `academic_year`, `term_code = survey_round`, and `round_rn = 1`
(in the `on`); keep rows where the submission is null.

- [ ] **Step 4: Run the unit test and confirm it passes**

- [ ] **Step 5: Add the exposure**

`leader_intent_to_return_followup`, label `Leader Intent to Return Follow-up`,
`type: application`, `owner.name: Data Team`,
`depends_on: ref("rpt_gsheets__leader_intent_to_return_followup")`,
`kinds: [googlesheets]`, `url: TODO(#6251) follow-up sheet URL` until Task 6.
Copy the shape of `survey_reminder_email_feed`.

- [ ] **Step 6: Build in dev**

Expected: build, contract, and tests pass. Outside the survey window the model
returns 0 rows; that is correct.

- [ ] **Step 7: Commit**

`feat(surveys): add leader intent to return follow-up extract`.

### Task 5: Leader answers in the seat tracker and dashboard

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__seat_tracker_roster.sql:9-45`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/appsheet/properties/rpt_appsheet__seat_tracker_roster.yml`
  (`itr_response` description)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__survey_responses.sql:101`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql:111-113`

- [ ] **Step 1: Map leader answers in `itr_response`**

Filter `term_code in ('ITR', 'LITR')` and
`question_shortname in ('itr_plans', 'litr_plans')`. Add `case` branches, before
`else`, matching the start of the answer with `starts_with`:

- `This is my last school year in my current role` → `Not Returning`
- `Committed through SY 27-28` → `Returning 1 Year`
- `Committed through SY 28-29` → `Returning 2 Years`
- `Committed for the next 2+ years` → `Returning 2+ Years`

Confirm the 4 prefixes against the leader form's answers once it exists (Task
6), and fix any that differ.

- [ ] **Step 2: Update the `itr_response` description**

Name both surveys and the 3 new Returning values.

- [ ] **Step 3: Add the leader survey to the dashboard filter**

Append `'Leader Intent to Return Survey'` to the `survey_title in (...)` list at
`rpt_tableau__survey_responses.sql:101`.

- [ ] **Step 4: Classify the survey in `dim_surveys`**

Add
`struct('Leader Intent to Return Survey', 'Intent to Return', 'Staff Retention')`
next to the staff intent to return row.

- [ ] **Step 5: Build in dev**

Build the 3 models in dev (defer). Expected: all pass. `dim_surveys` will not
contain the new survey until its first submission; that is existing behavior.

- [ ] **Step 6: Commit**

`feat(surveys): map leader intent to return answers`.

### Task 6: Setup values, final checks, PR

- [ ] **Step 1: Get the setup values**

Ask the user for the 4 setup values if they are not in the ledger. Stop here
until the form URL and Sheet URL exist.

- [ ] **Step 2: Replace the placeholders**

Leader link in `rpt_tableau__survey_links.sql` (with the same `&entry.<id>=`
prefill pattern the staff form uses, if the copied form has one) and the
exposure `url`.

- [ ] **Step 3: Grep for placeholders**

Run: `rg -n 'TODO\(#6251\)' src/dbt/kipptaf`. Expected: no output.

- [ ] **Step 4: Check the seat tracker prefixes**

Compare Task 5's 4 prefixes with the form's answer choices; fix mismatches.

- [ ] **Step 5: Check the Survey Dashboard workbook**

With the Tableau MCP, find the Survey Dashboard workbook and look for a
hard-coded `survey` filter or calculated field listing survey names. If one
exists, tell the user which sheet and field need
`Leader Intent to Return Survey` added; workbook edits are theirs.

- [ ] **Step 6: Lint and full dev build**

Run
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <every changed file> </dev/null`
and fix findings. Then build every touched model plus `+1` children in dev.
Expected: all pass.

- [ ] **Step 7: Commit, push, open the PR**

PR body from `.github/pull_request_template.md`, with `Closes #6251` and the
setup steps the user still owns (terms row, extension sheet row, Zap pointing at
the new Sheet, "[deadline]" reading Friday, December 11, AppSheet's
`itr_response` allowed values). Then offer CI watch and claude-review response
per the repo CLAUDE.md.
