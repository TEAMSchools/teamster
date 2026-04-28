# Batch B Staff Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve PR Batch B (issues
[#3687](https://github.com/TEAMSchools/teamster/issues/3687) and
[#3716](https://github.com/TEAMSchools/teamster/issues/3716)) by (1) fixing all
five failing `relationships` tests on staff-side surrogate keys via defensive
SQL, and (2) replacing date-range joins through
`int_people__staff_roster_history` in `fct_staff_attrition` and
`bridge_survey_expectations` (renamed from `dim_survey_expectations`) with
SCD-correct star-schema traversal through existing dims plus one new narrow SCD
mart, `dim_work_assignment_primary`.

**Architecture:** Mart-only edits; one staging exception (a single test account
filter in `stg_schoolmint_grow__users`). New mart `dim_work_assignment_primary`
provides date-correct `is_primary_position` history; `fct_staff_attrition` and
`bridge_survey_expectations` traverse
`dim_work_assignment_status × dim_work_assignment_primary [× dim_work_assignment_jobs] × dim_staff_work_assignments`
instead of `int_people__staff_roster_history`. No new output FKs (would diamond
to `dim_staff`); the SCDs are used inside CTEs only.

**Tech Stack:** dbt 1.11+ (BigQuery dialect),
`dbt-utils.generate_surrogate_key`, `dbt-utils.deduplicate`. Local dbt invoked
via `uv run --directory src/dbt/kipptaf dbt ...`. SQL formatted by trunk's
sqlfluff (BigQuery, line length 88, single quotes, trailing commas). YAML under
`src/dbt/kipptaf/models/marts/dimensions/properties/`.

**Spec:**
[`docs/superpowers/specs/2026-04-27-batch-b-staff-coverage-design.md`](../specs/2026-04-27-batch-b-staff-coverage-design.md)

---

## File Structure

**New files:**

- `src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_primary.sql`
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_primary.yml`

**Files renamed (delete old, create new):**

- `dim_survey_expectations.sql` → `bridge_survey_expectations.sql`
- `properties/dim_survey_expectations.yml` →
  `properties/bridge_survey_expectations.yml`

**Files modified:**

- `src/dbt/kipptaf/models/marts/facts/fct_staff_observation_goals.sql`
- `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql`
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml`
- `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`
- `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml`
- `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql`
- `src/dbt/kipptaf/models/exposures/cube.yml`
- `src/dbt/kipptaf/models/marts/CLAUDE.md`
- `docs/superpowers/specs/2026-04-15-column-naming-audit.md`

**Note on `cd` and `uv run`:** Worktree is at
`/workspaces/teamster/.worktrees/cbini/fix/claude-batch-b-staff-coverage`. All
commands assume that as the working directory unless prefixed with `cd`. Use
`uv run --directory src/dbt/kipptaf dbt ...` for dbt commands.

---

## Task 1: Null-wrap `creator_staff_key` in `fct_staff_observation_goals`

The existing `relationships` test on `creator_staff_key` fails with 48,786 rows
because the key is generated from `sr_creator.employee_number` behind a LEFT
JOIN with no null-wrap. All 48,786 orphans hash to the
`generate_surrogate_key(NULL)` placeholder (`f14cc5cdce0420f4a5a6b6d9d7b85f39`).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_staff_observation_goals.sql:10-11`

- [ ] **Step 1: Verify the existing test fails (capture baseline).**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-b-staff-coverage
uv run --directory src/dbt/kipptaf dbt test \
  --select fct_staff_observation_goals,test_name:relationships \
  --target dev 2>&1 | tail -40
```

Expected: at least one `relationships` test fails on `creator_staff_key`. (If
your dev target doesn't have the data, skip to Step 5 and rely on dbt Cloud CI —
see Task 15.)

- [ ] **Step 2: Apply the null-wrap to `creator_staff_key`.**

Replace lines 10-11 of `fct_staff_observation_goals.sql`:

```sql
    if(
        sr_creator.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sr_creator.employee_number"]) }},
        cast(null as string)
    ) as creator_staff_key,
```

- [ ] **Step 3: Build the model and verify the test passes.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select fct_staff_observation_goals --target dev 2>&1 | tail -30
```

Expected: model builds; `relationships` test on `creator_staff_key` passes (or
skips locally and will pass in dbt Cloud CI).

- [ ] **Step 4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_observation_goals.sql
git commit -m "fix(dbt): null-wrap fct_staff_observation_goals.creator_staff_key

48,786 orphan rows on the dim_staff relationships test were null-hash
placeholders from a LEFT JOIN to sr_creator.employee_number without the
null-wrap pattern. Refs #3716."
```

---

## Task 2: Null-wrap `teacher_staff_key` in `fct_staff_observation_goals`

The 2 orphans on `teacher_staff_key` come from a SchoolMint Grow test account
(`internal_id_int = 999999`). Task 5 filters that account at staging — but
null-wrap the key here too as defense in depth (and to match the codebase
pattern of always wrapping nullable surrogate-key inputs).

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_observation_goals.sql:8`

- [ ] **Step 1: Apply the null-wrap to `teacher_staff_key`.**

Replace line 8 of `fct_staff_observation_goals.sql`:

```sql
    if(
        gu.internal_id_int is not null,
        {{ dbt_utils.generate_surrogate_key(["gu.internal_id_int"]) }},
        cast(null as string)
    ) as teacher_staff_key,
```

- [ ] **Step 2: Build the model.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select fct_staff_observation_goals --target dev 2>&1 | tail -20
```

Expected: model builds; tests pass (or pass in dbt Cloud CI).

- [ ] **Step 3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_observation_goals.sql
git commit -m "fix(dbt): null-wrap fct_staff_observation_goals.teacher_staff_key

Defense in depth alongside Task 5's staging filter for the
'Awesome Teacher' test account. Refs #3716."
```

---

## Task 3: Null-wrap `teacher_staff_key` and `observer_staff_key` in `fct_staff_observations`

The 9 orphans on `teacher_staff_key` split: 4 are null-hash placeholders, 5 are
sentinel `employee_number = 999999` (the same SchoolMint Grow test account, also
present in `int_performance_management__observations`). Wrap both staff-key
surrogates with the standard nullable-FK pattern.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql:58-61`

- [ ] **Step 1: Replace the bare `teacher_staff_key` and `observer_staff_key`.**

Replace lines 58-61 (the two
`dbt_utils.generate_surrogate_key(...) as *_staff_key` blocks):

```sql
    if(
        employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["employee_number"]) }},
        cast(null as string)
    ) as teacher_staff_key,

    if(
        observer_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["observer_employee_number"]) }},
        cast(null as string)
    ) as observer_staff_key,
```

- [ ] **Step 2: Build the model.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select fct_staff_observations --target dev 2>&1 | tail -20
```

Expected: model builds; relationships tests pass (or in CI).

- [ ] **Step 3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql
git commit -m "fix(dbt): null-wrap fct_staff_observations staff-side keys

Wrap teacher_staff_key and observer_staff_key with the standard
nullable-FK pattern. Closes 4 null-hash placeholder orphans;
sentinel employee_number=999999 is removed by the staging filter
in Task 5. Refs #3716."
```

---

## Task 4: Add sentinel exclusion to `dim_staffing_positions`

Seat-tracker uses placeholder employee numbers (0, 1, 2, 999995–999999) for
positions whose real employee_number is not yet linked. The current null-wraps
on `incumbent_staff_key` and `recruiter_staff_key` only check `is not null`;
extend the predicate to also reject these confirmed placeholder codes so they
don't generate orphan FKs.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql:10-20`

- [ ] **Step 1: Replace the two existing null-wrap blocks.**

Replace lines 10-20 of `dim_staffing_positions.sql`:

```sql
    if(
        teammate is not null
        and teammate not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
        {{ dbt_utils.generate_surrogate_key(["teammate"]) }},
        cast(null as string)
    ) as incumbent_staff_key,

    if(
        recruiter is not null
        and recruiter not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
        {{ dbt_utils.generate_surrogate_key(["recruiter"]) }},
        cast(null as string)
    ) as recruiter_staff_key,
```

- [ ] **Step 2: Build the model.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select dim_staffing_positions --target dev 2>&1 | tail -20
```

Expected: model builds; both relationships tests pass (or in CI).

- [ ] **Step 3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql
git commit -m "fix(dbt): null-map seat-tracker placeholder codes in dim_staffing_positions

incumbent_staff_key (692 orphans) and recruiter_staff_key (107 orphans)
were generating real surrogate hashes for placeholder teammate/recruiter
values (0, 1, 2, 999995-999999). Confirmed domain placeholders, not test
records — rows preserved, only spurious employee_number replaced with
NULL. Refs #3716."
```

---

## Task 5: Filter the SchoolMint Grow test account at staging

`stg_schoolmint_grow__users` carries one user with `internal_id_int = 999999`,
name "Awesome Teacher", email `awesometeacher@apps.teamschools.org`. Real test
account observed 5 times in production observation data. Filter at staging to
remove all downstream traces (closes the remaining 5 + 2 orphans on
`fct_staff_observations` and `fct_staff_observation_goals`).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql`

- [ ] **Step 1: Append a `where` clause to exclude the test account.**

The current model is a flat `select ... from {{ source(...) }}` with no `where`
clause. Append:

```sql
where coalesce(safe_cast(internalid as int), 0) != 999999
```

The `coalesce` keeps rows where `internalid` is non-numeric or null (otherwise
`safe_cast` returns null and the comparison would drop them).

After the edit, the trailing `from {{ source(...) }}` line should be followed by
the new `where` line, then a blank line.

- [ ] **Step 2: Build the staging model and downstream observation marts.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select stg_schoolmint_grow__users+ \
  --exclude tag:exposure --target dev 2>&1 | tail -30
```

Expected: stg model rebuilds; `fct_staff_observations` and
`fct_staff_observation_goals` rebuild and pass tests.

- [ ] **Step 3: Commit.**

```bash
git add src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql
git commit -m "fix(dbt): filter 'Awesome Teacher' test account from stg_schoolmint_grow__users

internal_id_int=999999 is a real SchoolMint Grow test account that flowed
into int_performance_management__observations and produced 7 dim_staff
relationship-test orphans (5 in fct_staff_observations, 2 in
fct_staff_observation_goals). Filter at staging removes all downstream
traces. Refs #3716."
```

---

## Task 6: Create `dim_work_assignment_primary` SQL

New narrow SCD mart on `(item_id, effective_start_date)` with a single projected
attribute `is_primary_position`. Same change-point structure as
`dim_staff_status` and `dim_work_assignment_status`. Source is
`int_adp_workforce_now__workers__work_assignments`.

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_primary.sql`

- [ ] **Step 1: Write the new model SQL.**

Create the file with this content:

```sql
with
    assignments as (
        select
            wa.item_id,
            wa.effective_date_start,
            wa.primary_indicator,

            {{
                dbt_utils.generate_surrogate_key(
                    ["wa.primary_indicator"]
                )
            }} as attribute_hash,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as attribute_hash_lag,
        from assignments
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            primary_indicator,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where attribute_hash != attribute_hash_lag
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_primary_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    primary_indicator as is_primary_position,
    effective_date_start as effective_start_date,
    effective_date_end as effective_end_date,

    if(effective_date_end = '9999-12-31', true, false) as is_current,
from change_points
```

- [ ] **Step 2: Compile to verify SQL parses (no model build yet — YAML in next
      task).**

```bash
uv run --directory src/dbt/kipptaf dbt compile \
  --select dim_work_assignment_primary --target dev 2>&1 | tail -20
```

Expected: compile succeeds. (Build will fail without the YAML — that comes in
Task 7.)

- [ ] **Step 3: Stage; do not commit yet.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_work_assignment_primary.sql
```

(Combined commit happens at end of Task 7 once YAML exists.)

---

## Task 7: Create `dim_work_assignment_primary` properties YAML

Marts inherit `contract: enforced: true` and `materialized: view` from
`dbt_project.yml`. Required tests: `unique` + `not_null` on PK, `not_null` on
FK, `relationships` to parent dim, `expression_is_true` for date ordering.

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_primary.yml`

- [ ] **Step 1: Write the properties YAML.**

```yaml
models:
  - name: dim_work_assignment_primary
    description: >-
      Primary-position SCD for ADP work assignments. One row per work assignment
      x is_primary_position version. Hash-based change detection over
      int_adp_workforce_now__workers__work_assignments collapses adjacent SCD
      rows whose primary_indicator value is unchanged. Used as a date-correct
      lookup by fct_staff_attrition and bridge_survey_expectations to determine
      which work assignment was primary at a point in time; primary_indicator
      changes within an item_id over time on roughly 4% of work assignments.
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: effective_start_date <= effective_end_date
    columns:
      - name: work_assignment_primary_key
        data_type: string
        description: >-
          Surrogate primary key derived from item_id and effective_date_start.
          Generated with generate_surrogate_key(["item_id",
          "effective_date_start"]).
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: work_assignment_key
        data_type: string
        description: >-
          Foreign key to dim_staff_work_assignments. Surrogate key derived from
          item_id. Generated with generate_surrogate_key(["item_id"]).
        constraints:
          - type: foreign_key
            to: ref('dim_staff_work_assignments')
            to_columns: [work_assignment_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff_work_assignments')
                field: work_assignment_key

      - name: is_primary_position
        data_type: boolean
        description: >-
          TRUE if this work assignment was the worker's primary work assignment
          during the version's effective window. A worker may have multiple
          concurrent assignments; at most one is primary at any moment.
        data_tests:
          - not_null

      - name: effective_start_date
        data_type: date
        description: >-
          Date this is_primary_position version became effective, from the
          source SCD row that triggered the change point.
        data_tests:
          - not_null

      - name: effective_end_date
        data_type: date
        description: >-
          Date through which this is_primary_position version is in effect.
          '9999-12-31' for the current version (no later change point).

      - name: is_current
        data_type: boolean
        description: >-
          TRUE when effective_end_date is the sentinel '9999-12-31' (this row is
          the latest version per work assignment).
```

- [ ] **Step 2: Build the model with tests.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select dim_work_assignment_primary --target dev 2>&1 | tail -30
```

Expected: model builds; all four data tests pass (unique, not_null on
PK/FK/is_primary/start_date, relationships to dim_staff_work_assignments,
expression_is_true on date ordering).

- [ ] **Step 3: Commit (combined with Task 6 SQL).**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/properties/dim_work_assignment_primary.yml
git commit -m "feat(dbt): add dim_work_assignment_primary SCD mart

Narrow change-point SCD on (item_id, effective_start_date) tracking
is_primary_position over time. ~4% of work assignments have
primary_indicator change within their lifetime; this dim provides
date-correct primary lookups for fct_staff_attrition and
bridge_survey_expectations to traverse via dim_work_assignment_status.
Refs #3687."
```

---

## Task 8: Add `dim_work_assignment_primary` to `cube.yml`

The Cube semantic-layer exposure is the contract for downstream BI consumers.
Add the new mart to `depends_on` so Cube's catalog picks it up.

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`

- [ ] **Step 1: Insert the new ref in alphabetical order.**

Inside the `depends_on:` list, add a new line for the new dim. Alphabetically it
goes after `dim_work_assignment_organizational_units` and
`dim_work_assignment_reporting_relationships` (both sort before `primary`), and
before `dim_work_assignment_status` (since "primary" < "status" lexically would
be wrong — verify by sorting). The correct alphabetical position is between
`ref("dim_work_assignment_organizational_units")` and
`ref("dim_work_assignment_reporting_relationships")` because "p" < "r":

```yaml
- ref("dim_work_assignment_organizational_units")
- ref("dim_work_assignment_primary")
- ref("dim_work_assignment_reporting_relationships")
```

- [ ] **Step 2: Verify cube.yml still parses by running dbt parse.**

```bash
uv run --directory src/dbt/kipptaf dbt parse --target dev 2>&1 | tail -10
```

Expected: parse succeeds, no errors.

- [ ] **Step 3: Commit.**

```bash
git add src/dbt/kipptaf/models/exposures/cube.yml
git commit -m "chore(dbt): add dim_work_assignment_primary to cube exposure

Refs #3687."
```

---

## Task 9: Drop `is_primary_position` from `dim_staff_work_assignments`

`dim_work_assignment_primary` now provides the date-correct
`is_primary_position`. Keeping the current-snapshot version on
`dim_staff_work_assignments` invites consumers to use the wrong one (R8/R9 of
`marts/CLAUDE.md`). Drop it. Cube consumers that filter on
`staff_work_assignments.is_primary_position` will need to traverse to the new
mart — flag in PR description.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql:7,55`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml`

- [ ] **Step 1: Remove `wa.primary_indicator,` from the projected columns.**

In `dim_staff_work_assignments.sql`, line 7 currently reads:

```sql
            wa.primary_indicator,
```

Delete that whole line. (Trunk's sqlfluff will rewrap; ST06 column-ordering will
not be affected because `primary_indicator` was a plain enumeration in the same
group.)

- [ ] **Step 2: Remove the `is_primary_position` output column.**

In the same file, line 55 currently reads:

```sql
    wa.primary_indicator as is_primary_position,
```

Delete that whole line.

- [ ] **Step 3: Remove the `is_primary_position` block from the YAML.**

In `properties/dim_staff_work_assignments.yml`, find the column entry for
`is_primary_position` (around line 69):

```yaml
- name: is_primary_position
  data_type: boolean
  description: >-
    TRUE if this is the primary work assignment for the worker. A worker may
    have multiple assignments; at most one is primary.
```

Delete that entire entry (the `- name:` line through the description closing).
Leave a single blank line between the surrounding columns.

- [ ] **Step 4: Build and verify the contract still matches.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select dim_staff_work_assignments --target dev 2>&1 | tail -20
```

Expected: model builds; contract enforcement does not complain (column removed
from both SQL and YAML simultaneously).

- [ ] **Step 5: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql \
       src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml
git commit -m "refactor(dbt): drop is_primary_position from dim_staff_work_assignments

Redundant with the new date-correct dim_work_assignment_primary SCD.
R8/R9 cleanup. Cube consumers filtering on
staff_work_assignments.is_primary_position must traverse to
dim_work_assignment_primary instead. Refs #3687."
```

---

## Task 10: Rebuild `fct_staff_attrition` cohort and termination CTEs

Replace the current `teammate_history` CTE (which sources
`int_people__staff_roster_history` with `select distinct` workarounds) with a
new chain through
`dim_work_assignment_status × dim_work_assignment_primary × dim_work_assignment_jobs × dim_staff_work_assignments`.
No new output FKs (the existing `staff_status_key` chain to `dim_staff` would
diamond against any new FK to `dim_work_assignment_status`). Drop all
`-- TODO: #3687` comments.

The model has three attrition variants — `foundation`, `nj_compliance`,
`recruitment` — each with `year_cohort`, `returner_cohort`, and `terminations`
CTEs sharing the same shape but different date windows. The rewrite preserves
the variant structure.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`

- [ ] **Step 1: Rewrite the `teammate_history` and `academic_years` CTEs.**

Replace the file's CTE block from line 1 down through the `academic_years` CTE
(currently line 28). Replace with:

```sql
with
    /* Per-employee assignment-status timeline derived from
       dim_work_assignment_status (status SCD) + dim_work_assignment_primary
       (is_primary_position SCD) + dim_work_assignment_jobs (position_title
       SCD, for intern filter) + dim_staff_work_assignments (resolves
       staff-side employee_number). One row per
       (employee_number, item_id, status-version) representing the
       primary, non-Intern assignment-status windows. */
    teammate_history as (
        select
            swa.employee_number,
            wast.work_assignment_key,
            wast.status_code,
            wast.reason_code,
            wast.reason_name,
            wast.effective_start_date,
            wast.effective_end_date,
            -- assignment-status effective_date is currently equal to
            -- effective_start_date in dim_work_assignment_status; expose
            -- both so attrition-year boundary logic stays explicit
            wast.effective_start_date as assignment_status_effective_date,

            {{
                date_to_fiscal_year(
                    date_field="wast.effective_start_date",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("dim_work_assignment_status") }} as wast
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and wast.effective_start_date <= wap.effective_end_date
            and wast.effective_end_date >= wap.effective_start_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_work_assignment_jobs") }} as waj
            on wast.work_assignment_key = waj.work_assignment_key
            and wast.effective_start_date <= waj.effective_end_date
            and wast.effective_end_date >= waj.effective_start_date
            and waj.position_title != 'Intern'
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        where swa.employee_number is not null
    ),

    academic_years as (
        select distinct employee_number, academic_year, from teammate_history
    ),
```

- [ ] **Step 2: Update the `foundation_year_cohort` CTE.**

The next CTE currently filters
`th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')`. Replace
that filter with `th.status_code = 'A'` (`'A' = Active`). The CTE shape is
otherwise unchanged. Replace lines ~32-46 with:

```sql
    /* Foundation Attrition: latest record for staff not  */
    /* in an inactive status between 9/1 and 4/30 of an academic year  */
    foundation_year_cohort as (
        select
            ay.academic_year,

            th.employee_number,

            max(th.effective_start_date) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_start_date <= date(ay.academic_year + 1, 4, 30)
            and th.effective_end_date >= date(ay.academic_year, 9, 1)
        where th.status_code = 'A'
        group by ay.academic_year, th.employee_number
    ),
```

- [ ] **Step 3: Update `foundation_returner_cohort`.**

Drop the `select distinct` and the `-- TODO: #3687` comment. Replace the CTE
(lines ~50-59) with:

```sql
    /* Foundation Attrition: any staff not in terminated or deceased status  */
    /* on 9/1 of the following academic year  */
    foundation_returner_cohort as (
        select ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on date(ay.academic_year + 1, 9, 1)
            between th.effective_start_date and th.effective_end_date
        where th.status_code = 'A'
        group by ay.academic_year, th.employee_number
    ),
```

- [ ] **Step 4: Update `foundation_terminations`.**

Replace `assignment_status in ('Terminated', 'Deceased')` filter with
`status_code in ('T', 'D')`, and `assignment_status_reason` → `reason_name`.
Drop the legacy column references. Replace the CTE (lines ~61-80) with:

```sql
    /* Foundation Attrition: first termination record within the window  */
    foundation_terminations as (
        select
            ay.academic_year,

            th.employee_number,
            th.reason_name as termination_reason,
            th.assignment_status_effective_date as termination_effective_date,

            row_number() over (
                partition by ay.academic_year, th.employee_number
                order by th.assignment_status_effective_date asc
            ) as rn,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.assignment_status_effective_date
            between date(ay.academic_year, 9, 1) and date(ay.academic_year + 1, 4, 30)
        where th.status_code in ('T', 'D')
    ),
```

- [ ] **Step 5: Apply the same three-CTE rewrite to the NJ variant.**

For each of `nj_year_cohort`, `nj_returner_cohort`, and `nj_terminations`, apply
the analogous changes:

- `assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')` →
  `status_code = 'A'`
- Drop `select distinct` and `-- TODO: #3687` comments
- `assignment_status in ('Terminated', 'Deceased')` →
  `status_code in ('T', 'D')`
- `assignment_status_reason` → `reason_name`

Date windows for NJ: `7/1` to `6/30 of next year` (annual), boundary date `7/1`
of next year for the returner cohort. Otherwise structurally identical to
foundation. Use the foundation CTEs above as the template.

- [ ] **Step 6: Apply the same three-CTE rewrite to the recruitment variant.**

Same edits as Step 5; date windows are `9/1` to `8/31 of next year`, boundary
date `9/1` of next year for the returner cohort.

- [ ] **Step 7: Verify no remaining `int_people__staff_roster_history`
      references.**

```bash
grep -n "int_people__staff_roster_history\|select distinct\|TODO: #3687" \
  src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql
```

Expected: no output (all three references removed).

- [ ] **Step 8: Build the model.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select fct_staff_attrition --target dev 2>&1 | tail -40
```

Expected: model builds; existing `unique` test on `staff_attrition_key` still
passes.

- [ ] **Step 9: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql
git commit -m "refactor(dbt): rebuild fct_staff_attrition via SCD traversal

Retire int_people__staff_roster_history date-range joins (which fan out
on every full-row SCD change) and the three SELECT DISTINCT workarounds
they required. New chain traverses dim_work_assignment_status (status,
date-range), dim_work_assignment_primary (primary, date-range),
dim_work_assignment_jobs (position_title, date-range; intern filter),
and dim_staff_work_assignments (staff_key resolution).

No new output FKs — adding work_assignment_status_key would create a
diamond path to dim_staff alongside the existing staff_status_key
chain. Refs #3687."
```

---

## Task 11: Update `fct_staff_attrition` properties YAML

The model description references the prior join chain and may have stale test
entries. Update the description to describe the new traversal; verify no FK
columns were added (we deliberately avoided introducing
`primary_work_assignment_status_key`).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml`

- [ ] **Step 1: Read the current model description.**

```bash
grep -A 20 "name: fct_staff_attrition" \
  src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml | head -25
```

- [ ] **Step 2: Update the model description to reflect the new join chain.**

In the file, replace the `description: >-` block on the model. Use this text
(preserving the existing `>-` indentation):

```yaml
description: >-
  Staff attrition fact. One row per employee_number x academic_year x
  attrition_type (foundation, nj_compliance, recruitment). is_attrition is true
  when the employee was in a primary, non-Intern, Active assignment during the
  year window but not on the year-following boundary date. Source-of-truth is
  dim_work_assignment_status (assignment-status SCD) intersected with
  dim_work_assignment_primary (is_primary_position SCD) and
  dim_work_assignment_jobs (position_title SCD, for the intern filter), joined
  to dim_staff_work_assignments to resolve employee_number. FKs to
  dim_staff_status (the worker-status version effective on
  outcome_determination_date).
```

- [ ] **Step 3: Verify column entries are unchanged.**

The YAML's `columns:` list should not contain a
`primary_work_assignment_status_key` or `work_assignment_status_key` entry (we
deliberately did not introduce those). If you find one, delete it. The existing
`staff_status_key` entry stays.

```bash
grep -n "work_assignment_status_key" \
  src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml
```

Expected: no output.

- [ ] **Step 4: Build to verify YAML parses and contract holds.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select fct_staff_attrition --target dev 2>&1 | tail -20
```

Expected: builds; tests pass.

- [ ] **Step 5: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml
git commit -m "docs(dbt): update fct_staff_attrition description for new join chain

Refs #3687."
```

---

## Task 12: Rename `dim_survey_expectations` → `bridge_survey_expectations`

Three rename targets: SQL file, properties YAML, doc md (if exists). After this
task the model still has the old logic — Task 13 rebuilds the CTEs. The split
keeps the rename mechanically simple.

**Files:**

- Rename: `dim_survey_expectations.sql` → `bridge_survey_expectations.sql`
- Rename: `properties/dim_survey_expectations.yml` →
  `properties/bridge_survey_expectations.yml`
- Modify: properties YAML's `name:` field
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml` (rename ref)
- Modify: `src/dbt/kipptaf/models/marts/CLAUDE.md` (update example)

- [ ] **Step 1: Rename the SQL file.**

```bash
git mv src/dbt/kipptaf/models/marts/dimensions/dim_survey_expectations.sql \
       src/dbt/kipptaf/models/marts/dimensions/bridge_survey_expectations.sql
```

- [ ] **Step 2: Rename the YAML file.**

```bash
git mv src/dbt/kipptaf/models/marts/dimensions/properties/dim_survey_expectations.yml \
       src/dbt/kipptaf/models/marts/dimensions/properties/bridge_survey_expectations.yml
```

- [ ] **Step 3: Update the YAML model name.**

In `properties/bridge_survey_expectations.yml`, change line 2:

```yaml
- name: bridge_survey_expectations
```

Also rename the PK column from `survey_expectation_key` to
`survey_expectation_key` — wait, the PK name doesn't need to change (it already
refers to the conceptual entity, not the model name). Leave the PK column name
alone. **No other YAML changes in this task.**

- [ ] **Step 4: Update the cube.yml reference.**

In `src/dbt/kipptaf/models/exposures/cube.yml` find the line:

```yaml
- ref("dim_survey_expectations")
```

Replace with:

```yaml
- ref("bridge_survey_expectations")
```

(Re-sort if needed — `bridge_*` sorts before `dim_*` alphabetically. Move the
line to the appropriate alphabetical position above the `dim_*` block.)

- [ ] **Step 5: Update the marts/CLAUDE.md example.**

In `src/dbt/kipptaf/models/marts/CLAUDE.md`, line 5 currently reads:

```text
Intra-mart refs are permitted (e.g. `dim_survey_expectations → dim_surveys`,
```

Change to:

```text
Intra-mart refs are permitted (e.g. `bridge_survey_expectations → dim_surveys`,
```

- [ ] **Step 6: Verify no other refs to the old name in the repo.**

```bash
grep -rn "dim_survey_expectations" src/dbt/ --include="*.sql" --include="*.yml" --include="*.md" 2>&1 | grep -v target
```

Expected: no results.

- [ ] **Step 7: Build to verify the rename is consistent.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select bridge_survey_expectations --target dev 2>&1 | tail -20
```

Expected: model builds with the old logic intact; tests pass.

- [ ] **Step 8: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/bridge_survey_expectations.sql \
       src/dbt/kipptaf/models/marts/dimensions/properties/bridge_survey_expectations.yml \
       src/dbt/kipptaf/models/exposures/cube.yml \
       src/dbt/kipptaf/models/marts/CLAUDE.md
git commit -m "refactor(dbt): rename dim_survey_expectations to bridge_survey_expectations

The model is functionally a bridge (factless fact linking surveys to
respondents via many-to-many), not a dim. First bridge_* model in the
repo. Logic unchanged by this commit; rebuild via SCD traversal in the
next commit. Refs #3687."
```

---

## Task 13: Rebuild `bridge_survey_expectations` staff CTEs

Replace the three staff CTEs (`staff_scd`, `staff_manager`, `staff_support`) to
traverse
`dim_work_assignment_status × dim_work_assignment_primary × dim_staff_work_assignments`
instead of `int_people__staff_roster_history`. Output FK shape unchanged (no new
`work_assignment_status_key` FK — would diamond to `dim_staff` via the existing
`staff_key`).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/bridge_survey_expectations.sql`

- [ ] **Step 1: Replace each staff CTE with the new SCD-traversal version.**

The three CTEs (`staff_scd`, `staff_manager`, `staff_support`) share the same
shape — only the `where sa.name = '<survey-name>'` filter differs. Replace each
CTE entirely with the corresponding block below.

**`staff_scd`** (filter: `'School Community Diagnostic Staff Survey'`):

```sql
    /* Staff SCD expectations: active staff during SCD window */
    staff_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_type,

            {{ dbt_utils.generate_surrogate_key(["swa.employee_number"]) }}
            as staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

            swa.employee_number,
        from survey_admin as sa
        inner join
            {{ ref("dim_work_assignment_status") }} as wast
            on sa.response_deadline_date
            between wast.effective_start_date and wast.effective_end_date
            and wast.status_code = 'A'
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and sa.response_deadline_date
            between wap.effective_start_date and wap.effective_end_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        where sa.name = 'School Community Diagnostic Staff Survey'
    ),
```

**`staff_manager`**: same SELECT and joins, comment block
`/* Staff Manager Survey expectations: direct reports evaluate manager */`,
filter `where sa.name = 'Manager Survey'`.

**`staff_support`**: same SELECT and joins, comment block
`/* Staff Support Survey expectations */`, filter
`where sa.name = 'Support Survey'`.

The 8-column output is identical to the prior CTEs (`survey_administration_key`,
`survey_key`, `term_key`, `respondent_type`, `staff_key`,
`student_enrollment_key`, `student_contact_person_key`, `employee_number`) —
preserves PK composition and the downstream `union all` shape.

- [ ] **Step 2: Verify no `int_people__staff_roster_history` references remain
      in the file.**

```bash
grep -n "int_people__staff_roster_history\|srh\." \
  src/dbt/kipptaf/models/marts/dimensions/bridge_survey_expectations.sql
```

Expected: no output.

- [ ] **Step 3: Build the model.**

```bash
uv run --directory src/dbt/kipptaf dbt build \
  --select bridge_survey_expectations --target dev 2>&1 | tail -30
```

Expected: model builds; existing PK uniqueness test still passes.

- [ ] **Step 4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/bridge_survey_expectations.sql
git commit -m "refactor(dbt): rebuild bridge_survey_expectations via SCD traversal

Retire int_people__staff_roster_history date-range joins. New chain
traverses dim_work_assignment_status (status='A', date-range),
dim_work_assignment_primary (is_primary_position, date-range), and
dim_staff_work_assignments (staff_key resolution). Output FK shape
unchanged — adding a work_assignment_status_key FK would create a
diamond path to dim_staff. Refs #3687."
```

---

## Task 14: Update `marts/CLAUDE.md` with `bridge_*` paragraph and strike #3687

Two edits: add a short paragraph defining the new `bridge_*` model category, and
remove #3687 from the "Deferred structural follow-ups" list (it's resolved).

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/CLAUDE.md`

- [ ] **Step 1: Add the `bridge_*` paragraph.**

Find the section describing `rpt_` and `dim_*`/`fct_*` (in the parent
`kipptaf/CLAUDE.md` it's "Model Layer Distinctions"; in `marts/CLAUDE.md` it's a
similar paragraph in the intro). Locate it in `marts/CLAUDE.md`. The current
intro paragraph (line 3):

```text
Dimensional marts (star schema) consumed by Cube and Tableau. Most-downstream
layer — no `ref()` from staging, intermediate, or reporting into marts.
Intra-mart refs are permitted (e.g. `bridge_survey_expectations → dim_surveys`,
`fct_staff_attrition → dim_staff_status`). When renaming a mart column, grep
`ref(...)` within `marts/` too — not just outside.
```

Add a new paragraph immediately after this one:

```text
**Bridge models (`bridge_*`)** are factless facts that link two or more
dimensions via a many-to-many relationship and carry no measures. Naming
follows `bridge_<entity>_<entity>` or `bridge_<concept>` when the linked
entities are obvious from context. Like dims and facts, bridges inherit
`contract: enforced: true` and `materialized: view`, and require an
explicit uniqueness test on their PK. Bridges follow the same strict-chain
rule as facts — no diamond paths to a shared ancestor dim.
```

- [ ] **Step 2: Strike #3687 from "Deferred structural follow-ups".**

Find the section "## Deferred structural follow-ups" near the end of
`marts/CLAUDE.md`. The list contains:

```text
- #3687 — `int_people__staff_roster_history` multi-assignment fan-out
```

Delete that whole bullet.

- [ ] **Step 3: Verify the file still renders cleanly.**

```bash
/workspaces/teamster/.trunk/tools/trunk fmt \
  src/dbt/kipptaf/models/marts/CLAUDE.md 2>&1 | tail -5
```

Expected: formatted without errors.

- [ ] **Step 4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/CLAUDE.md
git commit -m "docs(dbt): add bridge_* paragraph and strike #3687 from deferred list

bridge_survey_expectations is the first bridge_* model in the repo;
document the convention. Refs #3687."
```

---

## Task 15: Append hash-change entry to column-naming audit spec

`marts/CLAUDE.md` requires every surrogate-key hash change to be logged in the
audit spec. Only one new key was introduced — `work_assignment_primary_key`
(Composition: structural add).

**Files:**

- Modify: `docs/superpowers/specs/2026-04-15-column-naming-audit.md`

- [ ] **Step 1: Locate the "Enumerated surrogate-key changes" section.**

```bash
grep -n "Enumerated surrogate-key changes\|## " \
  docs/superpowers/specs/2026-04-15-column-naming-audit.md | head -20
```

- [ ] **Step 2: Append a new row to the table.**

Add the entry to the existing table. Match the existing row format. The row
content:

```text
| `dim_work_assignment_primary` | `work_assignment_primary_key` | new | `surrogate_key([item_id, effective_start_date])` | Structural add — new SCD mart introduced in PR Batch B (#3687) |
```

- [ ] **Step 3: Commit.**

```bash
git add docs/superpowers/specs/2026-04-15-column-naming-audit.md
git commit -m "docs: log dim_work_assignment_primary surrogate-key in audit spec

Refs #3687."
```

---

## Task 16: Pre-push verification + reconciliation probes

Worktrees lack trunk's pre-commit hooks, so trunk must be run manually before
push. Reconciliation queries can run against the dbt Cloud PR-branch schema once
CI completes (the schema name pattern is
`dbt_cloud_pr_<ci_id>_<pr_num>_kipptaf_marts`).

- [ ] **Step 1: Run trunk check and fix any issues.**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-batch-b-staff-coverage
/workspaces/teamster/.trunk/tools/trunk check --ci 2>&1 | tail -40
```

Expected: clean exit. If issues are reported, fix them and amend the relevant
commit (or add follow-up commits).

- [ ] **Step 2: Push the branch and open the PR.**

```bash
git push -u origin cbini/fix/claude-batch-b-staff-coverage
```

Open the PR via `gh pr create` (use `.github/pull_request_template.md` as the
body). Title: `fix(dbt): batch B staff coverage`. Body should reference both
#3687 and #3716, and link to the design spec.

- [ ] **Step 3: Wait for dbt Cloud CI to complete.**

Watch via `gh pr checks <pr_num> --watch` or the dbt Cloud UI. Note the
PR-branch schema name from the CI logs (e.g.,
`dbt_cloud_pr_70403xxxxxx_NNNN_kipptaf_marts`).

- [ ] **Step 4: Run reconciliation probe — `fct_staff_attrition` row counts by
      region.**

Substitute `<schema>` with the PR-branch schema name. Run via the BigQuery MCP
(or in the BigQuery console):

```sql
with prod as (
  select
    coalesce(d.location_region, 'UNKNOWN') as region,
    a.academic_year,
    count(*) as n_rows,
    countif(a.is_attrition) as n_attrition,
  from `teamster-332318.kipptaf_marts.fct_staff_attrition` a
  left join `teamster-332318.kipptaf_marts.dim_staff` s
    on a.staff_status_key = s.staff_key
  left join `teamster-332318.kipptaf_marts.dim_staff_work_assignments` w
    on s.staff_key = w.staff_key
  left join `teamster-332318.kipptaf_marts.dim_work_assignment_locations` l
    on w.work_assignment_key = l.work_assignment_key
  left join `teamster-332318.kipptaf_marts.dim_locations` d
    on l.location_key = d.location_key
  group by region, a.academic_year
),
pr as (
  select coalesce(d.location_region, 'UNKNOWN') as region,
    a.academic_year,
    count(*) as n_rows,
    countif(a.is_attrition) as n_attrition,
  from `teamster-332318.<schema>.fct_staff_attrition` a
  -- (mirror the same joins against the PR schema; substitute <schema> on each)
  group by region, a.academic_year
)
select
  coalesce(prod.region, pr.region) as region,
  coalesce(prod.academic_year, pr.academic_year) as ay,
  prod.n_rows as prod_rows, pr.n_rows as pr_rows,
  pr.n_rows - prod.n_rows as row_delta,
  prod.n_attrition as prod_attrition, pr.n_attrition as pr_attrition,
  pr.n_attrition - prod.n_attrition as attrition_delta,
from prod
full outer join pr using (region, academic_year)
order by region, ay desc
```

Expected:

- Non-Paterson regions: small drift (≤ ~3.8% from primary-history correction).
- Paterson region: 0 → N (incidental coverage). Sanity-check N is plausible
  relative to Paterson headcount.

If non-Paterson drift exceeds ~10%, treat as a logic regression and debug before
merging.

- [ ] **Step 5: Run reconciliation probe — `bridge_survey_expectations`.**

Substitute `<schema>` with the PR-branch schema name. Note: prod still has
`dim_survey_expectations` (renamed in this PR), so the prod CTE queries that
name; the PR CTE queries `bridge_survey_expectations`.

```sql
with prod as (
  select
    coalesce(d.location_region, 'UNKNOWN') as region,
    e.survey_administration_key,
    count(*) as n_rows,
  from `teamster-332318.kipptaf_marts.dim_survey_expectations` e
  left join `teamster-332318.kipptaf_marts.dim_staff_work_assignments` w
    on e.staff_key = w.staff_key
  left join `teamster-332318.kipptaf_marts.dim_work_assignment_locations` l
    on w.work_assignment_key = l.work_assignment_key
  left join `teamster-332318.kipptaf_marts.dim_locations` d
    on l.location_key = d.location_key
  where e.respondent_type = 'staff'
  group by region, e.survey_administration_key
),
pr as (
  select
    coalesce(d.location_region, 'UNKNOWN') as region,
    e.survey_administration_key,
    count(*) as n_rows,
  from `teamster-332318.<schema>.bridge_survey_expectations` e
  left join `teamster-332318.<schema>.dim_staff_work_assignments` w
    on e.staff_key = w.staff_key
  left join `teamster-332318.<schema>.dim_work_assignment_locations` l
    on w.work_assignment_key = l.work_assignment_key
  left join `teamster-332318.<schema>.dim_locations` d
    on l.location_key = d.location_key
  where e.respondent_type = 'staff'
  group by region, e.survey_administration_key
)
select
  coalesce(prod.region, pr.region) as region,
  coalesce(prod.survey_administration_key, pr.survey_administration_key) as sak,
  prod.n_rows as prod_rows,
  pr.n_rows as pr_rows,
  pr.n_rows - prod.n_rows as row_delta,
from prod
full outer join pr using (region, survey_administration_key)
order by region, sak
```

Expected drift pattern:

- Non-Paterson regions: small drift per `survey_administration_key`, in line
  with the ~3.8% primary-history correction.
- Paterson region: 0 → N for any survey administration that included Paterson
  staff. Sanity-check N is plausible relative to Paterson primary-active staff
  during each survey window.

If non-Paterson drift exceeds ~10% on any survey administration, treat as a
logic regression and debug before merging.

- [ ] **Step 6: Document reconciliation results in the PR description.**

Add a section to the PR body summarizing the row-delta and attrition- delta
numbers from Steps 4-5, partitioned by region. This is the evidence the reviewer
needs to approve the merge.

- [ ] **Step 7: Triage any unexpected test failures or fan-out.**

Per the spec's in-flight triage rule:

1. Triage immediately — classify side-effect / latent / unrelated.
2. Address in this PR if small + mechanically related.
3. File and defer otherwise.
4. Document each triage decision in the PR description.

Known triage candidate: **#3681** (`dim_staff_status` has 0 rows). If the
reconciliation surfaces `fct_staff_attrition.staff_status_key` mass-orphaning,
that's #3681 manifesting. Triage decision: fix in this PR if root cause is a
narrow SQL bug in `dim_staff_status.sql`; defer otherwise.

- [ ] **Step 8: Mark PR ready and request review.**

Once CI is green and reconciliation is documented, mark ready for review and
link the PR back to both #3687 and #3716.

---

## Self-review checklist (worker should run before declaring done)

After completing all tasks, run through this list:

- [ ] All 16 tasks committed; `git log --oneline origin/main..HEAD` shows the
      expected commit sequence.
- [ ] No remaining references to `int_people__staff_roster_history` in
      `fct_staff_attrition.sql` or `bridge_survey_expectations.sql`.
- [ ] No remaining `select distinct` or `-- TODO: #3687` in those files.
- [ ] No `is_primary_position` column in `dim_staff_work_assignments` (SQL or
      YAML).
- [ ] No `work_assignment_status_key` or `primary_work_assignment_status_key`
      output FK on either consumer (those would diamond to `dim_staff`).
- [ ] `dim_work_assignment_primary` mart, YAML, and Cube exposure all present.
- [ ] `bridge_survey_expectations` files present; no leftover
      `dim_survey_expectations` files.
- [ ] `marts/CLAUDE.md` has `bridge_*` paragraph; #3687 struck from deferred
      list.
- [ ] Hash-change audit entry appended.
- [ ] `trunk check --ci` clean.
- [ ] All five originally failing relationships tests pass on the PR schema.
- [ ] Reconciliation row-delta documented in PR body, partitioned by region.
