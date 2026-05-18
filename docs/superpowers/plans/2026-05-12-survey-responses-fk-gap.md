# Survey Responses FK Gap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the
`fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
relationships-test gap (143,758 orphan response rows / 12,261 orphan submissions
on 2026-05-12) by fixing two upstream join defects.

**Architecture:** Two coordinated upstream edits.

1. `int_surveys__survey_responses.sql` — add an additive Google Directory
   alias-resolution fallback so staff respondents who took the survey from an
   aliased email pick up their `respondent_employee_number`. Empirically
   recovers 21 of 23 currently-null staff submissions with 0 silent
   reassignments and 0 regressions.
2. `fct_survey_submissions.sql` — replace the student-leg join predicate
   (`enroll_status = 0 AND academic_year =`) with a date-range membership check
   on `date_submitted` against the enrollment's `[entrydate, exitdate)` window;
   drop the now-unnecessary `row_number()` tiebreaker; drop the staff-leg
   `respondent_employee_number is not null` filter and wrap `staff_key` with the
   nullable-FK pattern.

**Tech Stack:** dbt 1.11+ (BigQuery), `dbt_utils.generate_surrogate_key`,
`uv run dbt` invocation, sqlfluff via trunk (auto-applied at commit/push).

**Working directory:** All paths in this plan are relative to the worktree root
`/workspaces/teamster/.worktrees/cbini/fix/claude-survey-responses-fk-gap`. Use
absolute paths or `git -C <worktree>` /
`uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` from any other
location (project root or other worktree).

**Pre-flight:** Confirm `target/prod/manifest.json` exists under the dbt project
(`src/dbt/kipptaf/target/prod/`). If absent or stale (older than the most recent
`git pull`), regenerate it with:

```bash
uv run dbt parse --target prod \
  --project-dir src/dbt/kipptaf \
  --target-path target/prod
