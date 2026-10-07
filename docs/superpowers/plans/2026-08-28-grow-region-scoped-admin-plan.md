# Grow region-scoped admin access implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the job-title role rule in `rpt_schoolmint_grow__users` with
an ADP `job_function` tier plus a department gate, stop assigning `Sub Admin`,
and make `Coach` additive so it stacks with an admin role.

**Architecture:** All logic changes live in one dbt model,
`rpt_schoolmint_grow__users.sql`. Three CTEs change: `staff` gains a tier and a
department-gate flag, `instructional_managers` gets a parenthesisation fix, and
the `people` CTE's role expression drops its `coalesce` for a single additive
array. `group_type` in the `roster` CTE becomes two independent predicates. No
column is added or removed, so `grow_user_sync` needs no change in this
sub-project.

**Tech Stack:** dbt (BigQuery), dbt unit tests defined in the model's properties
YAML, `uv run dbt` for all commands.

**Spec:** `docs/superpowers/specs/2026-08-28-grow-region-scoped-admin-design.md`

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin`.
  Use `git -C <worktree>` for every git call and
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` for every dbt call.
- Branch is `cristinabaldor/feat/claude-grow-region-scoped-admin`. Never commit
  to `main`.
- Python and dbt run through `uv run` only. Never bare `dbt` or `python`.
- Conventional commit messages. Every commit body ends with `Refs #5052`.
- Never introduce a `job_title` match except the one documented Associate
  Director promotion. A null `job_function` yields no role, deliberately.
- The role vocabulary is exactly: `Regional Admin`, `School Admin`,
  `School Assistant Admin`, `Coach`, `Teacher`. `Sub Admin` must never be
  emitted.
- Gate departments, verbatim: `Teaching and Learning`, `School Support`,
  `Teacher Development`, `New Teacher Development`, `Special Education`,
  `School Leadership`, `Leadership Development`, `KIPP Forward`,
  `Special Projects`, `Executive`.
- Tier values, verbatim from ADP: `Chief Level`, `EDs, HOSs, MDOs`,
  `KTAF or Regional Managing Director`, `KTAF or Regional Director`,
  `KTAF or Regional Staff`, `School Leader`, `Assistant School Leaders`,
  `Deans`, `Teacher`, `Teacher in Residence`.
- Do not run `trunk fmt` or `trunk check` by hand. The pre-commit hook formats;
  run `.trunk/tools/trunk check --force` on changed SQL only before pushing.

---

## File Structure

| File                                                                                   | Responsibility                                          | Tasks      |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------- | ---------- |
| `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`            | All role and observation-group logic                    | 1, 2, 3    |
| `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml` | Column docs, model-level data tests, and all unit tests | 1, 2, 3, 4 |

Both files already exist. Nothing is created. The model is a single file by
existing convention and is not split by this plan.

---

