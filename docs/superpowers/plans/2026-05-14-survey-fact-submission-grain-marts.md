# Survey-fact submission-grain marts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the `survey_submission_key` hash composition between
`fct_survey_responses` and `fct_survey_submissions` and remove all
`select distinct` from survey-fact / admin-dim CTEs, baking the submission-grain
collapse into the mart models via `dbt_utils.deduplicate()`.

**Architecture:** Each mart introduces a `submissions_grain` CTE that calls
`dbt_utils.deduplicate(relation=ref("int_surveys__survey_responses"), partition_by="survey_id, survey_response_id", order_by="survey_question_id")`.
All per-respondent-type legs source respondent identity from this CTE. The
Manager Survey leg additionally left-joins `int_surveys__manager_survey_details`
on `(survey_id, survey_response_id)` for the subject-of-evaluation overlay only
— hash inputs always come from `submissions_grain`. The historic Alchemer
Manager archive becomes its own union arm in `fct_survey_submissions`, sourcing
from `int_surveys__manager_survey_details` filtered to
`survey_id = 'historic_alchemer_Manager_survey'` and using the deterministic
fallback hash.

**Tech Stack:** dbt 1.11+, BigQuery, `dbt_utils.deduplicate`,
`dbt_utils.generate_surrogate_key`.

**Spec:**
[docs/superpowers/specs/2026-05-14-survey-fact-submission-grain-marts-design.md](../specs/2026-05-14-survey-fact-submission-grain-marts-design.md)

**Tracking:** Closes #3899, #3896. Defers structural refactor to #3918.

---

## File Map

| File                                                                                  | Change                                                                                                                                    |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql`                       | Restructure — 4 `select distinct` → 1 `submissions_grain` CTE + per-leg filters + Manager subject overlay + isolated historic archive arm |
| `src/dbt/kipptaf/models/marts/dimensions/dim_survey_administrations.sql`              | Restructure — 3 `select distinct` + trailing `deduped` → `submissions_grain` + `dbt_utils.deduplicate` on admin grain                     |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml`              | Add `severity: error` to `survey_submission_key` relationships test                                                                       |
| `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__manager_survey_details.sql` | Header comment noting narrowed role                                                                                                       |

No new files. No YAML schema changes (mart columns unchanged).

---

## Working directory

All commands assume the worktree at
`/workspaces/teamster/.worktrees/cbini/refactor/claude-survey-fact-submission-grain-marts`.
Use `git -C <worktree>` and
`uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` per root CLAUDE.md.

```bash
WT=/workspaces/teamster/.worktrees/cbini/refactor/claude-survey-fact-submission-grain-marts
```

---

### Task 1: Refactor `fct_survey_submissions.sql`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql` (full
  rewrite)

The current file (338 lines) has four `select distinct` CTEs
(`staff_submissions`, `student_submissions`, `family_gforms`,
`manager_submissions`) feeding three `combined_*` CTEs that hash
`survey_administration_key`, then three union-all leg SELECTs that hash
`survey_submission_key`. The Manager leg sources from
`int_surveys__manager_survey_details` and has a
`coalesce(survey_response_id, concat(...))` fallback applied to all rows.

After refactor: one `submissions_grain` CTE (deduped from
`int_surveys__survey_responses`), per-respondent-type filter CTEs, a Manager
subject overlay join on the existing `int_surveys__manager_survey_details`, and
an isolated `historic_archive_submissions` union arm for Alchemer Manager
archive rows. Hash composition unchanged: `[survey_id, survey_response_id]`.

- [ ] **Step 1: Replace the file contents**

Path: `src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql`