```

The `post-merge` git hook normally does this; only re-run if a build fails with
"Could not find manifest".

---

## File Structure

| File                                                                            | Action | Responsibility                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql` | Modify | Add `gdir_alias_map` CTE; add fallback `left join`s in both Google Forms (lines 41-58) and Alchemer (lines 101-120) branches; `coalesce` the resolved `employee_number` / `sam_account_name` / `user_principal_name` / `formatted_name`.                              |
| `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql`                 | Modify | Student leg: rewrite join predicate to half-open date-range, drop `row_number()` tiebreaker, collapse two CTEs into one, source `academic_year` from `enr` not `sr`. Staff leg: drop `is not null` filter, wrap `staff_key` with nullable-FK pattern at final SELECT. |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml`      | Modify | Update model `description:` to document the date-range attribution rule and nullable `student_enrollment_key` / `staff_key` semantics.                                                                                                                                |

No new files. No schema/contract changes.

---

## Task 1: Add Google Directory alias-fallback to `int_surveys__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`

This task is purely additive. The existing `left join` on
`int_people__staff_roster_history` stays. We add (a) a `gdir_alias_map` CTE that
flattens `stg_google_directory__users` aliases / emails / primary, (b) a second
`left join` chain that maps `respondent_email` → `primary_email` → fresh `srh`
row, in **both** the Google Forms branch (lines 41-58) and the Alchemer branch
(lines 101-120). At the final projection we `coalesce` the resolved values,
current-path-first.

### Step 1.1: Read the file in full to confirm structure

- [ ] Run:

```bash
cat src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql
```

Expected: file is 128 lines; two `union all` branches inside an `enriched` CTE;
both use a `left join` to `int_people__staff_roster_history as srh` to populate
`respondent_employee_number`, `respondent_preferred_name`,
`respondent_samaccountname`, `respondent_userprincipalname`.

### Step 1.2: Replace the file body with the alias-fallback version

- [ ] Apply this Edit. Old string is the existing `with` keyword opening through
      the end of the file's terminal `from enriched as e`; new string adds the
      `gdir_alias_map` CTE before `enriched`, plus the two fallback `left join`
      blocks and `coalesce` projections inside each union branch.

The four columns to coalesce (in this order) are:

```text
respondent_employee_number  ← srh.employee_number,  fallback srh_alias.employee_number
respondent_preferred_name   ← srh.formatted_name,   fallback srh_alias.formatted_name
respondent_samaccountname   ← srh.sam_account_name, fallback srh_alias.sam_account_name
respondent_userprincipalname← srh.user_principal_name, fallback srh_alias.user_principal_name
```

The Google Forms branch passes the response timestamp into the time-bound
predicate as `timestamp(fr.last_submitted_time)`. The Alchemer branch passes
`sr.response_date_submitted`. Use the same expressions for the alias-fallback
join.

Replace the entire file content with the version below. (It's easier and safer
to overwrite than to patch — the file is small.)

```sql
with
    gdir_alias_map as (
        select gd.primary_email, addr.address as known_address,
        from {{ ref("stg_google_directory__users") }} as gd,
            unnest(gd.emails) as addr
        union distinct
        select gd.primary_email, alias,
        from {{ ref("stg_google_directory__users") }} as gd,
            unnest(gd.aliases) as alias
        union distinct
        select gd.primary_email, gd.primary_email,
        from {{ ref("stg_google_directory__users") }} as gd
    ),

    enriched as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.question_id as survey_question_id,
            fr.text_value as answer,
            fr.item_title as question_title,
            fr.item_abbreviation as question_shortname,
            fr.respondent_email,

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

            safe_cast(fr.text_value as numeric) as answer_value,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

            concat(
                'https://docs.google.com/forms/d/',
                fr.form_id,
                '/edit#response=',
                fr.response_id
            ) as survey_response_link,

            if(safe_cast(fr.text_value as int) is null, 1, 0) as is_open_ended,

            dense_rank() over (
                partition by fr.respondent_email, rt.academic_year, rt.code, fr.form_id
                order by fr.last_submitted_time desc
            ) as round_rn,
        from {{ ref("int_google_forms__form_responses") }} as fr
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on fr.info_title = rt.name
            and date(fr.last_submitted_time) between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                lower(regexp_extract(fr.respondent_email, r'^([^@]+)'))
                = srh.sam_account_name
                or fr.respondent_email = srh.google_email
            )
            and timestamp(fr.last_submitted_time)
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join gdir_alias_map as gam on fr.respondent_email = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and timestamp(fr.last_submitted_time)
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator

        union all

        select
            safe_cast(sr.survey_id as string) as survey_id,

            sr.survey_title,

            safe_cast(sr.response_id as string) as survey_response_id,

            safe_cast(sr.question_id as string) as survey_question_id,

            sr.response_value as answer,
            sr.question_title_english as question_title,
            sr.question_short_name as question_shortname,

            ri.respondent_mail as respondent_email,

            coalesce(sr.campaign_fiscal_year - 1, rt.academic_year) as academic_year,

            coalesce(regexp_extract(sr.campaign_name, r'\s(.*)'), rt.code) as term_code,

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

            safe_cast(sr.response_value as numeric) as answer_value,

            sr.response_date_started as date_started,
            sr.response_date_submitted as date_submitted,

            concat(
                sr.survey_link_default,
                '?snc=',
                sr.response_session_id,
                '&sg_navigate=start'
            ) as survey_response_link,

            if(safe_cast(sr.response_value as int) is null, 1, 0) as is_open_ended,

            1 as round_rn,
        from {{ source("alchemer", "base_alchemer__survey_results") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.name
            and sr.response_date_submitted_date between rt.start_date and rt.end_date
        left join
            {{ source("surveys", "int_surveys__response_identifiers") }} as ri
            on sr.survey_id = ri.survey_id
            and sr.response_id = ri.response_id
        left join
            {{ ref("int_people__staff_roster_history") }} as srh
            on (
                lower(regexp_extract(ri.respondent_mail, r'^([^@]+)'))
                = srh.sam_account_name
                or ri.respondent_mail = srh.google_email
            )
            and sr.response_date_submitted
            between srh.effective_date_start_timestamp
            and srh.effective_date_end_timestamp
            and srh.primary_indicator
        left join gdir_alias_map as gam on ri.respondent_mail = gam.known_address
        left join
            {{ ref("int_people__staff_roster_history") }} as srh_alias
            on gam.primary_email = srh_alias.google_email
            and sr.response_date_submitted
            between srh_alias.effective_date_start_timestamp
            and srh_alias.effective_date_end_timestamp
            and srh_alias.primary_indicator
    )

select
    e.*,
    coalesce(
        cast(e.respondent_employee_number as string), e.respondent_email
    ) as respondent_identifier,
from enriched as e
```

### Step 1.3: Build the model with downstream tests

- [ ] Run:

```bash
uv run dbt build --select int_surveys__survey_responses+1 \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer --state target/prod/
```

Expected: PASS for `int_surveys__survey_responses` and all
immediately-downstream tests. `+1` limits to direct children so this step stays
fast; the full `+` selector comes in Task 5.

If the build fails with "Could not find manifest" or "table not found" on a
`stg_*` source, regenerate the prod manifest (see Pre-flight).

### Step 1.4: Verify zero silent reassignments + alias recovery sizing

- [ ] Run via BigQuery MCP `mcp__bigquery__execute_sql`. Replace `<dev_schema>`
      with the developer's dev schema (look it up via `~/.dbt/profiles.yml` or
      the dbt parse output if unsure — it follows the pattern
      `zz_<github_username>_kipptaf_surveys`).

```sql
with new_resolution as (
  select
    survey_response_id,
    survey_title,
    respondent_email,
    respondent_employee_number as new_emp,
  from `teamster-332318.<dev_schema>.int_surveys__survey_responses`
  where survey_title in (
    'School Community Diagnostic Staff Survey',
    'Engagement & Support Surveys'
  )
),
prod_resolution as (
  select
    survey_response_id,
    respondent_email,
    respondent_employee_number as prod_emp,
  from `teamster-332318.kipptaf_surveys.int_surveys__survey_responses`
  where survey_title in (
    'School Community Diagnostic Staff Survey',
    'Engagement & Support Surveys'
  )
),
joined as (
  select n.survey_response_id, n.respondent_email, p.prod_emp, n.new_emp
  from new_resolution as n
  inner join prod_resolution as p using (survey_response_id)
)
select
  count(distinct survey_response_id) as distinct_submissions,
  countif(prod_emp is null and new_emp is not null) as recovered,
  countif(prod_emp is null and new_emp is null) as still_null,
  countif(prod_emp is not null and new_emp != prod_emp) as reassignments,
  countif(prod_emp is not null and new_emp is null) as regressions,
from joined
```

Expected:

- `recovered` ≥ 21 (multiple response rows per submission collapse here; the
  distinct-submission target is 21, raw rows will be higher)
- `still_null` corresponds to the 1 unresolvable email
  (`jperez@apps.teamschools.org` per the spec residual)
- `reassignments` = 0
- `regressions` = 0

**If `reassignments > 0`**: STOP. Investigate which email got reassigned and to
which `employee_number`. Likely cause: a Google Directory record holds an alias
that another active employee uses as their `sam_account_name`. Do NOT proceed
until reassignments are 0 — the wrap design assumes additive-only recovery.

**If `regressions > 0`**: STOP. The `coalesce(srh.x, srh_alias.x)` is
current-first, so regressions should be impossible. If they occur, a bug exists
in the new SQL.

### Step 1.5: Commit and push

- [ ] Run:

```bash
git -C . add src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql
git -C . commit -m "$(cat <<'EOF'
fix(dbt): add Google Directory alias fallback to survey response resolution

Refs #3794. When the current sam_account_name / google_email join against
int_people__staff_roster_history returns null for a staff survey response,
fall through to a Google Directory alias-resolution path: respondent_email
→ stg_google_directory__users (emails/aliases/primary) → primary_email →
fresh srh lookup. Coalesce current-first.

Recovers 21 of 23 currently-null respondent_employee_number values across
staff and engagement surveys (prod 2026-05-12) with 0 silent reassignments
and 0 regressions to currently-resolved submissions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git -C . push
```

Expected: pre-commit fmt runs cleanly; pre-push trunk-check passes
sqlfluff/yamllint; remote receives the commit.

---

## Task 2: `fct_survey_submissions` — student-leg rewrite

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql` (lines
  39-99, the `student_submissions_ranked` and `student_submissions` CTEs)

Three changes in one CTE:

1. Replace the join predicate
   `enr.enroll_status = 0 AND sr.academic_year = enr.academic_year` with
   `enr.entrydate <= sr.date_submitted AND enr.exitdate > sr.date_submitted`.
2. Drop the
   `row_number() OVER (PARTITION BY sr.survey_response_id ORDER BY enr.entrydate DESC)`
   tiebreaker and the wrapper `student_submissions` CTE — collapse to a single
   CTE.
3. Source `academic_year` from `enr.academic_year` (not `sr.academic_year`) so
   the `student_enrollment_key` hash composition matches
   `dim_student_enrollments`.

### Step 2.1: Apply the student-leg edit

- [ ] Edit `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql`.
      Replace the block from line 38 `    /* Student SCD submissions */` through
      line 99 `    ),` (inclusive — through and including the closing
      parenthesis of `student_submissions`) with:

```sql
    /* Student SCD submissions */
    student_submissions as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.respondent_email,
            sr.date_submitted,
            sr.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'student' as respondent_type,

            enr.student_number,
            enr._dbt_source_relation,
            enr.academic_year,
            enr.entrydate,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and sr.term_code = rt.code
            and rt.type = 'SURVEY'
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sr.respondent_email = enr.student_email
            and enr.entrydate <= sr.date_submitted
            and enr.exitdate > sr.date_submitted
        where sr.survey_title = 'School Community Diagnostic Student Survey'
    ),
```

Key points to verify after editing:

- `sr.academic_year` is no longer in the SELECT list of `student_submissions`.
  `enr.academic_year` replaces it.
- The two-CTE shape (`student_submissions_ranked` → `student_submissions`)
  collapses to one CTE named `student_submissions`. The `combined_student` and
  downstream `select ... from combined_student` references continue to compile
  because the new CTE preserves the same column set the old
  `student_submissions` exposed (the `rn_enrollment` column is dropped — confirm
  via grep below it has no other consumers).

### Step 2.2: Confirm `rn_enrollment` was only referenced in the dropped wrapper

- [ ] Run:

```bash
grep -rn "rn_enrollment" src/dbt/kipptaf/
```

Expected: zero matches. If any match exists outside the file you just edited,
that's a real consumer — STOP and resolve.

### Step 2.3: Build the model and run tests

- [ ] Run:

```bash
uv run dbt build --select fct_survey_submissions \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer --state target/prod/
```

Expected: model materializes successfully; `unique` test on
`survey_submission_key` passes; FK relationships tests against
`dim_student_enrollments`, `dim_staff`, `dim_survey_administrations`,
`dim_dates`, and `dim_student_contact_persons` all PASS or WARN (some WARN at
default mart severity, which is acceptable per the spec).

**If `unique` fails**: Investigate fan-out. Cause is either (a) an enrollment
overlap that does intersect a submission date for some student (a hypothesis the
spec explicitly tests as "currently zero"), or (b) a duplicate response
upstream. Re-run the spec's overlap-detection query (see spec § "Implementation"
→ "fct_survey_submissions.sql — student leg") against the dev schema's
`student_submissions` materialization to characterize.

