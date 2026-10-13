# Survey Submissions From Response Grain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `int_surveys__survey_submissions` read response-grain sources
instead of collapsing the 4.1M-row question-grain view, and make
`int_surveys__survey_responses` read submissions for its per-submission columns.

**Architecture:** Dependency inversion between 2 dbt models in
`src/dbt/kipptaf/models/surveys/intermediate/`. Submissions becomes the single
owner of respondent and reporting-term resolution (roster joins, alias map,
terms join, `round_rn`) at 1 row per response. `survey_responses` inner-joins
submissions on (`survey_id`, `survey_response_id`) and keeps its output columns
unchanged, so its 7 consumers need no edits. A `mutually_exclusive_ranges` test
on the reporting-terms sheet plus a sheet fix close #5276.

**Tech Stack:** dbt 1.x on BigQuery, `dbt_utils`, `uv`, trunk (sqlfluff, sqlfmt,
yamllint, markdownlint), BigQuery MCP for verification queries.

Spec:
`docs/superpowers/specs/2026-09-14-survey-submissions-response-grain-design.md`.
Refs #5277, #5276.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain`.
  Every git call is `git -C <worktree>`; every file path is under the worktree,
  spelled out absolute.
- Every dbt call is `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf`,
  run from cwd `/workspaces/teamster`. Never bare `dbt`. Never `--target prod`.
- Dev builds use
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  The `--state` path must be absolute.
- Dev relations land in `zz_cbini_kipptaf_<schema>` (for example
  `zz_cbini_kipptaf_surveys`, `zz_cbini_kipptaf_marts`). Confirm with
  `select schema_name from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA where schema_name like 'zz_cbini_kipptaf%'`
  before trusting a comparison.
- SQL conventions in `.claude/rules/dbt-sql.md`: ST06 column order (plain refs,
  then casts, then literals, then simple functions, then nested, then window),
  no calculations in join predicates (precompute as a named column), no
  `qualify`, no `select *` in union branches, `cast(null as <type>)` padding in
  union branches, trailing commas.
- YAML conventions in `.claude/rules/dbt-yaml.md`: every new column gets a
  `description`; columns with per-column `data_tests` sort to the top; PII
  columns carry `config.meta.contains_pii: true`.
- Open every `src/dbt/` file with the Read tool, not `cat`.
- Before each commit:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. Fix or `trunk-ignore` every finding.
- Commit messages end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. If the commit hook
  blocks a `-m` message, write it to
  `/workspaces/teamster/.claude/scratch/commit-msg.txt` and use `-F`.
- Never emit PII values (emails, names, employee numbers) in commits, PR text,
  or issue comments. Aggregates only.
- Behavior preservation is the bar. The only accepted row-set change is the 4
  phantom null-`response_id` submissions disappearing. Any other delta stops the
  task and gets reported.

---

## File Structure

| File                                                                                              | Change  | Responsibility                                                              |
| ------------------------------------------------------------------------------------------------- | ------- | --------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml` | Modify  | Add `mutually_exclusive_ranges` test on `SURVEY` rows                       |
| `src/dbt/kipptaf/models/alchemer/sources-bigquery.yml`                                            | Modify  | Declare `stg_alchemer__survey_response` and `stg_alchemer__survey_campaign` |
| `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_submissions.sql`                 | Rewrite | Response-grain live arms; owns roster, terms, `round_rn`, link              |
| `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_submissions.yml`      | Modify  | Drop cron, describe 8 new columns, update model description                 |
| `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`                   | Rewrite | Join submissions instead of roster and terms                                |
| `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`        | Modify  | Description reflects the new source of per-submission columns               |

---

### Task 1: Reporting-terms overlap test

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml`
  (model-level `data_tests`, after the second `unique_combination_of_columns`
  block, before `columns:`)

**Interfaces:**

- Consumes: nothing.
- Produces: test node
  `dbt_utils_mutually_exclusive_ranges_stg_google_sheets__reporting__terms_...`.
  Task 5 expects it to fail with 1 row until the sheet is fixed.

- [ ] **Step 1: Run the existing tests to record the baseline**

Run from `/workspaces/teamster`:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf
uv run dbt test --select stg_google_sheets__reporting__terms --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: 2 tests, both PASS. (The `--defer` runs them against the prod
relation; no dev build needed.)

- [ ] **Step 2: Add the test**

Read the YAML file, then insert after the existing second
`dbt_utils.unique_combination_of_columns` block (the one ending
`severity: error` under `grade_band`) and before `columns:`:

```yaml
# A SURVEY submission resolves its term by joining its submit date into
# these windows on name alone. Two same-name windows that overlap fan
# that join out and hand the submission two academic years. #5276
- dbt_utils.mutually_exclusive_ranges:
    arguments:
      lower_bound_column: start_date
      upper_bound_column: end_date
      partition_by: name
      gaps: allowed
    config:
      severity: error
      where: type = 'SURVEY'
```

- [ ] **Step 3: Run the tests and confirm the new one fails on exactly the known
      pair**