```sql
with
    /*
     * Submission-grain projection of int_surveys__survey_responses.
     * One row per (survey_id, survey_response_id). The order_by choice is
     * arbitrary because projected columns don't vary across questions of the
     * same submission — survey_question_id is used for determinism only.
     * TODO: #3918 — extract int_surveys__survey_submissions intermediate.
     */
    submissions_grain as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_surveys__survey_responses"),
                partition_by="survey_id, survey_response_id",
                order_by="survey_question_id",
            )
        }}
    ),

    /* Staff SCD submissions */
    staff_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,

            cast(null as int64) as subject_employee_number,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sg.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
    ),

    /* Student SCD submissions */
    student_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_email,
            sg.date_submitted,
            sg.term_code,

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
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sg.respondent_email = enr.student_email
            and enr.entrydate <= date(sg.date_submitted)
            and enr.exitdate > date(sg.date_submitted)
        where sg.survey_title = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD submissions */
    family_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'family' as respondent_type,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sg.survey_title in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic'
            )
    ),

    /*
     * Manager Survey submissions — hash inputs from submissions_grain (Google
     * Forms branch of int_surveys__survey_responses). Subject-of-evaluation
     * staff columns come from int_surveys__manager_survey_details as a thin
     * overlay; that model is retained for subject context and the historic
     * Alchemer archive only. TODO: #3918.
     */
    manager_subject_overlay as (
        select distinct
            survey_id,
            survey_response_id,
            subject_df_employee_number,
        from {{ ref("int_surveys__manager_survey_details") }}
        where survey_response_id is not null
    ),

    manager_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,

            mso.subject_df_employee_number as subject_employee_number,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        left join
            manager_subject_overlay as mso
            on sg.survey_id = mso.survey_id
            and sg.survey_response_id = mso.survey_response_id
        where sg.survey_title = 'Manager Survey'
    ),

    /*
     * Historic Alchemer Manager archive — these rows have survey_response_id
     * NULL and don't appear in int_surveys__survey_responses, so they need
     * the deterministic fallback hash. They produce no FK orphans against
     * fct_survey_responses because no response-grain rows exist for them.
     */
    historic_archive_submissions as (
        select
            ms.survey_id,

            coalesce(
                ms.survey_response_id,
                concat(
                    ms.respondent_df_employee_number,
                    '_',
                    ms.subject_df_employee_number,
                    '_',
                    ms.campaign_reporting_term
                )
            ) as survey_response_id,

            ms.respondent_df_employee_number as respondent_employee_number,
            ms.subject_df_employee_number as subject_employee_number,
            ms.date_submitted,
            ms.campaign_academic_year as academic_year,
            ms.campaign_reporting_term as term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and ms.campaign_academic_year = rt.academic_year
            and ms.campaign_reporting_term = rt.code
            and rt.type = 'SURVEY'
        where
            ms.survey_id = 'historic_alchemer_Manager_survey'
            and ms.campaign_academic_year is not null
    ),

    /* Combine all staff-type submissions (live SCD + Manager + archive) */
    combined_staff as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_type,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,
        from staff_submissions

        union all

        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_type,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,
        from manager_submissions

        union all

        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_type,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,
        from historic_archive_submissions
    ),

    combined_student as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_type,
            student_number,
            _dbt_source_relation,
            academic_year,
            entrydate,
            date_submitted,
        from student_submissions
    ),

    combined_family as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_type,
            date_submitted,
            academic_year,
        from family_submissions
    )

/* Staff submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

    if(
        respondent_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
        cast(null as string)
    ) as staff_key,

    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,

    if(
        subject_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["subject_employee_number"]) }},
        cast(null as string)
    ) as subject_staff_key,

    academic_year,

    date_submitted as `timestamp`,
from combined_staff

union all

/* Student submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

    cast(null as string) as staff_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_relation",
                "academic_year",
                "entrydate",
            ]
        )
    }} as student_enrollment_key,

    cast(null as string) as student_contact_person_key,
    cast(null as string) as subject_staff_key,

    academic_year,

    date_submitted as `timestamp`,
from combined_student

union all

/* Family submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

    cast(null as string) as staff_key,
    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,
    cast(null as string) as subject_staff_key,

    academic_year,

    date_submitted as `timestamp`,
from combined_family
```

- [ ] **Step 2: Run dbt build on the fact and its downstream tests**

```bash
uv run dbt build \
  --select fct_survey_submissions+ \
  --project-dir $WT/src/dbt/kipptaf
```

Expected: PASS. Watch for `survey_submission_key unique` on
`fct_survey_submissions` and `dbt_utils.unique_combination_of_columns` if
present. The new `submissions_grain` CTE is grained on
`(survey_id, survey_response_id)` so per-leg `where` filters carve disjoint
subsets — uniqueness should hold.