### Step 2.4: Commit and push

- [ ] Run:

```bash
git -C . add src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql
git -C . commit -m "$(cat <<'EOF'
fix(dbt): use date-range membership for student-leg enrollment join

Refs #3794. Replaces the student-leg join in fct_survey_submissions from
(academic_year =, enroll_status = 0) to a half-open date-range membership
check on enr.entrydate <= sr.date_submitted < enr.exitdate. The old
predicates were both wrong: enroll_status is a student-level current-active
flag (drops historical enrollments for since-departed students), and the
academic_year equality misses mid-year enrollment year-tag changes.

Collapses student_submissions_ranked and student_submissions into a single
CTE, dropping the row_number() tiebreaker after verifying zero
enrollment-overlap fan-out on actual survey submissions. The PK uniqueness
test on survey_submission_key remains the regression guard.

Sources academic_year from the matched enrollment row so
student_enrollment_key hash inputs match dim_student_enrollments.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git -C . push
```

---

## Task 3: `fct_survey_submissions` — staff-leg nullable FK

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql` (lines
  30-31 in the `staff_submissions` CTE; line 289 in the staff-leg final SELECT)

Two changes:

1. Drop the `sr.respondent_employee_number is not null and` predicate from
   `staff_submissions`'s WHERE clause.
2. Wrap `staff_key` with the nullable-FK
   `if(... is not null, generate_surrogate_key(...), cast(null as string))`
   pattern, mirroring `subject_staff_key`.

### Step 3.1: Drop the `is not null` filter

- [ ] Edit. Replace:

```sql
        where
            sr.respondent_employee_number is not null
            and sr.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