```bash
uv run dbt test --select stg_google_sheets__reporting__terms --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: 3 tests. The 2 existing PASS. The new `mutually_exclusive_ranges` test
FAILS with `Got 1 result`. That 1 row is the `KTAF Support Survey` 2025/2026
pair; the sheet owner fixes it outside this PR (see Task 5). A result other than
1 means a second overlap appeared since 2026-09-14: stop and report.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain commit -m "test(surveys): fail when SURVEY reporting-term windows overlap

Refs #5276.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Declare the 2 missing Alchemer sources

**Files:**

- Modify: `src/dbt/kipptaf/models/alchemer/sources-bigquery.yml`

**Interfaces:**

- Produces: `source("alchemer", "stg_alchemer__survey_response")` and
  `source("alchemer", "stg_alchemer__survey_campaign")`, used by Task 3.

- [ ] **Step 1: Add the tables**

Read the file. Replace its `tables:` list so the file reads:

```yaml
sources:
  - name: alchemer
    schema: kipptaf_alchemer
    tables:
      - name: base_alchemer__survey_results
        config:
          meta:
            dagster:
              asset_key:
                - kipptaf
                - alchemer
                - base_alchemer__survey_results
      - name: stg_alchemer__survey
      - name: stg_alchemer__survey_campaign
      - name: stg_alchemer__survey_question
      - name: stg_alchemer__survey_response
```

The Alchemer integration is disabled at project level
(`alchemer: +enabled: false` in `dbt_project.yml`), so these frozen tables are
read via `source()`, matching how `base_alchemer__survey_results` and
`stg_alchemer__survey` already are.

- [ ] **Step 2: Parse to confirm the sources resolve**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev
uv run dbt ls --resource-type source --select "source:alchemer.*" --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev
```

Expected: parse succeeds; `ls` prints 5 sources including
`source:kipptaf.alchemer.stg_alchemer__survey_response` and
`source:kipptaf.alchemer.stg_alchemer__survey_campaign`.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/alchemer/sources-bigquery.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain commit -m "chore(alchemer): declare survey_response and survey_campaign frozen tables as sources

Refs #5277.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Rewrite `int_surveys__survey_submissions` at response grain

**Files:**

- Rewrite:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_submissions.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_submissions.yml`

**Interfaces:**

- Consumes: Task 2's 2 sources; `stg_google_forms__responses` (columns
  `form_id`, `response_id`, `respondent_email`, `create_timestamp`,
  `last_submitted_timestamp`); `stg_google_forms__form` (`form_id`,
  `info_title`); `stg_google_sheets__reporting__terms`;
  `int_people__staff_roster_history`; `stg_google_directory__users`;
  `int_surveys__manager_survey_details` (archive arm, unchanged).
- Produces: table `int_surveys__survey_submissions` with columns, in this order:
  `survey_id string`, `survey_response_id string`, `survey_title string`,
  `respondent_email string`, `respondent_employee_number int64`,
  `respondent_preferred_name string`, `respondent_samaccountname string`,
  `respondent_userprincipalname string`, `date_started timestamp`,
  `date_submitted timestamp`, `academic_year int64`, `term_code string`,
  `term_name string`, `survey_response_link string`, `round_rn int64`,
  `respondent_identifier string`, `survey_submission_key string`. Task 4 joins
  on (`survey_id`, `survey_response_id`) and selects every column except the
  key.

- [ ] **Step 1: Record the prod baseline the build must reproduce**

Run via BigQuery MCP:

```sql
with
    cur_ranked as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            academic_year,
            term_code,
            term_name,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            survey_response_link,
            round_rn,
            respondent_identifier,
            row_number() over (
                partition by survey_id, survey_response_id order by survey_question_id
            ) as rn,
        from `teamster-332318`.kipptaf_surveys.int_surveys__survey_responses
    )
select
    count(*) as live_submissions,
    countif(survey_response_id is null) as phantom_rows,
    bit_xor(farm_fingerprint(concat(survey_id, '|', coalesce(survey_response_id, '')))) as key_fp,
