# Grow region scope, revoke path and observation groups implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship sub-projects 2, 3 and 4 of the Grow admin work — give
`Regional Admin` real school scope, let the sync revoke roles it no longer
grants, and replace each school's single flat observation group with one group
per coach.

**Architecture:** Four extract changes in `rpt_schoolmint_grow__users.sql`, two
new columns on `stg_schoolmint_grow__users`, and three changes to
`grow_user_sync`. The extract gains `regional_admin_school_ids` and `readonly`;
the sync writes both to the Grow user, and rebuilds each school's
`observationGroups` as one group per coach instead of one per school.

**Tech Stack:** dbt (BigQuery) with contract-enforced extracts and unit tests in
the properties YAML; Dagster (Python) for `grow_user_sync`; `uv run` for
everything.

**Spec:** `docs/superpowers/specs/2026-08-28-grow-region-scoped-admin-design.md`

## Global Constraints

- Worktree
  `/workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin`.
  `git -C <worktree>` for git;
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` for dbt. Never
  `uv --directory <worktree> run dbt`.
- Branch `cristinabaldor/feat/claude-grow-region-scoped-admin`. Never commit to
  `main`.
- `uv run` only. Never bare `dbt` or `python`.
- Conventional commits, body ends `Refs #5052`.
- **Extracts are contract-enforced** (`dbt_project.yml:116-119`). Every new
  column on `rpt_schoolmint_grow__users` needs a `data_type` entry in the
  properties YAML or the build fails.
- The role vocabulary stays exactly `Regional Admin`, `School Admin`,
  `School Assistant Admin`, `Coach`, `Teacher`. `Sub Admin` is never emitted.
- Exactly one `job_title` match may exist in the model (the Associate Director
  promotion). Do not add a second.
- `group_type` values stay `observees`, `observers`, `observees;observers` or
  empty — `grow_user_sync` tests them with a Python substring check.
- dbt unit-test fixtures: an empty typed mock needs `from unnest([1])` before
  `where false`, and `expect:` must use dict format, not `format: sql`. Copy the
  four shared mock inputs from the committed tests in the properties YAML.
- Do NOT run `trunk fmt` or `trunk check`; the pre-commit hook formats.

---

## File Structure

| File                                                                                       | Responsibility                                                     | Tasks   |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | ------- |
| `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql`            | Expose destination-side `readonly` and `regionalAdminSchools`      | 1       |
| `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__users.yml` | Contract types for those two columns                               | 1       |
| `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`                | Region school list, readonly, either-name school join, revoke path | 2, 3, 4 |
| `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`     | Contract, docs, unit tests                                         | 2, 3, 4 |
| `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`                            | User payload fields, per-coach groups, multi-school admin lists    | 5, 6, 7 |

---

## Task 1: Expose `readonly` and `regionalAdminSchools` on the staging model

The extract needs the destination-side values to detect drift. The staging model
selects neither today.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__users.yml`

**Interfaces:**

- Produces: `stg_schoolmint_grow__users.read_only` as `boolean`, and
  `regional_admin_schools` as `array<struct<name string, _id string>>`. Task 2
  consumes both.

- [ ] **Step 1: Add the two columns to the staging SQL**

In `stg_schoolmint_grow__users.sql`, add these two lines to the select list,
immediately after the existing `coach,` line:

```sql
    readonly as read_only,
```

and add this to the repeated-records group, immediately after `roles,`:

```sql
    regionaladminschools as regional_admin_schools,
```

Source columns are lower-cased by the Avro external table, matching the existing
`archivedat` / `defaultinformation` style already in this file.

- [ ] **Step 2: Add the contract types**

In the properties YAML, the file already carries commented-out stubs for both.
Replace the commented `# - name: read_only` / `# - name: regional_admin_schools`
stubs with live entries, placed with the other active columns:

```yaml
- name: read_only
  data_type: boolean
- name: regional_admin_schools
  data_type: |
    array<struct<name string, _id string>>
```

- [ ] **Step 3: Build and confirm the columns resolve**

