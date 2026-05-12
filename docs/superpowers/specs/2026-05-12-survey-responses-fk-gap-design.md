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

`fct_survey_submissions.student_submissions_ranked`
([fct_survey_submissions.sql:71-75](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L71-L75))
joins `int_extracts__student_enrollments` on `(respondent_email, academic_year)`
with `enr.enroll_status = 0`. Both legs of that predicate are wrong:

- **`enroll_status` is a student-level flag**, not an enrollment-level one — it
  reflects the student's _current_ active status across all their enrollment
  rows, not whether the row in hand was active on `date_submitted`. Filtering by
  it drops every historical enrollment row for students who have since withdrawn
  / transferred / graduated, even though those students were active when they
  submitted the survey.
- **`academic_year` equality** assumes the submission's academic-year tag
  exactly matches the enrollment's; for students with mid-year enrollment
  changes (transfer in/out, exit + re-entry) the matching enrollment row may
  fall under a different year tag than the submission's term.

The correct membership condition is **`date_submitted` falls inside the
enrollment's `[entrydate, exitdate)` window** — that's the only join predicate
that answers "which enrollment was this student in when they submitted?"

The staff leg has a separate, smaller coverage gap with two contributing causes:

1. **Upstream null `respondent_employee_number`.**
   `int_surveys__survey_responses` resolves `respondent_employee_number` by
   joining `int_people__staff_roster_history` on either
   `local_part(respondent_email) = srh.sam_account_name` or
   `respondent_email = srh.google_email`, time-bounded to the row's effective
   window. `int_people__staff_roster_history` carries the **current**
   `sam_account_name` / `google_email` on every effective-dated row — those
   identifiers are not historicized — so a survey submitted under an employee's
   prior email/username can never match. Empirically (prod, 2026-05-12) 23 of
   35,600 staff/engagement responses across 14 distinct emails are null; 13 of
   the 14 emails are preserved as historical entries in
   `stg_google_directory__users.emails` / `aliases` with a current
   `primary_email` that does resolve to an `employee_number`.
2. **Downstream filter on the resolved value.**
   `fct_survey_submissions.staff_submissions`
   ([fct_survey_submissions.sql:30-31](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L30-L31))
   then filters `respondent_employee_number is not null`, dropping the residual
   from `fct_survey_submissions` entirely.

## Decision

**Replace the student-leg join predicate with a date-range membership check on
`date_submitted` against the enrollment's entry / exit dates, and drop
`enroll_status` and `academic_year` from the join.** Use a half-open interval
per `marts/CLAUDE.md` → "Date-range joins" to avoid boundary fan-out on
back-to-back enrollments.

For the staff leg, two changes:

1. **Upstream in `int_surveys__survey_responses`**: add an additive Google
   Directory alias-resolution fallback for `respondent_employee_number` — when
   the existing `sam_account_name` / `google_email` join returns null, map
   `respondent_email` to its `primary_email` via `stg_google_directory__users`
   (any of `primary_email`, `aliases`, `emails[].address`), then re-join
   `int_people__staff_roster_history` on `srh.google_email = primary_email`.
   Empirically recovers 21 of 23 currently- null submissions with zero silent
   reassignments and zero regressions to currently-resolved submissions; the 2
   residuals are one employee whose `int_people__staff_roster_history` coverage
   gap (separate upstream issue) leaves them unresolved.
2. **Downstream in `fct_survey_submissions`**: drop the
   `respondent_employee_number is not null` filter and let `staff_key` be null
   when source is null, covering the residual.

Rejected alternatives:

- _Keep `academic_year` in the join and only fix `enroll_status`_ — still drops
  responses whose submission-year tag disagrees with the enrollment's year tag
  (the year-tag mismatch is real for mid-year transfers).
- _Filter `fct_survey_responses` down to the active-enrollment scope_ — drops
  real response events; analysts counting "students who answered Q1" would get a
  silently low number.
- _Sentinel "unknown enrollment" submission row_ — pollutes
  `dim_student_enrollments` with synthetic keys. Strict-chain traversal
  consumers would treat it as a real enrollment.

## Implementation

### `fct_survey_submissions.sql` — student leg

Rewrite `student_submissions_ranked` so the join is:

```sql
inner join
    {{ ref("int_extracts__student_enrollments") }} as enr
    on sr.respondent_email = enr.student_email
    and enr.entrydate <= sr.date_submitted
    and enr.exitdate > sr.date_submitted
```