If `survey_submission_key unique` fails: a `survey_title` matches multiple
`where` predicates across legs. Inspect failure rows; the leg `where` predicates
are the only place this can collide.

- [ ] **Step 3: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql
git -C $WT commit -m "$(cat <<'EOF'
refactor(dbt): bake submission-grain unification into fct_survey_submissions

Replaces four `select distinct` CTEs with a single `submissions_grain` CTE
sourcing `int_surveys__survey_responses` via `dbt_utils.deduplicate()`. The
Manager Survey leg now hashes survey_submission_key from the same source row
as fct_survey_responses, closing the ~100-orphan FK gap. The historic
Alchemer Manager archive is isolated as its own union arm with the
deterministic fallback hash; it produces no FK orphans because the archive
has no response-grain rows.

Refs #3899, closes #3896. Structural extraction tracked in #3918.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Refactor `dim_survey_administrations.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_survey_administrations.sql`

The current file has three `select distinct` admin-grain CTEs (`survey_terms`,
`manager_terms`, `support_terms`) plus a trailing `deduped` CTE that does
another `select distinct` on the union. After refactor: one `submissions_grain`
CTE for the SCD legs (staff + manager + family share this source today via
`int_surveys__survey_responses`), one for support, and `dbt_utils.deduplicate`
on the final admin grain.

Note: `support_terms` joins `int_surveys__response_identifiers` to
`int_surveys__survey_responses` on cast-mismatched IDs. That logic survives but
moves to source from `submissions_grain`.

- [ ] **Step 1: Replace the file contents**

Path: `src/dbt/kipptaf/models/marts/dimensions/dim_survey_administrations.sql`

```sql
with
    /*
     * Submission-grain projection of int_surveys__survey_responses.
     * One row per (survey_id, survey_response_id); the order_by choice does
     * not affect correctness because projected columns don't vary across
     * questions of a submission.
     * TODO: #3918 — extract int_surveys__survey_submissions intermediate.
     */
    submissions_grain as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_surveys__survey_responses"),
                partition_by="survey_id, survey_response_id",
                order_by="survey_question_id",
            )
        }}
    ),

    /* SCD + Manager Survey admin-grain rows */
    survey_terms as (
        select
            sg.survey_id,
            sg.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where sg.academic_year is not null
    ),

    /* Historic Alchemer Manager archive admin rows */
    historic_archive_terms as (
        select
            ms.survey_id,
            ms.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and ms.campaign_academic_year = rt.academic_year
            and ms.campaign_reporting_term = rt.code
            and rt.type = 'SURVEY'
        where
            ms.survey_id = 'historic_alchemer_Manager_survey'
            and ms.campaign_academic_year is not null
    ),

    support_terms as (
        select
            ss.survey_id,
            ss.survey_title,

            rt.type as term_type,
            rt.code as term_code,
            rt.`name` as term_name,
            rt.start_date as term_start_date,
            rt.end_date as term_end_date,
            rt.academic_year,
            rt.region,
            rt.school_id,
        from {{ source("surveys", "int_surveys__response_identifiers") }} as ri
        inner join
            submissions_grain as ss
            on ri.survey_id = safe_cast(ss.survey_id as int64)
            and ri.response_id = safe_cast(ss.survey_response_id as int64)
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Support Survey'
            and ss.academic_year = rt.academic_year
            and ss.term_code = rt.code
            and rt.type = 'SURVEY'
        where ss.survey_title = 'Support Survey' and ss.academic_year is not null
    ),

    all_administrations as (
        select *,
        from survey_terms
        union all
        select *,
        from historic_archive_terms
        union all
        select *,
        from support_terms
    ),

    /*
     * Collapse to admin grain. submissions_grain is row-grained, so several
     * submissions roll up to one admin row across all union arms.
     * TODO: #3918 — when extracted, the upstream will already be admin-grain.
     */
    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_administrations",
                partition_by=(
                    "survey_id, term_type, term_code, term_name,"
                    " term_start_date, region, school_id"
                ),
                order_by="academic_year",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "term_type",
                "term_code",
                "term_name",
                "term_start_date",
                "region",
                "school_id",
            ]
        )
    }} as survey_administration_key,

    {{ dbt_utils.generate_surrogate_key(["survey_id"]) }} as survey_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "term_type",
                "term_code",
                "term_name",
                "term_start_date",
                "region",
                "school_id",
            ]
        )
    }} as term_key,

    academic_year,

    term_end_date as response_deadline_date,

    case
        when term_end_date < current_date('{{ var("local_timezone") }}')
        then 'closed'
        when term_start_date <= current_date('{{ var("local_timezone") }}')
        then 'open'
        else 'upcoming'
    end as status,
from deduped
```