```bash
uv run dbt build --select stg_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS. A contract mismatch here means the declared type does not match
the source; fix the YAML type, not the SQL.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(dbt): expose Grow readonly and regionalAdminSchools in staging

The extract needs both on the destination side to detect scope drift.

Refs #5052"
```

---

## Task 2: Region school list and `readonly` on the extract

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: `read_only` and `regional_admin_schools` from Task 1.
- Produces: `regional_admin_school_ids` as `array<string>` and `readonly` as
  `int64` (0/1, matching the existing `inactive` convention), plus
  `regional_admin_school_ids_ws` and `readonly_ws` on the destination side. Task
  5 consumes the two source-side columns.

- [ ] **Step 1: Write the failing unit test**

Append a new entry under `unit_tests:`. Copy the four shared mock inputs
(`stg_schoolmint_grow__roles`, `stg_schoolmint_grow__schools`,
`stg_schoolmint_grow__users`, `stg_schoolmint_grow__generic_tags`) from a
committed test in this same file, then extend the schools mock to three rows and
add the crosswalk input:

```yaml
- name: unit_grow_users_region_scope
  description:
    Pins region scope. A Chief Level user gets every active school regardless of
    region. A Director-tier user gets only the schools whose crosswalk region
    matches their own. A teacher gets an empty list. readonly is 1 for Regional
    Admin holders and 0 for everyone else.
  model: rpt_schoolmint_grow__users
  given:
    - input: ref('int_people__staff_roster')
      format: sql
      rows: |
        select
            300 as employee_number,
            'chief@apps.teamschools.org' as google_email,
            cast(null as int64) as reports_to_employee_number,
            'KIPP TEAM Academy' as home_work_location_reporting_name,
            'KIPP TEAM Academy' as home_work_location_name,
            'Teaching and Learning' as home_department_name,
            'kippnewark' as home_work_location_dagster_code_location,
            'Chief' as given_name,
            'Network' as family_name_1,
            'Active' as assignment_status,
            'Chief Level' as job_function,
            'Chief Academic Officer' as job_title,
            cast(null as int64) as primary_grade_level_taught,
            'chief@apps.teamschools.org' as user_principal_name,
            cast(null as date) as worker_termination_date
        union all
        select
            301, 'md@apps.teamschools.org', cast(null as int64),
            'KIPP TEAM Academy', 'KIPP TEAM Academy', 'School Support',
            'kippnewark', 'Regional', 'Leader', 'Active',
            'EDs, HOSs, MDOs', 'Head of Schools', cast(null as int64),
            'md@apps.teamschools.org', cast(null as date)
        union all
        select
            302, 'teach@apps.teamschools.org', 301,
            'KIPP TEAM Academy', 'KIPP TEAM Academy', 'Elementary',
            'kippnewark', 'Plain', 'Teacher', 'Active', 'Teacher',
            'Teacher', 5, 'teach@apps.teamschools.org', cast(null as date)
    - input: ref('int_people__location_crosswalk')
      format: sql
      rows: |
        select
            'KIPP TEAM Academy' as location_name,
            'kippnewark' as location_dagster_code_location
        union all
        select 'KIPP Courage Academy', 'kippmiami'
    - input: ref('stg_schoolmint_grow__schools')
      format: sql
      rows: |
        select 'sch-team' as school_id, 'KIPP TEAM Academy' as name,
               cast(null as string) as archived_at
        union all
        select 'sch-courage', 'KIPP Courage Academy', cast(null as string)
```

Reuse the other three mock inputs verbatim from the committed tests.

```yaml
expect:
  rows:
    - {
        user_internal_id: 300,
        regional_admin_school_ids: [sch-courage, sch-team],
        readonly: 1,
      }
    - {
        user_internal_id: 301,
        regional_admin_school_ids: [sch-team],
        readonly: 1,
      }
    - { user_internal_id: 302, regional_admin_school_ids: [], readonly: 0 }
```

Employee 300 is `Chief Level`, so they get both schools even though
`KIPP Courage Academy` is in a different region. Employee 301 is region-scoped
to `kippnewark`, so they get only `sch-team`. Employee 302 is a teacher with no
admin role, so an empty list and `readonly = 0`.

School ids are ordered, so sort them in the model.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run dbt test --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: FAIL — the columns do not exist yet.