Half-open interval (`entrydate <= ... and exitdate > ...`), not `BETWEEN` — per
`marts/CLAUDE.md`, `BETWEEN` fans out when consecutive enrollments share a
boundary date.

**Drop the existing `row_number() OVER (PARTITION BY survey_response_id ...)`
tiebreaker** and collapse the `student_submissions_ranked` →
`student_submissions` two-CTE structure into a single CTE.
`int_extracts__student_enrollments` has 3 overlapping date-range pairs in prod
across 2 students (one Camden boundary off-by-one between two consecutive
same-school years; one Miami student with a wide phantom multi-year row
coexisting with two short same-year rows). Joining all distinct student SCD
submissions against the table under the half-open predicate produces zero
multi-matches today — none of the three overlap windows intersect a submission
date for the affected students. The PK uniqueness test on
`survey_submission_key` guards against regression if a future overlap ever does
produce fan-out.

Responses whose email resolves to no enrollment row whose window contains
`date_submitted` fall out of the student leg. The `student_enrollment_key`
column is built from `student_number` / `_dbt_source_relation` / `academic_year`
/ `entrydate` at the final SELECT
([fct_survey_submissions.sql:320-329](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L320-L329)),
so the `academic_year` value attributed to the submission comes from the
enrollment row itself (`enr.academic_year`), not from `sr.academic_year`. Pull
`enr.academic_year` through the CTE alongside `student_number` /
`_dbt_source_relation` / `entrydate`, and reference it (not `sr.academic_year`)
in the `student_enrollment_key` hash inputs.

### `int_surveys__survey_responses.sql` — alias-resolution fallback

Both `respondent_employee_number`-producing branches of the file (Google Forms
union at `int_surveys__survey_responses.sql:17` and Alchemer-equivalent at
`int_surveys__survey_responses.sql:81`) currently `left join`
`int_people__staff_roster_history` on
`(local_part(respondent_email) = srh.sam_account_name OR respondent_email = srh.google_email)`
plus time-bound + `primary_indicator`. Keep that join. Add a second `left join`
against an alias-resolution CTE; pull
`coalesce(srh.employee_number, srh_alias.employee_number)` (and the parallel
`formatted_name` / `sam_account_name` / `user_principal_name`) through to the
SELECT.

Alias-resolution CTE shape:

```sql
gdir_alias_map as (
    select gd.primary_email, addr.address as known_address
    from {{ ref("stg_google_directory__users") }} as gd,
        unnest(gd.emails) as addr
    union distinct
    select gd.primary_email, alias
    from {{ ref("stg_google_directory__users") }} as gd,
        unnest(gd.aliases) as alias
    union distinct
    select gd.primary_email, gd.primary_email
    from {{ ref("stg_google_directory__users") }} as gd
),
```

Fallback join (applied in both union branches):

```sql
left join gdir_alias_map as gam
    on fr.respondent_email = gam.known_address
left join {{ ref("int_people__staff_roster_history") }} as srh_alias
    on gam.primary_email = srh_alias.google_email
    and timestamp(fr.last_submitted_time)
        between srh_alias.effective_date_start_timestamp
        and srh_alias.effective_date_end_timestamp
    and srh_alias.primary_indicator
```

Reference `stg_google_directory__users` is already a kipptaf source; no new
upstream package required. Verify that the new CTE doesn't introduce fan-out at
the response grain — the `union distinct` form on `gdir_alias_map` deduplicates
redundant (primary_email, known_address) pairs across users.

### `fct_survey_submissions.sql` — staff leg

Remove the `respondent_employee_number is not null` filter from
`staff_submissions`
([fct_survey_submissions.sql:30-31](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L30-L31)).
Apply the nullable-FK wrap to `staff_key` at the final SELECT
([fct_survey_submissions.sql:289](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L289)):

```sql
if(
    respondent_employee_number is not null,
    {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
    cast(null as string)
) as staff_key,
```