## Task 1: Teacher predicate and instructional-manager precedence

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql:1-27`
- Test:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `staff.is_teacher` as `bool` (never null), and
  `instructional_managers.reports_to_employee_number` as `int64`. Task 2 reads
  both.

- [ ] **Step 1: Write the failing unit test**

Append to
`src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`.
If the file has no `unit_tests:` key yet, add it at the top level, after
`models:`.

```yaml
unit_tests:
  - name: unit_grow_users_teacher_predicate_and_coach_precedence
    description:
      Pins the two fixes in Task 1. A teacher is identified by job_function
      alone, so a staff member titled "Teacher" with a null job_function is no
      longer a teacher and no longer makes their manager a Coach. The
      instructional-manager predicate is parenthesised, so a manager in a
      coaching department whose only report is terminated no longer qualifies.
    model: rpt_schoolmint_grow__users
    given:
      - input: ref('int_people__staff_roster')
        format: sql
        rows: |
          select
              1 as employee_number,
              'teach1@apps.teamschools.org' as google_email,
              10 as reports_to_employee_number,
              'KIPP TEAM Academy' as home_work_location_reporting_name,
              'Elementary' as home_department_name,
              'kippnewark' as home_work_location_dagster_code_location,
              'Ada' as given_name,
              'Real' as family_name_1,
              'Active' as assignment_status,
              'Teacher' as job_function,
              'Teacher' as job_title,
              5 as primary_grade_level_taught,
              'areal@apps.teamschools.org' as user_principal_name,
              cast(null as date) as worker_termination_date
          union all
          select
              2, 'teach2@apps.teamschools.org', 11, 'KIPP TEAM Academy',
              'Elementary', 'kippnewark', 'Nul', 'Function', 'Active',
              cast(null as string), 'Teacher', 5,
              'nfunction@apps.teamschools.org', cast(null as date)
          union all
          select
              3, 'term@apps.teamschools.org', 12, 'KIPP TEAM Academy',
              'Student Support', 'kippnewark', 'Gone', 'Already', 'Terminated',
              'Teacher', 'Teacher', 5, 'galready@apps.teamschools.org',
              date '2024-06-30'
          union all
          select
              10, 'mgr1@apps.teamschools.org', cast(null as int64),
              'KIPP TEAM Academy', 'School Leadership', 'kippnewark',
              'Real', 'Manager', 'Active', 'Assistant School Leaders',
              'Assistant School Leader', cast(null as int64),
              'rmanager@apps.teamschools.org', cast(null as date)
          union all
          select
              11, 'mgr2@apps.teamschools.org', cast(null as int64),
              'KIPP TEAM Academy', 'School Leadership', 'kippnewark',
              'Nulls', 'Only', 'Active', 'Assistant School Leaders',
              'Assistant School Leader', cast(null as int64),
              'nonly@apps.teamschools.org', cast(null as date)
          union all
          select
              12, 'mgr3@apps.teamschools.org', cast(null as int64),
              'KIPP TEAM Academy', 'Student Support', 'kippnewark',
              'Term', 'Reports', 'Active', 'Deans', 'Dean',
              cast(null as int64), 'treports@apps.teamschools.org',
              cast(null as date)
      - input: ref('stg_schoolmint_grow__roles')
        format: sql
        rows: |
          select 'r-coach' as role_id, 'Coach' as name
          union all
          select 'r-teacher', 'Teacher'
          union all
          select 'r-saa', 'School Assistant Admin'
          union all
          select 'r-sa', 'School Admin'
          union all
          select 'r-ra', 'Regional Admin'
      - input: ref('stg_schoolmint_grow__schools')
        format: sql
        rows: |
          select 'sch-team' as school_id, 'KIPP TEAM Academy' as name
      - input: ref('stg_schoolmint_grow__users')
        format: sql
        rows: |
          select
              cast(null as string) as user_id,
              cast(null as int64) as internal_id_int,
              cast(null as string) as archived_at,
              cast(null as string) as email,
              cast(null as string) as name,
              cast(null as string) as coach,
              cast(null as bool) as inactive,
              cast(null as string) as default_information_course,
              cast(null as string) as default_information_grade_level,
              cast(null as string) as default_information_school,
              cast(
                  null as array<struct<`_id` string, name string>>
              ) as roles
          where false
      - input: ref('stg_schoolmint_grow__generic_tags')
        format: sql
        rows: |
          select
              cast(null as string) as tag_id,
              cast(null as string) as name,
              cast(null as string) as abbreviation,
              cast(null as string) as tag_type
          where false
    expect:
      format: sql
      rows: |
        select 1 as user_internal_id, ['Teacher'] as role_names
        union all
        select 10, ['School Assistant Admin']
        union all
        select 11, ['School Assistant Admin']
