# Suspension Google Sheet Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `rpt_gsheets__suspensions`, one row per DeansList suspension
consequence for the current and prior academic year, and its Google Sheets
exposure.

**Architecture:** A kipptaf `rpt_` view reads
`int_deanslist__incidents__penalties`, `int_deanslist__incidents__attachments`,
and `int_extracts__student_enrollments`, the same models
`rpt_tableau__okrts_referrals` reads. Each suspension takes school and student
fields from the enrollment stint that covers its created date, falling back to
the year's `rn_year = 1` stint. The 2 DeansList reads are layer rule A1 edges,
recorded in `standard-baseline.tsv` under #5811.

**Tech Stack:** dbt (BigQuery), dbt unit tests, trunk.

**Spec:** `docs/superpowers/specs/2026-11-03-suspension-gsheet-feed-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-suspension-gsheet-feed`
  (`<wt>` below). Use `git -C <wt>` and absolute paths on every call.
- Window: `create_ts_academic_year >= {{ var("current_academic_year") - 1 }}`.
- Rows: `is_suspension` only. No referral-tier filter.
- Output `academic_year` is the display string (`2025-26`), from
  `academic_year_display`. The window filter compares the integer year.
- No `context`, `is_chronically_absent`, or `is_tier3_4` column.
- No Miami remap. Miami rows appear only once #5790 remaps upstream.
- Every join between 2 unioned models includes `_dbt_source_project` (A10).
- No `row_number() ... = 1` pick, `qualify`, or `dbt_utils.deduplicate` in the
  model (A5). Pick stints with join predicates and `rn_year`.
- SQL style: `.claude/rules/dbt-sql.md` (S1-S20). YAML:
  `.claude/rules/dbt-yaml.md`.