from cur_ranked
where rn = 1
```

Write the 3 numbers down. `phantom_rows` was 4 on 2026-09-14.

- [ ] **Step 2: Write the new model SQL**

Replace the whole file `int_surveys__survey_submissions.sql` with:

```sql
with
    gdir_alias_map as (
        select gd.primary_email, addr.address as known_address,
        from {{ ref("stg_google_directory__users") }} as gd, unnest(gd.emails) as addr
        union distinct
        select gd.primary_email, alias,
        from {{ ref("stg_google_directory__users") }} as gd, unnest(gd.aliases) as alias
        union distinct
        select gd.primary_email, gd.primary_email as known_address,
        from {{ ref("stg_google_directory__users") }} as gd
    ),

    /*
     * The terms join keys on the UTC date, which is what date() of the raw
     * string resolved to before this model read staging directly. The local
     * date differs on submissions near midnight; switching is a behavior
     * change for another issue.
     */
    gforms_responses as (
        select
            form_id,
            response_id,
            respondent_email,
            create_timestamp,
            last_submitted_timestamp,

            date(last_submitted_timestamp) as last_submitted_date,

            lower(regexp_extract(respondent_email, r'^([^@]+)')) as respondent_local_part,
        from {{ ref("stg_google_forms__responses") }}
    ),

    live_gforms as (
        select
            r.form_id as survey_id,
            r.response_id as survey_response_id,
            r.respondent_email,
            r.create_timestamp as date_started,
            r.last_submitted_timestamp as date_submitted,

            f.info_title as survey_title,

            rt.academic_year,
            rt.code as term_code,
            rt.name as term_name,

            coalesce(
                srh.employee_number, srh_alias.employee_number
            ) as respondent_employee_number,
            coalesce(
                srh.formatted_name, srh_alias.formatted_name
            ) as respondent_preferred_name,
            coalesce(
                srh.sam_account_name, srh_alias.sam_account_name
            ) as respondent_samaccountname,
            coalesce(
                srh.user_principal_name, srh_alias.user_principal_name
            ) as respondent_userprincipalname,

            concat(
                'https://docs.google.com/forms/d/',
                r.form_id,
                '/edit#response=',
                r.response_id
            ) as survey_response_link,

            dense_rank() over (
                partition by r.respondent_email, rt.academic_year, rt.code, r.form_id
                order by r.last_submitted_timestamp desc
            ) as round_rn,
        from gforms_responses as r
        inner join {{ ref("stg_google_forms__form") }} as f on r.form_id = f.form_id
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on f.info_title = rt.name
            and r.last_submitted_date between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                r.respondent_local_part = srh.sam_account_name
                or r.respondent_email = srh.google_email
            )
            and r.last_submitted_timestamp
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join
            gdir_alias_map as gam
            on srh.employee_number is null
            and r.respondent_email = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and r.last_submitted_timestamp
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
    ),

    alchemer_responses as (
        select
            sr.survey_id,
            sr.session_id,
            sr.date_started,
            sr.date_submitted,

            sr.id as response_id,

            s.title as survey_title,
            s.link_default as survey_link_default,

            date(sr.date_submitted) as date_submitted_date,
        from {{ source("alchemer", "stg_alchemer__survey_response") }} as sr
        inner join {{ source("alchemer", "stg_alchemer__survey") }} as s on sr.survey_id = s.id
    ),

    alchemer_identifiers as (
        select
            survey_id,
            response_id,
            respondent_mail,

            lower(regexp_extract(respondent_mail, r'^([^@]+)')) as respondent_local_part,
        from {{ source("surveys", "int_surveys__response_identifiers") }}
    ),

    /*
     * Inner join to reporting terms: an Alchemer response outside every
     * SURVEY window is not a submission, as before this model read the
     * response-grain tables directly.
     */
    live_alchemer as (
        select
            sr.survey_title,
            sr.date_started,
            sr.date_submitted,

            ri.respondent_mail as respondent_email,

            rt.name as term_name,

            cast(sr.survey_id as string) as survey_id,
            cast(sr.response_id as string) as survey_response_id,

            1 as round_rn,

            coalesce(sc.fiscal_year - 1, rt.academic_year) as academic_year,
            coalesce(regexp_extract(sc.name, r'\s(.*)'), rt.code) as term_code,

            coalesce(
                srh.employee_number, srh_alias.employee_number
            ) as respondent_employee_number,
            coalesce(
                srh.formatted_name, srh_alias.formatted_name
            ) as respondent_preferred_name,
            coalesce(
                srh.sam_account_name, srh_alias.sam_account_name
            ) as respondent_samaccountname,
            coalesce(
                srh.user_principal_name, srh_alias.user_principal_name
            ) as respondent_userprincipalname,

            concat(
                sr.survey_link_default, '?snc=', sr.session_id, '&sg_navigate=start'
            ) as survey_response_link,
        from alchemer_responses as sr
        left join
            {{ source("alchemer", "stg_alchemer__survey_campaign") }} as sc
            on sr.survey_id = sc.survey_id
            and sr.date_started between sc.link_open_date and sc.link_close_date
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.name
            and sr.date_submitted_date between rt.start_date and rt.end_date
        left join
            alchemer_identifiers as ri
            on sr.survey_id = ri.survey_id
            and sr.response_id = ri.response_id
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                ri.respondent_local_part = srh.sam_account_name
                or ri.respondent_mail = srh.google_email
            )
            and sr.date_submitted
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join
            gdir_alias_map as gam
            on srh.employee_number is null
            and ri.respondent_mail = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and sr.date_submitted
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    archive_source as (
        select
            survey_id,
            survey_title,
            respondent_email,
            date_submitted,
            campaign_academic_year,
            campaign_reporting_term,
            respondent_df_employee_number,
            effective_survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }}
        where
            survey_id = 'historic_alchemer_Manager_survey'
            and campaign_academic_year is not null
    ),

    /*
     * int_surveys__manager_survey_details is question-grain, so the archive
     * arrives at 18 rows per submission. Every column selected is constant
     * within the partition.
     */
    archive_submissions as (
        {{
            dbt_utils.deduplicate(
                relation="archive_source",
                partition_by="survey_id, effective_survey_response_id",
                order_by="respondent_df_employee_number",
            )
        }}
    ),

    all_submissions as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            academic_year,
            term_code,
            term_name,
            survey_response_link,
            round_rn,
        from live_gforms

        union all

        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            academic_year,
            term_code,
            term_name,
            survey_response_link,
            round_rn,
        from live_alchemer

        union all

        select
            survey_id,

            effective_survey_response_id as survey_response_id,

            survey_title,
            respondent_email,

            respondent_df_employee_number as respondent_employee_number,

            cast(null as string) as respondent_preferred_name,
            cast(null as string) as respondent_samaccountname,
            cast(null as string) as respondent_userprincipalname,
            cast(null as timestamp) as date_started,

            date_submitted,

            campaign_academic_year as academic_year,
            campaign_reporting_term as term_code,

            cast(null as string) as term_name,
            cast(null as string) as survey_response_link,
            cast(null as int) as round_rn,
        from archive_submissions
    )

