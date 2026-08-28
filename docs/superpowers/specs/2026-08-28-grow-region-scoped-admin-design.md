# Grow region-scoped admin access

Design for sub-project 1 of four: **role assignment correctness**.

Refs [#5052](https://github.com/TEAMSchools/teamster/issues/5052).

## Context

`rpt_schoolmint_grow__users` decides which Grow roles every staff member holds.
`grow_user_sync` sends that decision to the Grow API each morning at about 07:05
UTC.

Grow runs as a single district, `5ba2643ecd5f35424ee05d1e`, covering all 28
active schools across Newark, Camden and Miami. Paterson is excluded from the
extract. `Sub Admin` is a district-level role, so every Sub Admin sees every
school.

## Problem

Three defects, all rooted in the same CASE expression.

### Region is not an input

The extract has no region column. `Regional Admin` is produced by exactly one
rule, `job_title = 'Head of Schools'`, which matches 3 people. Everyone else who
leads a single region receives network-wide `Sub Admin` instead. 75 people hold
`Sub Admin` today.

Grow's school-level `region` field is null or empty on all 28 schools and
nothing reads it. Per-user scope lives in `User.regionalAdminSchools`, an array
of school refs that the sync has never written.

### Job titles are the wrong key

The rule matches on `job_title` substrings.
`home_department_name = 'Human Resources'` grants network-wide access at any
title, including 5 Specialists and 1 Specialist Temporary.
`contains_substr(job_title, 'Leader')` matches "School Leader" and fires before
the School Leader branch, so a School Support title containing "Leader" would
silently receive network-wide access.

### An admin role replaces Coach instead of adding to it

The role expression is:

```sql
coalesce(
    case /* admin branches */ end,
    array( /* Coach and Teacher */ )
)
```

`coalesce` returns the admin array whenever any admin branch matches, so the
Coach and Teacher array is never evaluated. 116 people who manage teachers hold
an admin role and therefore lost `Coach`. Each also resolves to
`group_type = 'observers'`, so none of them can be observed by their own
manager.

Teacher plus Coach was fixed in `ea8a93640` because both roles live inside the
array branch. Admin plus Coach was not.

## Decisions

| Decision                                                 | Rationale                                                                                                                                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Key roles on `job_function`, not `job_title`             | 15 clean values that already encode the org tier. `School Leader`, `Assistant School Leaders` and `Deans` are distinct values, so most substring matching disappears.                |
| Never assign `Sub Admin`                                 | Region scope plus `readonly` covers every case that motivated it. Removing it from circulation is the point of the change.                                                           |
| Network leaders get `Regional Admin` over all 28 schools | Same role, wider scope. Keeps one code path instead of two, and keeps `Sub Admin` at zero.                                                                                           |
| Pair every admin grant with `readonly`                   | Visibility without configuration power. The pattern already exists on 11 users, hand-maintained.                                                                                     |
| Coach is additive                                        | Fixes the 116. An admin who manages teachers holds both roles.                                                                                                                       |
| Human Resources does not pass the gate                   | The Employee Relations team rarely uses Grow and can get the same information elsewhere. Excluding it also avoids identifying that team by reporting line, which ADP cannot express. |

## Design

### Tier resolution

`job_function` is the tier. 38 active staff have a null `job_function`, so the
admin tiers need a job-title fallback mirroring the one the teacher predicate
already carries:

```sql
coalesce(
    job_function,
    case
        when contains_substr(job_title, 'Chief') then 'Chief Level'
        when contains_substr(job_title, 'Managing Director')
        then 'KTAF or Regional Managing Director'
        when contains_substr(job_title, 'Director') then 'KTAF or Regional Director'
        when job_title = 'School Leader' then 'School Leader'
        when contains_substr(job_title, 'Assistant School Leader')
        then 'Assistant School Leaders'
        when contains_substr(job_title, 'Dean') then 'Deans'
    end
)
```

Order matters. `Managing Director` is tested before `Director`, and
`Assistant School Leader` before `Dean`, so the more specific pattern wins.

One promotion applies afterwards: a tier of `KTAF or Regional Staff` whose title
contains `Associate Director` is promoted to `KTAF or Regional Director`. ADP
records three Special Education Associate Directors at staff level, which
understates them.

### Department gate

Director tier and above additionally require a passing department:

- Teaching and Learning
- School Support
- Teacher Development
- New Teacher Development
- Special Education
- School Leadership
- Leadership Development
- KIPP Forward
- Special Projects
- Executive

Talent Acquisition, Human Resources, Student Support, Operations, Finance,
Technology and the rest do not pass. School-level tiers (`School Leader`,
`Assistant School Leaders`, `Deans`, `Teacher`) do not consult the gate — the
tier alone is sufficient, which is what lets Assistant Deans in Student Support
qualify.

### Role matrix

| Tier                                 | Gate required | Role                          | Scope          |
| ------------------------------------ | ------------- | ----------------------------- | -------------- |
| `Chief Level`                        | yes           | `Regional Admin` + `readonly` | all 28 schools |
| `EDs, HOSs, MDOs`                    | yes           | `Regional Admin` + `readonly` | home region    |
| `KTAF or Regional Managing Director` | yes           | `Regional Admin` + `readonly` | home region    |
| `KTAF or Regional Director`          | yes           | `Regional Admin` + `readonly` | home region    |
| `School Leader`                      | no            | `School Admin`                | home school    |
| `Assistant School Leaders`           | no            | `School Assistant Admin`      | home school    |
| `Deans`                              | no            | `School Assistant Admin`      | home school    |
| `Teacher`, `Teacher in Residence`    | no            | `Teacher`                     | home school    |
| anything else                        | —             | none                          | —              |

### Additive roles

Replace the `coalesce` with a single array built from independent predicates.
Each predicate contributes at most one role and none suppresses another:

- the admin role from the matrix, if any
- `Coach`, when the user is an instructional manager
- `Teacher`, when the user satisfies the teacher predicate

A user with no contributing predicate emits an empty array. That case is dropped
at the `people_roles` inner join today; closing that hole is sub-project 3, not
this one.

### The instructional-manager predicate

The existing CTE carries an operator precedence bug:

```sql
where
    sr.assignment_status in ('Active', 'Leave')
    and sr.is_teacher
    or srm.home_department_name in ('School Support', 'Student Support', 'KIPP Forward')
```

`A and B or C` parses as `(A and B) or C`, so the second branch applies no
assignment-status filter and a manager qualifies on terminated reports. Add
explicit parentheses and apply the status filter to both branches.

## Output contract

`role_names` gains `Regional Admin` as a common value and loses `Sub Admin`
entirely. No column is added or removed in this sub-project — the region school
list arrives in sub-project 2.

Both existing model-level tests still apply and must keep passing:

- `array_length(role_ids) >= 1`
- `array_length(role_ids) = array_length(role_names)`

Add one more: no row emits the `Sub Admin` role id.

## Blast radius

Measured against the current production extract and roster.

| Change                                          | Count     |
| ----------------------------------------------- | --------- |
| `Sub Admin` to `Regional Admin`, region scope   | 42        |
| `Sub Admin` to `Regional Admin`, all 28 schools | 5         |
| `Sub Admin` to no access                        | 15        |
| Admins regaining `Coach`                        | about 113 |
| New to Grow                                     | 30        |
| Losing `School Assistant Admin`                 | 4         |

The 15 who lose access are the Executive Assistant and all 14 Human Resources
staff. The 30 who gain are 17 Assistant Deans in Student Support, 11 regional
leaders and 2 network leaders. The 4 who lose `School Assistant Admin` matched
the old title substring but sit outside the `Deans` and
`Assistant School Leaders` tiers.

## Testing

1. dbt unit tests on the role expression, one case per tier, plus a null
   `job_function` case and an Associate Director case.
1. A unit test asserting an instructional manager holding an admin role emits
   both roles, which is the 116-person regression.
1. `uv run dbt build --select rpt_schoolmint_grow__users+` in the worktree.
1. Compare the built model against production for the six blast-radius counts
   above before merging.

## Verified by spike

The Grow user PUT **merges**. Run `0845b6df-59eb-4e60-b02a-1ed77a0ffefe` on
2026-07-31 issued a PUT for `jlee@` at `...569505` and `rray@` at `...578709`.
Their Grow `lastModified` values are `...569757` and `...578966`, roughly 250 ms
later, and both users still hold `readonly: true` and a populated
`regionalAdminSchools`. Neither field appears in the payload.

Sub-project 2 can therefore write `regionalAdminSchools` and `readonly`
additively without disturbing anything the payload omits.

## Out of scope

- **Sub-project 2** — write `regionalAdminSchools` and `readonly` from the sync.
- **Sub-project 3** — the revoke path, and reconciling the 21 unmanaged admins
  and 5 terminated accounts.
- **Sub-project 4** — placeholder locations such as `Room 11`, the
  `KIPP Miami - Poinciana Campus` name mismatch, multi-school leaders, and
  per-coach observation groups.

## Open question

`group_type` must become additive alongside the roles, but who may be _observed_
is a policy call this design does not settle.

Today any admin resolves to `observers` and is therefore never an observee, so
nobody can observe a School Leader, an Assistant School Leader or a Dean.
Proposed default:

- `observers` when the user holds any admin role or `Coach`
- `observees` when the user is a `Teacher`, or holds `School Admin` or
  `School Assistant Admin`
- `Regional Admin` alone does not make someone an observee

This would newly allow school leadership to be observed by their manager.
Confirm before implementation.
