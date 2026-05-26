# SchoolMint Grow multi-role users — design

Refs #3928

## Problem

`rpt_schoolmint_grow__users` emits one row per Grow user with a single
`role_id`. The CASE in the `people` CTE evaluates Coach before Teacher, so any
instructional manager whose ADP `job_title` contains "Teacher" or "Learning"
lands on Coach only. The downstream Dagster sync (`grow_user_sync` in
`src/teamster/code_locations/kipptaf/level_data/grow/assets.py`) sends
`"roles": [u["role_id"]]` — always a single-element array.

Some staff are both Teacher and Coach. Grow's API accepts multiple roles per
user (`roles` is an array of role IDs), but the current dbt grain and sync
assumptions don't let us populate more than one.

## Goal

Support assigning multiple Grow role IDs to a single user without changing the
physical grain of `rpt_schoolmint_grow__users` (one row per user). Hybrid
Teacher+Coach is the immediate driver; the array shape generalizes if other
combinations come up.

## Non-goals

- No changes to admin classification rules (Sub Admin, Regional Admin, School
  Admin, School Assistant Admin). Admin branches return single-element arrays.
- No new source of "who is a hybrid" — the rule derives entirely from the
  existing Coach + Teacher predicates already in the model.
- No changes to `stg_schoolmint_grow__users` or other staging models.

## Approach

Keep one row per user in `rpt_schoolmint_grow__users`. Promote three columns
from scalar to `ARRAY<STRING>`:

| Old column          | New column    |
| ------------------- | ------------- |
| `role_name STRING`  | `role_names`  |
| `role_id STRING`    | `role_ids`    |
| `role_id_ws STRING` | `role_ids_ws` |

Hybrid rule: any user matching **both** the Coach predicate
(`employee_number IN instructional_managers`) **and** the Teacher predicate
(`job_title LIKE '%Teacher%' OR '%Learning%'`) emits `['Coach','Teacher']`. All
other branches (admins, pure Teacher, pure Coach) emit single-element arrays.

Array element order is alphabetical by `role_id` for both `role_ids` and
`role_ids_ws` — required for stable surrogate-key hashing across runs and for
the two arrays to compare equal as joined strings when the role sets match.
`role_names` is ordered by the same `role_id` ordering so its elements line up
positionally with `role_ids`.

## Detailed changes

### 1. `people` CTE — emit `role_names` array

Today's CASE returns a scalar string and short-circuits on the first match.
Restructure so that:

- Admin branches (everything above the Coach branch in the current CASE) return
  a single-element array via `[<role>]`.
