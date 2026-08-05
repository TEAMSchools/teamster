# Tableau Permissions Playbook

> **For the human executing this:** every step happens in Tableau Desktop or on
> Tableau Server. Work one workbook at a time; each section is self-contained
> and ends with its own verification.

This file is the **build reference**. It carries the paste-ready text of every
calculated field, the order to create them in, and how to attach them. Use it
when you are:

- building a new gated workbook from scratch — start at _Build a gated
  workbook_;
- repairing an existing one — find it under _Per-workbook sections_;
- restoring an archived workbook — its section still describes its pre-migration
  calculation, so redo that section before republishing.

[The Tableau permissions guide](../../guides/tableau-permissions.md) is the
companion page and describes **who can see what and why**. It no longer carries
calc text. Where the two disagree about behaviour the guide wins; where they
disagree about the text of a field, **this file wins**.

`docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md` holds
the design reasoning behind each tier and each peer-exclusion helper.

## Current state

**11 workbooks gated**, each tagged `entra-ready` on Tableau Server — Manager
Survey Reports, Manager Survey Rollup, Leadership Development, Coaching
Conversation Tool, SchoolMint Grow Dashboard, Survey Dashboard, Miami
Instructional Rubrics, Operations Systems, Stipend and Bonus Dashboard,
Personalized Survey Links, Federal Grants Timesheet Approval.

**2 workbooks archived rather than remediated** — Content Team Dashboard and
Teacher Goals. An archived workbook still holds its pre-migration calculation,
individual username grants included.

An audit of all 11 shipped workbooks on 2026-08-05 read the calculations out of
the `.twbx` files for the first time and found six gaps. See _Known gaps_ before
trusting any workbook's gate.

---

## Build a gated workbook

Six steps. Steps 1 and 2 are the ones people skip, and they are the two that
cause silent failure.

### Step 1 — resolve the field names in this workbook

**Do this before pasting anything.** Every formula in this file is written
against the dbt column names. Most workbooks rename those columns via the field
caption, and Tableau's calculation editor resolves the **caption**, not the
underlying column — so a pasted formula referencing `[home_business_unit_name]`
does not validate in a workbook where that field is captioned `Business Unit`.

Open the Data pane and write down what these four are actually called:

| Formula text                | Seen in the wild as                                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `[home_business_unit_name]` | `Business Unit` (7 workbooks), `Home Business Unit Name` (2), not renamed (SchoolMint Grow) |
| `[location_clean_name]`     | `Location` (7), `Location Clean Name` (2), not renamed (SchoolMint Grow)                    |
| `[home_department_name]`    | `Department` (5), `Home Department Name` (2), not renamed (SchoolMint Grow)                 |
| `[job_title]`               | `Job Title` almost everywhere                                                               |

The identity columns — `sam_account_name`, `user_principal_name`, `mail`,
`reports_to_sam_account_name`, `reports_to_mail` — are usually **not** renamed,
so Tier 1 pastes as written. Check anyway.

`rpt_tableau__survey_completion` is the exception that breaks the pattern
outright: its identity columns are `[username]` and `[samaccountname]` — no
underscores — not `[user_principal_name]` and `[sam_account_name]`.

### Step 2 — decide the apply scope, and prefer datasource-wide

Tableau **ANDs** every filter that reaches a mark, so a permission filter's
blast radius is decided by where you attach it:

| Scope             | How to set it                                                                                     | Covers                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Datasource-wide   | right-click the field on the Filters shelf → **Apply to Worksheets → All Using This Data Source** | every sheet on that datasource, including ones added later |
| Datasource filter | Data pane → datasource → **Edit Data Source Filters**                                             | same                                                       |
| Sheet-local       | drop on the Filters shelf, leave as **Only This Worksheet**                                       | that one sheet                                             |

**Default to datasource-wide.** A sheet-local gate has to be re-applied by hand
on every new sheet, and that is how two of the six audit gaps happened: a sheet
was added to a dashboard and nobody re-attached the filter.

Use sheet-local only when one datasource genuinely needs two different rules —
the Survey Dashboard's Intent to Return sheets versus its support sheets, or the
Stipend workbook's HR download sheets. When you do, say so in a comment on both
fields.

!!! warning "A datasource-wide gate hides a sheet-local one's defects"

    If both are attached, effective access is the intersection — so a stale
    sheet-local field cannot widen access while the datasource-wide gate is
    there. That containment is invisible and temporary: remove the
    datasource-wide filter, or copy the stale field into a new workbook, and the
    old behaviour is back. SchoolMint Grow is in exactly this state; see
    _Known gaps_.

### Step 3 — create the helper fields

In this order, because `Permissions` references them and will not validate until
they exist. Nothing depends on the order among the first three.

1. `RLS - Entity Gate`
1. `RLS - Location Gate`
1. `RLS - Role Gate`
1. `RLS - Subject Is Senior Leader` — only on workbooks that shield senior
   leaders from each other
1. Any workbook-specific gate — see _Workbook-specific gates_

Copy them between workbooks via the Data pane: right-click the field, **Copy**,
then paste into the next workbook's Data pane. After step 1's rename check, a
pasted field either resolves cleanly or fails loudly.

### Step 4 — create `Permissions`

Paste _The canonical Permissions block_ below, then apply only the variants
named in that workbook's section. Keep the five tiers in the same order in every
workbook so they diff by eye.

### Step 5 — attach it

Put **only** `Permissions` on the Filters shelf, set to `TRUE`, at the scope
chosen in step 2. The helpers belong on no shelf.

### Step 6 — verify, then tag

Work through _Validation_ below. Seeing **more** than expected is a security
finding; seeing **less** is a broken gate. Both matter. Then tag the workbook
`entra-ready` on Tableau Server — that tag is the inventory.

---

## Prerequisites

Do not start until all four hold.

1. **PR #4656 is merged and Dagster has materialized the extracts.** The renamed
   columns do not exist until then, so every field fix below fails against the
   old views. Confirm one model in BigQuery — `rpt_tableau__content_team` should
   have `location_clean_name` and no `location`.
1. **The location groups exist.** See _Groups_ below. A missing group does not
   error; it silently denies, which is the failure this rebuild exists to
   eliminate.
