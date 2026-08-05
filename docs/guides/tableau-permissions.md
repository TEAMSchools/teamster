# Tableau Permissions

How row-level security works on our Tableau workbooks — who can see whose data,
and how it is implemented.

This page has two halves. **Part 1** is for anyone who wants to understand or
question what they can see, and needs no Tableau knowledge. **Part 2** is the
implementation reference for whoever is building or editing a gated workbook.

**Status: live.** Eleven workbooks were remediated during the Entra ID identity
migration and carry the model described here. The entity gate is region-scoped
in all eleven, so the central-office leak described in Part 2 is closed.

---

## Part 1 — Who can see what

### The short version

Access is decided **per row**, not per dashboard. Opening a workbook does not
show you everything in it; it shows you the rows you are entitled to. Two people
looking at the same dashboard routinely see different numbers, and that is
working as intended.

Entitlement comes from **which Tableau groups you belong to**, not from your job
title or your position in the org chart. This is deliberate — it means access
can be granted or removed by changing a group, with no change to any workbook.

### The five ways you can be shown a row

You see a row if **any one** of these is true. They are additive.

|     | Route                    | You see                                                                                        |
| --- | ------------------------ | ---------------------------------------------------------------------------------------------- |
| 1   | **You, or your manager** | Your own row. Your direct reports' rows.                                                       |
| 2   | **A network-wide group** | Everything, for a small number of functional groups such as the data team and HR.              |
| 3   | **Regional operations**  | Your region's rows, if you are in a regional ops group.                                        |
| 4   | **Regional leadership**  | Your region's rows, if you are a regional leader.                                              |
| 5   | **Your school**          | Your school's rows, if you are in that school's staff group _and_ hold a role that permits it. |

Route 5 needs all three of the right entity, the right school, and a qualifying
role. Missing any one of them means no access by that route.

### What central office can and cannot see

Central office (KTAF) staff have **oversight of the regions, not of each
other**.

Being in the central office group grants visibility into TEAM, KIPP Cooper
Norcross, KIPP Miami, and KIPP Paterson rows. It does **not** grant visibility
into other central office rows. Those are reachable only by being the person
themselves, being their direct manager, or belonging to one of the network-wide
groups in route 2.

!!! note "A known consequence"

    A central office director does not see their reports' reports. Route 1 covers
    only the _direct_ manager. This is accepted rather than accidental — see
    _The KTAF branch is scoped to the regions_ in Part 2.

### Senior leaders are shielded further

On the workbooks that carry performance and development data, rows belonging to
senior leaders are restricted to that person, their manager, and the
network-wide groups. Peers at the same level do not see each other, including
peers who otherwise have broad access.

Seniority is read from the ADP job function rather than from job title text, so
a newly created senior title is covered automatically without anyone editing a
workbook.

### The Intent to Return survey is different

Your answers to the Intent to Return survey are visible to **you**, to **the
person who managed you when you answered**, and to the HR, Recruiting, and
Leadership Development teams. Nobody else — not colleagues, not other leaders at
your school, not people who report to you.

This survey deliberately does not follow the five routes above. Everywhere else
access follows group membership and site. Here it follows the reporting
relationship and nothing else, because the answers are only worth collecting if
people can give them honestly.

A manager who changes roles does not keep access to your older answers, and a
new manager does not gain access to answers you gave before they managed you.

### Rooms do not grant access

Working in a Room — the office locations rather than a school — does not grant
visibility of that Room's occupants. Room-based staff reach data through the
network-wide and regional-leadership routes instead.

This matters because Rooms are shared: Room 9 has occupants from more than one
entity, so treating a Room like a school would hand people access across entity
lines.

### Why you might see less than a colleague

In rough order of likelihood:

1. They are in a group you are not in. Group membership is the whole mechanism.
1. They are the person's manager and you are not.
1. The row belongs to a senior leader, and neither of you should see it — but
   they are in a network-wide group.
1. The row belongs to central office, and central office rows are not visible to
   other central office staff.

### How to get access

**Ask to be added to the relevant Tableau group.** Do not ask for a workbook
change. Every route above is driven by group membership, so a group change is
immediate, auditable, applies consistently across all workbooks, and is
reversible. A workbook edit is none of those things.

Individual, by-name grants inside a workbook are **not permitted**. They existed
historically, were invisible to anyone not reading the calculation, and were all
removed during the Entra ID migration.