```

with:

```sql
        where
            sr.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
```

### Step 3.2: Wrap `staff_key` with the nullable-FK pattern

- [ ] Edit. Replace the line in the staff-leg final SELECT (currently
      `fct_survey_submissions.sql:289`):

```sql
    {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }} as staff_key,
```

with:

```sql
    if(
        respondent_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
        cast(null as string)
    ) as staff_key,
```

### Step 3.3: Build and run tests

- [ ] Run:

```bash
uv run dbt build --select fct_survey_submissions \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer --state target/prod/
```

Expected: PASS. The relationships test `staff_key → dim_staff.staff_key` should
report zero orphans because every now-included null-employee submission produces
`staff_key = null` (relationships tests treat null FKs as not-applicable).

**If new `staff_key → dim_staff` orphans appear**: a recovered `employee_number`
from Task 1's alias resolution doesn't exist in `dim_staff`. Investigate by
joining the orphan keys back to `int_surveys__survey_responses`; cross-check
those emails against `dim_staff`. The expected resolution: file a follow-up
issue for the missing `dim_staff` row(s); for this PR, accept the WARN and call
it out in the PR description.

### Step 3.4: Commit and push

- [ ] Run:

```bash
git -C . add src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql
git -C . commit -m "$(cat <<'EOF'
fix(dbt): include null-employee staff survey submissions