```

Only three rows survive, and which rows are _absent_ is what this test pins.

- Employee 2 has a null `job_function`. Under the old title fallback they were a
  teacher, so they appeared with `['Teacher']`. After the fix they emit no role
  and drop out at the `people_roles` inner join.
- Employee 12 manages only employee 3, who is terminated. Under the buggy
  predicate the second branch skipped the status filter, so employee 12
  qualified as a Coach and appeared with `['Coach']`. After the fix they do not
  qualify and drop out.
- Employee 3 is terminated before the population cutoff and never appears at
  all.
- Employees 10 and 11 keep only `School Assistant Admin`. Employee 10 does
  manage an active teacher, but the `coalesce` still in place at this task
  suppresses `Coach`. Task 2 is what restores it — do not expect it here.

Note that `expect` compares only the columns it names, so the other output
columns are unconstrained.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: FAIL, with two extra rows in the actual output. Employee 2 appears
with `['Teacher']` because the current title fallback matches a null
`job_function`. Employee 12 appears with `['Coach']` because the current
predicate skips the assignment-status filter on its second branch and so counts
a terminated report.

- [ ] **Step 3: Replace the teacher predicate**

In `rpt_schoolmint_grow__users.sql`, replace the whole `staff` CTE:

```sql
    staff as (
        select
            *,

            /*
                job_function is the only tier input. A null job_function is an
                ADP data defect and is deliberately not patched over here --
                see docs/superpowers/specs/2026-08-28-grow-region-scoped-admin-design.md
            */
            coalesce(
                job_function in ('Teacher', 'Teacher in Residence'), false
            ) as is_teacher,
        from {{ ref("int_people__staff_roster") }}
        where home_work_location_dagster_code_location != 'kipppaterson'
    ),
```

- [ ] **Step 4: Parenthesise the instructional-manager predicate**

Replace the whole `instructional_managers` CTE:

```sql
    instructional_managers as (
        select distinct sr.reports_to_employee_number,
        from staff as sr
        join staff as srm on sr.reports_to_employee_number = srm.employee_number
        where
            sr.assignment_status in ('Active', 'Leave')
            and (
                sr.is_teacher
                or srm.home_department_name
                in ('School Support', 'Student Support', 'KIPP Forward')
            )
    ),
```

The only change is the parentheses. `A and B or C` parsed as `(A and B) or C`,
which let the second branch skip the assignment-status filter entirely.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "fix(dbt): key the Grow teacher predicate on job_function alone

Drops the job_title fallback so a null job_function yields no teacher,
surfacing the ADP data defect instead of hiding it. Also parenthesises the
instructional-manager predicate, whose second branch skipped the
assignment-status filter and qualified managers on terminated reports.

Refs #5052"
```

---