---

## Part 2 — Implementation reference

Everything below is for whoever edits a gated workbook.

### Field structure

Five calculated fields. Four are needed in every gated workbook; the fifth is
needed only where senior leaders are shielded.

| Field                            | Purpose                                                              |
| -------------------------------- | -------------------------------------------------------------------- |
| `RLS - Entity Gate`              | Is the viewer in the staff group for this row's entity?              |
| `RLS - Location Gate`            | Is the viewer in the staff group for this row's location?            |
| `RLS - Role Gate`                | Does the viewer hold a role that may see school-based rows?          |
| `RLS - Subject Is Senior Leader` | Should this row be shielded from peers?                              |
| `Permissions`                    | The five tiers. **This is the field that goes on the filter shelf.** |

**Build them in that order.** It is also the dependency order — `Permissions`
references the four helpers, so it cannot validate until they exist.

1. Create `RLS - Entity Gate`, `RLS - Location Gate`, and `RLS - Role Gate` from
   the sections below. Nothing depends on the order among these three.
1. On the three senior-leader workbooks only, create
   `RLS - Subject Is Senior Leader`. Skip it everywhere else.
1. Create `Permissions`, applying any variant listed for this workbook in
   _Per-workbook variants_.
1. Put `Permissions` on the filter shelf set to `TRUE` and apply it to all
   sheets using that data source. **Only `Permissions` goes on the shelf** — the
   other four are helpers and belong on no shelf.
1. Work through _After editing a workbook_ before moving to the next one.

Copy the fields between workbooks via the Data pane — right-click a field,
**Copy**, then paste into the next workbook's Data pane. Every gated extract
exposes identical column names, so a pasted field resolves with no edits. After
the first workbook, steps 1 and 2 become paste operations rather than typing.

Reasons for the split rather than one large calculation:

- The entity gate is needed by both Tier 4 and Tier 5. As one field it is
  written once, instead of duplicated where the copies can drift apart.
- Per-workbook variants become one-line edits to a small field rather than
  surgery inside a sixty-line calculation.
- Each gate can be dropped on a sheet by itself and compared against a row,
  which is how you debug a persona seeing the wrong thing.

### Field 1 of 5 — `RLS - Entity Gate`

```text
IF     ISMEMBEROF('KNJ-SG-Tableau All Staff TEAM Schools') AND [home_business_unit_name] = 'TEAM Academy Charter School'  THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KCNA')         AND [home_business_unit_name] = 'KIPP Cooper Norcross Academy' THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff MIA')          AND [home_business_unit_name] = 'KIPP Miami'                   THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff Paterson')     AND [home_business_unit_name] = 'KIPP Paterson'                THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KTAF')
       AND [home_business_unit_name] IN (
           'TEAM Academy Charter School',
           'KIPP Cooper Norcross Academy',
           'KIPP Miami',
           'KIPP Paterson'
       )                                                                                                                  THEN TRUE
ELSE FALSE
END
```

This reads **group membership**, never the viewer's own entity. That is
load-bearing: it is how cross-entity supervision works. Someone employed by TEAM
who oversees Paterson schools gets Paterson visibility by being added to the
Paterson group, with no calculation change.

!!! danger "Do not derive entity from the viewer's own roster row"

    It looks like a simplification. It would silently revoke access from every
    cross-entity supervisor, and silent revocation is the failure mode this design
    exists to prevent.

Single equality per branch. Entity values are normalized upstream in dbt, so no
extract emits the historical abbreviations `TEAM`, `KCNA`, `MIA`, or `KNJ`. Do
not re-add the old triple comparisons — an abbreviation branch can never match,
and its presence implies the extracts still carry abbreviations.

#### The KTAF branch is scoped to the regions

Central office oversees the regions; it does not get visibility into itself. The
four-region list encodes that.

This branch was previously unconditional —
`ELSEIF ISMEMBEROF('…KTAF') THEN TRUE` — returning TRUE on every row regardless
of entity, including other central office rows. That caused a real leak, found
while testing Manager Survey Rollup: two senior leaders at the same level, both
central office, both reporting to the same manager, could see each other.

The path was not the tier anyone would suspect:

1. Tier 1 correctly failed — neither was the other's manager.
1. The Tier 2 senior-leader shield correctly returned FALSE.
1. **Tier 4 granted it.** The viewer was in an operations group, and the
   unconditional KTAF branch made the entity gate TRUE on the other leader's
   row, so `(ops group) AND [Entity Gate]` passed and the shield never got a
   say.