- dbt runs from the main checkout:
  `uv run dbt <cmd> --project-dir <wt>/src/dbt/kipptaf --target dev`, adding
  `--defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
  for builds and tests.

## Review Focus

1. An incident created on a transfer day, where one stint exits and the next
   enters, takes the entering stint's school. Unit test row `9002`.
2. An incident created outside every stint of its year (summer, after a
   withdrawal) keeps its row and takes the `rn_year = 1` stint. Unit test row
   `9003`.
3. An `incident_id` that repeats in 2 regions never pulls the other region's
   letters. Unit test fixture `kippcamden` attachment on incident `501`.
4. A suspension whose student matches no enrollment (today, every Miami row)
   drops out rather than appearing with blank student fields. Unit test row
   `9006`.
5. A suspension older than the window drops out, so the July rollover moves the
   window. Unit test row `9005`.

---

### Task 1: `rpt_gsheets__suspensions` model, contract, tests, and baseline

**Files:**

- Create:
  `<wt>/src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__suspensions.sql`
- Create:
  `<wt>/src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__suspensions.yml`
- Modify: `<wt>/src/dbt/kipptaf/standard-baseline.tsv` (2 rows, in sort order
  among the `kipptaf.rpt_gsheets__*` A1 rows)

**Interfaces:**

- Consumes: `ref("int_deanslist__incidents__penalties")`,
  `ref("int_deanslist__incidents__attachments")`,
  `ref("int_extracts__student_enrollments")`.
- Produces: model `rpt_gsheets__suspensions` with these columns and contract
  types, in this select order:

  | Column                | Type    | From                                                    |
  | --------------------- | ------- | ------------------------------------------------------- |
  | `region`              | string  | enrollment `region`                                     |
  | `school`              | string  | enrollment `school`                                     |
  | `academic_year`       | string  | enrollment `academic_year_display`                      |
  | `student_number`      | int64   | enrollment `student_number`                             |
  | `student_name`        | string  | enrollment `student_name`                               |
  | `grade_level`         | int64   | enrollment `grade_level`                                |
  | `gender`              | string  | enrollment `gender`                                     |
  | `homeroom_section`    | string  | enrollment `team`                                       |
  | `iep_status`          | string  | enrollment `iep_status`                                 |
  | `ml_status`           | string  | enrollment `ml_status`                                  |
  | `incident_id`         | int64   | penalties                                               |
  | `created_date`        | date    | `date(create_ts_date)`                                  |
  | `entry_staff`         | string  | penalties `create_lastfirst`                            |
  | `referral_tier`       | string  | penalties                                               |
  | `category`            | string  | penalties                                               |
  | `admin_summary`       | string  | penalties                                               |
  | `reported_details`    | string  | penalties                                               |
  | `nj_state_reporting`  | string  | penalties                                               |
  | `ssds_incident_id`    | string  | penalties                                               |
  | `incident_penalty_id` | int64   | penalties                                               |
  | `penalty_name`        | string  | penalties                                               |
  | `suspension_type`     | string  | penalties                                               |
  | `start_date`          | date    | penalties                                               |
  | `end_date`            | date    | penalties                                               |
  | `num_days`            | float64 | penalties                                               |
  | `suspension_letters`  | string  | attachments, `INC-LETTER` with a suspension letter name |
  | `other_uploads`       | string  | attachments, `attachment_type = 'UPLOAD'`               |

- [ ] **Step 1: Write the properties YAML with the failing unit test**

Model `description`: one row per DeansList suspension consequence for the
current and prior academic year, for the Suspensions Google Sheet; school and
student fields come from the enrollment stint covering the incident's created
date, else the student's `rn_year = 1` stint for that year; Miami 2025-26 rows
are absent until Miami DeansList ids match Focus student numbers.

Model `data_tests`, each `config: severity: error`:
`dbt_utils.unique_combination_of_columns` on `region`, `incident_penalty_id`.
Column `data_tests`, `config: severity: error`: `not_null` on `region` and
`incident_penalty_id`; sort those 2 columns to the top of `columns:`.

Every column gets `data_type` from the table above and a `description`.
`suspension_letters`: suspension letters on file for the incident, each as
`<letter name> (<upload date>)`, joined with `; ` in upload-date order.
`other_uploads`: same format from uploaded file names. `academic_year`: school
year label, for example `2025-26`.

Tag `config.meta.contains_pii: true` on every column except `region`, `school`,
`academic_year`, `incident_id`, and `incident_penalty_id`.

Unit test `unit_rpt_gsheets_suspensions_stint_window_letters`, with
`overrides: vars: current_academic_year: 2026`:

`given` `ref("int_deanslist__incidents__penalties")` rows (all
`is_suspension: true` unless stated; `_dbt_source_project: kippnewark` unless
stated):

| incident_penalty_id | incident_id | student_school_id | create_ts_academic_year | create_ts_date      | other                            |
| ------------------- | ----------- | ----------------- | ----------------------- | ------------------- | -------------------------------- |
| 9001                | 501         | 1001              | 2026                    | 2026-10-15T09:00:00 |                                  |
| 9002                | 502         | 1001              | 2026                    | 2026-10-01T09:00:00 |                                  |
| 9003                | 503         | 1002              | 2025                    | 2026-07-15T09:00:00 |                                  |
| 9004                | 504         | 1001              | 2026                    | 2026-10-20T09:00:00 | `is_suspension: false`           |
| 9005                | 505         | 1002              | 2024                    | 2024-11-01T09:00:00 |                                  |
| 9006                | 506         | 123456            | 2025                    | 2025-11-01T09:00:00 | `_dbt_source_project: kippmiami` |

`given` `ref("int_extracts__student_enrollments")` rows, all
`_dbt_source_project: kippnewark`, `region: Newark`:

| student_number | academic_year | academic_year_display | school | entrydate  | exitdate   | rn_year |
| -------------- | ------------- | --------------------- | ------ | ---------- | ---------- | ------- |
| 1001           | 2026          | 2026-27               | SA     | 2026-08-20 | 2026-10-01 | 2       |
| 1001           | 2026          | 2026-27               | SB     | 2026-10-01 | 2027-06-20 | 1       |
| 1002           | 2025          | 2025-26               | SC     | 2025-09-02 | 2026-06-20 | 1       |

`given` `ref("int_deanslist__incidents__attachments")` rows:

| \_dbt_source_project | incident_id | attachment_type | entity_name | public_filename | file_posted_at__date |
| -------------------- | ----------- | --------------- | ----------- | --------------- | -------------------- |
| kippnewark           | 501         | INC-LETTER      | OSS         | oss.pdf         | 2026-10-16T08:00:00  |
| kippnewark           | 501         | UPLOAD          | null        | letter.pdf      | 2026-10-17T08:00:00  |
| kippcamden           | 501         | INC-LETTER      | OSS         | oss.pdf         | 2026-10-20T08:00:00  |

`expect` rows, columns `incident_penalty_id`, `school`, `academic_year`,
`suspension_letters`, `other_uploads`:

| incident_penalty_id | school | academic_year | suspension_letters | other_uploads           |
| ------------------- | ------ | ------------- | ------------------ | ----------------------- |
| 9001                | SB     | 2026-27       | OSS (2026-10-16)   | letter.pdf (2026-10-17) |
| 9002                | SB     | 2026-27       | null               | null                    |
| 9003                | SC     | 2025-26       | null               | null                    |

Fixture scalars stay unquoted (yamllint).

- [ ] **Step 2: Run the unit test to verify it fails**

Run (own Bash call first): `uv run dbt deps --project-dir <wt>/src/dbt/kipptaf`

Run:
`uv run dbt test --select "rpt_gsheets__suspensions,test_type:unit" --project-dir <wt>/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`

Expected: FAIL, because the unit test names a model that does not exist yet.

- [ ] **Step 3: Write `rpt_gsheets__suspensions.sql`**

CTEs, in order:

- `suspensions`: penalties columns from the table above plus
  `_dbt_source_project`, `student_school_id`, `create_ts_academic_year`, and
  `date(create_ts_date) as created_date`; `where is_suspension` and the window
  filter.
- `enrollment_picks`: one row per suspension, carrying `incident_penalty_id`,
  `_dbt_source_project`, and the picked stint's `entrydate`:

  ```sql
  coalesce(ed.entrydate, ey.entrydate) as entrydate
  -- ed: left join enrollments on student, academic year, project,
  --     ed.entrydate <= s.created_date and ed.exitdate > s.created_date
  -- ey: left join enrollments on student, academic year, project,
  --     ey.rn_year = 1
  ```

- `attachments`: per attachment, `incident_id`, `_dbt_source_project`,
  `file_posted_at__date`, `entity_name`, `public_filename`,
  `format_datetime('%F', file_posted_at__date) as posted_date`,
  `is_suspension_letter` (`attachment_type = 'INC-LETTER'` and `entity_name` in
  the 7 names `rpt_tableau__okrts_referrals` lists in its `attachments` CTE),
  and `is_upload` (`attachment_type = 'UPLOAD'`).
- `attachment_labels`: `suspension_letter_label` is
  `concat(entity_name, ' (', posted_date, ')')` when `is_suspension_letter`,
  else null; `upload_label` is the same from `public_filename` when `is_upload`.
- `attachment_rollup`: grouped by `incident_id`, `_dbt_source_project`;
  `string_agg(<label>, '; ' order by file_posted_at__date)` for
  `suspension_letters` and `other_uploads`. `string_agg` skips the null labels.

Final select: `suspensions` inner join `enrollment_picks` on
`incident_penalty_id` and `_dbt_source_project`, inner join
`int_extracts__student_enrollments` on student, academic year, project, and
`entrydate`, left join `attachment_rollup` on `incident_id` and
`_dbt_source_project`. Columns in the table's order, enumerated (A9).

- [ ] **Step 4: Run the unit test to verify it passes**

Run the Step 2 test command. Expected: PASS, 1 unit test.

- [ ] **Step 5: Build the model and run its data tests**

Run:
`uv run dbt build --select rpt_gsheets__suspensions --project-dir <wt>/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`

Expected: PASS for the unit test, the view, `unique_combination_of_columns`, and
both `not_null` tests.

- [ ] **Step 6: Reconcile against DeansList for NJ**

Find the dev schema:
`select schema_name from \`teamster-332318\`.INFORMATION_SCHEMA.SCHEMATA where
schema_name like 'zz_%kipptaf_extracts'`.