## Task 2: Tier resolution, department gate, additive roles

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql` —
  the `staff` CTE and the `role_names` expression in the `people` CTE
- Test:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: `staff.is_teacher` (`bool`) and
  `instructional_managers.reports_to_employee_number` (`int64`) from Task 1.
- Produces: `staff.tier` as `string` (nullable) and
  `staff.passes_department_gate` as `bool`. `people.role_names` becomes
  `array<string>` drawn from exactly `Regional Admin`, `School Admin`,
  `School Assistant Admin`, `Coach`, `Teacher`. Task 3 reads `role_names`.

- [ ] **Step 1: Write the failing unit test**

Append a second entry under the existing `unit_tests:` key. Reuse the same five
`given` inputs as Task 1 verbatim except for `int_people__staff_roster`, which
is replaced with the rows below. Copy the four unchanged inputs
(`stg_schoolmint_grow__roles`, `stg_schoolmint_grow__schools`,
`stg_schoolmint_grow__users`, `stg_schoolmint_grow__generic_tags`) exactly as
written in Task 1.

```yaml
- name: unit_grow_users_role_matrix
  description:
    Pins the tier-times-gate role matrix. One row per tier that grants a role,
    plus a Director in a department outside the gate proving the gate blocks, an
    Associate Director proving the one title promotion, a null job_function
    proving no fallback exists, and an admin who manages a teacher proving Coach
    is additive rather than replaced.
  model: rpt_schoolmint_grow__users
  given:
    - input: ref('int_people__staff_roster')
      format: sql
      rows: |
        select
            100 as employee_number,
            'chief@apps.teamschools.org' as google_email,
            cast(null as int64) as reports_to_employee_number,
            'KIPP TEAM Academy' as home_work_location_reporting_name,
            'Teaching and Learning' as home_department_name,
            'kippnewark' as home_work_location_dagster_code_location,
            'Chief' as given_name,
            'Academic' as family_name_1,
            'Active' as assignment_status,
            'Chief Level' as job_function,
            'Chief Academic Officer' as job_title,
            cast(null as int64) as primary_grade_level_taught,
            'chief@apps.teamschools.org' as user_principal_name,
            cast(null as date) as worker_termination_date
        union all
        select
            101, 'hos@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'School Support', 'kippnewark',
            'Head', 'Schools', 'Active', 'EDs, HOSs, MDOs',
            'Head of Schools', cast(null as int64),
            'hos@apps.teamschools.org', cast(null as date)
        union all
        select
            102, 'md@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'Special Education', 'kippnewark',
            'Managing', 'Director', 'Active',
            'KTAF or Regional Managing Director', 'Managing Director',
            cast(null as int64), 'md@apps.teamschools.org', cast(null as date)
        union all
        select
            103, 'blocked@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'Finance', 'kippnewark',
            'Gated', 'Out', 'Active', 'KTAF or Regional Director',
            'Director', cast(null as int64),
            'blocked@apps.teamschools.org', cast(null as date)
        union all
        select
            104, 'assoc@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'Special Education', 'kippnewark',
            'Assoc', 'Promoted', 'Active', 'KTAF or Regional Staff',
            'Associate Director', cast(null as int64),
            'assoc@apps.teamschools.org', cast(null as date)
        union all
        select
            105, 'sl@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'School Leadership', 'kippnewark',
            'School', 'Leader', 'Active', 'School Leader', 'School Leader',
            cast(null as int64), 'sl@apps.teamschools.org', cast(null as date)
        union all
        select
            106, 'dean@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'Student Support', 'kippnewark',
            'Assistant', 'Dean', 'Active', 'Deans', 'Assistant Dean',
            cast(null as int64), 'dean@apps.teamschools.org',
            cast(null as date)
        union all
        select
            107, 'nulljf@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'Teaching and Learning', 'kippnewark',
            'Null', 'Tier', 'Active', cast(null as string),
            'Achievement Director', cast(null as int64),
            'nulljf@apps.teamschools.org', cast(null as date)
        union all
        select
            108, 'coachadmin@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'School Leadership', 'kippnewark',
            'Coaching', 'Admin', 'Active', 'Assistant School Leaders',
            'Assistant School Leader', cast(null as int64),
            'coachadmin@apps.teamschools.org', cast(null as date)
        union all
        select
            109, 'report@apps.teamschools.org', 108,
            'KIPP TEAM Academy', 'Elementary', 'kippnewark',
            'Real', 'Teacher', 'Active', 'Teacher', 'Teacher', 5,
            'report@apps.teamschools.org', cast(null as date)
  expect:
    format: sql
    rows: |
      select 100 as user_internal_id, ['Regional Admin'] as role_names
      union all
      select 101, ['Regional Admin']
      union all
      select 102, ['Regional Admin']
      union all
      select 104, ['Regional Admin']
      union all
      select 105, ['School Admin']
      union all
      select 106, ['School Assistant Admin']
      union all
      select 108, ['Coach', 'School Assistant Admin']
      union all
      select 109, ['Teacher']
```

Employee 103 is gated out and 107 has a null tier, so neither appears at all.
Employee 108 is the additive-Coach regression: today the `coalesce` would return
`['School Assistant Admin']` alone.

`role_names` is ordered by `role_id`, so element order follows the mocked role
ids alphabetically: `r-coach` before `r-ra`, `r-sa`, `r-saa`, `r-teacher`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: FAIL. Every admin row currently resolves through the old title CASE,
so 100 through 104 return `Sub Admin` and 108 loses its `Coach`.

- [ ] **Step 3: Add the tier and gate to the `staff` CTE**

Replace the `staff` CTE written in Task 1 with:

```sql
    staff as (
        select
            *,

            /*
                job_function is the only tier input. A null job_function is an
                ADP data defect and is deliberately not patched over here --
                see docs/superpowers/specs/2026-08-28-grow-region-scoped-admin-design.md
            */
            coalesce(
                job_function in ('Teacher', 'Teacher in Residence'), false
            ) as is_teacher,

            /*
                ADP records some Associate Directors at staff level, which
                understates them. This is the one deliberate title exception.
            */
            if(
                job_function = 'KTAF or Regional Staff'
                and contains_substr(job_title, 'Associate Director'),
                'KTAF or Regional Director',
                job_function
            ) as tier,

            home_department_name in (
                'Teaching and Learning',
                'School Support',
                'Teacher Development',
                'New Teacher Development',
                'Special Education',
                'School Leadership',
                'Leadership Development',
                'KIPP Forward',
                'Special Projects',
                'Executive'
            ) as passes_department_gate,
        from {{ ref("int_people__staff_roster") }}
        where home_work_location_dagster_code_location != 'kipppaterson'
    ),
