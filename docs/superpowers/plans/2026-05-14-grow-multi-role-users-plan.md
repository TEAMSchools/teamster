# SchoolMint Grow multi-role users — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `rpt_schoolmint_grow__users` emit multiple Grow role IDs per user
(Teacher + Coach hybrid) and update `grow_user_sync` to send the array.

**Architecture:** Promote `role_names` / `role_ids` / `role_ids_ws` from scalar
to `ARRAY<STRING>` in the existing extract, keep one row per user, and pass the
array straight through to Grow's `roles` API field. Surrogate keys hash a
deterministic `array_to_string(role_ids, ',')` projection so source/destination
comparison still detects drift.

**Tech Stack:** dbt 1.11+ on BigQuery, dbt_utils, Dagster + dagster-bigquery,
Python 3.13.

**Spec:**
`.worktrees/cbini/feat/claude-grow-multi-role-users/docs/superpowers/specs/2026-05-14-grow-multi-role-users-design.md`

**Tracking issue:** [#3928](https://github.com/TEAMSchools/teamster/issues/3928)

**Branch / worktree:** `cbini/feat/claude-grow-multi-role-users` at
`/workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users` (all
paths in this plan are relative to that worktree unless otherwise noted).

---

## File map

| Path                                                                                   | Action                                                                                             |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`            | Modify — rewrite `people`, `roster`, add `roster_hashed`, update `surrogate_keys` and final SELECT |
| `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml` | Modify — rename 3 columns to arrays, add descriptions, add array_length tests                      |
| `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`                        | Modify — `payload["roles"]`, admin grouping filter                                                 |

---

## Task 1: Rewrite the dbt model SQL

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`

This task replaces the file contents in one commit. The model is small (~240
lines) and the CTEs are tightly coupled — splitting into multiple commits would
leave half-broken SQL between commits.

- [ ] **Step 1: Replace file contents**

Overwrite
`src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql`
with:

```sql
with
    instructional_managers as (
        select distinct sr.reports_to_employee_number,
        from {{ ref("int_people__staff_roster") }} as sr
        join
            {{ ref("int_people__staff_roster") }} as srm
            on sr.reports_to_employee_number = srm.employee_number
        where
            sr.assignment_status in ('Active', 'Leave')
            and (
                contains_substr(sr.job_title, 'Teacher')
                or contains_substr(sr.job_title, 'Learning Specialist')
            )
            or srm.home_department_name
            in ('School Support', 'Student Support', 'KIPP Forward')
    ),

    people as (
        select
            sr.employee_number as user_internal_id,
            sr.google_email as user_email,
            sr.reports_to_employee_number as manager_internal_id,
            sr.home_work_location_reporting_name as school_name,
            sr.home_department_name as course_name,

            sr.given_name || ' ' || sr.family_name_1 as user_name,

            if(sr.assignment_status in ('Terminated', 'Deceased'), 1, 0) as inactive,

            if(
                sr.primary_grade_level_taught = 0,
                'K',
                cast(sr.primary_grade_level_taught as string)
            ) as grade_abbreviation,

            coalesce(
                case
                    /* network admins */
                    when sr.home_department_name = 'Executive'
                    then ['Sub Admin']
                    when sr.job_title = 'Head of Schools'
                    then ['Regional Admin']
                    when
                        sr.home_department_name in (
                            'Teaching and Learning',
                            'School Support',
                            'New Teacher Development'
                        )
                        and (
                            contains_substr(sr.job_title, 'Chief')
                            or contains_substr(sr.job_title, 'Leader')
                            or contains_substr(sr.job_title, 'Director')
                        )
                    then ['Sub Admin']
                    when sr.job_title = 'Achievement Director'
                    then ['Sub Admin']
                    when
                        sr.home_department_name = 'Special Education'
                        and contains_substr(sr.job_title, 'Director')
                    then ['Sub Admin']
                    when sr.home_department_name = 'Human Resources'
                    then ['Sub Admin']
                    /* school admins */
                    when sr.job_title = 'School Leader'
                    then ['School Admin']
                    when
                        sr.home_department_name = 'School Leadership'
                        and (
                            contains_substr(sr.job_title, 'Assistant School Leader')
                            or contains_substr(sr.job_title, 'Dean')
                            or sr.job_title = 'School Leader in Residence'
                        )
                    then ['School Assistant Admin']
                end,
                /* basic roles: Coach and Teacher are independent; a user can be both */
                array(
                    select rn
                    from
                        unnest([
                            if(
                                sr.employee_number in (
                                    select reports_to_employee_number
                                    from instructional_managers
                                ),
                                'Coach',
                                null
                            ),
                            if(
                                sr.job_title like '%Teacher%'
                                or sr.job_title like '%Learning%',
                                'Teacher',
                                null
                            )
                        ]) as rn
                    where rn is not null
                )
            ) as role_names,
        from {{ ref("int_people__staff_roster") }} as sr
        where
            sr.user_principal_name is not null
            and sr.home_department_name != 'Data'
            and coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            )
            >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    roster as (
        select
            p.user_internal_id,
            p.user_name,
            p.user_email,
            p.inactive,

            sch.school_id,

            u.user_id,
            u.archived_at,
            u.email as user_email_ws,
            u.name as user_name_ws,
            u.default_information_school as school_id_ws,
            u.default_information_grade_level as grade_id_ws,
            u.default_information_course as course_id_ws,
            u.coach as coach_id_ws,

            um.user_id as coach_id,

            cou.tag_id as course_id,

            gr.tag_id as grade_id,

            array(
                select rn
                from unnest(p.role_names) as rn
                inner join
                    {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
                order by r.role_id
            ) as role_names,

            array(
                select r.role_id
                from unnest(p.role_names) as rn
                inner join
                    {{ ref("stg_schoolmint_grow__roles") }} as r on rn = r.name
                order by r.role_id
            ) as role_ids,

            array(
                select role._id
                from unnest(u.roles) as role
                order by role._id
            ) as role_ids_ws,

            if(u.inactive, 1, 0) as inactive_ws,

            case
                when
                    exists (
                        select 1
                        from unnest(p.role_names) as rn
                        where rn like '%Admin%'
                    )
                then 'observers'
                when 'Coach' in unnest(p.role_names)
                then 'observees;observers'
                else 'observees'
            end as group_type,
        from people as p
        inner join
            {{ ref("stg_schoolmint_grow__schools") }} as sch on p.school_name = sch.name
        left join
            {{ ref("stg_schoolmint_grow__users") }} as u
            on p.user_internal_id = u.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__users") }} as um
            on p.manager_internal_id = um.internal_id_int
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as cou
            on p.course_name = cou.name
            and cou.tag_type = 'courses'
        left join
            {{ ref("stg_schoolmint_grow__generic_tags") }} as gr
            on p.grade_abbreviation = gr.abbreviation
            and gr.tag_type = 'grades'
    ),

    roster_hashed as (
        select
            *,
            array_to_string(role_ids, ',') as role_ids_hash,
            array_to_string(role_ids_ws, ',') as role_ids_ws_hash,
        from roster
        where array_length(role_ids) >= 1
    ),

    surrogate_keys as (
        select
            user_internal_id,
            user_name,
            user_email,
            inactive,
            role_names,
            school_id,
            role_ids,
            user_id,
            archived_at,
            user_email_ws,
            user_name_ws,
            school_id_ws,
            grade_id_ws,
            course_id_ws,
            coach_id_ws,
            coach_id,
            course_id,
            grade_id,
            role_ids_ws,
            inactive_ws,
            group_type,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "coach_id",
                        "course_id",
                        "grade_id",
                        "inactive",
                        "role_ids_hash",
                        "school_id",
                        "user_email",
                        "user_name",
                    ]
                )
            }} as surrogate_key_source,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "coach_id_ws",
                        "course_id_ws",
                        "grade_id_ws",
                        "inactive_ws",
                        "role_ids_ws_hash",
                        "school_id_ws",
                        "user_email_ws",
                        "user_name_ws",
                    ]
                )
            }} as surrogate_key_destination,
        from roster_hashed
    )

select
    user_internal_id,
    user_name,
    user_email,
    inactive,
    role_names,
    school_id,
    role_ids,
    user_id,
    archived_at,
    user_email_ws,
    user_name_ws,
    school_id_ws,
    grade_id_ws,
    course_id_ws,
    coach_id_ws,
    coach_id,
    course_id,
    grade_id,
    role_ids_ws,
    inactive_ws,
    group_type,
    surrogate_key_source,
    surrogate_key_destination,
from surrogate_keys
where
    /* create */
    (inactive = 0 and user_id is null)
    /* archive */
    or (inactive = 1 and user_id is not null and archived_at is null)
    /* update/reactivate */
    or inactive = 0
```

Key changes vs. original:

- `people` CTE: `role_name` (scalar `STRING`) becomes `role_names`
  (`ARRAY<STRING>`); the basic-roles branch builds an array from independent
  Coach and Teacher predicates so users matching both get both.
- `roster` CTE: removed the `inner join stg_schoolmint_grow__roles as r` from
  the FROM clause; added three `array(...)` subqueries to compute `role_names`
  (ordered), `role_ids`, and `role_ids_ws`; rewrote `group_type` to use `EXISTS`
  and `IN UNNEST`.
- New `roster_hashed` CTE: applies the `array_length(role_ids) >= 1` filter
  (replaces the row-drop that the old `INNER JOIN ... roles` did) and exposes
  scalar `role_ids_hash` / `role_ids_ws_hash` columns so
  `dbt_utils.generate_surrogate_key` can hash them without violating the "no
  inline expressions in `generate_surrogate_key`" rule.
- `surrogate_keys` CTE: `role_id` / `role_id_ws` replaced by `role_ids_hash` /
  `role_ids_ws_hash` in the two `generate_surrogate_key` calls; selected columns
  rename `role_name` → `role_names`, `role_id` → `role_ids`, `role_id_ws` →
  `role_ids_ws`.
- Final SELECT: same renames; hash columns are not emitted.

- [ ] **Step 2: Stage the file**

Run from the worktree:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users add src/dbt/kipptaf/models/extracts/schoolmint/rpt_schoolmint_grow__users.sql
```

Expected: no output. Do not commit yet — Task 2 lands the YAML in the same
commit so the contract stays in sync with the SQL.

---

## Task 2: Update the contract YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`

- [ ] **Step 1: Replace file contents**

Overwrite
`src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`
with:

```yaml
models:
  - name: rpt_schoolmint_grow__users
    description: >
      One row per Grow user, comparing the desired source-of-truth state (from
      ADP / staff roster) against the current destination state in SchoolMint
      Grow. Drives `grow_user_sync` create / update / archive / restore
      decisions via `surrogate_key_source` vs `surrogate_key_destination`. Users
      matching both the Coach predicate (instructional manager) and the Teacher
      predicate (job title contains "Teacher" or "Learning") receive both roles
      in `role_names` / `role_ids`. Admin classifications take precedence over
      Coach / Teacher.
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: array_length(role_ids) = array_length(role_names)
    columns:
      - name: role_ids
        data_type: array<string>
        description: >
          Grow role IDs the user should be assigned, ordered alphabetically by
          role_id. Lines up positionally with `role_names`. Sent verbatim as the
          `roles` array in the Grow API payload.
        data_tests:
          - dbt_utils.expression_is_true:
              arguments:
                expression: array_length(role_ids) >= 1
      - name: user_internal_id
        data_type: int64
        description: ADP employee number. Sent as Grow `internalId`.
      - name: user_name
        data_type: string
        description: Display name (`given_name || ' ' || family_name_1`).
      - name: user_email
        data_type: string
        description: ADP Google Workspace email. Sent as Grow `email`.
      - name: inactive
        data_type: int64
        description: >
          1 when ADP `assignment_status` is `Terminated` or `Deceased`, else 0.
          Drives archive vs create/update branching.
      - name: role_names
        data_type: array<string>
        description: >
          Human-readable role labels (`Sub Admin`, `Regional Admin`, `School
          Admin`, `School Assistant Admin`, `Coach`, `Teacher`), ordered
          alphabetically by `role_id` so elements align with `role_ids`.
      - name: school_id
        data_type: string
        description: >
          Grow school ID resolved from ADP home work location via
          `stg_schoolmint_grow__schools`.
      - name: user_id
        data_type: string
        description: >
          Grow user `_id` for an existing destination user, NULL when no
          matching Grow user exists yet.
      - name: archived_at
        data_type: string
        description:
          Grow archival timestamp; non-NULL when the Grow user is archived.
      - name: user_email_ws
        data_type: string
        description: Current `email` on the Grow user (destination side).
      - name: user_name_ws
        data_type: string
        description: Current `name` on the Grow user (destination side).
      - name: school_id_ws
        data_type: string
        description: Current `defaultInformation.school` on the Grow user.
      - name: grade_id_ws
        data_type: string
        description: Current `defaultInformation.gradeLevel` on the Grow user.
      - name: course_id_ws
        data_type: string
        description: Current `defaultInformation.course` on the Grow user.
      - name: coach_id_ws
        data_type: string
        description: Current `coach` (Grow user `_id`) on the Grow user.
      - name: coach_id
        data_type: string
        description: >
          Desired coach: Grow user `_id` of the manager identified by ADP
          `reports_to_employee_number`.
      - name: course_id
        data_type: string
        description: >
          Grow course tag `_id` matched from ADP `home_department_name` via
          `stg_schoolmint_grow__generic_tags` (tag_type = 'courses').
      - name: grade_id
        data_type: string
        description: >
          Grow grade tag `_id` matched from ADP `primary_grade_level_taught`
          (K-coded for 0) via `stg_schoolmint_grow__generic_tags` (tag_type =
          'grades').
      - name: role_ids_ws
        data_type: array<string>
        description: >
          Current Grow role IDs on the destination user, ordered alphabetically.
          Empty array when the Grow user has no roles.
      - name: inactive_ws
        data_type: int64
        description: Current Grow `inactive` flag (0/1) on the destination user.
      - name: group_type
        data_type: string
        description: >
          Observation-group membership directive consumed by `grow_user_sync`:
          `observers` for admins, `observees;observers` for users that include
          `Coach` in `role_names`, otherwise `observees`.
      - name: surrogate_key_source
        data_type: string
        description: >
          Hash of the desired-state fields (uses `array_to_string(role_ids,
          ',')` for the role component). Compared against
          `surrogate_key_destination` to decide whether to issue a Grow update.
      - name: surrogate_key_destination
        data_type: string
        description: >
          Hash of the destination-state fields (uses
          `array_to_string(role_ids_ws, ',')` for the role component).
```

Notes on the YAML:

- `role_ids` is sorted to the top of `columns:` because it carries a per-column
  data test (CLAUDE.md YAML convention).
- The model-level test cross-checks that `role_ids` and `role_names` array
  lengths agree — they must, because they're built from the same
  `unnest(p.role_names) inner join roles` subquery.
- Both tests use the dbt 1.11+ `arguments:` nesting form.
- Descriptions added for every column because the model is being modified
  (CLAUDE.md `src/dbt/`: "All new or modified models require `description:` on
  the model and every column").

- [ ] **Step 2: Stage the YAML**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users add src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml
```

Expected: no output.

- [ ] **Step 3: Commit the dbt-side changes**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users commit -m "$(cat <<'EOF'
feat(rpt_schoolmint_grow__users): emit role_names/role_ids/role_ids_ws as arrays

Refs #3928

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: a single commit landing the SQL + YAML together. trunk-fmt may
auto-format the files; let it.

---

## Task 3: Build and validate the model against staging

**Files:** none modified — this is a verification task.

- [ ] **Step 1: Parse the project**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users/src/dbt/kipptaf --target staging
```

Expected: `Found N models, ...` with no parse errors. If it errors with
"Compilation Error" referring to the model or YAML, re-read both files and fix
the discrepancy.

- [ ] **Step 2: Build the model and run its tests**

```bash
uv run dbt build --select rpt_schoolmint_grow__users --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users/src/dbt/kipptaf --target staging
```

Expected:

- `1 of N OK created sql view model dbt_<user>.rpt_schoolmint_grow__users`
- `2 of N PASS` for the two `expression_is_true` tests.

If `array_length(role_ids) >= 1` fails, the upstream
`stg_schoolmint_grow__roles` is missing a `name`-side match for a label emitted
by the CASE — inspect the offending row by querying `surrogate_keys` directly in
BigQuery and confirm the role label exists in `stg_schoolmint_grow__roles.name`.

If the contract fails (`data_type mismatch`), the YAML `data_type:` for one of
the array columns disagrees with the SQL output. BigQuery returns
`ARRAY<STRING>`; YAML spelling must be `array<string>` (lowercase).

- [ ] **Step 3: Confirm contract column count**

```bash
uv run dbt show --select rpt_schoolmint_grow__users --limit 0 --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users/src/dbt/kipptaf --target staging
```

Expected: column header row listing 23 columns ending in
`surrogate_key_destination`. `role_names`, `role_ids`, and `role_ids_ws` appear;
no `role_name`, `role_id`, or `role_id_ws`.

---

## Task 4: Spot-check hybrid rows via BigQuery

**Files:** none modified — this is a verification task. PII stays local; do not
paste row values into any PR comment, commit, or issue.

- [ ] **Step 1: Verify hybrid users land on both roles**

The model lives in `dbt_<user>` after the build. Use the BigQuery MCP
(`mcp__bigquery__execute_sql`):

```sql
select
    array_length(role_ids) as n_roles,
    count(*) as users,
from `teamster-332318`.dbt_<user>.rpt_schoolmint_grow__users
group by 1
order by 1
```

Expected: at least one row with `n_roles = 2` (the Teacher+Coach hybrids).
Pure-role rows show `n_roles = 1`. No rows should show `n_roles = 0` (the
`roster_hashed` WHERE filter prevents that).

- [ ] **Step 2: Inspect the hybrid role-name combination**

```sql
select
    role_names,
    count(*) as users,
from `teamster-332318`.dbt_<user>.rpt_schoolmint_grow__users
where array_length(role_names) > 1
group by 1
```

Expected: the only multi-role combination contains exactly `Coach` and `Teacher`
(order is whichever ordering the underlying `role_id` values produce — the test
in Task 3 already verified `role_ids` and `role_names` line up). If you see
admin labels combined with anything, the `coalesce(<admin-case>, <basic-array>)`
precedence in `people` is broken — re-check Task 1's SQL.

- [ ] **Step 3: Sanity-check counts against main**

```sql
select role_names, count(*) as users
from `teamster-332318`.dbt_<user>.rpt_schoolmint_grow__users
group by 1
order by 2 desc
```

Compare row counts per single-element role array against
`kipptaf_extracts.rpt_schoolmint_grow__users` (production) row counts per
`role_name`. Pure-Teacher / pure-Coach / admin counts should be approximately
stable; expect the Coach total to drop by the number of new hybrids (since those
users now show up under `['Coach','Teacher']` instead of `Coach` alone).

---

## Task 5: Update the Dagster sync

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`

- [ ] **Step 1: Update the payload role assignment**

In `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`, change the
`roles` line inside the payload dict.

Replace:

```python
            "coach": u["coach_id"],
            "roles": [u["role_id"]],
        }
```

With:

```python
            "coach": u["coach_id"],
            "roles": list(u["role_ids"]),
        }
