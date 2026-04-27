# Batch B — Staff Coverage Design

**Date:** 2026-04-27 **Issues:**
[#3687](https://github.com/TEAMSchools/teamster/issues/3687),
[#3716](https://github.com/TEAMSchools/teamster/issues/3716) **Project board:**
PR Batch B (staff coverage) on
[Project 4](https://github.com/orgs/TEAMSchools/projects/4/views/1)

## Summary

Batch B addresses two related staff-coverage issues in the kipptaf marts:

- **#3716** — Five `relationships` tests currently fail (~49K orphan rows)
  across `fct_staff_observation_goals`, `fct_staff_observations`, and
  `dim_staffing_positions`. A diagnostic probe (BigQuery, this spec) shows
  **none of these are real coverage gaps**. They split between null-hash
  placeholder bugs (LEFT JOIN to a surrogate-key call without the null-wrap
  pattern) and domain-encoded sentinel codes.
- **#3687** — `int_people__staff_roster_history` carries every change to a
  worker's full attribute set, so date-range joins for survey expectations and
  attrition fan out when concurrent or non-assignment-relevant changes occur.
  Two marts (`dim_survey_expectations`, `fct_staff_attrition`) work around this
  with `SELECT DISTINCT`.

The fix retires the `int_people__staff_roster_history` date-range join pattern
in favor of star-schema traversal through existing SCD dims
(`dim_work_assignment_status` for assignment status,
`dim_staff_work_assignments` for current attributes), plus one new narrow SCD
mart (`dim_work_assignment_primary`) that captures `primary_indicator` history.
`dim_survey_expectations` is renamed to `bridge_survey_expectations` to reflect
its factless-fact semantics.

## Diagnostic findings

Probes against the prod warehouse classified all 49K orphan rows reported by the
failing relationships tests:

| Test                                            |  Count | Class                                                                       | Resolution     |
| ----------------------------------------------- | -----: | --------------------------------------------------------------------------- | -------------- |
| `fct_staff_observation_goals.creator_staff_key` | 48,786 | Null-hash placeholder (LEFT JOIN, no null-wrap)                             | Mart null-wrap |
| `fct_staff_observations.teacher_staff_key`      |      4 | Null-hash placeholder                                                       | Mart null-wrap |
| `fct_staff_observations.teacher_staff_key`      |      5 | `employee_number = 999999` (SchoolMint Grow test account "Awesome Teacher") | Staging filter |
| `fct_staff_observation_goals.teacher_staff_key` |      2 | Same SchoolMint Grow test account                                           | Staging filter |
| `dim_staffing_positions.incumbent_staff_key`    |    692 | Seat-tracker placeholder codes (0, 1, 2, 999995–999999)                     | Mart null-map  |
| `dim_staffing_positions.recruiter_staff_key`    |    107 | Seat-tracker placeholder code (0)                                           | Mart null-map  |

The seat-tracker codes are confirmed domain placeholders (not test records) that
flag positions whose real employee_number is not yet linked (e.g., `999998` ≈
`Staffed/New Hire` pending ADP onboarding; `999997` ≈ `Position Closed`
swap/budget changes). Rows carry valid seat-state data and must be preserved;
only the spurious employee_number is replaced with NULL.

The "Awesome Teacher" account (SchoolMint Grow `internal_id_int = 999999`, email
`awesometeacher@apps.teamschools.org`) is a real test account in production
data; observed five times by employee 400096 between 2023-07 and 2024-04.
Filtered upstream at staging to remove all downstream traces.

For #3687, a separate probe found that `primary_indicator` changes within an
`item_id` over time on **177 of 4,683 work assignments (3.8%)** — non-trivial
for multi-year attrition tracking, justifying a date-correct SCD lookup rather
than relying on the current snapshot.

## Architecture

```text
# Internal lookups (CTEs in each consumer); NOT output FKs on the
# resulting bridge/fact (would create diamond paths to dim_staff).

bridge_survey_expectations  uses internally:
                            dim_work_assignment_status (status='A', date-range)
                            dim_work_assignment_primary (NEW; is_primary_position, date-range)
                            dim_staff_work_assignments (current; staff_key resolution)
                            output FKs unchanged: survey_administration_key,
                            staff_key, student_enrollment_key,
                            student_contact_person_key

fct_staff_attrition         uses internally:
                            dim_work_assignment_status (status transitions, date-range)
                            dim_work_assignment_primary (NEW; date-range)
                            dim_work_assignment_jobs    (position_title, date-range;
                                                          intern filter)
                            dim_staff_work_assignments (current; staff_key resolution)
                            output FKs unchanged: staff_status_key
```

The SCD dims drive _which rows are emitted_ and _what `is_attrition` /
status-related columns hold_, but they are not exposed as new top-level FKs on
either consumer. Adding `work_assignment_status_key` /
`primary_work_assignment_status_key` as output FKs would create a diamond path
to `dim_staff` (one route via the new FK through `dim_staff_work_assignments`,
another via the existing `staff_key` / `staff_status_key`), violating
`marts/CLAUDE.md`'s strict-chain rule.

Both consumers stop referencing `int_people__staff_roster_history` directly. The
traversal mirrors the existing star-schema pattern documented in
`marts/CLAUDE.md` (e.g.,
`fct_staff_observations → dim_staff_work_assignments → dim_work_assignment_locations → dim_locations → dim_regions`).

`dim_staff`, `dim_staff_status`, `dim_work_assignment_status`, and
`dim_work_assignment_jobs` remain unchanged. `dim_staff_work_assignments` is
edited only to drop the now-redundant `is_primary_position` column (its
date-correct counterpart now lives in the new `dim_work_assignment_primary`).
`int_people__staff_roster_history` remains unchanged (still drives `dim_staff`
and `int_people__staff_roster`).

## Components

### New mart: `dim_work_assignment_primary`

**Path:**
`src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_primary.sql`

**Source:** `int_adp_workforce_now__workers__work_assignments`.

**Logic:**

1. Project `(item_id, effective_date_start, primary_indicator)`.
2. Hash `primary_indicator` and LAG-compare per `item_id` ordered by
   `effective_date_start asc`. Keep change points only.
3. LEAD `effective_date_start` to compute `effective_end_date`; the most recent
   change-point gets `'9999-12-31'`.

**Output columns:**

| Column                        | Type   | Notes                                                           |
| ----------------------------- | ------ | --------------------------------------------------------------- |
| `work_assignment_primary_key` | string | `surrogate_key([item_id, effective_start_date])` — PK           |
| `work_assignment_key`         | string | `surrogate_key([item_id])` — FK to `dim_staff_work_assignments` |
| `is_primary_position`         | bool   | The projected attribute                                         |
| `effective_start_date`        | date   |                                                                 |
| `effective_end_date`          | date   | `'9999-12-31'` for current row                                  |
| `is_current`                  | bool   | `effective_end_date = '9999-12-31'`                             |

**Properties YAML:**

- Inherited `contract: enforced: true` and `materialized: view`.
- `unique` test on `work_assignment_primary_key`.
- `not_null` on `work_assignment_primary_key`, `work_assignment_key`,
  `effective_start_date`, `is_primary_position`.
- `relationships` test for `work_assignment_key` →
  `dim_staff_work_assignments.work_assignment_key`.
- `dbt_utils.expression_is_true` for
  `effective_start_date <= effective_end_date`.
- Description on model and every column.

**Cube exposure:** add to `cube.yml` `cube_semantic_layer.depends_on`.

### Edited mart: `dim_staff_work_assignments`

Drop the `is_primary_position` column from the SELECT and the properties YAML.
The date-correct value now lives on `dim_work_assignment_primary`; keeping both
forms invites mis-use (R8/R9). Cube consumers that filter on
`staff_work_assignments.is_primary_position` must traverse to
`dim_work_assignment_primary` instead — flag in the PR description.

No other column changes; surrogate-key composition unchanged.

### Renamed mart: `dim_survey_expectations` → `bridge_survey_expectations`

**Rename targets:**

- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_expectations.sql` →
  `bridge_survey_expectations.sql`
- `dim_survey_expectations.yml` → `bridge_survey_expectations.yml`
- `dim_survey_expectations.md` → `bridge_survey_expectations.md`
- All `ref("dim_survey_expectations")` calls in `marts/`, `cube.yml`, Tableau
  exposures.

**Logic refactor.** The three staff CTEs (`staff_scd`, `staff_manager`,
`staff_support`) drop their `int_people__staff_roster_history` ref and rebuild
as:

```sql
inner join dim_work_assignment_status as wast
    on sa.response_deadline_date between
       wast.effective_start_date and wast.effective_end_date
    and wast.status_code = 'A'
inner join dim_work_assignment_primary as wap
    on wast.work_assignment_key = wap.work_assignment_key
    and sa.response_deadline_date between
        wap.effective_start_date and wap.effective_end_date
    and wap.is_primary_position
inner join dim_staff_work_assignments as swa
    on wap.work_assignment_key = swa.work_assignment_key
```

(`dim_work_assignment_jobs` is not joined here — survey expectations don't
filter on job_title.)

Output FK shape unchanged: `survey_administration_key`, `staff_key`,
`student_enrollment_key`, `student_contact_person_key`. PK composition unchanged
(whatever `dim_survey_expectations` uses today — verified during
implementation). The SCD lookups stay inside CTEs to avoid a diamond path to
`dim_staff` via `dim_work_assignment_status → dim_staff_work_assignments`.

**Properties YAML:**

- Update `name`, model description, column descriptions for the rebuilt flow.
- Existing uniqueness test verified to still hold under new join chain.
- No new FK columns; no new relationships tests on the bridge.

### Edited mart: `fct_staff_attrition`

The three attrition variants (foundation / NJ compliance / recruitment) share
the same shape; the rebuild applies uniformly.

**Replace `teammate_history` CTE.** Cohort, returner, and termination CTEs
source from
`dim_work_assignment_status × dim_work_assignment_primary × dim_work_assignment_jobs × dim_staff_work_assignments`
instead of `int_people__staff_roster_history`.

- **Year cohort**: `dim_work_assignment_status` with `status_code = 'A'`
  overlapping the academic-year window, intersected with
  `dim_work_assignment_primary` (`is_primary_position` overlapping same window)
  and `dim_work_assignment_jobs` (`position_title != 'Intern'` overlapping same
  window), joined to `dim_staff_work_assignments` for `staff_key`. Date-correct
  intern filter via the SCD.
- **Returner cohort**: `dim_work_assignment_status` active on the year-boundary
  date (e.g., date(ay+1, 9, 1) for foundation), intersected with primary on that
  date and (where intern filter applies) jobs on that date.
- **Termination cohorts**: `dim_work_assignment_status` rows with
  `status_code = 'T'` and `effective_start_date` in window, intersected with
  primary on the termination date and jobs on the termination date.

**No new output FK.** A `primary_work_assignment_status_key` FK to
`dim_work_assignment_status` was considered for slicing attrition by role
context, but rejected — it would create a diamond path to `dim_staff` alongside
the existing `staff_status_key` chain. The SCD lookups stay inside CTEs only;
output FK shape is unchanged (`staff_status_key` remains the sole staff-side
FK). Consumers that want role context at termination time can build it as a
derived attribute in BI rather than via FK.

**Drop the three `SELECT DISTINCT` blocks** and their `-- TODO: #3687` comments.

**Properties YAML:** add column entry + relationships test for the new FK.
Update model description if grain language references the prior join chain.

### Defensive SQL edits

**`fct_staff_observation_goals`:**

- Wrap `creator_staff_key`:
  `if(sr_creator.employee_number is not null, surrogate_key([sr_creator.employee_number]), null)`
- Wrap `teacher_staff_key`:
  `if(gu.internal_id_int is not null, surrogate_key([gu.internal_id_int]), null)`
- The 999999 SchoolMint Grow test account is filtered upstream (see staging edit
  below); no per-mart filter needed.

**`fct_staff_observations`:**

- Wrap `teacher_staff_key`:
  `if(employee_number is not null, surrogate_key([employee_number]), null)`
- Wrap `observer_staff_key`:
  `if(observer_employee_number is not null, surrogate_key([observer_employee_number]), null)`
- Filter
  `where employee_number != 999999 and observer_employee_number != 999999` if
  any 999999 rows remain after upstream test-account filter (defense in depth;
  see staging edit).

**`dim_staffing_positions`:**

Extend existing null-wraps so sentinel placeholder codes also map to NULL:

```sql
if(
    teammate is not null
    and teammate not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
    surrogate_key([teammate]),
    cast(null as string)
) as incumbent_staff_key,

if(
    recruiter is not null
    and recruiter not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
    surrogate_key([recruiter]),
    cast(null as string)
) as recruiter_staff_key,
```

Add a `-- TODO: confirm seat-tracker placeholder semantics with ops` comment so
a follow-up issue can move the null-mapping upstream once domain meaning is
confirmed.

### Staging edit (one narrow exception)

**`stg_schoolmint_grow__users`:** filter out the test account. Add
`where internal_id_int != 999999` (or equivalent — match existing predicate
style in the staging model). This single edit removes 7 downstream orphans (5 in
`fct_staff_observations`, 2 in `fct_staff_observation_goals`) without per-mart
workarounds.

The seat-tracker placeholder codes are NOT filtered at staging — those rows
carry valid seat-state data and the placeholder semantics are not yet confirmed
with the seat-tracker domain owners.

### Documentation edits

**`src/dbt/kipptaf/models/marts/CLAUDE.md`:**

- Add a short paragraph defining the `bridge_*` model category (factless fact
  linking 2+ dims via many-to-many, no measures).
- Strike #3687 from the "Deferred structural follow-ups" list.

**`docs/superpowers/specs/2026-04-15-column-naming-audit.md`:**

- Append an entry to the "Enumerated surrogate-key changes" table for the new
  `work_assignment_primary_key` (composition:
  `[item_id, effective_start_date]`). No FK additions on `fct_staff_attrition`
  or `bridge_survey_expectations` — the SCDs are used in CTEs only, no new keys
  exposed.

## Data flow

### `dim_work_assignment_primary`

```text
int_adp_workforce_now__workers__work_assignments
  → project (item_id, effective_date_start, primary_indicator)
  → LAG primary_indicator over (partition by item_id order by effective_date_start)
  → keep rows where primary_indicator != lag (change points only)
  → LEAD effective_date_start over same window → effective_end_date
     (or '9999-12-31' for the most recent row)
  → surrogate_key(item_id, effective_start_date) → work_assignment_primary_key
```

### `bridge_survey_expectations` (per staff CTE)

```text
dim_survey_administrations × dim_surveys
  → filter to staff-survey names (SCD / Manager / Support)
  → inner join dim_work_assignment_status
       on response_deadline_date between effective_start_date and effective_end_date
      and status_code = 'A'
  → inner join dim_work_assignment_primary
       on dim_work_assignment_status.work_assignment_key
        = dim_work_assignment_primary.work_assignment_key
      and response_deadline_date between effective_start_date and effective_end_date
      and is_primary_position
  → inner join dim_staff_work_assignments
       on work_assignment_key (resolves staff_key)
  → emit (survey_administration_key, staff_key, respondent_type='staff')
  -- (no work_assignment_status_key FK on output; would diamond to dim_staff)
```

### `fct_staff_attrition` (foundation variant; NJ + recruitment analogous)

```text
year_cohort:
  for academic_year ay:
    dim_work_assignment_status WHERE status_code = 'A'
      AND effective_start_date <= date(ay+1, 4, 30)
      AND effective_end_date  >= date(ay, 9, 1)
    × dim_work_assignment_primary (overlap same window, is_primary_position=true)
    × dim_work_assignment_jobs    (overlap same window, position_title != 'Intern')
    × dim_staff_work_assignments  (resolves staff_key)
    → (ay, employee_number, max(effective_start_date) tiebreak)

returner_cohort:
  dim_work_assignment_status active on date(ay+1, 9, 1) (status_code='A')
    × dim_work_assignment_primary (primary on that date)
    × dim_work_assignment_jobs    (position_title != 'Intern' on that date)
    → (ay, employee_number)

terminations:
  dim_work_assignment_status WHERE status_code='T'
    AND effective_start_date BETWEEN date(ay, 9, 1) AND date(ay+1, 4, 30)
    × dim_work_assignment_primary (primary on termination date)
    × dim_work_assignment_jobs    (position_title != 'Intern' on termination date)
    → (ay, employee_number, termination details)

attrition rows:
  year_cohort
    LEFT JOIN returner_cohort
    LEFT JOIN terminations (rn=1)
    → is_attrition, termination_*
  -- (no work_assignment_status_key FK on output; would diamond to dim_staff)
```

### Defensive flows (#3716)

- `fct_staff_observation_goals` / `fct_staff_observations`: null-wrap on
  surrogate-key calls; `WHERE employee_number != 999999` defense.
- `dim_staffing_positions`: extend null-wrap predicate to also reject sentinel
  placeholder codes.
- `stg_schoolmint_grow__users`: drop `internal_id_int = 999999` rows at staging.

## Testing

### Existing failing relationships tests (target: all pass post-merge)

| Mart                          | Column                | Resolution                         |
| ----------------------------- | --------------------- | ---------------------------------- |
| `fct_staff_observation_goals` | `creator_staff_key`   | null-wrap (48,786 → NULL)          |
| `fct_staff_observation_goals` | `teacher_staff_key`   | staging filter (2 → 0)             |
| `fct_staff_observations`      | `teacher_staff_key`   | null-wrap + staging filter (9 → 0) |
| `dim_staffing_positions`      | `incumbent_staff_key` | null-map (692 → NULL)              |
| `dim_staffing_positions`      | `recruiter_staff_key` | null-map (107 → NULL)              |

### New tests on `dim_work_assignment_primary`

- `unique` on `work_assignment_primary_key`.
- `not_null` on `work_assignment_primary_key`, `work_assignment_key`,
  `effective_start_date`, `is_primary_position`.
- `relationships` `work_assignment_key` →
  `dim_staff_work_assignments.work_assignment_key`.
- `dbt_utils.expression_is_true` for
  `effective_start_date <= effective_end_date`.

### Tests on rebuilt `bridge_survey_expectations`

- Existing PK uniqueness test (`dbt_utils.unique_combination_of_columns` or
  `unique`) — verify still holds under new join chain.
- No new FK columns on the bridge → no new relationships tests.

### Tests on rebuilt `fct_staff_attrition`

- Existing `unique` on `staff_attrition_key` — must still hold.
- No new FK columns on the fact → no new relationships tests.

### Manual reconciliation probes

Run on the PR-branch dbt-Cloud-CI schema before merge:

- `fct_staff_attrition` — row count + `is_attrition` totals per academic year,
  before vs. after, **partitioned by region**. Expected drift:
  - Non-Paterson rows: ≤ ~3.8% drift from the `primary_indicator` correction.
    Larger drift in the non-Paterson partition = logic regression.
  - Paterson rows: 0 → N (incidental coverage). Sanity-check N is plausible
    relative to Paterson headcount.
- `bridge_survey_expectations` — row count per `survey_administration_key`,
  before vs. after, **partitioned by region**. Same expected drift shape: small
  drift in non-Paterson, 0 → N for Paterson.

### CI

dbt Cloud CI runs `dbt build --select state:modified+ --full-refresh` against
the PR-branch schema. New mart + edited marts rebuild and run their tests
automatically.

## Rollout

### Branch

- Worktree: `.worktrees/cbini/fix/claude-batch-b-staff-coverage` (this spec is
  being committed there).
- Branch is GitHub-linked to #3687 via `gh issue develop`. PR description links
  to both #3687 and #3716.

### Commit sequence

1. **Defensive null-wraps (#3716 part 1).** Edits to
   `fct_staff_observation_goals`, `fct_staff_observations`, and
   `dim_staffing_positions`.
2. **Staging filter (#3716 part 2).** Edit to `stg_schoolmint_grow__users` to
   exclude `internal_id_int = 999999`.
3. **New mart `dim_work_assignment_primary`.** SQL + properties YAML +
   `cube.yml` entry.
4. **Drop `is_primary_position` from `dim_staff_work_assignments`.** Remove from
   SELECT, properties YAML, and `cube.yml` (Cube schema). Verify no downstream
   `ref()` consumers rely on it.
5. **Rebuild `fct_staff_attrition`.** Rework cohort/termination CTEs to traverse
   `dim_work_assignment_status × dim_work_assignment_primary × dim_work_assignment_jobs × dim_staff_work_assignments`;
   drop `SELECT DISTINCT` blocks. No new output FKs (the SCDs stay inside CTEs
   to avoid a diamond to `dim_staff`). Update properties YAML.
6. **Rename + rebuild `bridge_survey_expectations`.** File rename + logic
   refactor + `cube.yml` rename + Tableau exposure rename + intra-mart `ref()`
   updates.
7. **`marts/CLAUDE.md`** — add `bridge_*` paragraph; strike #3687 from deferred
   follow-ups.
8. **Hash-change audit.** Append entries to
   `docs/superpowers/specs/2026-04-15-column-naming-audit.md`.

### Verification before merge

- Run `/workspaces/teamster/.trunk/tools/trunk check --ci` from the worktree
  root and fix any issues before push (worktrees lack trunk's pre-commit hooks).
- Run dbt Cloud CI; verify all five previously failing relationships tests pass.
- Run reconciliation probe queries against the PR-branch schema
  (`dbt_cloud_pr_<ci>_<num>_kipptaf_marts`); confirm drift is within expected
  ranges.

### In-flight triage rule

If implementation surfaces additional fan-out, coverage gaps, or test failures
unrelated to the planned changes:

1. **Triage immediately.** Classify as side-effect (in-scope), pre-existing
   latent issue exposed by stricter SCD traversal (judgment call), or unrelated
   (defer).
2. **Address in this PR if** the fix is small, mechanically related to the SCD
   traversal we're already changing, and shipping with Batch B is cleaner than a
   follow-up.
3. **File and defer if** the fix expands the structural surface area beyond
   staff coverage, requires its own spec/design, or risks dragging in unrelated
   dims.
4. **Document each triage decision** in the PR description so reviewers can see
   what was kept/punted and why.

**Known triage candidate — #3681** (`dim_staff_status` has 0 rows in
production). `fct_staff_attrition` retains its `staff_status_key` FK to
`dim_staff_status` (the diamond constraint blocks introducing a competing FK to
`dim_work_assignment_status`). If #3681 is still open when Batch B reaches
reconciliation, the existing `staff_status_key` chain will remain broken
regardless of our changes — the reconciliation probe will surface this. Triage
decision: fixing #3681 is small enough to fold into this PR _if_ the root cause
is a narrow SQL bug in `dim_staff_status.sql`; defer otherwise.

### Post-merge follow-ups

- Open an issue: "audit Paterson `business_unit_name` filter on
  `int_people__staff_roster_history`." Document why the filter exists, and
  whether the consumers that still depend on `int_people__staff_roster_history`
  (e.g., `dim_staff`, `int_people__staff_roster`) should also incidentally gain
  Paterson coverage by removing the filter — out of scope for Batch B but a
  natural follow-up given Batch B already exposes Paterson on the attrition /
  survey-expectation side.

## Incidental Paterson coverage

Paterson staff exist in ADP and flow through every dim Batch B traverses
(`dim_work_assignment_status`, `dim_work_assignment_primary` (NEW),
`dim_work_assignment_jobs`, `dim_staff_work_assignments`). Paterson is filtered
out of `int_people__staff_roster_history` only — see lines 113–118 of that
model:

```sql
where w.effective_date_end >= '2021-01-01'
  and coalesce(w.organizational_unit__home__business_unit__name, '')
      != 'KIPP Paterson'
  and coalesce(w.organizational_unit__assigned__business_unit__name, '')
      != 'KIPP Paterson'
```

Because Batch B retires that intermediate from `fct_staff_attrition` and
`bridge_survey_expectations`, those marts will gain Paterson rows after merge —
a coverage expansion that wasn't in the original issue scope but is a direct
consequence of the SCD-correct rebuild.

**Scope decision:** keep the incidental coverage. Filtering Paterson back out at
the mart layer would re-introduce the same kind of consumer-side workaround the
rebuild is meant to eliminate. The surface change is transparent: `dim_staff`
(current snapshot) and `int_people__staff_roster` (its derivative) still exclude
Paterson — no other models gain or lose Paterson rows.

**Reconciliation guidance:** the probe queries (Testing section) partition by
region so Paterson drift can be inspected separately. Sanity-check that Paterson
row counts are plausible relative to Paterson headcount; spot-check a few
attrition + survey rows for data quality. If Paterson ADP records have known
issues (the reason the filter exists in the first place), the probe will surface
them and we can decide whether to:

- ship as-is (incidental coverage, accept any Paterson data quality artifacts as
  a separate concern), or
- add a Paterson exclusion at the bridge / fact layer with a `-- TODO: <issue>`
  comment pointing at the audit follow-up.

## Out of scope

- `dim_staff` — unchanged.
- `dim_staff_status` — unchanged. Folding assignment attributes into it was
  considered and rejected (effective-date semantics mix; name becomes
  misleading).
- `dim_staff_work_assignments` — remains current-snapshot (only edit is dropping
  `is_primary_position`, covered above). Converting to full SCD2 was considered
  and rejected (large blast radius across all facts that FK to
  `work_assignment_key`).
- `dim_work_assignment_status` — unchanged. Folding `primary_indicator` into it
  was considered and rejected (effective-date semantics mix; name semantic
  stretch).
- `int_people__staff_roster_history` — unchanged. Still drives `dim_staff` and
  `int_people__staff_roster`.
- Paterson coverage — Paterson staff **are** in ADP and flow through
  `dim_work_assignment_status`, `dim_staff_work_assignments`,
  `dim_work_assignment_primary`, and `dim_work_assignment_jobs` (these source
  `int_adp_workforce_now__workers__work_assignments` directly, unfiltered).
  Today they're filtered out only at `int_people__staff_roster_history` (lines
  113–118: `business_unit_name != 'KIPP Paterson'`). Because Batch B retires
  that intermediate from the attrition / survey-expectation chain, **Paterson
  staff will incidentally appear** in `fct_staff_attrition` and
  `bridge_survey_expectations` after this batch. See "Incidental Paterson
  coverage" below.

## Related project-board issues

Batch B's blast radius touches several open issues besides #3687 and #3716.
Reviewed against the
[PR Batch B project view](https://github.com/orgs/TEAMSchools/projects/4/views/1):

**Partially resolves:**

- **#3704** — "simplify `dim_staff_observation_expectations` /
  `dim_survey_expectations` scaffolds." Survey side is largely addressed by this
  batch: the brittle `int_people__staff_roster_history` SCD chain in
  `dim_survey_expectations` is replaced with the SCD-correct
  `dim_work_assignment_status × dim_work_assignment_primary` traversal, and the
  model is renamed `bridge_survey_expectations` to reflect its factless-fact
  semantics. The observation side (`dim_staff_observation_expectations`) is
  untouched. After Batch B, #3704's residual scope shrinks to the observation
  half.

**Establishes precedent for:**

- **#3700** — "evaluate bridge table candidates for multi-value student/staff
  attributes." Different bridge use case (multi-value attribute vs. many-to-many
  association), but Batch B introduces the first `bridge_*` model and adds the
  `bridge_*` paragraph to `marts/CLAUDE.md` defining naming and shape
  conventions that #3700 will follow.

**Adjacent but not resolved:**

- **#3681** — `dim_staff_status` has 0 rows in production. Batch B retains
  `fct_staff_attrition`'s `staff_status_key` FK to `dim_staff_status` (the
  diamond rule prevents introducing a competing FK). If #3681 is open at ship
  time, the existing FK chain stays broken regardless. Surfaced as a known
  triage candidate (see "In-flight triage rule" above).
- **#3641, #3680, #3722** (Batch D — staff observations). Batch B edits
  `fct_staff_observation_goals` and `fct_staff_observations` for null-wraps and
  sentinel filters only. Their concerns (FK additions, intermediate refactor,
  rubric coverage) are unrelated.
- **#3686** — `dim_staffing_positions.location_key` coverage. Batch B touches
  the same model for null-mapping but does not address location coverage.