```

- [ ] **Step 4: Replace the role expression**

In the `people` CTE, replace the whole `coalesce(...) as role_names` expression
— from `coalesce(` through `) as role_names,` — with:

```sql
            /*
                Every predicate is independent and contributes at most one role.
                Nothing suppresses anything else, which is what lets an admin
                who manages teachers keep Coach.

                Chief Level and the three Director tiers both resolve to
                Regional Admin here; they differ only in school scope, which
                sub-project 2 supplies.
            */
            array(
                select rn
                from
                    unnest(
                        [
                            case
                                when
                                    sr.tier in (
                                        'Chief Level',
                                        'EDs, HOSs, MDOs',
                                        'KTAF or Regional Managing Director',
                                        'KTAF or Regional Director'
                                    )
                                    and sr.passes_department_gate
                                then 'Regional Admin'
                                when sr.tier = 'School Leader'
                                then 'School Admin'
                                when sr.tier in ('Assistant School Leaders', 'Deans')
                                then 'School Assistant Admin'
                            end,
                            if(
                                sr.employee_number in (
                                    select reports_to_employee_number
                                    from instructional_managers
                                ),
                                'Coach',
                                null
                            ),
                            if(sr.is_teacher, 'Teacher', null)
                        ]
                    ) as rn
                where rn is not null
            ) as role_names,
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS, both unit tests.

- [ ] **Step 6: Confirm `Sub Admin` is gone from the source**

```bash
grep -n "Sub Admin" \
  /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql
```

Expected: no matches.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(dbt): assign Grow roles from job_function tier and department gate

Replaces the job-title CASE with an ADP job_function tier plus a department
gate, and retires Sub Admin entirely in favour of region-scoped Regional
Admin. Drops the coalesce so admin roles add to Coach and Teacher instead
of replacing them, restoring Coach to admins who manage teachers.

Refs #5052"
```

---

## Task 3: Additive observation-group membership

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql` —
  the `group_type` expression in the `roster` CTE
- Test:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: `people.role_names` (`array<string>`) from Task 2.
- Produces: `roster.group_type` as `string`, one of `observees`, `observers`,
  `observees;observers` or the empty string. `grow_user_sync` tests it with
  `"observees" in u["group_type"]`, so the substring shape must not change.

- [ ] **Step 1: Write the failing unit test**

Append a third entry under `unit_tests:`. Reuse the four non-roster `given`
inputs from Task 1 verbatim.

