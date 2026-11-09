# Pension Plan Join Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `nj_pension_plan_name` for every roster position with an
active NJ pension.

**Architecture:** Delete one predicate from the pension `left join` in
`int_people__staff_roster_history.sql`. No new models, columns, or tests.

**Tech Stack:** dbt (kipptaf project), BigQuery.

**Spec:** `docs/superpowers/specs/2026-11-09-pension-plan-join-design.md`

## Global Constraints

- Do not commit or push. The user tests the change before anything is committed.
- Change only the join predicate; leave `rn_enrollment_recent` in the staging
  model.
- Post no row-level values to GitHub; aggregates only.

## Review Focus

- A position with 2 active NJ pension rows would fan out the roster. The
  existing `unique_combination_of_columns` test (`employee_number`,
  `effective_date_start`, `position_id`) on `int_people__staff_roster_history`
  must pass in Task 1 Step 3.
- Staff who already had a plan (114 in prod) must keep the same value. Task 1
  Step 4 checks this.
- Historical roster rows: the join has no date condition, so every history row
  for a position now gets the position's current plan. That matches how the 114
  existing values already behave; Task 1 Step 4 confirms row counts hold.

---

### Task 1: Remove the rank filter from the pension join

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster_history.sql:331`

**Interfaces:**

- Consumes: `stg_adp_workforce_now__pension_and_benefits_enrollments`
  (`position_id`, `enrollment_status`, `plan_name`).
- Produces: `nj_pension_plan_name` on `int_people__staff_roster_history`, read
  by `int_people__staff_roster` and `rpt_tableau__staff_roster` (Tableau
  `[NJ Pension Plan Name]`).

- [ ] **Step 1: Baseline from prod**

  Count distinct `employee_number` with non-null `nj_pension_plan_name` in
  `kipptaf_people.int_people__staff_roster`. Expected: 114.

- [ ] **Step 2: Delete `and pbe.rn_enrollment_recent = 1` from the join and
      limit the plan to the current record**

  The `on` clause keeps `position_id`, `enrollment_status = 'Active'`, and the
  3-plan `plan_name in (...)` list. Select
  `if(w.is_current_record, pbe.plan_name, null) as nj_pension_plan_name`, and
  add the column with a `description` to
  `properties/int_people__staff_roster_history.yml`.

- [ ] **Step 3: Build and test**

  Run from `src/dbt/kipptaf`:
  `uv run dbt build --select int_people__staff_roster_history+ 2>&1 | tail -n 30`
  Expected: the model and its uniqueness test pass. Note any downstream failures
  and check whether they also fail on `main` before attributing them to this
  change.

- [ ] **Step 4: Compare the dev build to prod**

  Against the dev `int_people__staff_roster`:
  - distinct `employee_number` with non-null `nj_pension_plan_name`: 1,244
  - total rows: same as prod
  - rows where prod's non-null `nj_pension_plan_name` differs from dev: 0

  Against the dev `int_people__staff_roster_history`:
  - rows with `not is_current_record` and non-null `nj_pension_plan_name`: 0
  - total rows: same as prod

- [ ] **Step 5: Hand to the user for testing**

  Report the counts. Do not commit.