select
    survey_id,
    survey_response_id,
    survey_title,
    respondent_email,
    respondent_employee_number,
    respondent_preferred_name,
    respondent_samaccountname,
    respondent_userprincipalname,
    date_started,
    date_submitted,
    academic_year,
    term_code,
    term_name,
    survey_response_link,
    round_rn,

    coalesce(
        cast(respondent_employee_number as string), respondent_email
    ) as respondent_identifier,

    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,
from all_submissions
```

Column names were verified against `kipptaf_alchemer.INFORMATION_SCHEMA.COLUMNS`
on 2026-09-14: `stg_alchemer__survey` has `id` (INT64), `title`, `link_default`;
`stg_alchemer__survey_campaign` has `survey_id` (INT64), `name`, `fiscal_year`
(INT64), `link_open_date` and `link_close_date` (TIMESTAMP). The frozen tables
do not change, so no re-check is needed.

- [ ] **Step 3: Update the properties YAML**

Replace the whole file `properties/int_surveys__survey_submissions.yml` with:

```yaml
models:
  - name: int_surveys__survey_submissions
    description: >-
      Canonical submission grain for every survey the network runs. One row per
      submission, across the live Google Forms and Alchemer feeds and the
      historic Alchemer Manager Survey archive.

      This model owns survey_submission_key and every per-submission derived
      column — survey title, reporting term, respondent identity resolved
      against the staff roster history, and round_rn. The live arms read the
      response-grain staging tables directly, so nothing collapses here.
      int_surveys__survey_responses joins this model for those columns rather
      than deriving them per question row.

      The live arm carries every survey title, not only the titles the marts
      currently model, so a new survey becomes available to a consumer without
      touching this model.

      Eager table. Google Forms responses land on a 15-minute sensor and the
      survey dashboard refreshes hourly through int_surveys__survey_responses,
      so this model rebuilds when its inputs change rather than on a nightly
      cron.
    config:
      materialized: table
    columns:
      - name: survey_submission_key
        description: >-
          Surrogate key derived from survey_id and survey_response_id. Primary
          key. For the historic archive, survey_response_id is the deterministic
          fallback described below, so the composition is identical across all
          arms.
        data_tests:
          - unique

      - name: survey_id
        description: >-
          Identifier of the survey itself — the Google Forms form id, the
          stringified Alchemer survey id, or the literal
          historic_alchemer_Manager_survey for the archive.

      - name: survey_response_id
        description: >-
          Identifier of the individual submission. On the historic Manager
          archive the source records no response id, so this carries the
          deterministic fallback built from respondent, subject and reporting
          term.

      - name: survey_title
        description: >-
          Display title of the survey, as the source system records it. Google
          Forms takes the form's info title; Alchemer takes the survey title.

      - name: respondent_email
        description: >-
          Email the respondent submitted under. Null on the historic Manager
          archive, which records no respondent email, and on Alchemer responses
          absent from the frozen response-identifiers table.
        config:
          meta:
            contains_pii: true

      - name: respondent_employee_number
        description: >-
          Employee number of the respondent, resolved against the staff roster
          history at the time of submission, first by email or account name and
          then through Google Directory aliases. Null when the respondent could
          not be matched to a staff record.
        config:
          meta:
            contains_pii: true

      - name: respondent_preferred_name
        description: >-
          Formatted name of the respondent from the same roster-history match as
          respondent_employee_number. Null on the archive arm.
        config:
          meta:
            contains_pii: true

      - name: respondent_samaccountname
        description: >-
          Active Directory account name of the respondent from the roster match.
          Null on the archive arm.
        config:
          meta:
            contains_pii: true

      - name: respondent_userprincipalname
        description: >-
          Active Directory user principal name of the respondent from the roster
          match. Null on the archive arm.
        config:
          meta:
            contains_pii: true

      - name: respondent_identifier
        description: >-
          Respondent employee number as a string, falling back to the respondent
          email when no staff record matched.
        config:
          meta:
            contains_pii: true

      - name: date_started
        description: >-
          Timestamp the respondent opened the survey. Null on the archive arm.

      - name: date_submitted
        description: Timestamp the respondent submitted the survey.

      - name: academic_year
        description: >-
          Academic year the submission falls in. Google Forms resolves it from
          the SURVEY reporting-terms windows by title and UTC submit date.
          Alchemer takes the campaign fiscal year minus one and falls back to
          the reporting-terms window. The archive carries the campaign year.

      - name: term_code
        description: >-
          Reporting term code the submission falls in, for example MGR1 or MGR2
          on the Manager Survey. Alchemer takes it from the campaign name and
          falls back to the reporting-terms window.

      - name: term_name
        description: >-
          Reporting-terms sheet name the submission matched. Null on the archive
          arm.

      - name: survey_response_link
        description: >-
          Deep link to the individual response in the source system. Null on the
          archive arm.

      - name: round_rn
        description: >-
          Recency rank of this submission among the same respondent's
          submissions to the same form in the same reporting term, 1 being the
          latest. Always 1 on Alchemer. Null on the archive arm.