Query the dev view and `kipptaf_deanslist.int_deanslist__incidents__penalties`
(`is_suspension`, window years, NJ projects) in 1 statement, counting rows per
region and academic year on each side.

Expected: the counts match for every NJ region and year, Miami has 0 rows in the
dev view, and `count(*)` equals the distinct (`region`, `incident_penalty_id`)
count.

- [ ] **Step 7: Add the baseline rows**

Add, tab-separated:

```text
kipptaf.rpt_gsheets__suspensions	A1	kipptaf.int_deanslist__incidents__attachments	#5811
kipptaf.rpt_gsheets__suspensions	A1	kipptaf.int_deanslist__incidents__penalties	#5811
```

- [ ] **Step 8: Lint**

Run from `<wt>`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__suspensions.sql src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__suspensions.yml </dev/null`

Expected: no lint issues (formatting-only findings are the commit hook's).

- [ ] **Step 9: Commit**

```bash
git -C <wt> add src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__suspensions.sql src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__suspensions.yml
git -C <wt> add -u
git -C <wt> commit -F <scratchpad>/commit-msg-suspension-model.txt
```

Message: `feat(dbt): add rpt_gsheets__suspensions feed`, body `Refs #6245`, then
the attribution line.

- [ ] **Step 10: Run the layer check**