```

The `list(...)` wrap normalizes the PyArrow array element into a plain Python
list for JSON serialization.

- [ ] **Step 2: Update the admin-role grouping filter**

Further down in the same function, in the school-update loop, the
`admin_roles.items()` loop compares against `u["role_name"]`. Replace:

```python
        for key, role_name in admin_roles.items():
            payload[key] = [
                {"_id": u["user_id"], "name": u["user_name"]}
                for u in school_users
                if role_name == u["role_name"]
            ]
```

With:

```python
        for key, role_name in admin_roles.items():
            payload[key] = [
                {"_id": u["user_id"], "name": u["user_name"]}
                for u in school_users
                if role_name in u["role_names"]
            ]
```

Admins never appear in a hybrid array (admin branches in the dbt CASE return
single-element arrays), so this still selects exactly the same rows as before —
just via membership instead of equality.

- [ ] **Step 3: Syntax-check the module**

```bash
uv run python -c "import teamster.code_locations.kipptaf.level_data.grow.assets"
```

Expected: no output (clean import). If `dagster definitions validate` is
available and runs without env-var errors in your codespace, prefer it;
otherwise the import check is sufficient.

- [ ] **Step 4: Stage and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users add src/teamster/code_locations/kipptaf/level_data/grow/assets.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users commit -m "$(cat <<'EOF'
feat(grow_user_sync): send multi-role payload to Grow

Refs #3928

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: one commit. trunk-fmt-pre-commit may reformat the file; let it.

---

## Task 6: Push and open the PR

**Files:** none modified.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users push -u origin cbini/feat/claude-grow-multi-role-users
```