Symmetric with `subject_staff_key`
([fct_survey_submissions.sql:294-298](src/dbt/kipptaf/models/marts/facts/fct_survey_submissions.sql#L294-L298)).

### Tests

- Keep
  `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
  relationships test at the default mart severity (`warn`); flip to
  `severity: error` once the orphan count returns to zero post-change.
- No `not_null` tests added on `student_enrollment_key` or `staff_key` — both
  are legitimately nullable on this fact (multi-respondent-type union).
- PK uniqueness test on `survey_submission_key` already exists. With the
  tiebreaker dropped, this test is the load-bearing guard against future
  enrollment-overlap fan-out — verify it still passes on the PR-branch schema.

### YAML

- Update `fct_survey_submissions` model description to note that the student leg
  attributes a response to the enrollment whose `[entrydate, exitdate)` window
  contains `date_submitted`, and that `student_enrollment_key` / `staff_key` are
  nullable for responses that can't be attributed.
- No column rename or contract change — hash composition is unchanged
  structurally (same input columns); the `academic_year` _value_ feeding the
  hash now sources from the enrollment row rather than the response row, which
  will reshuffle keys for any response whose response-year tag differed from its
  enrollment-year tag. Acceptable per `marts/CLAUDE.md` → "Spec authoring
  context" (no production consumers yet).

## Out of scope

- **#3777** (ES Writing bridge coverage) — separate spec, separate PR; same
  PR-batch label on project board.
- **#3629** (response-grain upstream refactor) — orthogonal; this fix lives
  entirely in `fct_survey_submissions`.
- **#3790** multi-select expansion — already merged; sizing in this spec
  includes its contribution.
- **`int_extracts__student_enrollments` semantics** — taken as authoritative for
  "what enrollments exist" and for `entrydate` / `exitdate` values. No upstream
  change.
- **Historicizing `sam_account_name` / `google_email` in
  `int_people__staff_roster_history`** — the alias-resolution fallback in
  `int_surveys__survey_responses` covers the staff-survey case empirically; a
  full historicization of the identifier columns would help other email-keyed
  joiners and should be filed separately.
- **LDAP `employeeID` provisioning gap** — one of the 14 null-employee emails
  (its own Directory primary, no alias chain) maps to an employee who is Active
  in ADP across the submission window AND has a complete LDAP
  (`stg_ldap__user_person`) record with the correct `google_email`,
  `sam_account_name`, `user_principal_name`, and `mail`. The break is in LDAP's
  `employee_number` column — it's NULL because the user's `employeeID` AD
  attribute was set to a temporary placeholder (`TMP00378`-style) at
  provisioning and never reconciled to her real ADP `employee_number`.
  `int_people__staff_roster_history` joins ADP ↔ LDAP on `employee_number`, so
  that NULL on the LDAP side strands her ADP record with no AD/Workspace
  identifiers. Neither the existing `sam_account_name` / `google_email` join nor
  the Directory-alias fallback can recover her. Remediation is administrative
  (correct her AD `employeeID` attribute), not a model change; tracked
  separately. The nullable `staff_key` wrap covers the residual here.

## Pre-merge checklist (per `marts/CLAUDE.md`)

- [ ] Scan touched models for diamond paths (none introduced — the join shape
      changes but the FK target is unchanged).
- [ ] Scan touched models for R1–R10 violations (no new columns).
- [ ] Pull marts-model warnings from latest CI run via dbt MCP
      `get_job_run_error(warning_only=true)`; confirm the
      `fct_survey_responses → fct_survey_submissions` warning disappears and no
      new warnings are introduced (incl. no new `staff_key → dim_staff` orphans
      from the alias-resolved employee numbers).
- [ ] Scan
      [project board #4](https://github.com/orgs/TEAMSchools/projects/4/views/1)
      for bonus issues incidentally resolved; close them in the PR.
- [ ] Confirm orphan rows return to 0 on the PR-branch schema
      (`dbt_cloud_pr_<ci_id>_3794_marts`).

## Acceptance criteria

- `fct_survey_responses.survey_submission_key → fct_survey_submissions.survey_submission_key`
  relationships test returns 0 rows on the PR-branch schema.
- `fct_survey_submissions.survey_submission_key` uniqueness test still passes.
- `student_enrollment_key` nullability: null only for responses whose email has
  no enrollment row covering `date_submitted` in
  `int_extracts__student_enrollments`.
- `staff_key` nullability: null only for responses whose
  `respondent_employee_number` cannot be resolved by either the existing
  `sam_account_name` / `google_email` join or the Google Directory alias
  fallback (sized at 2 distinct submissions, 1 email, in prod 2026-05-12).
- `int_surveys__survey_responses.respondent_employee_number`: no
  currently-non-null value changes; recovered null count matches the pre-merge
  verification (21 of 23 currently-null staff/engagement submissions resolve
  post-change).