```

- [ ] **Step 4: Build into dev**

```bash
uv run dbt build --select int_surveys__survey_submissions --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: model builds; the `unique` test on `survey_submission_key` FAILS with
`Got 68 results` while the sheet still has the overlapping `KTAF Support Survey`
windows (the 68 duplicated keys), and PASSES once the sheet is fixed. Any other
count: stop and diagnose before continuing. Confirm the dev schema with the
`SCHEMATA` query in Global Constraints.

- [ ] **Step 5: Compare dev against the prod baseline**

Run via BigQuery MCP (replace the schema if `SCHEMATA` showed a different one):

```sql
with
    cur_ranked as (
        select
            survey_id,
            survey_response_id,
            survey_title,
            respondent_email,
            academic_year,
            term_code,
            term_name,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            survey_response_link,
            round_rn,
            respondent_identifier,
            row_number() over (
                partition by survey_id, survey_response_id order by survey_question_id
            ) as rn,
        from `teamster-332318`.kipptaf_surveys.int_surveys__survey_responses
    ),
    cur as (select * except (rn) from cur_ranked where rn = 1),
    cand as (
        select *
        from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_submissions
        where survey_id != 'historic_alchemer_Manager_survey'
    ),
    cand_dedup as (
        select * except (rn)
        from (
            select *, row_number() over (partition by survey_id, survey_response_id) as rn
            from cand
        )
        where rn = 1
    ),
    j as (
        select
            c.survey_id is not null as in_cur,
            k.survey_id is not null as in_cand,
            c.survey_response_id is null as cur_phantom,
            c.survey_title is distinct from k.survey_title as d_title,
            c.respondent_email is distinct from k.respondent_email as d_email,
            c.academic_year is distinct from k.academic_year as d_ay,
            c.term_code is distinct from k.term_code as d_term,
            c.term_name is distinct from k.term_name as d_term_name,
            c.respondent_employee_number is distinct from k.respondent_employee_number as d_emp,
            c.respondent_preferred_name is distinct from k.respondent_preferred_name as d_pref,
            c.respondent_samaccountname is distinct from k.respondent_samaccountname as d_sam,
            c.respondent_userprincipalname is distinct from k.respondent_userprincipalname as d_upn,
            c.date_started is distinct from k.date_started as d_started,
            c.date_submitted is distinct from k.date_submitted as d_submitted,
            c.survey_response_link is distinct from k.survey_response_link as d_link,
            c.round_rn is distinct from k.round_rn as d_round,
            c.respondent_identifier is distinct from k.respondent_identifier as d_ident,
        from cur as c
        full outer join cand_dedup as k
            on c.survey_id = k.survey_id and c.survey_response_id = k.survey_response_id
    )
select
    countif(in_cur and not in_cand) as only_cur,
    countif(in_cur and not in_cand and cur_phantom) as only_cur_phantom,
    countif(not in_cur and in_cand) as only_cand,
    countif(in_cur and in_cand) as both_,
    countif(in_cur and in_cand and d_title) as d_title,
    countif(in_cur and in_cand and d_email) as d_email,
    countif(in_cur and in_cand and d_ay) as d_ay,
    countif(in_cur and in_cand and d_term) as d_term,
    countif(in_cur and in_cand and d_term_name) as d_term_name,
    countif(in_cur and in_cand and d_emp) as d_emp,
    countif(in_cur and in_cand and d_pref) as d_pref,
    countif(in_cur and in_cand and d_sam) as d_sam,
    countif(in_cur and in_cand and d_upn) as d_upn,
    countif(in_cur and in_cand and d_started) as d_started,
    countif(in_cur and in_cand and d_submitted) as d_submitted,
    countif(in_cur and in_cand and d_link) as d_link,
    countif(in_cur and in_cand and d_round) as d_round,
    countif(in_cur and in_cand and d_ident) as d_ident,
    (select count(*) from cand) as cand_rows,
    (select count(*) from cand_dedup) as cand_keys,
from j
```

Expected while the sheet is unfixed: `only_cur` = `only_cur_phantom` = 4,
`only_cand` = 0, every `d_*` = 0 except `d_ay` ≤ 68 and `d_term_name` ≤ 68 (the
ambiguous pair shares `term_code` `KTAF` so `d_term` stays 0), `cand_rows` =
`cand_keys` + 68. After the sheet fix: every `d_*` = 0 and `cand_rows` =
`cand_keys`. `only_cand` > 0 or any other `d_*` > 0 means the rewrite changed
behavior: stop and report which column.

Also check the archive arm did not move:

```sql
select
    (select count(*) from `teamster-332318`.kipptaf_surveys.int_surveys__survey_submissions where survey_id = 'historic_alchemer_Manager_survey') as prod_archive,
    (select count(*) from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_submissions where survey_id = 'historic_alchemer_Manager_survey') as dev_archive,
    (select bit_xor(farm_fingerprint(survey_submission_key)) from `teamster-332318`.kipptaf_surveys.int_surveys__survey_submissions where survey_id = 'historic_alchemer_Manager_survey') as prod_fp,
    (select bit_xor(farm_fingerprint(survey_submission_key)) from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_submissions where survey_id = 'historic_alchemer_Manager_survey') as dev_fp
```