Expected: push succeeds; `trunk-check-pre-push` runs sqlfluff / yamllint and
reports clean. If sqlfluff flags an ST06 column-ordering issue in the SQL,
reorder the affected column to match the rule (plain refs → constants → simple
funcs → nested funcs → logicals → case → window) and amend with a new commit (do
not `--amend` — make a new commit per project convention).

- [ ] **Step 2: Open the PR**

Use the `.github/pull_request_template.md` body. Read the template first:

```bash
cat /workspaces/teamster/.worktrees/cbini/feat/claude-grow-multi-role-users/.github/pull_request_template.md
```

Then create the PR:

```bash
gh pr create \
  --repo TEAMSchools/teamster \
  --base main \
  --head cbini/feat/claude-grow-multi-role-users \
  --title "feat(schoolmint-grow): support multi-role users in user sync" \
  --body "$(cat <<'EOF'
## Summary

- Promote `role_names` / `role_ids` / `role_ids_ws` in `rpt_schoolmint_grow__users` to `ARRAY<STRING>` so hybrid Teacher+Coach staff can carry both roles.
- Loosen the Coach vs Teacher CASE in the `people` CTE: each predicate is now evaluated independently, so a user matching both gets both. Admin classifications still win.
- Hash arrays for change detection via deterministic `array_to_string(role_ids, ',')` in a new `roster_hashed` CTE; surrogate-key inputs use the stringified projections.
- `grow_user_sync` sends `payload["roles"] = list(u["role_ids"])` and uses `role_name in u["role_names"]` for admin grouping.

Refs #3928

Design spec: `docs/superpowers/specs/2026-05-14-grow-multi-role-users-design.md`
Implementation plan: `docs/superpowers/plans/2026-05-14-grow-multi-role-users-plan.md`

## Test plan

- [ ] `uv run dbt build --select rpt_schoolmint_grow__users --project-dir src/dbt/kipptaf --target staging` passes (model + 2 expression_is_true tests).
- [ ] Spot-check via BigQuery: known Teacher+Coach staff land on `['Coach','Teacher']`; no rows have `array_length(role_ids) = 0`; pure-role counts are roughly stable vs. main.
- [ ] Branch-deployment smoke run of `grow_user_sync` confirms Grow accepts the multi-element `roles` payload without 4xx (review run logs; PII stays local).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. Project board auto-links via the `Refs #3928` line in
the body — do not `gh project item-add` the PR.

- [ ] **Step 3: Confirm CI kicks off**

```bash
gh pr checks <PR_NUMBER> --repo TEAMSchools/teamster --watch
```

Expected: trunk-check and dbt Cloud CI (`dbt build --select state:modified+`)
both queue and pass. If dbt Cloud CI fails on a stale defer relation for an
unmodified upstream, trigger the full `Clone - Staging` job in dbt Cloud (per
`src/dbt/kipptaf/CLAUDE.md`).

---

## Done when

- The PR is open with passing CI.
- The design spec and this plan are committed on the branch.
- The reviewer has the design spec link, the implementation plan link, and the
  staging spot-check evidence.

Post-merge rollout (out of scope for this PR): the next Dagster materialization
of `rpt_schoolmint_grow__users` rebuilds the extract; the first `grow_user_sync`
run after that will push an update for every active user (because the
surrogate-key hash recomposition shifts every row's `surrogate_key_source`). The
update is idempotent — Grow PUT replaces the user record — so this is safe.