What made it hard to spot: central office staff sit in Rooms, Rooms are absent
from the location gate by design, so **Tier 5 can never fire for them and Tier 4
is their only route**. That turns membership of any regional-leadership group
into whole-extract access.

A positive four-region list rather than
`!= 'KIPP TEAM and Family Schools Inc.'`: identical behaviour today, since these
extracts carry no null entity, but it is self-documenting and stays fail-closed
if a null ever appears.

Apply it in all gated workbooks. It is a no-op where there are no central office
subjects — the teacher-population extracts carry none — and only takes effect in
the people-oriented workbooks, which is exactly where the concern lives. Keep
one shared entity gate rather than forking it per workbook.

!!! warning "Accepted trade-off"

    Tier 1 covers only the direct manager, so a central office director loses
    skip-level visibility of their own org. The remaining routes for central
    office rows are self, direct manager, and the network-wide groups. If
    skip-level visibility is needed it should get its own explicit mechanism
    rather than falling out of the entity gate as a side effect, which is how the
    leak above arose.

### Field 2 of 5 — `RLS - Location Gate`

One branch per school location, because `ISMEMBEROF()` requires a literal
string. Tableau's
[user functions documentation](https://help.tableau.com/current/pro/desktop/en-us/functions_functions_user.htm)
states the argument "must be a literal string, not a field", so the concatenated
one-liner does not validate:

```text
ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])
```

A parameter cannot substitute. It holds one value for the whole view, so the
calculation evaluates once rather than per row and degenerates to
all-rows-or-none — which any viewer in any one location group could exploit.

The branch form is better regardless: a viewer in three location groups matches
three branches and sees all three schools, which a single expression cannot
express.

```text
(
       ([location_clean_name] = 'KIPP BOLD Academy'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP BOLD Academy'))
    OR ([location_clean_name] = 'KIPP Cooper Norcross High'       AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Cooper Norcross High'))
    OR ([location_clean_name] = 'KIPP Courage Academy'            AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Courage Academy'))
    OR ([location_clean_name] = 'KIPP Hatch Middle'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Hatch Academy'))                 // BRIDGE
    OR ([location_clean_name] = 'KIPP Justice Academy'            AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Justice Academy'))
    OR ([location_clean_name] = 'KIPP Lanning Square Middle'      AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Lanning Square Middle'))
    OR ([location_clean_name] = 'KIPP Lanning Square Primary'     AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Lanning Square Primary'))
    OR ([location_clean_name] = 'KIPP Legacy Elementary'          AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Legacy Elementary'))
    OR ([location_clean_name] = 'KIPP Legacy Middle'              AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Legacy Middle'))
    OR ([location_clean_name] = 'KIPP Life Academy'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Life Academy'))
    OR ([location_clean_name] = 'KIPP Miami - North Campus'       AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Miami - North Campus'))
    OR ([location_clean_name] = 'KIPP Miami - Poinciana Campus'   AND ISMEMBEROF('KNJ-SG-Tableau All Staff Poinciana Campus'))                   // BRIDGE
    OR ([location_clean_name] = 'KIPP Miami Technical High'       AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Miami Technical High'))
    OR ([location_clean_name] = 'KIPP Newark Collegiate Academy'  AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Newark Collegiate Academy'))
    OR ([location_clean_name] = 'KIPP Newark Lab High School'     AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Newark Lab High School'))
    OR ([location_clean_name] = 'KIPP Purpose Academy'            AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Purpose Academy'))
    OR ([location_clean_name] = 'KIPP Rise Academy'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Rise Academy'))
    OR ([location_clean_name] = 'KIPP Royalty Academy'            AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Royalty Academy'))
    OR ([location_clean_name] = 'KIPP SPARK Academy'              AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP SPARK Academy'))
    OR ([location_clean_name] = 'KIPP Seek Academy'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Seek Academy'))
    OR ([location_clean_name] = 'KIPP Sumner Elementary'          AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Sumner Academy'))                // BRIDGE
    OR ([location_clean_name] = 'KIPP TEAM Academy'               AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP TEAM Academy'))
    OR ([location_clean_name] = 'KIPP THRIVE Academy'             AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP THRIVE Academy'))
    OR ([location_clean_name] = 'KIPP Upper Roseville Academy'    AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Upper Roseville Academy'))
    OR ([location_clean_name] = 'Paterson Prep Elementary School' AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Paterson Prep Elementary'))      // BRIDGE
    OR ([location_clean_name] = 'Paterson Prep Middle School'     AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP Paterson Prep Middle'))          // BRIDGE
)
```

Rooms are absent by design — see _Rooms do not grant access_ in Part 1.

#### Group naming and the five bridges

The rule is `KNJ-SG-Tableau All Staff ` plus the exact `location_clean_name`.
Five locations break it, because the group name predates a school rename. Delete
a bridge once its group is renamed to match.

| `location_clean_name`             | Group                                      | Staff |
| --------------------------------- | ------------------------------------------ | ----- |
| `KIPP Hatch Middle`               | `…All Staff KIPP Hatch Academy`            | 33    |
| `KIPP Sumner Elementary`          | `…All Staff KIPP Sumner Academy`           | 48    |
| `Paterson Prep Elementary School` | `…All Staff KIPP Paterson Prep Elementary` | 55    |
| `Paterson Prep Middle School`     | `…All Staff KIPP Paterson Prep Middle`     | 33    |
| `KIPP Miami - Poinciana Campus`   | `…All Staff Poinciana Campus`              | 4     |

!!! warning "A missing group does not error"

    It silently denies. Before editing a workbook, confirm every location group
    exists. The dbt test
    `int_people__staff_roster__tableau_location_set_expected` asserts the data
    side of this invariant, but nothing can assert the Tableau side.

### Field 3 of 5 — `RLS - Role Gate`

```text
ISMEMBEROF('KNJ-SG-Tableau All DSO')
OR ISMEMBEROF('KNJ-SG-Tableau All SL')
OR (
    ISMEMBEROF('KNJ-SG-Tableau All AP')
    AND (
        [job_function] IN ('Teacher', 'Teacher in Residence')
        OR (
            ISNULL([job_function])
            AND (CONTAINS([job_title], 'Teacher') OR [job_title] = 'Learning Specialist')
        )
    )
)
```

The AP branch additionally requires **the row** to be a teacher, so an assistant
principal sees teachers at their school rather than every employee at it.

The `ISNULL([job_function])` fallback mirrors the same pattern in dbt and is
load-bearing rather than defensive: `job_function` is unpopulated on historical
roster rows and on newly created work assignments. Deleting it early silently
drops teachers out of the AP branch. It can be removed once
[#4631](https://github.com/TEAMSchools/teamster/issues/4631) lands, at which
point this becomes `[job_function_code] IN ('TEACH', 'TIR')`.

### Field 4 of 5 — `RLS - Subject Is Senior Leader`

Needed only in the workbooks that shield senior leaders — currently Manager
Survey Reports, Manager Survey Rollup, and Leadership Development.

There is no way to ask Tableau whether **the row's person** belongs to a group;
`ISMEMBEROF()` only ever answers for the current viewer. Subject-side seniority
therefore has to come from the data.

```text
IFNULL([job_function], '') = 'Chief Level'
OR (
    ISNULL([job_function])
    AND (
        CONTAINS(IFNULL([job_title], ''), 'Chief')
        OR CONTAINS(IFNULL([job_title], ''), 'President')
        OR CONTAINS(IFNULL([job_title], ''), 'Executive')
    )
)
```

This replaced matching `job_title` against `Chief` / `President` / `Executive`
directly, which was wrong in both directions: four active staff matched the
pattern without holding a senior job function, including an executive assistant
who was being hidden from the council, and fifteen genuinely senior staff the
pattern missed. Keying on `job_function` means a newly created senior title is
covered automatically, because ADP assigns it the function.

Two aspects of the shape are load-bearing:

- **The `IFNULL` wrappers** force TRUE or FALSE and never NULL, so the `NOT` in
  `Permissions` cannot go three-valued. Without them a null `job_function` makes
  the branch NULL, NULL is not TRUE in a filter, and every row with a null
  function silently disappears from council members' views — over a hundred
  thousand rows in Leadership Development alone.
- **The title fallback fires only when `job_function` is null.** Around 1,200
  rows in Leadership Development and 600 in the manager survey have a null
  function with a senior title. Without the fallback those rows stop being
  shielded.

Known narrowing versus the old title matching, deliberate but worth confirming
against the actual council roster: three deputy-chief staff and one executive
director hold job functions other than `Chief Level`, so they become visible. To
shield them, widen the first line to
`IFNULL([job_function], '') IN ('Chief Level', 'EDs, HOSs, MDOs')`; deputy chief
has no clean field and would still need a title test.

### Field 5 of 5 — `Permissions`

The field that goes on the filter shelf, set to `TRUE`. Five tiers in one `OR`
chain, in the same order in every workbook so they diff by eye.

#### Tier 1 — self and manager

```text
LOWER(USERNAME()) = LOWER([sam_account_name])
OR LOWER(USERNAME()) = LOWER([mail])
OR LOWER(USERNAME()) = LOWER([user_principal_name])
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])
```

The only tier that changes at the Entra ID cutover, and the reason the migration
needed no coordination with IT's switch window: both identity forms match, so it
is correct before and after.

`user_principal_name` is a hedge, not a widening. `mail` is the expected value
of `USERNAME()` after cutover, but Entra sign-in commonly presents UPN, and for
a small number of staff the two values disagree.

#### Tier 2 — network-wide functional groups

The only tier that legitimately differs per workbook. Read the workbook's
existing calculation and preserve its membership; the candidates are `All Data`,
`TC`, `All HR`, `All T&L`, `Recruiting`, `New Teacher Development`, and
`Leadership Development`.

Remove `Syndicate`, and remove **every individual username grant**, with no
exceptions.

On the three workbooks that shield senior leaders, the council grant carries the
exclusion:

```text
OR (ISMEMBEROF('Group Staff TEAM Council') AND NOT [RLS - Subject Is Senior Leader])
```

Note the `NOT`. The helper field answers "should this row be shielded", so the
grant is its negation. Writing the shielded condition here without negating it
grants the council exactly the rows meant to be hidden — the inversion is easy
to miss because both forms read plausibly.

!!! danger "This shield is only sufficient because the entity gate excludes
central-office-on-central-office"

    The two are coupled, and that coupling is what a future edit is most likely to
    break. A shield sitting in one branch of an `OR` chain does nothing about the
    other branches. If the KTAF branch in the entity gate is ever restored to its
    unconditional form, Tier 4 bypasses this shield again.

    If the shield ever needs to hold regardless of the entity gate, it has to wrap
    the whole calculation rather than sit in Tier 2:

    ```text
    IF [RLS - Subject Is Senior Leader] THEN
        <Tier 1, plus any network-wide groups you allow>
    ELSE
        <the full five-tier chain>
    END
    ```

#### Tier 3 — regional ops

```text
OR ([home_business_unit_name] IN ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
    AND ISMEMBEROF('Group Staff NJ Regional'))
OR ([home_business_unit_name] = 'KIPP Miami'
    AND ISMEMBEROF('Group Staff MIA Regional'))
```

#### Tier 4 — regional leaders

```text
OR (
    (
        ISMEMBEROF('KNJ-SG-Tableau All MDSO')
        OR ISMEMBEROF('KNJ-SG-Tableau All HOS')
        OR ISMEMBEROF('KNJ-SG-Tableau All MDO')
        OR ISMEMBEROF('KNJ-SG-Tableau AcOps')
    )
    AND [RLS - Entity Gate]
)
```

On a `Permissions - Norming*` or `Permissions - PulseChecker` field, replace the
whole tier with the ungated form, because cross-region norming is intentional:

```text
OR ISMEMBEROF('KNJ-SG-Tableau All MDSO') OR ISMEMBEROF('KNJ-SG-Tableau All HOS')
OR ISMEMBEROF('KNJ-SG-Tableau All MDO')  OR ISMEMBEROF('KNJ-SG-Tableau AcOps')
OR ISMEMBEROF('KNJ-SG-Tableau All SL')
```

Whichever form is used, keep an inline comment saying which it is and why. An
undocumented difference is what the next reader "corrects".

#### Tier 5 — school-based

```text
OR ([RLS - Entity Gate] AND [RLS - Location Gate] AND [RLS - Role Gate])
```

### The gated workbooks

Eleven workbooks carry the `Permissions` field. All sit in the `Production`
project and all are tagged `entra-ready` on Tableau Server. **That tag is the
inventory** — a gated workbook without it is either unfinished or was built
without following this guide.

Anything blank in the Variant column takes the base form unmodified.

| Workbook                          | Datasource                                                                                                                    | Variant                                                                                                                            |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Manager Survey Reports            | `rpt_tableau__manager_survey_details`                                                                                         | Senior-leader field plus the council branch in Tier 2                                                                              |
| Manager Survey Rollup             | `rpt_tableau__manager_survey_details`                                                                                         | Senior-leader field plus the council branch in Tier 2                                                                              |
| Leadership Development            | `rpt_tableau__leadership_development`                                                                                         | Senior-leader field plus the council branch in Tier 2                                                                              |
| Coaching Conversation Tool        | `rpt_tableau__schoolmint_grow_observation_details`                                                                            | Tier 1 self-branches gated by `RLS - Release Gate`                                                                                 |
| SchoolMint Grow Dashboard         | `rpt_tableau__schoolmint_grow_observation_details`, `rpt_tableau__schoolmint_grow_goals`, `rpt_tableau__teacher_observations` | Tier 4 ungated on the `Permissions - Norming*` fields                                                                              |
| Survey Dashboard                  | `rpt_tableau__survey_responses`, `rpt_tableau__survey_completion`                                                             | Tier 4 ungated on the `Permissions - PulseChecker` field. The Intent to Return sheets do not use the tier model at all — see below |
| Miami Instructional Rubrics       | `rpt_tableau__content_team`                                                                                                   | Role gate adds `OR ISMEMBEROF('TS-DL-NTN Coordinators')`                                                                           |
| Operations Systems                | `rpt_tableau__operations_pm`, `rpt_tableau__operations_ekg`                                                                   | Role gate: delete the AP branch                                                                                                    |
| Stipend and Bonus Dashboard       | `rpt_tableau__stipend_and_bonus_app`                                                                                          | Role gate: delete the AP branch                                                                                                    |
| Personalized Survey Links         | `rpt_tableau__survey_completion`, `rpt_tableau__survey_responses`                                                             | —                                                                                                                                  |
| Federal Grants Timesheet Approval | `rpt_tableau__grants_timesheets`                                                                                              | —                                                                                                                                  |

Datasource names come from the migration runbook, which derived them per
workbook in Desktop. Nothing on Tableau Server links a workbook to its table —
each of these uses an **embedded** extract — so this table is the mapping, and
it has to be maintained by hand when a workbook is repointed.

!!! warning "Two archived workbooks still hold pre-migration calculations"

    `Content Team Dashboard` and `Teacher Goals` appear in the migration runbook
    and were archived rather than remediated. Restoring either from its archived
    version brings back the old calculation — individual username grants
    included — and its field references no longer match the extracts. Re-apply
    this guide before republishing either one.

#### Federal Grants Timesheet Approval — `USERNAME()`, not `USERATTRIBUTE()`

Tier 1 in this workbook used `USERATTRIBUTE()` where every other workbook uses
`USERNAME()`. That was a defect, not a variant, and the migration replaced it
with the standard Tier 1 block.

Worth knowing because the mistake is easy to repeat: `USERATTRIBUTE()` reads an
attribute asserted by a connected app or embedding JWT, not the identity of the
person signed in to Tableau Server. On a workbook opened directly on Server
there is no such assertion to read, so it is not a substitute for `USERNAME()`.

#### Coaching Conversation Tool — the release gate

The only workbook whose Tier 1 differs. An observee must not see their own PM
scores before the observation is locked, or their own PM comments before the
term's lockbox date. Their manager and coach see both throughout.

This is a sixth field, used only here:

```text
IF [observation_type_abbreviation] = 'PMS'
THEN IFNULL([locked], FALSE)
ELSEIF ISNULL([tracking_academic_year])
THEN TRUE
ELSE NOT ISNULL([lockbox_date]) AND TODAY() >= [lockbox_date]
END
```

It attaches to the three self-match branches of Tier 1, never to the
`reports_to_*` branches:

```text
(
    (
        LOWER(USERNAME()) = LOWER([sam_account_name])
        OR LOWER(USERNAME()) = LOWER([mail])
        OR LOWER(USERNAME()) = LOWER([user_principal_name])
    )
    AND [RLS - Release Gate]  // observee waits: PMS for lock, PMC for lockbox date
)
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])
```

Also add a **data source filter** `[is_observed] = 1`. It drops the
completion-tracking scaffold rows, which carry no scores or comments.

Three things about this gate that are deliberate:

- **Tier 1 is a sufficient place to gate here, unlike anywhere else.** The
  extract filters subjects to teachers, and teachers hold no DSO, SL, or AP
  membership, so Tier 1 is their only route to their own row. On a workbook
  whose subjects included school leaders this would leak through Tier 5 — see
  the `!!! danger` under Tier 2.
- **`ISNULL([tracking_academic_year])` is the prior-year test, and it is what
  makes a missing lockbox date fail closed.** Prior-year rows come from the
  model's second `union all` branch, which hardcodes a null `lockbox_date`; a
  current-year row always carries a tracking year. Testing the lockbox date for
  nullness instead would release a current-year term the moment someone forgot
  to set its date.
- **`IFNULL([locked], FALSE)` fails closed** on the small number of PMS rows
  where `locked` is null.

### Survey Dashboard — Intent to Return is relationship-gated

The Intent to Return sheets do not use the five-tier model. They use this
instead, and nothing else:

```text
// Permissions - ITR
// Intent to Return: self, direct manager, and three named all-access groups.
// No entity, location, or role tier. See below for why.
LOWER(USERNAME()) = LOWER([sam_account_name])
OR LOWER(USERNAME()) = LOWER([mail])
OR LOWER(USERNAME()) = LOWER([user_principal_name])
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])
OR ISMEMBEROF('KNJ-SG-Tableau All HR')
OR ISMEMBEROF('KNJ-SG-Tableau All Recruiting')
OR ISMEMBEROF('Leadership Development')
```

`Leadership Development` carries no `KNJ-SG-Tableau` prefix. That is the real
group name, not a typo — group naming on this server is inconsistent by history,
so copy names exactly rather than normalizing them.

#### Why the tier model does not apply

The requirement is that **peers and subordinates learn nothing** about whether
someone plans to return. Tiers 3, 4, and 5 grant on group membership plus site
or region, which is lateral visibility by construction: a viewer in `All SL` or
`All DSO` reads every teacher, assistant school leader, dean, and office staff
member at their school, and a viewer in `All AP` reads every teacher there.
Almost none of those viewers is the respondent's manager.

That cannot be repaired by excluding job titles. A title exclusion changes who
is **observed**; this requirement is about who **observes**. An earlier version
of this field excluded seven leadership titles and still left every teacher's
and dean's response readable by a roomful of their colleagues.

So the tiers are deleted rather than narrowed. What remains is a relationship
test — self, plus the one manager the extract records — and an explicitly named
administrative set.

!!! note "Applies to any confidential self-report survey"

    The five-tier model assumes the row describes someone the viewer has a
    legitimate supervisory interest in. A self-report survey about staying or
    leaving breaks that assumption: the interest that justifies access is the
    reporting relationship itself and nothing wider. Reach for a relationship
    gate whenever the respondent would not have answered honestly knowing the
    audience.

#### What this extract looks like, and two traps

`rpt_tableau__survey_responses` holds 63,648 Intent to Return rows across
2023–2025, roughly 1,250 respondents a year.

- **`is_open_ended` is 1 on every ITR row**, including `itr_plans`, which has
  only 10 distinct answers and is the categorical intent question. The flag
  cannot separate aggregate-safe content from prose, so do not build an
  "aggregates only" variant on it. Free prose reaches 2,794 characters on
  `itr_considering_reasons`.
- **37% of ITR rows carry a null `question_shortname`** — 23,853 of them — so
  any rule written per question silently lets those rows through.

The extract also carries `respondent_name`, `race_ethnicity`, and `gender`. With
~1,250 respondents across 23 locations, a single-school view plus a demographic
breakdown re-identifies people whether or not the name field is on the sheet.

One thing works in your favour: `reports_to_mail` is **point-in-time, not
current-state**. Of 1,197 people who answered in more than one year, 833 have a
different manager recorded across years, so a 2023 response reaches whoever
managed them in 2023. A promotion does not hand someone their new report's older
answers.

#### The cost, and the wrong way to buy it back

A head of schools loses school-level retention rates. That need is real, and the
tempting fix — a second, wider permission field on the same extract, used only
on "aggregate" sheets — is the failure documented in the next section. Sheets
gated by a looser field on a row-level extract are one filter swap away from
exposing the prose behind them.

Build it in dbt instead: counts by `itr_plans` per location and year, minimum-N
suppression, no identity or demographic columns, published as its own data
source with its own permissions. Then who may see rates and who may read
comments are different objects rather than different filters on one object.

Members of the three all-access groups can read each other's responses. That is
accepted — those groups administer the process — but it is worth knowing before
someone in one of them assumes their own answers are private.

### One workbook can hold several permission fields

A workbook is not finished when `Permissions` is correct. Several carry
additional gates for particular sheets, and **every one of them is a separate
copy of the tier chain** that has to be brought forward independently.

The Survey Dashboard is the worst case, with four: `Permissions`,
`Permissions - PulseChecker`, `Permissions - Support`, and a dead
`Permissions - Support (Preview)`. A `Permissions - Support` left at its old
text grants the support sheets unconditionally to central office no matter how
correct the main `Permissions` field is — the sheets using it are simply gated
by a different, stale calculation.

Before calling a workbook done, enumerate its permission fields rather than
assuming there is one:

1. Sort the Data pane by name and read every field beginning `Permissions`. Fix
   or delete each. A field nothing uses is still a field the next editor will
   copy.
1. For each sheet, open the Filters shelf and note **which** permission field it
   filters on. Do not infer it from the sheet's topic.
1. Resolve each filter's field to its caption before believing it. A `.twb`
   filter stores the field's **internal** name, which never changes on rename —
   a filter reading `Permissions - ITR (copy)_155726081272713223` is displaying
   as `Permissions - Support`.

!!! danger "A dead permission field is not harmless"

    `Permissions - Support (Preview)` was a four-line leftover containing an
    individual by-name grant. Nothing filtered on it, so it passed every persona
    test — and it would have been the natural thing to copy when someone next
    added a support sheet. Delete dead permission fields; do not leave them for
    later.

### After editing a workbook

1. Confirm `[Permissions]` is on the filter shelf set to `TRUE` and applied to
   all sheets using that data source — step 4 of _Field structure_.
1. Search the workbook for `USERNAME()` compared against a **literal string**.
   There should be zero hits — Tier 1 compares against fields, never literals.
   That search is how you prove no individual grant survived. Search
   `ISMEMBEROF('The Syndicate')` too; it is retired and grants broadly.
1. Confirm every field named `Permissions*` was handled, not just the one on the
   shelf — see _One workbook can hold several permission fields_.
1. Run the personas below. Seeing **more** than expected is a security finding;
   seeing **less** is a broken gate. Both matter.
1. Tag the workbook `entra-ready` on Tableau Server.

| Persona                        | Expect                                              |
| ------------------------------ | --------------------------------------------------- |
| Teacher                        | self only                                           |
| Teacher's manager              | that teacher                                        |
| Assistant principal            | own school's teachers only                          |
| School leader                  | own school                                          |
| DSO                            | own schools                                         |
| Regional leader                | own region; cross-region only on norming sheets     |
| Central office                 | the four regions, **not** other central office rows |
| Paterson school staff          | Paterson rows                                       |
| Room 12 staff employed by TEAM | gates through the TEAM branch, not Paterson         |
| Cross-entity supervisor        | the supervised entity's rows                        |

On the three senior-leader workbooks, add these two. They are the cases that
caught a real leak, so run them rather than assuming:

| Persona                                             | Expect                                                          |
| --------------------------------------------------- | --------------------------------------------------------------- |
| A central office senior leader also in an ops group | regional rows yes; **another central office senior leader, no** |
| The manager both senior leaders report to           | **both of them**, via Tier 1                                    |

The first passes only if the entity gate excludes
central-office-on-central-office _and_ the Tier 2 shield is negated correctly.
The second is the counter-test that proves you have not over-blocked — if a
manager cannot see their own reports, the shield is too wide.

Also worth testing deliberately: a row with a **null** `job_function` and an
ordinary `job_title`, previewed as a council member, should be **visible**. That
case is the one both the over-blocking and under-blocking versions of the shield
get wrong, in opposite directions.

### Related

- Design rationale for each tier:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`
- Per-workbook remediation sequence:
  `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`
- [#4631](https://github.com/TEAMSchools/teamster/issues/4631) — surfaces
  `job_function_code` and fills the missing values, which removes the `ISNULL`
  fallbacks above
- [#4663](https://github.com/TEAMSchools/teamster/issues/4663) —
  `rpt_tableau__pm_outlier_detection`, deferred out of the migration
