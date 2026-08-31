# Grow region-scoped admin access

Design for all four sub-projects, shipping together in one pull request: role
assignment correctness, region scope delivery, the revoke path, and observation
groups plus school coverage.
[#5054](https://github.com/TEAMSchools/teamster/issues/5054) tracks the fourth.

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

The Role column names only the role this sub-project assigns. `readonly` is a
separate boolean field on the Grow User object, not a role — sub-project 2
writes it (see _Sub-project 2: region scope delivery_ below).

| Tier                                 | Gate required | Role                     | Scope          |
| ------------------------------------ | ------------- | ------------------------ | -------------- |
| `Chief Level`                        | yes           | `Regional Admin`         | all 28 schools |
| `EDs, HOSs, MDOs`                    | yes           | `Regional Admin`         | home region    |
| `KTAF or Regional Managing Director` | yes           | `Regional Admin`         | home region    |
| `KTAF or Regional Director`          | yes           | `Regional Admin`         | home region    |
| `School Leader`                      | no            | `School Admin`           | home school    |
| `Assistant School Leaders`           | no            | `School Assistant Admin` | home school    |
| `Deans`                              | no            | `School Assistant Admin` | home school    |
| `Teacher`, `Teacher in Residence`    | no            | `Teacher`                | home school    |
| null or anything else                | —             | none                     | —              |

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

Dropping out of the extract does not affect the user record the same way it
affects observation-group membership, and the two must not be conflated.

The `grow_user_sync` user PUT **merges** — a field the payload omits is left
alone (see _Verified by spike_ below). A user the extract stops emitting is
simply never sent a user PUT again, so their `roles` and other user-level fields
persist untouched. For roles alone, dropping out of the extract really is inert
on day one.

Observation-group membership is different, and it ships with sub-project 1, not
sub-project 3. In
`src/teamster/code_locations/kipptaf/level_data/grow/assets.py`, the school PUT
rebuilds `observationGroups.observees`, `observationGroups.observers`, `admins`,
and `assistantAdmins` from `school_users`, which is filtered from the same
extract. That payload is complete, not incremental, and it is sent for every
school on every run. A user absent from the extract is therefore REMOVED from
all four lists the first time the sync runs after they drop out — not
eventually, and not only once a revoke path ships.

**Consequence: the 18 teachers with a null `job_function`** (see _Data quality
dependency_ above) lose their spot in the Teachers observation group immediately
on the first sync after this change ships, even though their Grow user roles
remain untouched. **The ADP correction must therefore land before this change
ships**, not before sub-project 3 as previously stated — waiting until
sub-project 3 leaves those 18 teachers unobservable in the interim.

Sub-project 3 still matters for the user record: once its revoke path lands,
anyone the extract does not emit also has their `roles` stripped, closing the
gap this section describes for the user-level side.

### Why sub-projects 1 and 2 cannot ship separately

Sub-project 2 is what writes `regionalAdminSchools`. A user newly granted
`Regional Admin` by sub-project 1 has only whatever scope was already set on
their account by hand — sub-project 1 grants the role, not the scope.

Verified against the live Grow snapshot: of the 46 users converting from
`Sub Admin` to `Regional Admin` (see _Blast radius_ below), 32 have an EMPTY
`regionalAdminSchools` and would hold the role over zero schools if sub-project
1 shipped alone. The remaining 14 retain an existing manually-set scope and
would be unaffected. That 32/14 split is why the two sub-projects cannot ship
separately: shipping them together in the same pull request is what makes the
split moot, since sub-project 2's `regionalAdminSchools` column lands alongside
the role grant rather than after it.

## Output contract

`role_names` gains `Regional Admin` as a common value and loses `Sub Admin`
entirely. Sub-project 2 adds two columns:

- `regional_admin_school_ids` — `array<string>`, the Grow school ids the user
  should be scoped to
- `readonly` — `bool`, true when the user holds `Regional Admin`

The model-level test `array_length(role_ids) >= 1` is removed by sub-project 3,
because a no-role user is now emitted deliberately. The other two tests still
apply and must keep passing:

- `array_length(role_ids) = array_length(role_names)`
- no row emits the `Sub Admin` role id

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
| Coach-only users losing observee status                  | 6         |

The 16 losing `Sub Admin` outright are the Executive Assistant, all 14 Human
Resources staff, and Keyna McClinek. The 28 who gain are 16 Assistant Deans in
Student Support, 10 regional leaders and 2 network leaders.

`Sub Admin` totals 62 today and reaches zero: 41 plus 5 plus 16.

The 6 coach-only users hold `Coach` with no `Teacher` and no admin role. Today
they resolve to `observees;observers`, because the current first-match CASE
treats any `Coach` as sufficient for both memberships. Under the additive
`group_type` (see _Observation group membership_ below), `observers` still
follows from `Coach`, but `observees` now requires `Teacher`, `School Admin`, or
`School Assistant Admin` — none of which these 6 hold. They move to `observers`
alone and stop being observable by their own manager. This is spec-compliant,
not a regression, and was previously unenumerated.

The table above omits several access changes this design also produces, measured
against the current production extract and roster:

- 18 active `School-based Non-Instructional Staff` hold `Teacher` today and lose
  it, so they stop being observable.
- About 18 more, spread across `School-based Non-Instructional Staff`, `DSOs`,
  `KTAF or Regional Staff`, and `EDs, HOSs, MDOs`, hold `Coach` today and lose
  it.
- Of the 545 no-role rows the revoke path (sub-project 3) emits, most hold a
  Grow role literally named `No Role` today, so the substantive revoke — a user
  losing a role that actually granted them something — is roughly 335 accounts,
  not 545.
- 61 users hold a non-empty `regionalAdminSchools` today but are not
  `Regional Admin` under the new rules, so their scope is emptied entirely; one
  of them currently holds 23 schools.
- About 7 genuine Regional Admins have their scope NARROWED rather than emptied:
  24 schools down to 13, 20 down to 13, 20 down to 8, 20 down to 6, and 18 down
  to 13.

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

## Sub-project 2: region scope delivery

Two new columns on the extract.

`regional_admin_school_ids` is an `array<string>` of Grow school ids:

- a user whose tier is `Chief Level` and whose department passes the gate gets
  every active Grow school
- a user on any other `Regional Admin` tier gets the active Grow schools whose
  region matches their own `home_work_location_dagster_code_location`
- everyone else gets an empty array

`readonly` is a `bool`, true when the user holds `Regional Admin` and false
otherwise. School Admin and School Assistant Admin are deliberately NOT readonly
— they run observations and need write access. Only the network and regional
tiers get visibility without configuration power, which is the requirement this
whole design started from.

### Where school region comes from

Grow's own school `region` field is null or empty on all 28 schools, so it
cannot be used. The source is `int_people__location_crosswalk`, joined to
`stg_schoolmint_grow__schools` on `location_name = name`. That resolves 27 of
the 28 active schools, including `Poinciana Campus`, which a roster-derived
mapping misses because the roster calls it `KIPP Miami - Poinciana Campus`.

`[Training School]` has no region. It is excluded from every region list and
included only in the `Chief Level` all-schools list.

Campus and office entries — `Room 9`, `Room 10`, `Room 11`, `Poinciana Campus`,
`KIPP Miami - North Campus` — ARE included in region lists. `Room 9` alone
carries 59 observers and 13 observees, so excluding them would sever live
coaching relationships.

### Sync change

`grow_user_sync` adds two fields to the user payload: `regionalAdminSchools`,
from `regional_admin_school_ids`, and `readonly`.

Both must also join the surrogate keys, on both sides. Without that the sync
never detects that someone's scope drifted and never corrects a hand-edited one.
`stg_schoolmint_grow__users` therefore has to start selecting
`regionalAdminSchools` and `readonly`, which it does not today.

## Sub-project 3: the revoke path

Today a user who matches no role predicate produces an empty role array and is
dropped at the `people_roles` inner join. The sync never sees them, so it never
removes anything. 21 people hold admin roles the extract does not manage, 5 of
them terminated.

The change is small: `people_roles` becomes a LEFT join, so a no-role user
survives with empty `role_names` and `role_ids`, and the model's final `WHERE`
keeps them. The sync then sends `roles: []` for that user, stripping their
roles. Archival stays driven by `inactive` exactly as it is now.

The model-level test `array_length(role_ids) >= 1` is removed, because an empty
array is now a legitimate, deliberate output rather than a defect.

### What this does not fix

Three of the 21 have no roster record at all, so the extract cannot emit them
and cannot revoke them. They stay a manual cleanup.

### Sequencing

This sub-project is why the ADP `job_function` correction is urgent rather than
merely advisable. Once roles can be stripped, the 18 teachers with a null
`job_function` lose their Grow roles as well as their observation-group
membership.

## Sub-project 4: observation groups and school coverage

Tracked in [#5054](https://github.com/TEAMSchools/teamster/issues/5054).

### Why a coach-teacher can see their peers

Every school has exactly one observation group, named `Teachers`, holding every
teacher as an observee and every coach and admin as an observer. Membership is a
flat pool, so every observer sees every observee. A coach who is also a teacher
therefore sees peers they do not coach.

### The group model

Verified by API probe against `[Training School]`: a PUT to
`/external/schools/{id}` carrying an `observationGroups` entry with a `name` and
no `_id` creates that group and assigns it a real `_id`. The same probe
confirmed the school PUT REPLACES the array rather than merging it.

Each school keeps its `Teachers` group, matched by name so its existing `_id` is
reused and nothing recorded against it is orphaned. Its membership changes:
observees become only those teachers who have no `coach_id`, and observers
become the school's admins. As measured on 2026-08-31, all 738 observees have a
`coach_id`, so `Teachers` is empty in practice as of that date. This is a
measurement, not a guarantee, and it moves as coaches are demoted: Fix 3 (the
`_can_anchor_group` guard in `assets.py`) exists precisely because a coach who
loses their observer role, goes inactive, or becomes readonly can no longer
anchor a group, which pushes their reports back into `Teachers` and can drop the
figure below 738. Re-measure before relying on it.

Alongside it, one group per coach at that school. Each holds that coach as the
sole observer and only their own reports as observees. Peers stop seeing each
other because no group ever contains two teachers who share no coaching
relationship.

### Group naming is load-bearing

Because the PUT replaces the array and assigns ids to new entries, sending
groups without an `_id` on every run would recreate them daily with fresh ids,
churning group identity and orphaning history. The sync must GET the existing
groups, match each one, reuse its `_id`, and omit `_id` only for a genuinely new
group.

Name is the only stable key available, so it must be deterministic and survive a
person being renamed. Coach group names take the form
`{display name} ({employee_number})`. Matching is not parsed back out of the
string — the sync passes an explicit `match_key` alongside each wanted name, and
for a coach group that key is the parenthesised employee number,
`({employee_number})`. The opening paren is load-bearing: without it, employee
`1675` would match a group belonging to employee `101675`, since `"...101675)"`
ends with `"1675)"`. A group with no `match_key`, such as `Teachers`, gets no
fallback match, so a hand-made group can never be claimed by accident. A
display-name change therefore rewrites the label without breaking the match.

### School coverage fixes

Three defects in the same school PUT, fixed together because they all live in
it.

An earlier draft of this spec claimed that staff whose home work location is a
placeholder such as `Room 9`, `Room 10` or `Room 11` land in no observation
group at all. That is false, and no fix is needed. Those Rooms are themselves
Grow schools, so staff based there join the Room's own group: `Room 9` currently
holds 13 observees and 59 observers, `Room 10` holds 1 and 15, and `Room 11`
holds 0 and 20.

`Room 11` holding no observees is correct rather than broken — everyone based
there is regional staff carrying an admin or coach role, so none of them is an
observee. A regional leader based in a Room still reaches the schools where
their reports sit, because the `coaches` union in the school PUT follows the
reporting line rather than the home school. Deanna Applewhaite, based in
`Room 11`, reaches `KIPP Miami - North Campus` and `KIPP Royalty Academy` that
way.

Four staff had a home work location whose reporting name was
`KIPP Miami - Poinciana Campus`, while the Grow school was named
`Poinciana Campus`. The `roster` CTE joins `stg_schoolmint_grow__schools` on
`home_work_location_reporting_name` alone, by exact string equality, so those
four were dropped.

This was fixed in data, not code: the Grow school was renamed to
`KIPP Miami - Poinciana Campus`, and a matching alias row was added to the
location crosswalk sheet. The either-name join once proposed here (accepting
both `home_work_location_reporting_name` and `home_work_location_name` via an
`in (...)` predicate) was never implemented — the existing exact-name join
already resolves all four staff now that the names agree, and measured against
the current roster, zero active non-Paterson staff fail it.

The durable protection against this class of drift recurring — a school renamed
in the Grow UI without a matching roster/crosswalk update — is the new test
`rpt_schoolmint_grow__users__locations_resolve_to_grow_school`
(`src/dbt/kipptaf/tests/`), which fails loudly on any active, non-Paterson staff
location that no longer resolves to a Grow school by exact name.

The existing test `int_people__staff_roster__locations_resolve_to_crosswalk`
does not catch this, because it checks `home_work_location_name` while this
model joins on `home_work_location_reporting_name`.

`school_users` is filtered to one `school_id` per user, so a School Admin or
School Assistant Admin covering two campuses is written to only one. The
`coaches` union already walks the reporting line to reach other schools;
`admins` and `assistantAdmins` get the same treatment.

## Observation group membership

`group_type` becomes additive alongside the roles. Today it is a first-match
CASE, so any admin resolves to `observers` and is therefore never an observee —
nobody can observe a School Leader, an Assistant School Leader or a Dean.

The two memberships are now independent predicates:

- `observers` when the user holds any admin role or `Coach`
- `observees` when the user holds `Teacher`, `School Admin` or
  `School Assistant Admin`
- `Regional Admin` alone does not make someone an observee

School leadership therefore becomes observable by their manager, which is a
deliberate change from current behaviour.

The emitted string keeps its existing shape, `observees`, `observers` or
`observees;observers`, because `grow_user_sync` tests it with `in`. A user who
satisfies neither predicate emits an empty string and contributes to no group.