- [ ] **Step 3: Add the school-region CTE**

Add this CTE immediately after the `staff` CTE. It is the only place school
region is resolved.

```sql
    grow_schools as (
        select
            sch.school_id,
            lc.location_dagster_code_location as region,
        from {{ ref("stg_schoolmint_grow__schools") }} as sch
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sch.name = lc.location_name
        where sch.archived_at is null
    ),
```

`[Training School]` has no crosswalk row, so its `region` is null. It is
therefore absent from every region list and present only in the all-schools
list, which is the intended behaviour.

- [ ] **Step 4: Add `school_name_alt` to the `people` CTE**

Task 3 needs it. Add this line immediately after the existing
`sr.home_work_location_reporting_name as school_name,`:

```sql
            sr.home_work_location_name as school_name_alt,
```

- [ ] **Step 5: Build the two new columns in the `roster` CTE**

First add a CTE that resolves the school list per user. Do NOT write this as
`array(select ... from grow_schools where <correlated predicate>)` — a
correlated subquery that references another table creates a view successfully
and then fails on every read. Use a join and `array_agg` instead. Place it
immediately after `people_roles`:

```sql
    regional_scope as (
        select
            p.user_internal_id,
            array_agg(gs.school_id order by gs.school_id) as school_ids,
        from people as p
        inner join
            grow_schools as gs
            on (p.tier = 'Chief Level' or gs.region = p.region)
        where 'Regional Admin' in unnest(p.role_names)
        group by p.user_internal_id
    ),
```

Then join it into `roster` alongside the existing joins:

```sql
        left join
            regional_scope as rs on p.user_internal_id = rs.user_internal_id
```

and add these to the `roster` CTE's select list, after `sch.school_id,`:

```sql
            /*
                Chief Level sees every active school; the other Regional Admin
                tiers see their own region. Everyone else gets an empty array.
                [Training School] has no crosswalk region, so it appears only
                in the all-schools case.
            */
            ifnull(rs.school_ids, []) as regional_admin_school_ids,

            if('Regional Admin' in unnest(p.role_names), 1, 0) as readonly,

            array(
                select s._id
                from unnest(u.regional_admin_schools) as s
                order by s._id
            ) as regional_admin_school_ids_ws,

            if(u.read_only, 1, 0) as readonly_ws,
```

This requires `p.tier` and `p.region` to exist on the `people` CTE. Add both to
that CTE's select list:

```sql
            sr.tier,
            sr.home_work_location_dagster_code_location as region,
```

- [ ] **Step 6: Add both sides to the surrogate keys**

The sync compares these two hashes to decide whether to PUT. Without the new
fields, a hand-edited scope is never corrected.

Add `regional_admin_school_ids_hash` and `readonly` to the
`surrogate_key_source` argument list, keeping it alphabetical, and
`regional_admin_school_ids_ws_hash` and `readonly_ws` to
`surrogate_key_destination`.

Arrays cannot be hashed directly, so add both string forms to the
`roster_hashed` CTE alongside the existing `role_ids_hash`:

```sql
            array_to_string(regional_admin_school_ids, ',')
            as regional_admin_school_ids_hash,
            array_to_string(regional_admin_school_ids_ws, ',')
            as regional_admin_school_ids_ws_hash,
```

- [ ] **Step 7: Carry the columns through `surrogate_keys` and the final
      select**

Add `regional_admin_school_ids`, `readonly`, `regional_admin_school_ids_ws` and
`readonly_ws` to the `surrogate_keys` CTE's select list and to the final select,
matching the existing column order convention.

- [ ] **Step 8: Add the contract entries**

Extracts are contract-enforced, so the build fails without these. Add to the
properties YAML `columns:` list:

```yaml
- name: regional_admin_school_ids
  data_type: array<string>
  description: >
    Grow school ids this user should be scoped to, sent as
    `regionalAdminSchools`. Every active school for a `Chief Level` user, the
    user's own region for the other `Regional Admin` tiers, empty for everyone
    else. Ordered by school id so the surrogate key is stable.
- name: readonly
  data_type: int64
  description: >
    1 when the user holds `Regional Admin`, else 0. Sent as the Grow user
    `readonly` flag, which gives visibility without configuration power. School
    Admin and School Assistant Admin are deliberately not readonly.
- name: regional_admin_school_ids_ws
  data_type: array<string>
  description: Current `regionalAdminSchools` ids on the Grow user.
- name: readonly_ws
  data_type: int64
  description: Current `readonly` flag (0/1) on the Grow user.
```

- [ ] **Step 9: Run the tests**

```bash
uv run dbt build --select rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS, all unit tests and data tests.

- [ ] **Step 10: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(dbt): emit Grow region school scope and the readonly flag

Regional Admin is meaningless without schools attached. Chief Level gets
every active school, the other Regional Admin tiers get their own region,
resolved through int_people__location_crosswalk because Grow's own school
region field is empty everywhere. Both new fields join the surrogate keys
so a hand-edited scope is detected and corrected.

Refs #5052"
```

---

## Task 3: Accept either location name on the school join

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Consumes: `school_name_alt` from Task 2 Step 4.
- Produces: nothing new; four previously-dropped staff now appear.

- [ ] **Step 1: Write the failing unit test**

Append under `unit_tests:`, reusing the shared mock inputs:

```yaml
  - name: unit_grow_users_school_join_accepts_either_name
    description:
      Pins the either-name school join. A staff member whose reporting name
      matches the Grow school resolves, and so does one whose reporting name
      does not match but whose plain name does. The Poinciana case is the
      second: its reporting name is `KIPP Miami - Poinciana Campus` while the
      Grow school is `Poinciana Campus`.
    model: rpt_schoolmint_grow__users
    given:
      - input: ref('int_people__staff_roster')
        format: sql
        rows: |
          select
              400 as employee_number,
              'match@apps.teamschools.org' as google_email,
              cast(null as int64) as reports_to_employee_number,
              'KIPP TEAM Academy' as home_work_location_reporting_name,
              'KIPP TEAM Academy' as home_work_location_name,
              'Elementary' as home_department_name,
              'kippnewark' as home_work_location_dagster_code_location,
              'Reporting' as given_name,
              'Match' as family_name_1,
              'Active' as assignment_status,
              'Teacher' as job_function,
              'Teacher' as job_title,
              5 as primary_grade_level_taught,
              'match@apps.teamschools.org' as user_principal_name,
              cast(null as date) as worker_termination_date
          union all
          select
              401, 'poinc@kippmiami.org', cast(null as int64),
              'KIPP Miami - Poinciana Campus', 'Poinciana Campus',
              'Elementary', 'kippmiami', 'Plain', 'Match', 'Active',
              'Teacher', 'Teacher', 5, 'poinc@kippmiami.org',
              cast(null as date)
      - input: ref('stg_schoolmint_grow__schools')
        format: sql
        rows: |
          select 'sch-team' as school_id, 'KIPP TEAM Academy' as name,
                 cast(null as string) as archived_at
          union all
          select 'sch-poinc', 'Poinciana Campus', cast(null as string)
    expect:
      rows:
        - { user_internal_id: 400, school_id: sch-team }
        - { user_internal_id: 401, school_id: sch-poinc }
```

Employee 401 is the regression: today they are dropped entirely.

- [ ] **Step 2: Run the test to verify it fails**

Expected: FAIL — employee 401 is absent, because the join tests only the
reporting name.

- [ ] **Step 3: Widen the join**

In the `roster` CTE, replace:

```sql
        inner join
            {{ ref("stg_schoolmint_grow__schools") }} as sch on p.school_name = sch.name
```

with:

```sql
        /*
            Reporting name and plain name each match the Grow school for most
            locations but not all: Poinciana matches only on the plain name,
            while KIPP Hatch and KIPP Sumner match only on the reporting name.
            Accepting either resolves every active location to exactly one
            school, verified against the full roster, so this cannot fan out.
        */
        inner join
            {{ ref("stg_schoolmint_grow__schools") }} as sch
            on sch.name in (p.school_name, p.school_name_alt)
```

- [ ] **Step 4: Run the tests**

