# fct_survey_responses orphan resolution

**Issue:** [#4018](https://github.com/TEAMSchools/teamster/issues/4018)
**Branch:** `cbini/fix/claude-survey-attribution` **Author:** Claude
(brainstormed with cbini) **Date:** 2026-05-28

## Problem

`fct_survey_responses` has 47,788 rows / 2,727 distinct submissions whose
`survey_submission_key` has no match in `fct_survey_submissions`. The
`relationships_fct_survey_responses_survey_submission_key__…` test runs at
`severity: warn` so CI stays green; promoting it to `error` (the long-stated
goal) requires resolving the orphans first.

Issue #4018 attributes the orphans to three terms-sheet gaps plus a latent
NULL-collision risk in the historic_alchemer fallback hash. Diagnostic
verification on prod (2026-05-27) reproduces the bucket sizes but corrects two
of the framings — see comment
[#4558722536](https://github.com/TEAMSchools/teamster/issues/4018#issuecomment-4558722536).

### Verified attribution

| Mechanism                                                      | Distinct submissions |   % | Owner     |
| -------------------------------------------------------------- | -------------------: | --: | --------- |
| Terms-sheet missing admin tuple (Manager AY2022 MGR1/MGR2)     |                2,556 | 94% | Ops       |
| Terms-sheet date-window gap (Student/Staff SCD + live Manager) |                  142 |  5% | Ops       |
| Enrollment-match miss (Student SCD AY-bucketed)                |                   28 |  1% | Follow-up |
| NULL-collision in archive fallback hash (latent)               |                    0 |   — | Code      |

Both Ops categories share the same root cause: `int_surveys__survey_responses`
resolves `academic_year`/`term_code` via a `left join` to
`stg_google_sheets__reporting__terms` on
`date(date_submitted) between start_date and end_date and type = 'SURVEY'`.
Submissions outside any matching window land with null AY/term and never re-bind
in `fct_survey_submissions`. The Manager AY2022 case is the same mechanism in a
different shape: no
`(name='Manager Survey', AY=2022, code=MGR1|MGR2, type='SURVEY')` row exists at
all in the sheet, so the downstream join in
`fct_survey_submissions.manager_submissions` drops the 2,556 archive rows.

The 28 enrollment-residue rows have valid AY/term upstream but fail the
`int_extracts__student_enrollments` inner join in
`fct_survey_submissions.student_submissions` — 19 emails with no enrollment
record at all, 9 with enrollment records that don't overlap the submission date.
No clean upstream fix; tracked in a follow-up issue.

## Goals

- Drive the `relationships_fct_survey_responses_*` tests to zero violations.
- Promote those tests to `severity: error`.
- Make future terms-sheet gaps surface as warn-level dbt failures at the
  intermediate layer instead of silently producing null-AY/term rows that only
  show up at the downstream mart relationship check.
- Eliminate the latent NULL-collision risk in `historic_archive_submissions`.

## Non-goals

- Fixing the 28 enrollment-residue Student SCD rows. Tracked separately.
- Cube-side measure changes — column shape of `fct_survey_responses` is
  unchanged.
- Ops sheet edits themselves — handed to Ops via the PR description; not
  blocking for this PR's CI because the inner-join change (edit 4 below) removes
  all orphans at build time regardless of sheet state.

## Design

Four edits land together in one PR.

### Edit 1 — NULL-safe fallback hash in `historic_archive_submissions`

In
[src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql),
replace the `concat`-based fallback in
`historic_archive_submissions.survey_response_id`:

```sql
coalesce(
    ms.survey_response_id,
    format(
        '%T_%T_%T',
        ms.respondent_df_employee_number,
        ms.subject_df_employee_number,
        ms.campaign_reporting_term
    )
) as survey_response_id,
```

Per root CLAUDE.md ("For NULL-safe distinct counts on composite keys, use
`format("%T|%T", a, b)`"). `concat` returns NULL when any argument is NULL, so
two archive rows with NULL respondent or subject employee numbers would both
fall back to NULL and `generate_surrogate_key` would hash them to the same
placeholder. `%T` emits a NULL-distinguishable literal.

Hash-stability check: this changes the output for **all** fallback-path rows,
not just NULL ones (`A_B_C` vs `"A"_"B"_"C"`). Per issue #4018 the archive
fallback path is currently unused in prod (every archive row has a non-null
`survey_response_id`), so no observable hash churn — but verify pre-merge with:

```sql
select count(*)
from `teamster-332318.kipptaf_surveys.int_surveys__manager_survey_details`
where survey_id = 'historic_alchemer_Manager_survey'
  and survey_response_id is null
```

Expected result: 0. If non-zero, coordinate hash-change with downstream
consumers per
[src/dbt/kipptaf/models/marts/CLAUDE.md](src/dbt/kipptaf/models/marts/CLAUDE.md)
hash-change discipline before merging.

### Edit 2 — Warn-level test for window-gap rows in `int_surveys__survey_responses`

Add a model-level data_test in
[src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys\_\_survey_responses.yml](src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml)
using `dbt_utils.expression_is_true` (or a singular test in
`src/dbt/kipptaf/tests/`). The predicate flags rows where the survey title is
known to require terms-sheet attribution but the join landed null:

```yaml
- dbt_utils.expression_is_true:
    arguments:
      expression: |
        survey_title not in (
            'School Community Diagnostic Staff Survey',
            'School Community Diagnostic Student Survey',
            'KIPP NJ & KIPP Miami Family Survey',
            'KIPP Miami Re-Commitment Form & Family School Community Diagnostic',
            'Engagement & Support Surveys',
            'Manager Survey'
        )
        or (academic_year is not null and term_code is not null)
    config:
      severity: warn
```

Surfaces future window-gap submissions at the staging layer with a clear signal
("widen terms-sheet windows") instead of bleeding into the downstream FK test
where the mechanism is obscured.

### Edit 3 — Warn-level test for missing admin tuples in `int_surveys__manager_survey_details`

Symmetric coverage for the Manager-historic shape, which doesn't flow through
the date-window mechanism. Add a singular test at
`src/dbt/kipptaf/tests/test_int_surveys__manager_survey_details__terms_coverage.sql`
asserting every `(campaign_academic_year, campaign_reporting_term)` tuple
resolves to a `(name='Manager Survey', type='SURVEY')` row in
`stg_google_sheets__reporting__terms`:

```sql
{{ config(severity='warn') }}

select
    ms.campaign_academic_year,
    ms.campaign_reporting_term,
    count(*) as orphan_rows,
from {{ ref("int_surveys__manager_survey_details") }} as ms
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on rt.`name` = 'Manager Survey'
    and ms.campaign_academic_year = rt.academic_year
    and ms.campaign_reporting_term = rt.code
    and rt.type = 'SURVEY'
where ms.campaign_academic_year is not null
  and rt.academic_year is null
group by 1, 2
```

Add the test's `description:` (and `meta.dagster.ref` if Dagster surfacing is
desired) under `data_tests:` in a tests-level properties yml per
src/dbt/CLAUDE.md singular-test description placement rule.

### Edit 4 — Inner-join FK enforcement in `fct_survey_responses`

In
[src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql](src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql),
project `survey_submission_key` once in the `all_responses` CTE and inner join
`fct_survey_submissions` on it:

```sql
all_responses as (
    select
        survey_id,
        survey_response_id,
        survey_question_id,
        question_shortname,
        response_text,
        response_value,
        {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
            as survey_submission_key,
    from general_responses
    union all
    select
        survey_id,
        survey_response_id,
        survey_question_id,
        question_shortname,
        response_text,
        response_value,
        {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
            as survey_submission_key,
    from manager_responses
)

select
    {{ dbt_utils.generate_surrogate_key(
        ["survey_id", "survey_response_id", "survey_question_id"]) }}
        as survey_response_key,

    ar.survey_submission_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
        as survey_question_key,

    response_value,
    response_text,
from all_responses as ar
inner join {{ ref("fct_survey_submissions") }} as fss
    using (survey_submission_key)
```

Encodes the relationships test's contract as a model-level invariant. Intra-
mart `ref()` is permitted (src/dbt/kipptaf/models/marts/CLAUDE.md). No circular
dependency: `fct_survey_submissions` doesn't `ref()` `fct_survey_responses`.

Effect on row counts at merge:

- Today: 47,788 orphan response rows present.
- After merge (before any Ops edits): 47,788 fewer rows in
  `fct_survey_responses`. `relationships_*` test = 0 violations.
- After Ops adds Manager AY2022 MGR1/MGR2 rows: ~43,810 of those rows re-appear
  with valid `survey_submission_key`.
- After Ops widens SCD/MGR windows: ~142 more re-appear.
- 28 enrollment-residue rows stay filtered until follow-up issue resolves.

### Edit 5 — Severity promotion in `fct_survey_responses.yml`

In
[src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml](src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml):

```yaml
- relationships:
    arguments:
      to: ref('fct_survey_submissions')
      field: survey_submission_key
    config:
      severity: error
```

Same change for the `survey_administration_key` relationship if it's currently
set to warn.

## Acceptance criteria

1. `historic_archive_submissions` fallback uses `format('%T_%T_%T', …)`.
2. Warn-level test on `int_surveys__survey_responses` for window-gap rows.
3. Warn-level test on `int_surveys__manager_survey_details` for missing admin
   tuples.
4. `fct_survey_responses` projects `survey_submission_key` in `all_responses`
   and `inner join`s `fct_survey_submissions` on it.
5. Both `relationships_fct_survey_responses_*` tests at `severity: error`.
6. Pre-merge query confirms hash-stability (`survey_response_id is null` archive
   count = 0).
7. dbt Cloud CI passes with `relationships_*` at error and the two new
   warn-level tests expected to fail until Ops sheet edits land.
8. Post-merge BigQuery confirms 0 orphans:

   ```sql
   select count(*)
   from `teamster-332318.kipptaf_marts.fct_survey_responses` r
   left join `teamster-332318.kipptaf_marts.fct_survey_submissions` s
       using (survey_submission_key)
   where s.survey_submission_key is null
   ```

## Verification

- **Local:**
  `uv run dbt build --select fct_survey_responses+ fct_survey_submissions+ int_surveys__survey_responses int_surveys__manager_survey_details --project-dir .worktrees/cbini/fix/claude-survey-attribution/src/dbt/kipptaf`
- **dbt Cloud CI:** confirm `relationships_fct_survey_responses_*` PASS at
  error. The two new warn-level tests are expected in `warning_only=true` fetch
  while Ops sheet edits are pending — not blocking.
- **Post-merge prod:** orphan-count query above returns 0.

## Follow-up issues to file before PR opens

- **Enrollment-attribution residue.** 28 Student SCD responses with no matching
  `int_extracts__student_enrollments` row overlapping `date_submitted`. 19
  emails with no enrollment ever; 9 with enrollment but date-miss. Filtered out
  at build time by edit 4. Link from #4018 and from the PR.

## Ops-sheet handoff (called out in PR body, not blocking)

- Add
  `(name='Manager Survey', academic_year=2022, code='MGR1', type='SURVEY', …)`
  and `(… code='MGR2' …)` rows. Reclaims 2,556 submissions.
- Widen Student SCD AY2025 window (currently 2025-12-01 → 2026-03-01) and/or add
  interim windows for off-period submissions. Reclaims 114.
- Add Staff SCD coverage for the 2024-11-09 → 2025-02-13 gap. Reclaims 19.
- Widen Manager Survey AY2024 MGR1/MGR2 windows to cover 2024-11-09 → 2025-04-26
  stragglers. Reclaims 9.
- Once orphans hit zero, the two new warn-level tests clear.

## Out of scope

- 28 enrollment-residue Student SCD rows (separate follow-up).
- Cube-side measure changes (column shape unchanged).