Run, each in its own call:

- `git -C <wt> diff -U0 --no-renames origin/main...HEAD > <scratchpad>/suspension-pr.diff`
- `uv run dbt parse --project-dir <wt>/src/dbt/kipptaf`
- `VIRTUAL_ENV= uv --directory <wt> run python <wt>/scripts/check_dbt_standard.py --project-dir src/dbt/kipptaf --diff <scratchpad>/suspension-pr.diff`

Expected: no new violations and no stale baseline rows. Fix any finding in a new
commit.

### Task 2: Google Sheets exposure

**Files:**

- Modify: `<wt>/src/dbt/kipptaf/models/exposures/google-sheets.yml`

**Interfaces:**

- Consumes: `rpt_gsheets__suspensions` from Task 1.
- Produces: exposure `rpt_gsheets__suspensions`.

Blocked until the user gives the Sheet URL. Ask for it; never invent one.

- [ ] **Step 1: Add the exposure**

Next to the other `rpt_gsheets__*` exposures: `name: rpt_gsheets__suspensions`,
`label: Suspensions`, `type: analysis`, `owner.name: Data Team`, `url:` the
user's Sheet URL, `depends_on: [ref("rpt_gsheets__suspensions")]`,
`config.meta.dagster.kinds: [googlesheets]`.

- [ ] **Step 2: Verify it parses and passes the layer check**

Run
`uv run dbt ls --select exposure:rpt_gsheets__suspensions --project-dir <wt>/src/dbt/kipptaf`.
Expected: 1 exposure listed.

- [ ] **Step 3: Lint and commit**

Lint `src/dbt/kipptaf/models/exposures/google-sheets.yml` as in Task 1 Step 8.
Commit `feat(dbt): add suspensions Google Sheet exposure`, body `Refs #6245`,
then the attribution line.

- [ ] **Step 4: Re-run the layer check**

Re-run Task 1 Step 10. Expected: no A8 violation.