Expected: PASS. The existing
`unique_rpt_schoolmint_grow__users_user_internal_id` test is the fan-out guard —
if the join duplicated anyone, it fails here.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "fix(dbt): match Grow schools on either staff location name

Four Poinciana staff were dropped because the join tested only the
reporting name. Switching to the plain name alone would have dropped 81
staff at KIPP Hatch and KIPP Sumner instead. Accepting either resolves
every active location to exactly one school.

Refs #5052"
```

---

## Task 4: The revoke path

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

**Interfaces:**

- Produces: rows with empty `role_names` / `role_ids`. Task 5 relies on the sync
  sending `roles: []` for them, which the existing payload code already does.

- [ ] **Step 1: Write the failing unit test**

```yaml
- name: unit_grow_users_emits_no_role_users
  description:
    Pins the revoke path. A staff member who matches no role predicate is
    emitted with empty role arrays rather than dropped, so the sync can strip
    their Grow roles. Today they vanish at the people_roles inner join and the
    sync never sees them.
  model: rpt_schoolmint_grow__users
  given:
    - input: ref('int_people__staff_roster')
      format: sql
      rows: |
        select
            500 as employee_number,
            'norole@apps.teamschools.org' as google_email,
            cast(null as int64) as reports_to_employee_number,
            'KIPP TEAM Academy' as home_work_location_reporting_name,
            'KIPP TEAM Academy' as home_work_location_name,
            'Finance' as home_department_name,
            'kippnewark' as home_work_location_dagster_code_location,
            'No' as given_name,
            'Role' as family_name_1,
            'Active' as assignment_status,
            'KTAF or Regional Director' as job_function,
            'Director' as job_title,
            cast(null as int64) as primary_grade_level_taught,
            'norole@apps.teamschools.org' as user_principal_name,
            cast(null as date) as worker_termination_date
  expect:
    rows:
      - { user_internal_id: 500, role_names: [], role_ids: [], group_type: "" }
