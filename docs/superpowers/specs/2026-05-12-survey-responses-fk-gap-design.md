# `fct_survey_responses → fct_survey_submissions` FK gap — design

Refs #3794. Part of project [#4](https://github.com/orgs/TEAMSchools/projects/4)
"enrollment FK cluster" batch.

## Problem

After #3793 unified the `survey_submission_key` hash composition on both facts,
`fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
relationships test still WARNs. Residual is coverage, not hash drift.

Current prod sizing (BigQuery, 2026-05-12):

- 143,758 orphan response rows
- 12,261 distinct orphan submissions

## Root cause

`fct_survey_submissions` filters student responses to an active-enrollment
match; `fct_survey_responses` carries every student response with a non-null
`question_shortname`. Two scope mismatches produce orphans:

1. **Student leg** — `fct_survey_submissions.student_submissions_ranked`
   (`fct_survey_submissions.sql:71-75`) does an `INNER JOIN` to
   `int_extracts__student_enrollments` on `(respondent_email, academic_year)`
   with `enroll_status = 0`. Any response whose email doesn't resolve to an
   active enrollment in the same academic year is dropped from submissions but
   remains in responses.
2. **Staff leg** — `fct_survey_submissions.staff_submissions`
   (`fct_survey_submissions.sql:30-31`) filters
   `respondent_employee_number is not null`. Responses with null employee number
   stay in `fct_survey_responses`.

Three orphan sub-classes within the student leg (from the prior verification
captured on the issue):

- (a) **Inactive but known** — email matches an enrollment row in a different
  academic year, or in the same year with `enroll_status != 0`. Resolvable.
- (b) **Unknown email** — email never appears in
  `int_extracts__student_enrollments`. Not resolvable; must accept null FK.
- (c) **Staff residual** — null `respondent_employee_number`. Small class.

## Decision

**Widen `fct_survey_submissions` to cover every response that
`fct_survey_responses` carries.** The student leg becomes a `LEFT JOIN` with a
last-known-enrollment fallback for `student_enrollment_key`; the staff leg drops
the null-employee-number filter and lets `staff_key` be null when source is
null.

Rejected alternatives:

- _Filter `fct_survey_responses` down to the active-enrollment scope_ — drops
  real response events; analysts counting "students who answered Q1" would get a
  silently low number.
- _Sentinel "unknown enrollment" submission row_ — pollutes
  `dim_student_enrollments` with synthetic keys. Strict-chain traversal
  consumers would treat it as a real enrollment.

## Implementation

### `fct_survey_submissions.sql` — student leg

Replace the `student_submissions_ranked` CTE so it:

1. `LEFT JOIN`s `int_extracts__student_enrollments` on
   `(respondent_email, academic_year)` with **no** `enroll_status` predicate.
2. Tiebreak with
   `row_number() OVER (PARTITION BY survey_response_id ORDER BY (enroll_status = 0) DESC, entrydate DESC)`
   so an active match wins, then most recent entrydate.
3. For responses whose email has no match in the same academic year, add a
   second CTE that looks up the same student's most recent enrollment across any
   academic year by `respondent_email`, partitioned with
   `row_number() OVER (PARTITION BY respondent_email ORDER BY academic_year DESC, entrydate DESC)`
   so we attribute to the latest known enrollment.
4. `COALESCE` the same-year match with the fallback. Responses whose email is
   unknown to enrollments entirely fall through with null `student_number` /
   `_dbt_source_relation` / `entrydate`.

`student_enrollment_key` is already wrapped in the
`if(... is not null, generate_surrogate_key(...), cast(null as string))` pattern
at the final SELECT, so null inputs produce a null FK without further changes.

### `fct_survey_submissions.sql` — staff leg

Remove the `respondent_employee_number is not null` filter from
`staff_submissions` (`fct_survey_submissions.sql:30-31`). The final SELECT's
`staff_key` already would need wrapping — apply the nullable-FK pattern:

```sql
if(
    respondent_employee_number is not null,
    {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
    cast(null as string)
) as staff_key,
```

The same wrap is already used for `subject_staff_key`; this just makes
`staff_key` symmetric.

### Tests

- Keep
  `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
  relationships test at the default mart severity (`warn`); flip to
  `severity: error` once the orphan count returns to zero post-change.
- No `not_null` tests added on `student_enrollment_key` or `staff_key` — both
  are legitimately nullable on this fact (multi-respondent-type union).
- PK uniqueness test on `survey_submission_key` already exists; verify it still
  holds after the widening (composition unchanged, so should be a no-op).

### YAML

- Update `fct_survey_submissions` model description to note that the student leg
  attributes to the most recent known enrollment when no active-year enrollment
  exists, and that `student_enrollment_key` / `staff_key` are nullable for
  responses that can't be attributed.
- No column rename or contract change — hash composition is unchanged, all
  output columns keep their types.

## Out of scope

- **#3777** (ES Writing bridge coverage) — separate spec, separate PR; same
  PR-batch label on project board.
- **#3629** (response-grain upstream refactor) — orthogonal; this fix lives
  entirely in `fct_survey_submissions`.
- **#3790** multi-select expansion — already merged; sizing in this spec
  includes its contribution.
- **`int_extracts__student_enrollments` semantics** — taken as authoritative for
  "what enrollments exist." No upstream change.

## Pre-merge checklist (per `marts/CLAUDE.md`)

- [ ] Scan touched models for diamond paths (none introduced — only adds a
      same-target fallback path within the existing
      `int_extracts__student_enrollments` join).
- [ ] Scan touched models for R1–R10 violations (no new columns).
- [ ] Pull marts-model warnings from latest CI run via dbt MCP
      `get_job_run_error(warning_only=true)`; confirm the
      `fct_survey_responses → fct_survey_submissions` warning disappears and no
      new warnings are introduced.
- [ ] Scan
      [project board #4](https://github.com/orgs/TEAMSchools/projects/4/views/1)
      for bonus issues incidentally resolved; close them in the PR.
- [ ] Confirm orphan rows return to 0 on the PR-branch schema
      (`dbt_cloud_pr_<ci_id>_3794_marts`).

## Acceptance criteria

- `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
  relationships test returns 0 rows on the PR-branch schema.
- `fct_survey_submissions.survey_submission_key` uniqueness test still passes.
- Row count of `fct_survey_submissions` increases by approximately the number of
  orphan submissions resolved (~12K), not by a fan-out multiplier.
- `student_enrollment_key` nullability: null only for responses whose email is
  unknown to `int_extracts__student_enrollments` entirely (sized at ~17 from the
  prior verification, likely similar now).
- `staff_key` nullability: null only for responses with null
  `respondent_employee_number` (~23 distinct submissions in the prior
  verification).