- Coach and Teacher are no longer in the same CASE — they're independent
  predicates. Build the array as:

  ```sql
  array(
      select role_name
      from unnest([
          if(<coach predicate>, 'Coach', null),
          if(<teacher predicate>, 'Teacher', null)
      ]) as role_name
      where role_name is not null
  )
  ```

  Wrap this in an outer `coalesce(<admin-array>, <basic-roles-array>)` so admin
  matches win over Coach/Teacher (matches today's precedence).

Drop users with empty `role_names` (`array_length(role_names) = 0`) in the
`people` CTE WHERE clause — today's CASE returns NULL `role_name`, which already
excludes them via the join in `roster`. Keep that exclusion explicit rather than
relying on the join.

### 2. `roster` CTE — UNNEST + ARRAY_AGG to get `role_ids`

Replace the scalar join to `stg_schoolmint_grow__roles` with:

```sql
left join unnest(p.role_names) as role_name_unnested
left join {{ ref("stg_schoolmint_grow__roles") }} as r
    on role_name_unnested = r.name
...
array_agg(r.role_id order by r.role_id) as role_ids,
array_agg(role_name_unnested order by r.role_id) as role_names_ordered
```

`role_names_ordered` replaces `p.role_names` in the final SELECT so its elements
line up positionally with `role_ids`.

Apply the same UNNEST + sort treatment to the destination side (`u.roles` from
`stg_schoolmint_grow__users`) to produce `role_ids_ws`:

```sql
array(
    select role._id
    from unnest(u.roles) as role
    order by role._id
) as role_ids_ws
```

Drop the existing `role_id_ws` scalar (`u.roles[0]._id`) — replaced by the
array.

### 3. `group_type` derivation

Today:

```sql
case
    when p.role_name = 'Coach' then 'observees;observers'
    when p.role_name like '%Admin%' then 'observers'
    else 'observees'
end
```

New (admin check first since admins are never hybrid; both checks use array
membership):

```sql
case
    when exists (
        select 1 from unnest(p.role_names) as rn where rn like '%Admin%'
    )
    then 'observers'
    when 'Coach' in unnest(p.role_names)
    then 'observees;observers'
    else 'observees'
end
```

A Teacher+Coach lands on `'observees;observers'` (same as a pure Coach).

### 4. `surrogate_keys` CTE — stable hashing over arrays

`dbt_utils.generate_surrogate_key` stringifies scalar inputs and does not handle
arrays cleanly. Compute deterministic scalar projections in the prior CTE:

```sql
array_to_string(role_ids, ',') as role_ids_hash,
array_to_string(role_ids_ws, ',') as role_ids_ws_hash,
```

Substitute these in the two `generate_surrogate_key` input lists in place of
`role_id` / `role_id_ws`. Because the arrays are alphabetically ordered, the
joined strings are stable across runs and across the source/destination sides
when the role sets match.

`role_ids_hash` / `role_ids_ws_hash` are internal — not selected in the final
`SELECT` and not part of the contract.

### 5. Contract / `properties.yml`

In
`src/dbt/kipptaf/models/extracts/schoolmint/properties/rpt_schoolmint_grow__users.yml`:

- Rename `role_name` → `role_names`, `data_type: array<string>`.
- Rename `role_id` → `role_ids`, `data_type: array<string>`.
- Rename `role_id_ws` → `role_ids_ws`, `data_type: array<string>`.
- Update descriptions to document the array semantics, hybrid rule, and
  alphabetical ordering.
- Add a column-level data test asserting
  `dbt_utils.expression_is_true: array_length(role_ids) >= 1` and
  `array_length(role_ids) = array_length(role_names)`.

### 6. `grow_user_sync` sync changes

In `src/teamster/code_locations/kipptaf/level_data/grow/assets.py`:

- Payload: `payload["roles"] = list(u["role_ids"])` (PyArrow arrays unbox to
  Python lists already; keep `list(...)` defensively to guarantee JSON
  serialization).
- Admin grouping at the `admin_roles` loop: `if role_name == u["role_name"]`
  becomes `if role_name in u["role_names"]`. Admins are never hybrid so this
  still selects exactly the same rows, just via membership instead of equality.
- `observees` / `observers` derivation reads `u["group_type"]` which still
  carries the precomputed string from the dbt model — no change needed in the
  observation-group loop.
- No changes to `school_users` filtering, the restore/create/update/archive
  branch tree, or error handling.

## Testing

- `uv run dbt build --select rpt_schoolmint_grow__users+ --project-dir src/dbt/kipptaf --target staging`
  — verify contract holds and `array_length` test passes.
- Spot-check via BigQuery MCP that known Teacher+Coach staff land on
  `['Coach','Teacher']` and counts of pure-Teacher / pure-Coach / admin rows are
  stable vs. main.
- Dagster sensor / `grow_user_sync` smoke run in branch deployment to confirm
  Grow accepts the multi-element `roles` payload without 4xx. PII stays local —
  do not paste user rows to the PR.

## Rollout

Single PR; squash merge. After merge, the next Dagster materialization of
`rpt_schoolmint_grow__users` rebuilds the extract; the next `grow_user_sync` run
picks up the new array columns and reconciles hybrid users via the update branch
(because `surrogate_key_source != surrogate_key_destination` for any affected
row).

## Risks

- **Surrogate-key churn**: every existing row's source surrogate key changes
  (`role_id` → `array_to_string(role_ids,',')` is a different scalar even for
  pure-Teacher / pure-Coach users). The first post-deploy sync run will update
  every active user via the `update/reactivate` branch. This is expected and
  matches today's update path (idempotent PUT).
- **Grow API rejection**: if Grow rejects a `roles` array containing both
  Teacher and Coach IDs (validation we haven't seen), the error is logged and
  collected in `errors[]` by the existing per-user try/except — no batch
  failure. Mitigated by the branch-deployment smoke run.
- **Empty `role_names`**: any user who matched none of the CASE branches today
  produced NULL `role_name` and was filtered out by the inner join to
  `stg_schoolmint_grow__roles`. The new model filters explicitly on
  `array_length(role_names) >= 1` — same effective behavior.