Note: `all_administrations` retains the existing `select *` union-all shape (the
source CTEs project the same columns in the same order).
`dbt_utils.deduplicate(relation="all_administrations", ...)` consumes the CTE —
per src/dbt/CLAUDE.md "sqlfluff ST03 on dbt_utils.deduplicate input CTEs", a
trunk-ignore comment on the `all_administrations` CTE is required.

- [ ] **Step 2: Add the trunk-ignore comment for the CTE**

Apply this edit to the file you just wrote — the `all_administrations` CTE needs
the ST03 ignore because it's only referenced via
`dbt_utils.deduplicate(relation=...)`:

Replace:

```sql
    all_administrations as (
        select *,
        from survey_terms
```

with:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    all_administrations as (
        select *,
        from survey_terms
```

- [ ] **Step 3: Run dbt build**

```bash
uv run dbt build \
  --select dim_survey_administrations+ \
  --project-dir $WT/src/dbt/kipptaf
```

Expected: PASS. The model's `survey_administration_key` uniqueness test must
pass. Hash composition is unchanged; `submissions_grain` carries one row per
submission while admin grain rolls up across submissions, so `deduped` provides
the final 1-row-per-administration grain.

If uniqueness fails: a `(survey_id, term_*, region, school_id)` tuple appears
with multiple `academic_year` values. Per BigQuery's `array_agg` semantics in
`dbt_utils.deduplicate`, `order_by="academic_year"` (ascending, NULLS LAST
default) picks the earliest non-null year — adjust the `order_by` if a different
canonical pick is needed.

- [ ] **Step 4: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/dimensions/dim_survey_administrations.sql
git -C $WT commit -m "$(cat <<'EOF'
refactor(dbt): bake submission-grain unification into dim_survey_administrations

Replaces three `select distinct` admin-grain CTEs and the trailing
`deduped` collapse with a single `submissions_grain` source for SCD legs
plus `dbt_utils.deduplicate` on the admin grain. Isolates the historic
Alchemer Manager archive as its own union arm.

Refs #3899. Structural extraction tracked in #3918.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Promote relationships test to error severity

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml` (line
  34-37)

The spec's acceptance criterion:
`fct_survey_responses.survey_submission_key → fct_survey_submissions`
relationships test must return 0 orphans and be promoted from WARN to error in
this PR.

- [ ] **Step 1: Edit the YAML**

Replace:

```yaml
data_tests:
  - relationships:
      arguments:
        to: ref('fct_survey_submissions')
        field: survey_submission_key
```

with:

```yaml
data_tests:
  - relationships:
      arguments:
        to: ref('fct_survey_submissions')
        field: survey_submission_key
      config:
        severity: error
```

- [ ] **Step 2: Run the test in isolation**

```bash
uv run dbt test \
  --select fct_survey_responses,test_type:relationships \
  --project-dir $WT/src/dbt/kipptaf
```

Expected: PASS with 0 orphans. If orphans remain, do NOT proceed — investigate
before commit. The expected residuals per the spec are:

- Staff: ~230 rows with null `respondent_employee_number` — these still have
  non-null `survey_response_id`, so they will join fine in the new design.
- Student: rows where `respondent_email` doesn't resolve to active enrollment —
  these are filtered out by the student leg's `inner join` to
  `int_extracts__student_enrollments`, but the response-side row remains. **This
  is the residual that may still produce orphans.** If non-zero, file a
  follow-up issue and leave the test at WARN (revert this YAML change), then
  proceed.

- [ ] **Step 3: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml
git -C $WT commit -m "$(cat <<'EOF'
test(dbt): promote fct_survey_responses.survey_submission_key relationships test to error

Now that fct_survey_submissions and fct_survey_responses hash from the same
source row, the FK can be enforced at error severity.

Refs #3899, #3896.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Annotate `int_surveys__manager_survey_details.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__manager_survey_details.sql`
  (line 1)

Per spec: the intermediate is no longer the source of truth for Manager
respondent identity. Add a header comment noting its narrowed role so future
readers don't extend it.

- [ ] **Step 1: Edit the file**

Insert at the top of the file (before `with`):

Replace:

```sql
with
    response_identifiers as (
```

with:

```sql
/*
 * NOTE (post-#3899): This model is retained for two purposes only:
 *  - The subject-of-evaluation overlay (subject_df_employee_number and
 *    subject staff columns), joined onto submissions_grain in
 *    fct_survey_submissions.
 *  - The historic Alchemer Manager archive (survey_id =
 *    'historic_alchemer_Manager_survey'), sourced directly by
 *    fct_survey_submissions and dim_survey_administrations.
 *
 * Manager Survey respondent identity (live Google Forms) now flows through
 * int_surveys__survey_responses, not this model. Do not extend the
 * Google-Forms arm here; add new logic to int_surveys__survey_responses
 * or wait for the int_surveys__survey_submissions extraction (#3918).
 */
with
    response_identifiers as (
```

- [ ] **Step 2: Parse to confirm the comment doesn't break anything**

```bash
uv run dbt parse --project-dir $WT/src/dbt/kipptaf --no-partial-parse
```

Expected: clean parse, no errors.

- [ ] **Step 3: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/surveys/intermediate/int_surveys__manager_survey_details.sql
git -C $WT commit -m "$(cat <<'EOF'
docs(dbt): annotate int_surveys__manager_survey_details narrowed role

Refs #3899, #3918.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Full downstream build + final verification

**Files:** none.

Catch anything the per-task `+`-selectors missed (other consumers of the touched
models).

- [ ] **Step 1: Full downstream build from both marts**

```bash
uv run dbt build \
  --select fct_survey_submissions+ dim_survey_administrations+ fct_survey_responses+ \
  --project-dir $WT/src/dbt/kipptaf
```

Expected: PASS. Watch for any unexpected downstream failures (Cube semantic
layer views, Tableau extracts, etc.).

- [ ] **Step 2: Check warnings**

After the build completes, scan the log for warning-severity test failures:

```bash
grep -E "WARN|warn " $WT/src/dbt/kipptaf/logs/dbt.log | tail -40
```

Expected: no new warnings on `fct_survey_submissions`,
`dim_survey_administrations`, or `fct_survey_responses`. Pre-existing warnings
on adjacent models are fine.

- [ ] **Step 3: Push and open PR**

```bash
git -C $WT push -u origin cbini/refactor/claude-survey-fact-submission-grain-marts
```

PR body uses `.github/pull_request_template.md`. Title:
`refactor(dbt): bake submission-grain unification into survey-fact marts`. Body
must reference `Closes #3899` and `Closes #3896` and `Refs #3918`.

---

## Verification summary against spec acceptance

| Acceptance item                                                                                                                                     | Task                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| All four CTEs in `fct_survey_submissions` source from `submissions_grain` via `dbt_utils.deduplicate()` — no `select distinct`                      | Task 1                                                                   |
| All three (+ trailing `deduped`) CTEs in `dim_survey_administrations` source from `submissions_grain` — no `select distinct`                        | Task 2                                                                   |
| Manager subject overlay joins `int_surveys__manager_survey_details` only for subject columns; hash inputs come from `submissions_grain`             | Task 1 (manager_subject_overlay CTE)                                     |
| Historic Alchemer Manager archive isolated as its own union arm in `fct_survey_submissions`                                                         | Task 1 (historic_archive_submissions CTE)                                |
| `survey_submission_key` uniqueness test passes on both facts                                                                                        | Tasks 1, 5                                                               |
| `dim_survey_administrations` PK uniqueness test passes                                                                                              | Tasks 2, 5                                                               |
| `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key` relationships test returns 0 orphans (promote to error) | Task 3                                                                   |
| Stale TODO refs (#3629, #3635) replaced with #3918                                                                                                  | Tasks 1, 2 (`TODO: #3918` in `submissions_grain` and `deduped` comments) |
| `int_surveys__manager_survey_details` carries header comment noting narrowed role                                                                   | Task 4                                                                   |