```yaml
- name: unit_grow_users_group_type_additive
  description:
    Pins observee and observer membership as two independent predicates. A
    School Assistant Admin who coaches is now both, where the old first-match
    CASE made every admin an observer only. A Regional Admin is an observer but
    never an observee. A plain teacher stays an observee.
  model: rpt_schoolmint_grow__users
  given:
    - input: ref('int_people__staff_roster')
      format: sql
      rows: |
        select
            200 as employee_number,
            'ra@apps.teamschools.org' as google_email,
            cast(null as int64) as reports_to_employee_number,
            'KIPP TEAM Academy' as home_work_location_reporting_name,
            'School Support' as home_department_name,
            'kippnewark' as home_work_location_dagster_code_location,
            'Regional' as given_name,
            'Leader' as family_name_1,
            'Active' as assignment_status,
            'EDs, HOSs, MDOs' as job_function,
            'Head of Schools' as job_title,
            cast(null as int64) as primary_grade_level_taught,
            'ra@apps.teamschools.org' as user_principal_name,
            cast(null as date) as worker_termination_date
        union all
        select
            201, 'saa@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'School Leadership', 'kippnewark',
            'Assistant', 'Leader', 'Active', 'Assistant School Leaders',
            'Assistant School Leader', cast(null as int64),
            'saa@apps.teamschools.org', cast(null as date)
        union all
        select
            202, 'teach@apps.teamschools.org', 201,
            'KIPP TEAM Academy', 'Elementary', 'kippnewark',
            'Plain', 'Teacher', 'Active', 'Teacher', 'Teacher', 5,
            'teach@apps.teamschools.org', cast(null as date)
  expect:
    format: sql
    rows: |
      select 200 as user_internal_id, 'observers' as group_type
      union all
      select 201, 'observees;observers'
      union all
      select 202, 'observees'
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: FAIL. Employee 201 returns `observers` under the current first-match
CASE, because the admin branch fires before the Coach branch.

- [ ] **Step 3: Replace the `group_type` expression**

In the `roster` CTE, replace the whole `case ... end as group_type,` block with:

```sql
            /*
                Observee and observer are independent. An admin who coaches is
                both; Regional Admin is an observer only, because a regional
                leader is not observed inside a school's Teachers group.
            */
            case
                when
                    exists (
                        select 1
                        from unnest(p.role_names) as rn
                        where
                            rn in ('Teacher', 'School Admin', 'School Assistant Admin')
                    )
                    and exists (
                        select 1
                        from unnest(p.role_names) as rn
                        where rn like '%Admin%' or rn = 'Coach'
                    )
                then 'observees;observers'
                when
                    exists (
                        select 1
                        from unnest(p.role_names) as rn
                        where rn like '%Admin%' or rn = 'Coach'
                    )
                then 'observers'
                when
                    exists (
                        select 1
                        from unnest(p.role_names) as rn
                        where
                            rn in ('Teacher', 'School Admin', 'School Assistant Admin')
                    )
                then 'observees'
                else ''
            end as group_type,
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run dbt test \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS, all three unit tests.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(dbt): make Grow observation-group membership additive

Observee and observer become independent predicates instead of a
first-match CASE, so an admin who coaches lands in both lists. School Admin
and School Assistant Admin are now observees, letting their managers
observe them; Regional Admin stays observer-only.

Refs #5052"
```

---

## Task 4: Documentation and the no-Sub-Admin data test

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: the final `role_names` vocabulary from Task 2 and the `group_type`
  values from Task 3.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the model-level data test**

Under the existing `data_tests:` key on `rpt_schoolmint_grow__users`, add a
third entry alongside the two `dbt_utils.expression_is_true` tests already
there:

```yaml
- dbt_utils.expression_is_true:
    arguments:
      expression: "'Sub Admin' not in unnest(role_names)"
```

- [ ] **Step 2: Rewrite the model description**

Replace the `description:` value on `rpt_schoolmint_grow__users` with:

```yaml
description: >
  One row per Grow user, comparing the desired source-of-truth state (from ADP /
  staff roster) against the current destination state in SchoolMint Grow. Drives
  `grow_user_sync` create / update / archive / restore decisions via
  `surrogate_key_source` vs `surrogate_key_destination`. Excludes Paterson
  staff, who do not use Grow. Roles are assigned from the ADP `job_function`
  tier, gated by `home_department_name` for Director tier and above; `Sub Admin`
  is never assigned, because region-scoped `Regional Admin` replaces it. A null
  `job_function` yields no role at all and is treated as an ADP data defect
  rather than patched over with a job title. The one title exception is
  `Associate Director`, promoted from staff tier to Director tier. Every role
  predicate is independent, so a user who matches both an admin tier and the
  Coach predicate receives both.
```

- [ ] **Step 3: Rewrite the `role_names` and `group_type` column descriptions**

Replace the `description:` on the `role_names` column with:

```yaml
description: >
  Human-readable role labels (`Regional Admin`, `School Admin`, `School
  Assistant Admin`, `Coach`, `Teacher`), ordered alphabetically by `role_id` so
  elements align with `role_ids`. `Sub Admin` is never emitted.