```

Finance does not pass the department gate, so this Director-tier user gets no
admin role, is not a coach, and is not a teacher.

- [ ] **Step 2: Run the test to verify it fails**

Expected: FAIL — no rows returned, because the user is dropped at the join.

- [ ] **Step 3: Make `people_roles` a LEFT join and coalesce**

Replace the `people_roles` CTE with:

```sql
    people_roles as (
        select
            p.user_internal_id,
            ifnull(
                array_agg(rn ignore nulls order by r.role_id), []
            ) as role_names,
            ifnull(
                array_agg(r.role_id ignore nulls order by r.role_id), []
            ) as role_ids,
        from people as p
        left join unnest(p.role_names) as rn
        left join {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
        group by p.user_internal_id
    ),
```

`left join unnest(...)` keeps a user whose `role_names` array is empty, and
`ignore nulls` keeps the aggregate empty rather than producing `[null]`.

- [ ] **Step 4: Remove the obsolete model-level test**

Delete this entry from `data_tests:` on the model — an empty array is now a
deliberate output, not a defect:

```yaml
- dbt_utils.expression_is_true:
    arguments:
      expression: array_length(role_ids) >= 1
```

Leave the other two model-level tests in place.

- [ ] **Step 5: Run the tests**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
      src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(dbt): emit no-role Grow users so the sync can revoke

A user matching no role predicate was dropped at an inner join, so the sync
never saw them and never removed anything. 21 people hold admin roles the
extract does not manage. They are now emitted with empty role arrays.

Refs #5052"
```

---

## Task 5: Write `regionalAdminSchools` and `readonly` from the sync

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`

**Interfaces:**

- Consumes: `regional_admin_school_ids` and `readonly` from Task 2.

- [ ] **Step 1: Add both fields to the user payload**

In `grow_user_sync`, the user payload dict currently ends with `"coach"` and
`"roles"`. Add two entries so it reads:

```python
        payload: dict[str, Any] = {
            "district": grow.district_id,
            "name": u["user_name"],
            "email": user_email,
            "internalId": u["user_internal_id"],
            "inactive": inactive,
            "defaultInformation": {
                "school": u["school_id"],
                "gradeLevel": u["grade_id"],
                "course": u["course_id"],
            },
            "coach": u["coach_id"],
            "roles": list(u["role_ids"]),
            "regionalAdminSchools": list(u["regional_admin_school_ids"]),
            "readonly": bool(u["readonly"]),
        }
```

The user PUT merges, so these two were previously left untouched — that is why
11 users carry a hand-set `readonly` today. Sending them explicitly is what
brings them under management.

- [ ] **Step 2: Validate the Dagster definitions still load**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipptaf.definitions
```

Expected: no errors. If the module path differs, use the one named in
`.github/workflows/deploy-prod-kipptaf.yaml`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/teamster/code_locations/kipptaf/level_data/grow/assets.py
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(grow): write regionalAdminSchools and readonly to the Grow user

Regional Admin over zero schools is not access. Both fields were previously
unmanaged, which is why 11 users carry a hand-set readonly flag.

Refs #5052"
```

---

## Task 6: One observation group per coach

The substantial change. Read the whole task before starting.

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`

**Interfaces:**

- Consumes: `group_type`, `coach_id`, `user_id`, `user_internal_id` and
  `user_name` on every extract row.

- [ ] **Step 1: Replace the observation-group block**

In the per-school loop, replace everything from `# observation groups` through
the `payload["observationGroups"] = [...]` assignment with:

```python
        # observation groups: one per coach, so a coach who is also a teacher
        # sees only their own reports rather than every teacher at the school.
        existing_groups = {
            g["name"]: g["_id"] for g in school["observationGroups"]
        }

        school_observers = [
            u["user_id"] for u in school_users if "observers" in u["group_type"]
        ]

        # Route every observee to their coach's group, or to the fallback.
        by_coach: dict[str, list[str]] = {}
        uncoached: list[str] = []

        for u in school_users:
            if "observees" not in u["group_type"]:
                continue

            coach_id = u["coach_id"]

            # A coach absent from the extract cannot own a group, so their
            # reports fall back rather than disappearing.
            if coach_id is None or coach_id not in users_by_grow_id:
                uncoached.append(u["user_id"])
            else:
                by_coach.setdefault(coach_id, []).append(u["user_id"])

        def coach_group_name(coach: dict[str, Any]) -> str:
            # The employee-number prefix is the match key, so a display-name
            # change relabels the group without breaking its identity.
            return f"Coach {coach['user_internal_id']} - {coach['user_name']}"

        wanted: dict[str, dict[str, Any]] = {
            # Teachers survives as the fallback for observees with no coach.
            "Teachers": {"observees": uncoached, "observers": school_observers}
        }

        for coach_id, observee_ids in by_coach.items():
            coach = users_by_grow_id[coach_id]

            wanted[coach_group_name(coach)] = {
                "observees": observee_ids,
                "observers": [coach_id],
            }

        # Match by the "Coach <employee_number>" prefix so a renamed coach
        # keeps their group's _id.
        def match_existing(name: str) -> str | None:
            if name in existing_groups:
                return existing_groups[name]

            prefix = " - ".join(name.split(" - ")[:1]) + " - "

            return next(
                (
                    group_id
                    for group_name, group_id in existing_groups.items()
                    if group_name.startswith(prefix)
                ),
                None,
            )

        observation_groups = []
        claimed: set[str] = set()

        for name, members in wanted.items():
            group: dict[str, Any] = {"name": name, **members}
            group_id = match_existing(name)

            if group_id is not None:
                group["_id"] = group_id
                claimed.add(group_id)

            observation_groups.append(group)

        # The school PUT REPLACES this array, so a group left out is deleted.
        # Emit every surviving group emptied rather than dropping it, so no
        # observation history is ever orphaned by a coach moving on.
        for group_name, group_id in existing_groups.items():
            if group_id in claimed:
                continue

            observation_groups.append(
                {
                    "_id": group_id,
                    "name": group_name,
                    "observees": [],
                    "observers": [],
                }
            )

        payload["observationGroups"] = observation_groups
```

- [ ] **Step 2: Build the coach index once, above the school loop**

`users_by_grow_id` must exist before the loop. Add it immediately after the
`schools = grow.get("schools")["data"]` line:

```python
    # A coach's home school often differs from their reports', so resolve
    # coaches from the full user set rather than from school_users.
    users_by_grow_id = {
        u["user_id"]: u for u in users if u["user_id"] is not None
    }
```

- [ ] **Step 3: Validate the definitions load**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipptaf.definitions
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/teamster/code_locations/kipptaf/level_data/grow/assets.py
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "feat(grow): build one observation group per coach

Every school had a single Teachers group holding every teacher as an
observee and every coach as an observer, so a coach who also teaches saw
peers they do not coach. Each coach now gets a group containing only their
own reports. Teachers survives, emptied, as the fallback for an observee
with no coach. Groups are matched by an employee-number prefix so a rename
cannot churn their ids, and a group no longer wanted is emptied rather than
deleted so its history is never orphaned.

Refs #5052"
```

---

## Task 7: Multi-school admin lists

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`

- [ ] **Step 1: Reach every school a leader covers**

`school_users` is filtered to one `school_id`, so a School Admin covering two
campuses is written to only one. The `coaches` union already walks the reporting
line; give the admin lists the same treatment. Replace the
`for key, role_name in admin_roles.items():` block with:

```python
        for key, role_name in admin_roles.items():
            # Home-school membership, plus anyone whose reports sit at this
            # school -- a leader covering two campuses belongs to both.
            admins_here = {
                u["user_id"] for u in school_users if role_name in u["role_names"]
            }

            for u in school_users:
                manager = users_by_grow_id.get(u["coach_id"])

                if manager is not None and role_name in manager["role_names"]:
                    admins_here.add(manager["user_id"])

            payload[key] = [
                {
                    "_id": user_id,
                    "name": users_by_grow_id[user_id]["user_name"],
                }
                for user_id in sorted(admins_here)
            ]
```

- [ ] **Step 2: Validate and commit**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipptaf.definitions
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  add src/teamster/code_locations/kipptaf/level_data/grow/assets.py
git -C /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin \
  commit -m "fix(grow): reach every school a multi-campus leader covers

admins and assistantAdmins were built from home school alone, so a leader
covering two campuses was written to one. They now follow the reporting
line the same way the coaches union already does.

Refs #5052"
```

---

## Task 8: Verification

**Files:** none modified.

- [ ] **Step 1: Full build**

```bash
uv run dbt build --select +rpt_schoolmint_grow__users \
  --project-dir /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin/src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 2: Re-run the blast radius against production**

The dev schema's `int_people__staff_roster` is weeks stale, so a dev-vs-prod
table comparison is meaningless. Use the existing script, which rewrites the
compiled SQL's dev schema references to production and evaluates it live:

```bash
uv run --with google-cloud-bigquery python .claude/scratch/grow_blast_radius.py
```

Expected: the sub-project 1 counts are unchanged — 46 to `Regional Admin`, 16
losing access, 28 new to Grow, 18 teachers dropped, zero `Sub Admin` — plus 4
Poinciana staff newly appearing from Task 3.

- [ ] **Step 3: Confirm region scope is populated**

```sql
select
    countif(array_length(regional_admin_school_ids) > 0) as with_scope,
    countif(readonly = 1) as readonly_users,
    max(array_length(regional_admin_school_ids)) as max_schools
from `teamster-332318.<dev_schema>.rpt_schoolmint_grow__users`
where inactive = 0
```

Expected: `with_scope` and `readonly_users` both equal the `Regional Admin`
count, and `max_schools` equals the active school count for the `Chief Level`
users.

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor-feat-claude-grow-region-scoped-admin && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql \
  src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml \
  src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__users.sql \
  src/teamster/code_locations/kipptaf/level_data/grow/assets.py </dev/null
```

Expected: no findings.

- [ ] **Step 5: Stop**

Do not push and do not open the pull request. Both are the human partner's to
authorise, and the merge is gated on the ADP `job_function` correction.

---

## Known gates

- The ADP `job_function` correction must land before this merges. Without it 18
  teachers lose their Grow roles and their observation-group membership.
- Three of the 21 unmanaged admins have no roster record, so the revoke path
  cannot reach them. They stay a manual cleanup.