Expected: `prod_archive` = `dev_archive` and `prod_fp` = `dev_fp`.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_submissions.sql src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_submissions.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain commit -m "perf(surveys): build survey submissions from response grain

Read stg_google_forms__responses and the frozen Alchemer response tables
directly instead of collapsing the 4.1M-row question-grain view. The model
now owns respondent and reporting-term resolution and round_rn at 1 row per
response, and rebuilds eagerly so the hourly survey dashboard stays fresh.

Refs #5277.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `int_surveys__survey_responses` joins submissions

**Files:**

- Rewrite:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`
  (description only)

**Interfaces:**

- Consumes: Task 3's table and its column names verbatim.
- Produces: view `int_surveys__survey_responses` with the same 24 output columns
  as today (see the properties YAML `columns:` list). Column order in the view
  changes; every consumer selects by name.

- [ ] **Step 1: Record the prod baseline for the question grain**

Run via BigQuery MCP:

```sql
select
    count(*) as rows_,
    countif(survey_response_id is null) as phantom_rows,
    bit_xor(farm_fingerprint(concat(
        survey_id, '|', coalesce(survey_response_id, ''), '|', coalesce(survey_question_id, ''), '|',
        coalesce(question_shortname, ''), '|', coalesce(answer, '')
    ))) as grain_fp,