```

Replace the `description:` on the `group_type` column with:

```yaml
description: >
  Observation-group membership directive consumed by `grow_user_sync`. Observee
  and observer are independent: `observees` covers `Teacher`, `School Admin` and
  `School Assistant Admin`, `observers` covers any admin role plus `Coach`, and
  a user who matches both gets `observees;observers`. Empty string when the user
  matches neither.
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run dbt build \
  --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS. The new `expression_is_true` test confirms no row carries
`Sub Admin`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "docs(dbt): document the job_function role rule, assert no Sub Admin

Refs #5052"
```

---

## Task 5: Blast-radius verification against production

**Files:** none modified. This task produces evidence, not code.

**Interfaces:**

- Consumes: the built model from Task 4.
- Produces: a confirmed or refuted match against the spec's expected counts.

- [ ] **Step 1: Build the model into your development schema**

```bash
uv run dbt build \
  --select +rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS. Note the schema it wrote to; it will be
`zz_<username>_kipptaf_extracts`.

- [ ] **Step 2: Compare the new roles against production**

Run this against BigQuery, substituting your development schema for
`<dev_schema>`:

```sql
select
    ifnull(array_to_string(prod.role_names, ' + '), '(not in extract)') as before,
    ifnull(array_to_string(dev.role_names, ' + '), '(not in extract)') as after,
    count(*) as n
from `teamster-332318.<dev_schema>.rpt_schoolmint_grow__users` as dev
full outer join
    `teamster-332318.kipptaf_extracts.rpt_schoolmint_grow__users` as prod
    on dev.user_internal_id = prod.user_internal_id
where ifnull(dev.inactive, 0) = 0 or ifnull(prod.inactive, 0) = 0
group by 1, 2
order by n desc
```

Expected, matching the spec's blast-radius table:

| before             | after                                        | n        |
| ------------------ | -------------------------------------------- | -------- |
| `Sub Admin`        | `Regional Admin` or `Regional Admin + Coach` | 46 total |
| `Sub Admin`        | `(not in extract)`                           | 16       |
| `Teacher`          | `(not in extract)`                           | 18       |
| `(not in extract)` | `School Assistant Admin`                     | 16       |
| `(not in extract)` | `Regional Admin`                             | 10       |

- [ ] **Step 3: Confirm the Coach restoration**

```sql
select count(*) as admins_regaining_coach
from `teamster-332318.<dev_schema>.rpt_schoolmint_grow__users` as dev
join
    `teamster-332318.kipptaf_extracts.rpt_schoolmint_grow__users` as prod
    on dev.user_internal_id = prod.user_internal_id
where
    'Coach' in unnest(dev.role_names)
    and 'Coach' not in unnest(prod.role_names)
    and dev.inactive = 0
```

Expected: about 115. Treat anything below 100 or above 130 as a defect worth
investigating before merging.

- [ ] **Step 4: Confirm no row carries `Sub Admin`**

```sql
select count(*) as sub_admin_rows
from `teamster-332318.<dev_schema>.rpt_schoolmint_grow__users`
where 'Sub Admin' in unnest(role_names)
```

Expected: `0`.

- [ ] **Step 5: Lint the changed SQL before pushing**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
  src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml </dev/null
```

Expected: no sqlfluff or yamllint findings. Formatting findings are fixed by the
pre-commit hook and can be ignored.

- [ ] **Step 6: Push and open the pull request**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  push -u origin cristinabaldor/feat/claude-grow-region-scoped-admin
```

Then open the PR using `.github/pull_request_template.md` as the body, with
`Closes #5052` so the issue links.

---

## Deferred, do not implement here

- Writing `regionalAdminSchools` and `readonly` from `grow_user_sync`. That is
  sub-project 2 and needs a new column on this model.
- The revoke path for users the extract no longer emits. That is sub-project 3,
  and it must not ship before the ADP `job_function` correction, or 18 teachers
  lose Grow access.
- Per-coach observation groups, placeholder locations and the Poinciana name
  mismatch. Tracked in
  [#5054](https://github.com/TEAMSchools/teamster/issues/5054).