1. **`ISMEMBEROF()` takes a literal string only — this is settled, do not
   re-test it.** The concatenated form

   ```text
   ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])
   ```

   does not validate. A parameter does not rescue it either: a parameter holds
   one value per view, so the calc evaluates once instead of per row and
   degenerates to all-rows-or-none — a bypass, not a gate. The location gate is
   therefore 26 explicit `ISMEMBEROF` branches, one per school location, Rooms
   excluded. See _Tier 5_ below.

1. **You know which Tier 2 groups each workbook currently grants.** Tier 2 is
   the only tier that legitimately differs across the 13, and this runbook
   cannot tell you a workbook's membership — read it out of the existing calc
   before you replace it. The HPT audit HTML is the other source.

---

## The canonical Permissions block

Five tiers, one `OR` chain, same order in every workbook so they diff by eye.
Paste this, then apply only the variants named in that workbook's section.

### Tier 1 — self and manager

The only tier that changes at cutover, and the reason this needs no coordination
with IT's switch window: both identity forms match, so it is correct before and
after.

```text
LOWER(USERNAME()) = LOWER([sam_account_name])
OR LOWER(USERNAME()) = LOWER([mail])
OR LOWER(USERNAME()) = LOWER([user_principal_name])
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])
```

`user_principal_name` is a hedge, not a widening. `mail` is the expected value
of `USERNAME()` after cutover but that is an expectation, not a confirmation,
and Entra sign-in commonly presents UPN. For 1,623 of 1,627 active staff the two
agree; for 3 they do not, and those 3 would silently fail a mail-only match.

### Tier 2 — all-access functional groups

Preserve each workbook's existing membership from this list: `All Data`, `TC`,
`All HR`, `All T&L`, `Recruiting`, `New Teacher Development`,
`Leadership Development`.

Two rules apply everywhere. Remove `Syndicate`. Remove **all 12 individual
username grants** — this tier is where they lived, and no individual grant
survives anywhere. The 12 names are held in `.claude/scratch/`, deliberately
uncommitted because staff usernames are identifiers.

### Tier 3 — regional ops

```text
OR ([home_business_unit_name] IN ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
    AND ISMEMBEROF('Group Staff NJ Regional'))
OR ([home_business_unit_name] = 'KIPP Miami' AND ISMEMBEROF('Group Staff MIA Regional'))
```

### Tier 4 — regional leaders

```text
OR ((ISMEMBEROF('KNJ-SG-Tableau All MDSO') OR ISMEMBEROF('KNJ-SG-Tableau All HOS')
     OR ISMEMBEROF('KNJ-SG-Tableau All MDO') OR ISMEMBEROF('KNJ-SG-Tableau AcOps'))
    AND [entity gate from Tier 5])
```

Two variants, both deliberate, and each must carry an inline comment saying
which it is and why. An undocumented difference is what the next reader
"corrects".

- On a main `Permissions` block, the entity gate applies as written.
- On `Permissions - Norming*` and `Permissions - PulseChecker` blocks, the tier
  is **ungated** and additionally includes `KNJ-SG-Tableau All SL`, because
  cross-region norming is intentional.

### Tier 5 — school-based

Requires all three of entity, location, and role.

Entity gate:

```text
IF ISMEMBEROF('KNJ-SG-Tableau All Staff TEAM Schools') AND [home_business_unit_name] = 'TEAM Academy Charter School' THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KCNA')     AND [home_business_unit_name] = 'KIPP Cooper Norcross Academy' THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff MIA')      AND [home_business_unit_name] = 'KIPP Miami' THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff Paterson') AND [home_business_unit_name] = 'KIPP Paterson' THEN TRUE
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KTAF')
       AND [home_business_unit_name] IN (
           'TEAM Academy Charter School',
           'KIPP Cooper Norcross Academy',
           'KIPP Miami',
           'KIPP Paterson'
       ) THEN TRUE
ELSE FALSE END
```

The Paterson branch is new and unblocks 96 staff.

**The KTAF branch is scoped to the four regions, not unconditional.** Central
office oversees the regions; it does not get visibility into itself. An earlier
version of this runbook said the branch stays unconditional — that was wrong and
caused a real leak, found while testing Manager Survey Rollup: two senior
leaders at the same level, both central office, both reporting to the same
manager, could see each other. The unconditional branch made the entity gate
TRUE on every row, and since KTAF staff sit in Rooms — absent from the location
gate by design — Tier 4 is their only route, so any regional-leadership group
membership became whole-extract access. Do not restore the unconditional form.

Two things not to "clean up" here. First, **single equality per branch** — dbt
now normalizes entity, so no extract can emit `TEAM`, `KCNA`, `MIA`, or `KNJ`
any more. Delete the old triple comparisons rather than carrying them forward;
an abbreviation branch cannot match anything and its presence implies the
extracts still emit abbreviations. Second, **the gate reads group membership,
not the viewer's own entity.** That is how cross-entity supervision works — a
TEAM employee who oversees Paterson gets Paterson visibility by being added to
the Paterson group, with no calc change. Deriving entity from the viewer's
roster row would silently revoke access from every cross-entity supervisor.

Location gate: 26 explicit branches, one per school location. This text is
byte-identical in all 9 workbooks that carry it — verified by hashing the
formula on 2026-08-05 — so paste it whole rather than retyping.

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

Rooms are absent by design — central office reaches data through Tiers 2 and 4,
never through location.

Role gate. **This is the one helper that legitimately differs per workbook** —
the audit found five distinct shapes across 10 workbooks. The canonical form:

```text
ISMEMBEROF('KNJ-SG-Tableau All DSO')
OR ISMEMBEROF('KNJ-SG-Tableau All SL')
OR (ISMEMBEROF('KNJ-SG-Tableau All AP')
    AND ([job_function] IN ('Teacher', 'Teacher in Residence')
         OR (ISNULL([job_function])
             AND (CONTAINS([job_title], 'Teacher') OR [job_title] = 'Learning Specialist'))))
```

The `ISNULL([job_function])` fallback mirrors what dbt now does upstream and is
load-bearing, not defensive: `job_function` is unpopulated on historical roster
rows and on newly created work assignments. It is removed when #4631 lands.

The AP branch requires **the row** to be a teacher, so an assistant principal
sees teachers at their school rather than every employee at it.

The five shapes in use today, so a deviation reads as intent rather than
accident. **Comment any deviation inline** — Miami's is the model to copy:

| Shape                                                                                         | Workbooks                                                                                                     |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Canonical, as above                                                                           | Coaching Conversation Tool, Manager Survey Reports, Manager Survey Rollup, SchoolMint Grow, Stipend and Bonus |
| Canonical + `OR ISMEMBEROF('TS-DL-NTN Coordinators')`, marked `// Workbook-specific addition` | Miami Instructional Rubrics                                                                                   |
| `All DSO` OR `All SL` OR `All AP`, AP unrestricted — **uncommented**                          | Survey Dashboard                                                                                              |
| `All DSO` OR `All SL` only — **uncommented**                                                  | Operations Systems                                                                                            |
| `All SL` only — **uncommented**                                                               | Leadership Development                                                                                        |

### `RLS - Subject Is Senior Leader`

Needed only where senior leaders are shielded from each other — currently
Manager Survey Reports, Manager Survey Rollup, and Leadership Development.

There is no way to ask Tableau whether **the row's person** belongs to a group;
`ISMEMBEROF()` only ever answers for the current viewer. Subject-side seniority
has to come from the data.

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

Two aspects are load-bearing:

- **The `IFNULL` wrappers** force TRUE or FALSE and never NULL, so the `NOT` in
  `Permissions` cannot go three-valued. Without them a null `job_function` makes
  the branch NULL, NULL is not TRUE in a filter, and every row with a null
  function silently disappears from council members' views — over a hundred
  thousand rows in Leadership Development alone.
- **The title fallback fires only when `job_function` is null.** Around 1,200
  rows in Leadership Development and 600 in the manager survey have a null
  function with a senior title. Without it those rows stop being shielded.

!!! warning "Bare `Executive` catches an executive assistant"

    The third title test matches `Executive Assistant`, which is not a senior
    leader, so an executive assistant is currently hidden from the council on all
    three workbooks. `RLS - Comp Peer Row` on the Stipend workbook solved the same
    problem correctly by matching `'EXECUTIVE DIRECTOR'` and documents why. Make
    these three agree with it.

The council grant in Tier 2 carries the exclusion:

```text
OR (ISMEMBEROF('Group Staff TEAM Council') AND NOT [RLS - Subject Is Senior Leader])
```

Note the `NOT`. The helper answers "should this row be shielded", so the grant
is its negation. Writing the shielded condition here without negating it grants
the council exactly the rows meant to be hidden — the inversion is easy to miss
because both forms read plausibly.

!!! danger "The shield only works because the entity gate excludes KTAF-on-KTAF"

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

### Retired-location bridge

Five locations where the canonical clean name and the group name disagree. Each
bridge branch carries a comment referencing the issue that deletes it.

| `location_clean_name`             | Group                                        | Staff |
| --------------------------------- | -------------------------------------------- | ----- |
| `KIPP Hatch Middle`               | `...All Staff KIPP Hatch Academy`            | 33    |
| `KIPP Sumner Elementary`          | `...All Staff KIPP Sumner Academy`           | 48    |
| `Paterson Prep Elementary School` | `...All Staff KIPP Paterson Prep Elementary` | 55    |
| `Paterson Prep Middle School`     | `...All Staff KIPP Paterson Prep Middle`     | 33    |
| `KIPP Miami - Poinciana Campus`   | `...All Staff Poinciana Campus`              | 4     |

### Remove everywhere

All individual usernames. `Syndicate` from all-access. The three campus groups
`Norfolk St Campus`, `Lanning Sq Campus`, `18th Ave Campus`.
`Group Staff Hatch Middle` and `Group Staff Sumner Elementary`. Every retired
location string. The dead `Learning Specialist Coordinator` title. The redundant
explicit `ESE Teacher`. And the `KNJ-SG-Tableau All Staff KIPP Whittier MIddle`
typo, which has never matched anything.

Keep `Group Staff NJ Regional` and `Group Staff MIA Regional`.

!!! warning "No Tier 3 in any of the 8 workbooks names Paterson"

    Paterson is in NJ and appears in both the entity gate and the location gate,
    but never in Tier 3 — so NJ regional ops staff see TEAM and KCNA rows and not
    Paterson rows. Either `'KIPP Paterson'` joins the NJ list or Paterson gets its
    own regional group. Nobody has decided, and it is an 8-workbook edit, so settle
    it before touching Tier 3 anywhere.

---

## Workbook-specific gates

Two workbooks compose a non-identity predicate into the tier chain. They are the
model for extending the pattern rather than forking `Permissions`.

### `RLS - Release Gate` — Coaching Conversation Tool

An observee must not see their own PM scores before the observation is locked,
or their own PM comments before the term's lockbox date. Their manager and coach
see both throughout.

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

Also add a **data source filter** `[is_observed] = 1`, which drops the
completion-tracking scaffold rows — they carry no scores or comments.

Three deliberate choices:

- **Tier 1 is a sufficient place to gate here, unlike anywhere else.** The
  extract filters subjects to teachers, and teachers hold no DSO, SL, or AP
  membership, so Tier 1 is their only route to their own row. On a workbook
  whose subjects included school leaders this would leak through Tier 5.
- **`ISNULL([tracking_academic_year])` is the prior-year test, and it is what
  makes a missing lockbox date fail closed.** Prior-year rows come from the
  model's second `union all` branch, which hardcodes a null `lockbox_date`; a
  current-year row always carries a tracking year. Testing the lockbox date for
  nullness instead would release a current-year term the moment someone forgot
  to set its date.
- **`IFNULL([locked], FALSE)` fails closed** on the small number of PMS rows
  where `locked` is null.

### `RLS - Comp Peer Row` — Stipend and Bonus Dashboard

TRUE for rows whose stipend must be hidden from the broad tiers. Chiefs and
senior leaders do not see each other's compensation; self and manager visibility
is preserved in Tier 1.

```text
[job_function] IN (
    'Chief Level',
    'EDs, HOSs, MDOs',
    'KTAF or Regional Managing Director'
)
OR (
    ISNULL([job_function])
    AND (
        CONTAINS(UPPER(IFNULL([job_title], '')), 'CHIEF')
        OR CONTAINS(UPPER(IFNULL([job_title], '')), 'PRESIDENT')
        OR CONTAINS(UPPER(IFNULL([job_title], '')), 'MANAGING DIRECTOR')
        OR CONTAINS(UPPER(IFNULL([job_title], '')), 'HEAD OF SCHOOLS')
        OR CONTAINS(UPPER(IFNULL([job_title], '')), 'EXECUTIVE DIRECTOR')
    )
)
```

It negates and wraps Tiers 2b through 5, leaving Tier 1 and the comp
administrators outside the suppression:

```text
<Tier 1>
OR ISMEMBEROF('KNJ-SG-Tableau All Data')
OR ISMEMBEROF('KNJ-SG-Tableau All HR')
OR (
    (
        <Tier 2b TEAM Council, Tier 3, Tier 4, Tier 5>
    )
    AND NOT [RLS - Comp Peer Row]
)
```

!!! danger "The wrapping parentheses are load-bearing"

    `AND` binds tighter than `OR`, so without them the suppression attaches to Tier
    5 alone and leaves Tiers 2b, 3, and 4 wide open — including Tier 4, which is
    how MDSOs, HOSs, and MDOs reach this dashboard. Do not flatten them.

---

## The Intent to Return variant

`Permissions - ITR` on the Survey Dashboard keeps the tier idea but adds a
**peer exclusion at every level**: a viewer never sees a respondent at their own
level. Peers and subordinates learn nothing about whether someone plans to
return; leaders above the respondent legitimately need to know.

This is the live text as audited on 2026-08-05. Field references are written
against the dbt column names — in this workbook they are captioned
`[Job Title]`, `[Department]`, `[Mail]`, `[Business Unit]`, and `[Location]`, so
translate per step 1.

```text
// Permissions - ITR

// 1. Self, and the manager recorded on the response
LOWER(USERNAME()) = LOWER([sam_account_name])
OR LOWER(USERNAME()) = LOWER([mail])
OR LOWER(USERNAME()) = LOWER([user_principal_name])
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])

// 2. Administrators of the process
OR ISMEMBEROF('KNJ-SG-Tableau All Data')
OR ISMEMBEROF('KNJ-SG-Tableau All HR')
OR ISMEMBEROF('KNJ-SG-Tableau All Recruiting')
OR ISMEMBEROF('Leadership Development')

// 3a. MDSO / HOS / MDO: their region, minus their own level.
//     They sit above every director, so directors stay visible.
OR (
    (
        ISMEMBEROF('KNJ-SG-Tableau All MDSO')
        OR ISMEMBEROF('KNJ-SG-Tableau All HOS')
        OR ISMEMBEROF('KNJ-SG-Tableau All MDO')
    )
    AND [RLS - Entity Gate]
    AND NOT [RLS - ITR Respondent Is Regional Leadership]
)

// 3b. The Syndicate: their region, minus regional leadership and minus
//     director-rank peers - but school operations directors stay visible.
OR (
    ISMEMBEROF('KNJ-SG-Tableau The Syndicate')
    AND [RLS - Entity Gate]
    AND NOT [RLS - ITR Respondent Is Regional Leadership]
    AND (
        NOT [RLS - ITR Respondent Is a Department Director]
        OR [RLS - ITR Respondent Is a School Operations Director]
    )
)

// 3c. School Support Directors: their region, minus regional leadership
//     and minus every director rank.
OR (
    ISMEMBEROF('KNJ-SG-Tableau School Support Directors')
    AND [RLS - Entity Gate]
    AND NOT [RLS - ITR Respondent Is Regional Leadership]
    AND NOT [RLS - ITR Respondent Is a Department Director]
)

// 4. School leaders and DSOs: their school, minus each other
OR (
    (ISMEMBEROF('KNJ-SG-Tableau All DSO') OR ISMEMBEROF('KNJ-SG-Tableau All SL'))
    AND [RLS - Entity Gate]
    AND [RLS - Location Gate]
    AND NOT [RLS - ITR Respondent Is School Leadership]
)

// 5. Assistant principals: teachers at their school, nobody else
OR (
    ISMEMBEROF('KNJ-SG-Tableau All AP')
    AND [RLS - Entity Gate]
    AND [RLS - Location Gate]
    AND (
        CONTAINS(UPPER([job_title]), 'TEACHER')
        OR CONTAINS(UPPER([job_title]), 'LEARNING SPECIALIST')
    )
)

// 6. Departmental directors: their own department in their own region,
//    minus director-rank peers. Associate directors stay visible.
OR (
    ISMEMBEROF('KNJ-SG-Tableau Special Education Directors')
    AND [home_department_name] = 'Special Education'
    AND [RLS - Entity Gate]
    AND NOT [RLS - ITR Respondent Is a Department Director]
)
OR (
    ISMEMBEROF('KNJ-SG-Tableau KIPP Forward Directors')
    AND [home_department_name] = 'KIPP Forward'
    AND [RLS - Entity Gate]
    AND NOT [RLS - ITR Respondent Is a Department Director]
)

// 7. TEAM Council: everyone, except other chief-level respondents.
OR (
    ISMEMBEROF('Group Staff TEAM Council')
    AND NOT [RLS - ITR Respondent Is Chief Level]
)
```

Three things about branch 2 and 3: `All Parliament` is deliberately absent
because it contains peers and subordinates of the respondents; `TEAM Council`
also holds network-wide access and appears in branch 7 instead, carrying a
shield; and `Leadership Development` carries no `KNJ-SG-Tableau` prefix — that
is the real group name, not a typo.

`AcOps` is **not** in branch 3a. It was removed deliberately; do not re-add it
by copying the canonical Tier 4.

### The five peer-exclusion helpers

They are shaped differently on purpose — pattern-matching for regional ranks,
enumeration for school ranks. The reasoning is in the spec.

```text
// RLS - ITR Respondent Is Regional Leadership
UPPER([job_title]) = 'HEAD OF SCHOOLS'
OR CONTAINS(UPPER([job_title]), 'MANAGING DIRECTOR')
OR CONTAINS(UPPER([job_title]), 'CHIEF')
OR CONTAINS(UPPER([job_title]), 'PRESIDENT')
OR CONTAINS(UPPER([job_title]), 'EXECUTIVE DIRECTOR')
```

```text
// RLS - ITR Respondent Is School Leadership
// No ops fellow here on purpose - school leaders and DSOs see them.
UPPER([job_title]) IN (
    'SCHOOL LEADER',
    'DIRECTOR SCHOOL OPERATIONS',
    'DIRECTOR CAMPUS OPERATIONS',
    'DIRECTOR OF CAMPUS OPERATIONS'
)
OR [RLS - ITR Respondent Is Regional Leadership]
```

```text
// RLS - ITR Respondent Is a Department Director
// Any director rank. Associate directors are not peers.
CONTAINS(UPPER([job_title]), 'DIRECTOR')
AND NOT CONTAINS(UPPER([job_title]), 'ASSOCIATE')
```

