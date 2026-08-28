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

| Decision                                                        | Rationale                                                                                                                                                                            |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Key roles on `job_function`, not `job_title`                    | 15 clean values that already encode the org tier. `School Leader`, `Assistant School Leaders` and `Deans` are distinct values, so most substring matching disappears.                |
| Never assign `Sub Admin`                                        | Region scope plus `readonly` covers every case that motivated it. Removing it from circulation is the point of the change.                                                           |
| Network leaders get `Regional Admin` over all 28 schools        | Same role, wider scope. Keeps one code path instead of two, and keeps `Sub Admin` at zero.                                                                                           |
| Pair every admin grant with `readonly`                          | Visibility without configuration power. The pattern already exists on 11 users, hand-maintained.                                                                                     |
| Coach is additive                                               | Fixes the 116. An admin who manages teachers holds both roles.                                                                                                                       |
| Human Resources does not pass the gate                          | The Employee Relations team rarely uses Grow and can get the same information elsewhere. Excluding it also avoids identifying that team by reporting line, which ADP cannot express. |
| No job-title fallback anywhere, including the teacher predicate | A null `job_function` is an ADP data defect. Coding around it hides the defect and preserves the title matching this design exists to remove. Fix the source instead.                |

## Design

### Tier resolution

`job_function` is the tier, and it is the only tier input. A staff member whose
`job_function` is null receives no role at all.

The teacher predicate becomes
`job_function in ('Teacher', 'Teacher in Residence')`, dropping its
`job_title like '%Teacher%' or job_title like '%Learning%'` fallback. This is
the same decision applied consistently.

One adjustment applies on top: a tier of `KTAF or Regional Staff` whose title
contains `Associate Director` is promoted to `KTAF or Regional Director`. ADP
records three Special Education Associate Directors at staff level, which
understates them. This is a deliberate, narrow exception, not a general
fallback.

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
| null or anything else                | —             | none                          | —              |

### Additive roles

Replace the `coalesce` with a single array built from independent predicates.
Each predicate contributes at most one role and none suppresses another:

- the admin role from the matrix, if any
- `Coach`, when the user is an instructional manager
- `Teacher`, when `job_function` is `Teacher` or `Teacher in Residence`

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
explicit parentheses and apply the status filter to both branches. This alone
moves the `Coach` population by a small number.

## Data quality dependency

50 active staff have a null `job_function`: 38 outside Paterson and 12 within
it. The full list, with a suggested `job_function` per row, is exported to
`.claude/scratch/adp-null-job-function.csv` for the ADP system administrator. 17
of the 50 have a job title that suggests no obvious value and need a human
decision.

Because this design adds no fallback, those records cost access until ADP is
corrected:

| Who                                                                | Effect                                                                     |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| 18 teachers with a null `job_function`                             | lose the `Teacher` role and drop out of the extract                        |
| 1 School Leadership manager                                        | loses `Coach`, because every teacher they manage has a null `job_function` |
| Keyna McClinek, Achievement Director, Teaching and Learning, Miami | loses `Sub Admin`, receives nothing                                        |
| Joezer Antoine and Sharon Rojas, Assistant School Leaders          | lose `School Assistant Admin`, keep `Coach`                                |
| Quayon Boone, Assistant Dean, Student Support, Newark              | does not gain `School Assistant Admin`                                     |

### Sequencing constraint

Dropping out of the extract is not the same as losing access. There is no revoke
path yet, so a user the extract stops emitting is simply never sent to Grow
again — their existing Grow account persists untouched. The practical effect on
day one is that these people stop being maintained, not that they are locked
out.

**Sub-project 3 changes that.** Once the revoke path lands, anyone the extract
does not emit has their roles stripped. The ADP correction must therefore land
before sub-project 3 ships, or 18 teachers lose Grow access.

## Output contract

`role_names` gains `Regional Admin` as a common value and loses `Sub Admin`
entirely. No column is added or removed in this sub-project — the region school
list arrives in sub-project 2.

Both existing model-level tests still apply and must keep passing:

- `array_length(role_ids) >= 1`
- `array_length(role_ids) = array_length(role_names)`

Add one more: no row emits the `Sub Admin` role id.

## Blast radius

Measured against the current production extract and roster, with no job-title
fallback anywhere and the precedence bug fixed.

| Change                                                   | Count     |
| -------------------------------------------------------- | --------- |
| `Sub Admin` to `Regional Admin`, region scope            | 41        |
| `Sub Admin` to `Regional Admin`, all 28 schools          | 5         |
| `Sub Admin` to nothing, drops out of the extract         | 16        |
| Teachers dropping out on a null `job_function`           | 18        |
| Admins regaining `Coach`                                 | about 115 |
| New to Grow                                              | 28        |
| Losing `School Assistant Admin` with no replacement      | 6         |
| Promoted from `School Assistant Admin` to `School Admin` | 2         |

The 16 losing `Sub Admin` outright are the Executive Assistant, all 14 Human
Resources staff, and Keyna McClinek. The 28 who gain are 16 Assistant Deans in
Student Support, 10 regional leaders and 2 network leaders.

`Sub Admin` totals 62 today and reaches zero: 41 plus 5 plus 16.

## Testing

1. dbt unit tests on the role expression, one case per tier, plus a null
   `job_function` case asserting no role at all and an Associate Director case
   asserting promotion.
1. A unit test asserting an instructional manager holding an admin role emits
   both roles, which is the 116-person regression.
1. A unit test on the corrected instructional-manager predicate, asserting a
   manager whose only teacher reports are terminated does not qualify.
1. `uv run dbt build --select rpt_schoolmint_grow__users+` in the worktree.
1. Compare the built model against production for the blast-radius counts above
   before merging.

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
  and 5 terminated accounts. Gated on the ADP correction above.
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