Refs #3794. Drops the respondent_employee_number is not null filter from
fct_survey_submissions.staff_submissions and wraps staff_key with the
nullable-FK if-not-null pattern. Submissions whose respondent_employee_number
still cannot be resolved after upstream alias resolution now produce a row
with staff_key = null, restoring 1:1 coverage with fct_survey_responses.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git -C . push
```

---

## Task 4: Update `fct_survey_submissions` model description

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml`
  (lines 3-10 model description; line 70-72 `staff_key`; line 86-88
  `student_enrollment_key`)

Update the descriptions to document (a) the date-range attribution rule for the
student leg, (b) the nullable-FK semantics on `staff_key` and
`student_enrollment_key`.

### Step 4.1: Update model-level description

- [ ] Edit. Replace lines 3-10:

```yaml
description: >-
  Survey submission fact table. One row per respondent x survey_administration.
  Records survey completion events across all populations (staff, student,
  family). The respondent_type discriminator determines which respondent FK is
  populated (exactly one per row). Nullable subject_staff_key is populated only
  for Manager Survey submissions (role-playing FK to dim_staff for the manager
  being evaluated). FK to dim_survey_administrations and dim_dates.
```

with:

```yaml
description: >-
  Survey submission fact table. One row per respondent x survey_administration.
  Records survey completion events across all populations (staff, student,
  family). The respondent_type discriminator determines which respondent FK is
  populated (exactly one per row). For student submissions,
  student_enrollment_key resolves to the enrollment row whose [entrydate,
  exitdate) window contains date_submitted. staff_key and student_enrollment_key
  are nullable for respondents whose identity cannot be resolved (e.g. staff
  respondents whose employee_number was never linked, or student respondents
  whose email is not present in int_extracts__student_enrollments). Nullable
  subject_staff_key is populated only for Manager Survey submissions
  (role-playing FK to dim_staff for the manager being evaluated). FK to
  dim_survey_administrations and dim_dates.
```