```text
// RLS - ITR Respondent Is a School Operations Director
// The Syndicate's own line of report - stays visible to them.
UPPER([job_title]) IN (
    'DIRECTOR SCHOOL OPERATIONS',
    'DIRECTOR CAMPUS OPERATIONS',
    'DIRECTOR OF CAMPUS OPERATIONS',
    'FELLOW SCHOOL OPERATIONS DIRECTOR'
)
```

```text
// RLS - ITR Respondent Is Chief Level
// Council peers. Deliberately NOT the shared RLS - Subject Is Senior Leader:
// that keys on job_function, which is unpopulated here, and its title fallback
// matches 'Executive' and so catches an executive assistant.
CONTAINS(UPPER([job_title]), 'CHIEF')
OR CONTAINS(UPPER([job_title]), 'PRESIDENT')
```

### Two rules this variant establishes

- **These helpers test job title, not `job_function`.** That contradicts
  `RLS - Subject Is Senior Leader`, and the reason is data rather than
  preference: `job_function` is populated on **0.06%** of
  `rpt_tableau__survey_responses` and **0% for 2019 through 2024**. Revisit
  after [#4631](https://github.com/TEAMSchools/teamster/issues/4631) backfills
  history, at which point every title test collapses to a job-function test.
- **Branch 1 has no peer exclusion, deliberately.** A manager sees their report
  even when both are director-rank. "No peers" means "no peers you don't
  manage."

!!! warning "Viewer attributes are current-state; row attributes are historical"

    Tableau group membership follows today's roster. Every column on
    `rpt_tableau__survey_responses` — `job_title`, `home_department_name`,
    `location_clean_name`, `reports_to_*` — is a snapshot from when the person
    answered. So a school leader sees three years of their school's rows including
    their predecessor's staff, someone who changes schools leaves their answers
    with the old school's leadership, and **peer exclusions match the row's title,
    not the person's current one**.

    This is also why test personas must be built from
    `kipptaf_people.int_people__staff_roster` with `assignment_status = 'Active'`,
    never from the extract.

!!! note "Do not build an aggregate variant on this extract"

    The tempting way to give a head of schools a school-level retention rate is a
    second, wider permission field used only on "aggregate" sheets. Sheets gated by
    a looser field on a row-level extract are one filter swap away from exposing the
    prose behind them. `is_open_ended` is 1 on **every** ITR row including the
    categorical `itr_plans`, so it cannot separate aggregate-safe content from
    prose, and 37% of ITR rows carry a null `question_shortname`.

    Build it in dbt instead — counts by `itr_plans` per location and year, minimum-N
    suppression, no identity or demographic columns — and publish it as its own
    datasource with its own permissions.

---

## Groups

The naming rule is `KNJ-SG-Tableau All Staff ` + the exact
`location_clean_name`, with the five bridge exceptions above. Rooms 9 through 12
follow a different pattern (`KNJ-SG-Tableau All Room 9`) and are not used by the
location gate.

There are **30** gated locations. Minus the four Rooms, that is the **26**
location branches the Tier 5 gate needs. Verify every one exists before editing
any workbook — the dbt test
`int_people__staff_roster__tableau_location_set_expected` asserts the dbt side
of this invariant, but nothing can assert the Tableau side, so it is a manual
check.

```text
KIPP BOLD Academy                  KIPP Rise Academy
KIPP Cooper Norcross High          KIPP Royalty Academy
KIPP Courage Academy               KIPP SPARK Academy
KIPP Hatch Middle          (bridge) KIPP Seek Academy
KIPP Justice Academy               KIPP Sumner Elementary      (bridge)
KIPP Lanning Square Middle         KIPP TEAM Academy
KIPP Lanning Square Primary        KIPP THRIVE Academy
KIPP Legacy Elementary             KIPP Upper Roseville Academy
KIPP Legacy Middle                 Paterson Prep Elementary School (bridge)
KIPP Life Academy                  Paterson Prep Middle School     (bridge)
KIPP Miami - North Campus          Room 9   (not location-gated)
KIPP Miami - Poinciana Campus (bridge) Room 10  (not location-gated)
KIPP Miami Technical High          Room 11  (not location-gated)
KIPP Newark Collegiate Academy     Room 12  (not location-gated)
KIPP Newark Lab High School
KIPP Purpose Academy
```

If a location appears here with no group, create the group before proceeding. If
a group exists for a location not on this list, it is retired — leave it alone
but do not reference it.

---

## Per-workbook sections

Each section lists the datasource, the fields whose names changed, and the
variants. **The field list is the minimum.** A renamed column breaks every
reference — filters, tooltips, other sheets, not just the Permissions calc — so
use Desktop's field-replacement rather than hand-editing the calc and hoping.

The rename map is derived from what PR #4656 actually removed, not from the
design doc's earlier estimate.

### Content Team Dashboard

- **Datasource:** `rpt_tableau__content_team`
- **Fields:** `[entity]` → `[home_business_unit_name]`, `[location]` →
  `[location_clean_name]`, `[department]` → `[home_department_name]`,
  `[report_to_sam_account_name]` → `[reports_to_sam_account_name]`
- **Role variant:** add `TS-DL-NTN Coordinators` to the role gate
- **Verify:** a Content Team member sees their own rows; an unrelated school
  teacher sees none

### Miami Instructional Rubrics

- **Datasource:** `rpt_tableau__content_team`
- **Fields:** same four as Content Team Dashboard
- **Role variant:** add `TS-DL-NTN Coordinators`
- **Verify:** a Miami school leader sees Miami rows only

### Leadership Development

- **Datasource:** `rpt_tableau__leadership_development`
- **Fields:** `[entity]` → `[home_business_unit_name]`, `[location]` →
  `[location_clean_name]`, `[department]` → `[home_department_name]`,
  `[report_to_sam_account_name]` → `[reports_to_sam_account_name]`
- **Note:** this model now excludes rows whose employee number resolves to no
  roster record, so a small number of previously-visible rows are gone by design
- **Senior-leader shield:** this workbook needs the fifth calculated field plus
  the council branch in Tier 2. Both are in `RLS - Subject Is Senior Leader`
  above.
- **Verify:** a participant sees their own record; their manager sees it too.
  Also run the two senior-leader personas in _Preview as User_.

### SchoolMint Grow Dashboard

- **Datasources:** `rpt_tableau__schoolmint_grow_observation_details`,
  `rpt_tableau__schoolmint_grow_goals`, `rpt_tableau__teacher_observations`
- **Fields, all three datasources:** `[entity]` → `[home_business_unit_name]`,
  `[location]` → `[location_clean_name]`, `[department]` →
  `[home_department_name]`; and on the two `schoolmint_grow_*` datasources
  `[report_to_sam_account_name]` → `[reports_to_sam_account_name]`
- **Tier 4 variant:** the `Permissions - Norming*` blocks are the ungated
  variant that adds `KNJ-SG-Tableau All SL`
- **Note:** `rpt_tableau__pm_outlier_detection` was **dropped from PR #4656**
  and is unchanged, so any calc referencing it needs no edit. Its remaining work
  is #4663.
- **Note:** `rpt_tableau__teacher_observations` now excludes observations logged
  against non-teachers, and resolves ESL teachers that previously fell out
- **Verify:** an AP sees only their own school's teachers; a school leader sees
  their school; norming sheets show cross-region data for MDSO/HOS/AcOps/SL

### Coaching Conversation Tool

- **Datasource:** `rpt_tableau__schoolmint_grow_observation_details`
- **Fields:** `[entity]`, `[location]`, `[department]`,
  `[report_to_sam_account_name]` — as above
- **Verify:** a coach sees their own conversations; a teacher sees theirs

### Survey Dashboard

- **Datasources:** `rpt_tableau__survey_responses`,
  `rpt_tableau__survey_completion`
- **Fields on `survey_responses`:** `[legal_entity]` →
  `[home_business_unit_name]`, `[location]` → `[location_clean_name]`,
  `[department]` → `[home_department_name]`, `[manager]` → `[manager_name]`,
  `[manager_email]` → `[reports_to_mail]`
- **Fields on `survey_completion`:** `[business_unit]` →
  `[home_business_unit_name]`, `[location]` → `[location_clean_name]`,
  `[department]` → `[home_department_name]`
- **Tier 4 variant:** `Permissions - PulseChecker` is the ungated variant
- **Verify:** a respondent sees their own responses; a manager sees their
  reports'

### Personalized Survey Links

- **Datasources:** `rpt_tableau__survey_completion`,
  `rpt_tableau__survey_responses`
- **Fields:** same as Survey Dashboard, plus `[samaccountname]` →
  `[sam_account_name]` and `[username]` → `[mail]` if those references exist
- **Verify:** each viewer sees only their own link

### Operations Systems

- **Datasources:** `rpt_tableau__operations_pm`, `rpt_tableau__operations_ekg`
- **Fields on `operations_pm`:** `[region]` → `[home_business_unit_name]`,
  `[home_work_location_name]` → `[location_clean_name]`
- **Fields on `operations_ekg`:** `[region]` → `[home_business_unit_name]`,
  `[respondent_location]` → `[location_clean_name]`, `[respondent_job_title]` →
  `[job_title]`
- **Role variant:** omit the AP branch entirely
- **Note:** `operations_pm` keeps `[respondent_job_title]` and
  `[respondent_name]` — that model has two people per row and the respondent is
  not the gated person. Do not "align" it with `operations_ekg`.
- **Note:** `operations_ekg` now resolves every respondent, where previously 235
  rows were invisible to all gated viewers
- **Verify:** a DSO sees their own schools; an ops teammate sees their own PM
  rows

### Stipend and Bonus Dashboard

- **Datasource:** `rpt_tableau__stipend_and_bonus_app`
- **Fields:** `[entity]` → `[home_business_unit_name]`, `[location]` →
  `[location_clean_name]`, `[department]` → `[home_department_name]`
- **Role variant:** omit the AP branch entirely
- **Keep:** `[entity_short]` — a genuinely different value, not a second name
- **Verify:** an approver sees their queue; a teammate sees their own stipends

### Federal Grants Timesheet Approval

- **Datasource:** `rpt_tableau__grants_timesheets`
- **Fields:** `[respondent_userprincipalname]` → `[user_principal_name]`,
  `[respondent_legal_entity_name]` → `[home_business_unit_name]`,
  `[respondent_primary_site]` → `[location_clean_name]`,
  `[respondent_primary_job]` → `[job_title]`
- **Keep:** `[respondent_df_employee_number]` and `[respondent_preferred_name]`
- **Fix the identity source, not just the names.** This workbook's calc uses
  `USERATTRIBUTE()` where every other uses `USERNAME()`. That is a defect, not a
  variant — replace it with `USERNAME()` and the standard Tier 1 block.
- **Verify:** a certifier sees their own timesheet; their approver sees it

### Manager Survey Reports

- **Datasource change, not a field fix.** Repoint from the intermediate
  `int_surveys__manager_survey_details` to the new extract
  `rpt_tableau__manager_survey_details`.
- **Fields:** the new extract drops seven `subject_*` duplicates that were
  second names for the gated person's own values — `subject_samaccountname`,
  `subject_userprincipalname`, `subject_department_name`,
  `subject_legal_entity_name`, `subject_manager_samaccountname`,
  `subject_primary_job`, `subject_primary_site`. Repoint each to its contract
  equivalent: `sam_account_name`, `user_principal_name`, `home_department_name`,
  `home_business_unit_name`, `reports_to_sam_account_name`, `job_title`,
  `location_clean_name`.
- **Keep:** `subject_preferred_name`, `subject_manager_name`,
  `subject_manager_userprincipalname`, `subject_df_employee_number`,
  `is_manager`, and the `respondent_*` fields — all genuinely different values
- **Senior-leader shield:** this workbook needs the fifth calculated field plus
  the council branch in Tier 2. Both are in `RLS - Subject Is Senior Leader`
  above.
- **Verify:** a rated manager sees their own results; their manager sees them.
  Also run the two senior-leader personas in _Preview as User_.

### Manager Survey Rollup

- **Datasource change:** same repoint as Manager Survey Reports
- **Fields:** same seven `subject_*` repoints
- **Senior-leader shield:** same as Manager Survey Reports — the fifth
  calculated field plus the council branch in Tier 2, from
  `RLS - Subject Is Senior Leader` above. This is the workbook the leak was
  found in.
- **Verify:** rollup totals match the pre-repoint numbers — the new extract
  wraps the same intermediate at the same grain, 175,670 rows, so any change in
  a total means a field was mapped wrong. Also run the two senior-leader
  personas in _Preview as User_.

### Teacher Goals

- **No field fixes.** No dbt-side rename touches this workbook.
- **Apply the canonical Permissions block only.**
- **No exposure was added** — its datasource could not be determined, because
  every workbook here uses an embedded extract and the read-only Tableau MCP
  exposes no workbook-to-table mapping. If you identify the model while in
  Desktop, say so and the exposure can be added in a one-line PR.

---

## Validation

### Preview as User

Run each persona against each workbook you have just edited. A persona that sees
**more** than expected is a security finding; one that sees **less** is a broken
gate. Both matter.

| Persona                         | Expect                                                |
| ------------------------------- | ----------------------------------------------------- |
| Teacher                         | self only, via Tier 1                                 |
| Teacher's manager               | that teacher, via Tier 1 manager match                |
| AP                              | own school's teachers only                            |
| School Leader                   | own school                                            |
| DSO                             | own schools                                           |
| MDSO / HOS / AcOps              | own region; cross-region **only** on norming sheets   |
| KTAF central office             | the four regions, **not** other central office rows   |
| Paterson school staff           | Paterson rows — this is the branch that did not exist |
| Room 12 staff under TEAM        | gates through the TEAM branch, not Paterson           |
| Cross-entity supervisor         | the supervised entity's rows, via group membership    |
| One of the 3 UPN-mismatch staff | self, proving the UPN hedge works                     |

On the three senior-leader workbooks — Manager Survey Reports, Manager Survey
Rollup, Leadership Development — add these two. They are the cases that caught
the real leak, so run them rather than assuming.

| Persona                                          | Expect                                                |
| ------------------------------------------------ | ----------------------------------------------------- |
| A KTAF senior leader who is also in an ops group | regional rows yes; **another KTAF senior leader, no** |
| The manager both senior leaders report to        | **both of them**, via Tier 1                          |

The first passes only if the entity gate excludes KTAF-on-KTAF _and_ the Tier 2
shield is negated correctly. The second is the counter-test proving you have not
over-blocked — a manager who cannot see their own reports means the shield is
too wide.

### Cutover rehearsal

Tier 1 matches both identity forms, so it can be tested before IT switches
anything. Confirm a viewer resolves by `sam_account_name` today, and confirm the
same viewer's `mail` and `user_principal_name` values are present and correct in
the extract. If both hold, cutover needs no coordination.

### Enumerate every permission field, do not assume there is one

A workbook is not finished when `Permissions` is correct. Several carry
additional gates for particular sheets, and **each is a separate copy of the
tier chain** that has to be brought forward independently. SchoolMint Grow has
five; the Survey Dashboard has two.

1. Sort the Data pane by name and read every field beginning `Permissions`. Fix
   or delete each one. A field nothing uses is still a field the next editor
   will copy.
1. For each sheet, open the Filters shelf and note **which** permission field it
   filters on, and at what scope. Do not infer it from the sheet's topic.
1. Resolve each filter's field to its caption before believing it. A `.twb`
   filter stores the field's **internal** name, which never changes on rename —
   a filter reading `Permissions - ITR (copy)_155726081272713223` displays as
   `Permissions - Support`, and `RLS - Role Gate` in Leadership Development is
   stored as `RLS - Entity Gate (copy)_1662461611803287552`.

!!! danger "A dead permission field is not harmless"

    It passes every persona test, because nothing filters on it — and it is the
    natural thing to copy when someone next adds a sheet. The audit found three,
    one of them 112 lines carrying two unconditional KTAF branches and three
    by-name grants. Delete dead permission fields; do not leave them for later.

### Confirm the individual grants are actually gone

Search every calculation in the workbook — not just `Permissions` — for each of
these. All four should return nothing:

| Search                                          | Why                                                                                                                                                                                                         |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USERNAME()` next to a quoted string            | an individual by-name grant. Tier 1 compares against fields, never literals                                                                                                                                 |
| `The Syndicate`                                 | retired network-wide and grants broadly. The one legitimate use is branch 3b of `Permissions - ITR`                                                                                                         |
| `All Staff KTAF` not followed by an entity list | the unconditional KTAF branch. The correct form ANDs it with the four-entity list                                                                                                                           |
| `USERATTRIBUTE`                                 | reads an attribute asserted by a connected app or embedding JWT, not the signed-in identity. On a workbook opened directly on Server there is no such assertion, so it is not a substitute for `USERNAME()` |

Separately, confirm each formerly-hardcoded individual still has access through
a group. Losing them is the one regression this could plausibly introduce, and
it is silent.

### Confirm every data sheet is actually reachable by a gate

The audit's most severe finding was not a wrong formula — it was two sheets on a
landing dashboard that no permission filter reached at all, and a correct field
that had never been attached to anything.

For each sheet in the workbook, answer: which permission field reaches this
sheet, at which scope? Title and text sheets with no datasource need no gate;
everything else does. If the answer is "none", that is the finding.

---

## Known gaps

Found by the 2026-08-05 audit of all 11 shipped workbooks, which read the
calculations out of the `.twbx` files, and reviewed with the owner the same day.
The working checklist is in `.claude/scratch/tableau_permissions_audit/`,
uncommitted because it names staff usernames.

| #   | Workbook                          | Gap                                                                                                                                                                   | Status                                                                                                                          |
| --- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Survey Dashboard                  | `Completion Tracking` and `Individual Tracking` were on the `Home` dashboard and **ungated** — full roster names, employee numbers, job titles, and completion status | **Fixed** — five-tier gate built on `rpt_tableau__survey_completion`                                                            |
| 2   | Miami Instructional Rubrics       | a correct five-tier `Permissions` existed and was **applied at no scope**, so both data sheets were ungated                                                           | **Fixed** — field attached datasource-wide                                                                                      |
| 3   | Survey Dashboard                  | `Permissions - Support` carries the unconditional `All Staff KTAF` branch, still grants `AcOps`, and is the only gate on five sheets                                  | **Accepted for now** — replaced by department scoping in [#4728](https://github.com/TEAMSchools/teamster/pull/4728), Tasks 7-10 |
| 4   | Operations Systems                | `rpt_tableau__operations_ekg`'s `Permissions` is 8 lines of group tests with no self clause and no location gate — applied datasource-wide over 10 sheets             | **Open** — see below                                                                                                            |
| 5   | Federal Grants Timesheet Approval | no permission fields at all, 7 ungated data sheets                                                                                                                    | **Accepted** — intentional                                                                                                      |
| 6   | Leadership Development            | `RLS - Entity Gate` has no Paterson branch, so Paterson rows are invisible to Paterson's own leadership                                                               | **Accepted** — intentional                                                                                                      |

Three cleanups with no live leak: two dead permission fields, SchoolMint Grow's
three legacy sheet-local fields (contained today only because a datasource-wide
gate ANDs over them), and 16 by-name `USERNAME()` grants across five fields.

### Gap 3 — what #4728 already covers

#4728 lists the Tableau slice as its Tasks 7-10: the `RLS - Department Gate`
field, scoping the blanket KTAF grant, deleting
`Permissions - Support (Preview)`, removing `The Syndicate`, and the #4656
renames.

Two of those are already done. The audit found **no**
`Permissions - Support (Preview)` field and **no** `The Syndicate` reference in
`Permissions - Support`. What remains is the department gate, the KTAF scoping,
and the renames.

### Gap 4 — Operations Systems

The broad groups (`All Data`, `TEAM Council`, `All MDSO`, `All MDO`,
`The Syndicate`) are intentionally cross-regional and stay. `All DSO` and
`All SL` come out of the flat list and get scoped to their own school.

That cannot be written yet, and the blocker is data rather than the calculation.

**Why the field is a flat group list today.** The workbook's embedded extract is
stale. The model gained the full access contract in `801303f80` (PR #4656) and
prod carries all ten roster columns populated on all 3,577 rows — but the
extract has 23 columns and none of them: no `location_clean_name`, no
`home_business_unit_name`, no identity columns. Someone already hit this: the
ekg datasource holds a `Region (copy)` field whose formula is just
`[home_business_unit_name]`, pasted from `operations_pm` and referencing a
column its own datasource does not have.

**The trap once the columns arrive.** `location_clean_name` on this model
describes **the respondent** — the person who performed the walkthrough —
because the roster joins on `respondent_email`. The school being walked is a
separate column, `[school]`, pivoted out of form item `669334db`. Scoping school
leaders by `location_clean_name` would give them "walkthroughs I performed", not
"walkthroughs of my school".

**And `[school]` cannot be gated as-is.** It is a form dropdown value, and 5 of
its 23 values disagree with the canonical location names the groups are built
from:

| `school` value                     | Canonical `location_clean_name`   | Resolves via crosswalk?            |
| ---------------------------------- | --------------------------------- | ---------------------------------- |
| `KIPP Cooper Norcross High School` | `KIPP Cooper Norcross High`       | yes                                |
| `KIPP Hatch Academy`               | `KIPP Hatch Middle`               | yes                                |
| `KIPP Sumner Academy`              | `KIPP Sumner Elementary`          | yes                                |
| `KIPP Paterson Prep ES`            | `Paterson Prep Elementary School` | **no — absent from the crosswalk** |
| `KIPP Paterson Prep MS`            | `Paterson Prep Middle School`     | **no — absent from the crosswalk** |

Two details make this worse than a rename list. `KIPP Hatch Academy` and
`KIPP Hatch Middle` both appear, as do `KIPP Sumner Academy` and
`KIPP Sumner Elementary` — the same physical school under two labels, so a gate
on the raw string silently denies half of that school's rows. And the two
Paterson labels resolve to nothing: the crosswalk holds ten Paterson aliases and
neither is among them, so **602 rows across 25 walkthroughs already carry a null
`grade_band`**. That is a live defect independent of permissions.

The fix, in order:

1. **Ops appends two rows to the location crosswalk sheet** behind
   `stg_google_sheets__people__location_crosswalk` — `name` to `clean_name`:
   `KIPP Paterson Prep ES` to `Paterson Prep Elementary School`, and
   `KIPP Paterson Prep MS` to `Paterson Prep Middle School`. This also clears
   the 602 null `grade_band` rows, so it is worth doing regardless.
1. **dbt surfaces the walked school's clean name.** The model already joins the
   crosswalk on `school` for `grade_band`; it just does not select the clean
   name from that join. One additive line in the `final` CTE:

   ```sql
   sc.location_clean_name as school_clean_name,
   ```

1. **Refresh the workbook's embedded extract** so the roster columns and
   `school_clean_name` appear.
1. **Build the gate.** Recreate `RLS - Location Gate` on the ekg datasource with
   every branch testing `[school_clean_name]` rather than
   `[location_clean_name]` — group names and the five bridges unchanged — then:

   ```text
   //Admin and all access - deliberately cross-regional
   ISMEMBEROF('KNJ-SG-Tableau All Data')
   OR ISMEMBEROF('Group Staff TEAM Council')
   OR ISMEMBEROF('KNJ-SG-Tableau All MDSO')
   OR ISMEMBEROF('KNJ-SG-Tableau All MDO')
   OR ISMEMBEROF('KNJ-SG-Tableau The Syndicate')

   //School leaders and DSOs - own school only, on the school walked
   OR (
       (ISMEMBEROF('KNJ-SG-Tableau All DSO') OR ISMEMBEROF('KNJ-SG-Tableau All SL'))
       AND [RLS - Location Gate]
   )
   ```

   No entity gate on the second clause: the location gate is already strictly
   narrower, since every location belongs to exactly one entity.

Verify on `detail_scores`, an ekg-only sheet — one school for a school leader,
every school for an MDSO. Check a Hatch or Sumner leader specifically, since
those are the two-label schools and both labels' rows should now appear.

!!! note "This is the generalisable lesson"

    A gate that looks unexplainably crude is often a stale extract rather than a
    lazy author. Before rewriting one, check whether the columns it would need are
    actually in the workbook's extract.

---

## Tagging and close-out

1. Tag each finished workbook `entra-ready` on Server.
1. The 8 TEMP and Archive copies already tagged `entra-broken-accepted` need no
   work — confirm none is still published to a Production project.
1. Note in #4638 which of the 13 are done, so the remaining set is visible
   without opening Desktop.

## Rollback

Every change here is a workbook revision on Server, so rollback is per-workbook:
restore the previous revision. Nothing in this runbook is destructive to data.

The one exception is the two Manager Survey datasource repoints. Reverting those
means pointing back at `int_surveys__manager_survey_details`, which still exists
and is unchanged — three mart models still read it — so that rollback is also
clean.

If PR #4656 itself is reverted after these edits land, every field fix here
breaks in the opposite direction. Sequence the revert as: restore workbook
revisions first, then revert the dbt PR.