from `teamster-332318`.kipptaf_surveys.int_surveys__survey_responses
```

Write the 3 numbers down.

- [ ] **Step 2: Write the new model SQL**

Replace the whole file `int_surveys__survey_responses.sql` with:

```sql
with
    alchemer_results as (
        select
            survey_title,
            question_title_english,
            question_short_name,
            response_value,

            cast(survey_id as string) as survey_id,
            cast(response_id as string) as survey_response_id,
            cast(question_id as string) as survey_question_id,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
    ),

    enriched as (
        select
            fr.form_id as survey_id,
            fr.response_id as survey_response_id,
            fr.question_id as survey_question_id,
            fr.item_title as question_title,
            fr.item_abbreviation as question_shortname,

            ss.survey_title,
            ss.respondent_email,
            ss.academic_year,
            ss.term_code,
            ss.term_name,
            ss.respondent_employee_number,
            ss.respondent_preferred_name,
            ss.respondent_samaccountname,
            ss.respondent_userprincipalname,
            ss.date_started,
            ss.date_submitted,
            ss.survey_response_link,
            ss.round_rn,
            ss.respondent_identifier,

            safe_cast(fr.text_value as numeric) as answer_value,

            coalesce(fr.text_value, fr.file_upload_file_name) as answer,

            if(safe_cast(fr.text_value as int) is null, 1, 0) as is_open_ended,
        from {{ ref("int_google_forms__form_responses") }} as fr
        inner join
            {{ ref("int_surveys__survey_submissions") }} as ss
            on fr.form_id = ss.survey_id
            and fr.response_id = ss.survey_response_id

        union all

        select
            sr.survey_id,
            sr.survey_response_id,
            sr.survey_question_id,

            sr.question_title_english as question_title,
            sr.question_short_name as question_shortname,

            ss.survey_title,
            ss.respondent_email,
            ss.academic_year,
            ss.term_code,
            ss.term_name,
            ss.respondent_employee_number,
            ss.respondent_preferred_name,
            ss.respondent_samaccountname,
            ss.respondent_userprincipalname,
            ss.date_started,
            ss.date_submitted,
            ss.survey_response_link,
            ss.round_rn,
            ss.respondent_identifier,

            safe_cast(sr.response_value as numeric) as answer_value,

            sr.response_value as answer,

            if(safe_cast(sr.response_value as int) is null, 1, 0) as is_open_ended,
        from alchemer_results as sr
        inner join
            {{ ref("int_surveys__survey_submissions") }} as ss
            on sr.survey_id = ss.survey_id
            and sr.survey_response_id = ss.survey_response_id
    ),

    question_departments as (
        /* the crosswalk is already one row per abbreviation, so this joins at
           grain with no projection. Lowered on both sides because sheet entry is
           not case-constrained; the crosswalk's unique_lowered_abbreviation test
           is what keeps lowering from collapsing two rows into a fan-out. */
        select
            rated_department_code,
            rated_department_name,

            lower(abbreviation) as question_shortname,
        from {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
        where abbreviation is not null
    )

select e.*, qd.rated_department_code, qd.rated_department_name,
from enriched as e
left join
    question_departments as qd on lower(e.question_shortname) = qd.question_shortname
```

Note `answer` sits after `answer_value` in the Google Forms branch because ST06
orders `safe_cast` before `coalesce`; the Alchemer branch mirrors that position
so the union binds by position. `answer` in the Alchemer branch is a plain
column ref placed among functions to hold its union position; if sqlfluff ST06
flags it, add
`-- trunk-ignore(sqlfluff/ST06): union position must match the Google Forms branch`
on the line above it.

- [ ] **Step 3: Update the description**

In `properties/int_surveys__survey_responses.yml`, replace the model
`description` with:

```yaml
description: >-
  Unioned raw response grain across Google Forms and Alchemer sources. One row
  per (survey_id, survey_response_id, survey_question_id, question_shortname,
  answer). Google Forms grid and check-all-that-apply questions produce multiple
  rows per (response, question_id) — one per row shortname or selected option —
  so the natural grain extends to shortname + answer. File-upload questions emit
  one row per uploaded file with the filename projected into `answer`. Marts
  that need per-shortname or per-question rollups project to that grain
  themselves.

  Every per-submission column — survey title, respondent identity, reporting
  term, dates, response link and round_rn — is selected through from
  int_surveys__survey_submissions, which owns that resolution. This model adds
  only the question and answer columns.
```

Leave `data_tests:` and `columns:` unchanged.

- [ ] **Step 4: Build the view and its dependents into dev**

```bash
uv run dbt build --select int_surveys__survey_responses+ --exclude resource_type:test --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: every selected model builds. `int_surveys__survey_submissions` is
already in dev from Task 3 and unselected here, but `--favor-state` would
resolve the unselected ref to PROD (old columns). So this build MUST select
both. Re-run as:

```bash
uv run dbt build --select int_surveys__survey_submissions int_surveys__survey_responses+ --exclude resource_type:test --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Use only the second command's result. Confirm the compiled SQL of the view reads
the dev submissions table:
`grep -c 'zz_cbini_kipptaf_surveys' /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf/target/compiled/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
returns 2.

- [ ] **Step 5: Compare the question grain against the baseline**

```sql
select
    count(*) as rows_,
    countif(survey_response_id is null) as phantom_rows,
    bit_xor(farm_fingerprint(concat(
        survey_id, '|', coalesce(survey_response_id, ''), '|', coalesce(survey_question_id, ''), '|',
        coalesce(question_shortname, ''), '|', coalesce(answer, '')
    ))) as grain_fp,
from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_responses
```

Expected: `phantom_rows` = 0. `rows_` = baseline `rows_` minus the baseline
`phantom_rows` question rows, plus 1 extra row per question for each of the 68
ambiguous submissions while the sheet is unfixed (each fans out to 2 submissions
rows). `grain_fp` will differ from baseline by exactly those rows. Confirm the
delta is only those with:

```sql
with
    p as (
        select survey_id, survey_response_id, survey_question_id, question_shortname, answer
        from `teamster-332318`.kipptaf_surveys.int_surveys__survey_responses
        where survey_response_id is not null
    ),
    d as (
        select distinct survey_id, survey_response_id, survey_question_id, question_shortname, answer
        from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_responses
    )
select
    (select count(*) from p) as prod_nonphantom,
    (select count(*) from d) as dev_distinct,
    (select count(*) from (select * from p except distinct select * from d)) as only_prod,
    (select count(*) from (select * from d except distinct select * from p)) as only_dev
```

Expected: `only_prod` = 0 and `only_dev` = 0. The distinct grain is identical;
only the 68-submission duplication (while the sheet is unfixed) and the phantom
rows differ.

- [ ] **Step 6: Run the model's own tests**

```bash
uv run dbt test --select int_surveys__survey_responses --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `unique_combination_of_columns` FAILS while the sheet is unfixed (the
68 duplicated submissions fan every question row), PASSES after. The
`expression_is_true` warn test matches its prod status.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain commit -m "refactor(surveys): read per-submission columns from survey submissions

Drop the roster, alias-map and reporting-terms joins from the question-grain
view and inner-join int_surveys__survey_submissions for those columns. Output
columns are unchanged. The 4 phantom null-response rows from forms with no
responses no longer appear.

Refs #5277.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Mart fingerprints, push, PR

**Files:**

- None new. Verification, push, PR.

**Interfaces:**

- Consumes: dev builds from Tasks 3 and 4 (already in `zz_cbini_kipptaf_*`).

- [ ] **Step 1: Ask the sheet owner to fix the row, if not already done**

The reporting-terms Google Sheet has 2 `SURVEY` rows named
`KTAF Support Survey`: `academic_year` 2025 with window 2026-01-01 to
2026-02-28, and `academic_year` 2026 with window 2026-01-04 to 2026-01-15. The
2026 row is the anomaly. Hand this to the user in plain text; it is not a code
change. Then rebuild the staging table into dev so the check below reads the
fixed sheet:

```bash
uv run dbt build --select stg_google_sheets__reporting__terms --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected after the fix: all 3 tests PASS, including Task 1's. If the fix has not
landed, continue with the remaining steps, and record in the PR that CI is red
on that test until it does.

- [ ] **Step 2: Build the 3 marts into dev with the whole chain selected**

```bash
uv run dbt build --select stg_google_sheets__reporting__terms int_surveys__survey_submissions+ --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all models build. With the sheet fixed, all tests PASS. Without it,
the same 3 tests fail as in Tasks 1, 3 and 4 and nothing else.

- [ ] **Step 3: Fingerprint the marts, prod versus dev**

Run via BigQuery MCP:

```sql
with
    k as (
        select 'fct_survey_submissions' as model, 'survey_submission_key' as key_name, survey_submission_key as k from `teamster-332318`.kipptaf_marts.fct_survey_submissions
        union all
        select 'fct_survey_submissions', 'survey_administration_key', survey_administration_key from `teamster-332318`.kipptaf_marts.fct_survey_submissions
        union all
        select 'dim_survey_administrations', 'survey_administration_key', survey_administration_key from `teamster-332318`.kipptaf_marts.dim_survey_administrations
        union all
        select 'fct_survey_responses', 'survey_submission_key', survey_submission_key from `teamster-332318`.kipptaf_marts.fct_survey_responses
    ),
    d as (
        select 'fct_survey_submissions' as model, 'survey_submission_key' as key_name, survey_submission_key as k from `teamster-332318`.zz_cbini_kipptaf_marts.fct_survey_submissions
        union all
        select 'fct_survey_submissions', 'survey_administration_key', survey_administration_key from `teamster-332318`.zz_cbini_kipptaf_marts.fct_survey_submissions
        union all
        select 'dim_survey_administrations', 'survey_administration_key', survey_administration_key from `teamster-332318`.zz_cbini_kipptaf_marts.dim_survey_administrations
        union all
        select 'fct_survey_responses', 'survey_submission_key', survey_submission_key from `teamster-332318`.zz_cbini_kipptaf_marts.fct_survey_responses
    ),
    agg as (
        select 'prod' as side, model, key_name, count(*) as rows_, count(distinct k) as distinct_keys,
            (select bit_xor(farm_fingerprint(x)) from unnest(array_agg(distinct k)) as x) as fp
        from k group by model, key_name
        union all
        select 'dev', model, key_name, count(*), count(distinct k),
            (select bit_xor(farm_fingerprint(x)) from unnest(array_agg(distinct k)) as x)
        from d group by model, key_name
    )
select
    p.model, p.key_name,
    p.rows_ as prod_rows, v.rows_ as dev_rows,
    p.distinct_keys as prod_distinct, v.distinct_keys as dev_distinct,
    p.fp = v.fp as fp_match
from agg as p
join agg as v on p.model = v.model and p.key_name = v.key_name and v.side = 'dev'
where p.side = 'prod'
order by 1, 2
```

Expected with the sheet fixed: `fct_survey_submissions` /
`survey_submission_key` has `dev_rows` = `prod_rows` minus 4 and `fp_match`
false only because of those 4; every other row has `fp_match` true and equal
counts. Confirm the 4 with:

```sql
select count(*) as missing_in_dev
from `teamster-332318`.kipptaf_marts.fct_survey_submissions as p
left join `teamster-332318`.zz_cbini_kipptaf_marts.fct_survey_submissions as d using (survey_submission_key)
where d.survey_submission_key is null
```

Expected: 4. Also confirm the reverse direction returns 0 (swap `p` and `d`).
Any other movement: stop and report.

If a mart key column named above does not exist (for example
`fct_survey_responses` has no `survey_submission_key`), read that model's
properties YAML for the actual key names and adjust the query; do not skip the
mart.

- [ ] **Step 4: Confirm the #5276 reproduce query returns 0**

Only meaningful with the sheet fixed. Run against dev:

```sql
with per_partition as (
  select count(distinct academic_year) as n_ay
  from `teamster-332318`.zz_cbini_kipptaf_surveys.int_surveys__survey_responses
  group by survey_id, survey_response_id
)
select countif(n_ay > 1) as varying_academic_year from per_partition
```

Expected: 0.

- [ ] **Step 5: Lint everything the branch touched, then push**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain diff --name-only origin/main...HEAD) </dev/null
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-survey-submissions-response-grain push -u origin cbini/perf/claude-survey-submissions-response-grain
```

Expected: no lint issues; push succeeds.

- [ ] **Step 6: Open the PR**

Read `.github/pull_request_template.md` in the worktree and fill every section
in place. Title: `perf(surveys): build survey submissions from response grain`.
Body must include `Closes #5277`, `Closes #5276`, the mart fingerprint table
from Step 3 (aggregates only, no key values), the note that 4 phantom
submissions drop out, and, if the sheet fix has not landed, a line stating that
the new reporting-terms test and the 2 uniqueness tests are red until the
`KTAF Support Survey` 2026 row is fixed in the sheet. Do not hard-wrap the body.
End with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
Create with `mcp__github__create_pull_request` (owner `TEAMSchools`, repo
`teamster`, base `main`, head
`cbini/perf/claude-survey-submissions-response-grain`). After creation, read the
PR back and confirm the title and body match.

Then invoke the `pr-ci-review` skill and watch CI. Expect dbt Cloud CI to
rebuild `state:modified+`, which includes the 7 consumers of
`int_surveys__survey_responses` and the 3 marts.

---

## Self-review

Spec coverage: Decision bullets 1 and 2 are Tasks 3 and 4; bullet 3 is Task 1;
bullet 4 and the sheet fix are Task 5 Step 1; verification section is Task 3
Step 5, Task 4 Step 5, Task 5 Steps 3 and 4; the Alchemer source additions are
Task 2; cron removal is Task 3 Step 3. Out-of-scope items have no task, as
intended.

Type consistency: every column name and type in Task 3's Produces block matches
the SQL in Task 3 Step 2, the YAML in Step 3, and the `ss.` selects in Task 4
Step 2. `respondent_local_part` is used only inside Task 3.