### Step 4.2: Update `staff_key` column description

- [ ] Edit. Replace:

```yaml
- name: staff_key
  data_type: string
  description: >-
    FK to dim_staff for the respondent. Populated when respondent_type is staff.
    Null for student and family.
```

with:

```yaml
- name: staff_key
  data_type: string
  description: >-
    FK to dim_staff for the respondent. Populated when respondent_type is staff
    AND the upstream respondent_employee_number resolves. Null for student /
    family respondents AND for staff respondents whose identity cannot be
    resolved upstream.
```

### Step 4.3: Update `student_enrollment_key` column description

- [ ] Edit. Replace:

```yaml
- name: student_enrollment_key
  data_type: string
  description: >-
    FK to dim_student_enrollments for the respondent. Populated when
    respondent_type is student. Null for staff and family.
```

with:

```yaml
- name: student_enrollment_key
  data_type: string
  description: >-
    FK to dim_student_enrollments for the respondent, resolved by matching
    respondent_email to an enrollment row whose [entrydate, exitdate) window
    contains date_submitted. Populated when respondent_type is student AND such
    an enrollment exists. Null for staff / family respondents AND for student
    respondents whose email is not present in int_extracts__student_enrollments
    or has no enrollment row covering date_submitted.
```

### Step 4.4: Re-parse the project to verify YAML is well-formed

- [ ] Run:

```bash
uv run dbt parse --target dev \
  --project-dir src/dbt/kipptaf \
  --no-partial-parse
```

Expected: parse completes without errors. `--no-partial-parse` forces a full
re-parse so any description-merge edge case surfaces.

### Step 4.5: Commit and push

- [ ] Run:

```bash
git -C . add src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml
git -C . commit -m "$(cat <<'EOF'
docs(dbt): update fct_survey_submissions description for nullable FKs

Refs #3794. Documents the date-range attribution rule for the student leg
and the nullable-FK semantics on staff_key and student_enrollment_key.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git -C . push
```

---

## Task 5: Final verification on PR-branch schema

After Task 4 pushes, the dbt Cloud CI job builds the PR's models into a schema
named `dbt_cloud_pr_<ci_id>_3794_<schema_part>`. Wait for CI to complete
(visible on the GitHub PR), then verify against the materialized PR-branch
tables.

### Step 5.1: Find the CI run's PR-schema id

- [ ] Run:

```bash
gh pr view --json number,statusCheckRollup
```

Look for the dbt Cloud CI run and its run id. The PR-branch schema follows the
pattern `dbt_cloud_pr_<env_id>_<pr_number>_<schema_suffix>`. For this repo
`env_id` is `70403104388001` and `pr_number` is whatever GitHub assigned. The
suffix matches the model's prod schema suffix (`surveys`, `marts`, `extracts`,
etc.).

### Step 5.2: Verify orphan count returns to zero on PR-branch marts schema

- [ ] Run via `mcp__bigquery__execute_sql`, substituting the correct PR-branch
      schema names:

```sql
select
  count(*) as orphan_responses,
  count(distinct r.survey_submission_key) as orphan_distinct_submissions,
from `teamster-332318.dbt_cloud_pr_70403104388001_<PR>_marts.fct_survey_responses` as r
left join `teamster-332318.dbt_cloud_pr_70403104388001_<PR>_marts.fct_survey_submissions` as s
  on r.survey_submission_key = s.survey_submission_key
where r.survey_submission_key is not null
  and s.survey_submission_key is null
```

Expected: `orphan_responses = 0` and `orphan_distinct_submissions = 0`.

If non-zero, run the diagnostic breakdown:

```sql
select
  r.respondent_type,
  r.survey_title,
  count(*) as orphan_rows,
  count(distinct r.survey_submission_key) as distinct_submissions,
from `teamster-332318.dbt_cloud_pr_70403104388001_<PR>_marts.fct_survey_responses` as r
left join `teamster-332318.dbt_cloud_pr_70403104388001_<PR>_marts.fct_survey_submissions` as s
  on r.survey_submission_key = s.survey_submission_key
where r.survey_submission_key is not null
  and s.survey_submission_key is null
group by 1, 2
order by orphan_rows desc
```

### Step 5.3: Confirm PK uniqueness and FK relationships tests pass

- [ ] Use `mcp__dbt__get_job_run_error` with `warning_only=true` on the CI run's
      job id and look for any test referencing `fct_survey_submissions`. The
      relationship test for
      `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
      should report zero rows; the `unique` test on `survey_submission_key`
      should pass.

If the `fct_survey_responses → fct_survey_submissions` relationships test
reports zero rows, optionally flip its severity from default `warn` to `error`
(in the properties yml for `fct_survey_responses`); confirm with the user before
doing so since severity changes affect deploy-time gating.

### Step 5.4: Marts pre-merge checklist

- [ ] Walk the `marts/CLAUDE.md` § "Pre-merge checklist" items inline in the PR
      description:
  - Diamond paths introduced? (Expected: no — only join shape changed.)
  - R1–R10 violations? (Expected: no — no new columns.)
  - Marts-model warnings from latest CI run via
    `mcp__dbt__get_job_run_error(warning_only=true)`. List any new warnings; for
    each, search open issues by model name + FK target. Confirm the survey-FK
    warning disappears and no new warnings (incl. `staff_key → dim_staff`)
    appear.
  - Scan `https://github.com/orgs/TEAMSchools/projects/4/views/1` for bonus
    issues incidentally resolved; close them in the PR.

### Step 5.5: Open the PR

- [ ] Open the PR using the repository's PR template
      (`.github/pull_request_template.md` — `gh pr create` loads it by default).
      Title: `fix(dbt): close survey responses → submissions FK gap`. Body: fill
      in the template's _Summary & Motivation_ with:

  > When merged, this pull request will close the
  > `fct_survey_responses → fct_survey_submissions` FK gap (143,758 orphan
  > response rows / 12,261 orphan submissions on 2026-05-12) by adding a Google
  > Directory alias-resolution fallback in `int_surveys__survey_responses` and
  > rewriting the `fct_survey_submissions` student-leg join to use date-range
  > enrollment membership. Closes #3794.

  Add an _AI Assistance_ note: spec authoring, plan generation, and SQL drafting
  were Claude-assisted; data verification (BigQuery queries against prod and dev
  schemas) and final review human-directed.

  Check the dbt section items as applicable (no new exposures, no new external
  sources, no breaking column renames). Leave the unrelated sections unchecked /
  let the template's "skip if no X changes" guidance apply.

- [ ] Run:

```bash
gh pr create --title "fix(dbt): close survey responses → submissions FK gap"
```

(omitting `--body` so `gh` opens an editor pre-filled with the template; paste
in the summary above before saving)

---

## Follow-up issues to file (not part of this PR)

- **LDAP `employeeID` provisioning gap** — the `jperez@apps.teamschools.org`
  residual. Administrative remediation, not a model change.
- **`int_people__staff_roster_history` identifier historicization** —
  `sam_account_name` / `google_email` / `user_principal_name` overwritten with
  current values across all effective-dated rows; a true effective-dated
  identifier history would obviate the Directory-alias fallback added in this
  PR.
- **Paterson `primary_indicator = false` on currently-effective rows** — for
  both Paterson Prep staff in `int_people__staff_roster_history`, the most
  recent effective row has `primary_indicator = false`, meaning the existing
  survey-response join would miss them even if AD linkage were intact.
- **`int_extracts__student_enrollments` overlapping date ranges** — 3
  overlapping pairs across 2 students in prod 2026-05-12. Doesn't affect survey
  submissions today but warrants the upstream
  `base_powerschool__student_enrollments` cleanup tracked in #3633.
