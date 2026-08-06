# Tableau RLS rebuild for the Entra ID identity migration

Refs #4638

> **Authoritative reference for calc text:** the playbook,
> `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`. This spec
> is the design reasoning behind those fields;
> [the Tableau permissions guide](../../guides/tableau-permissions.md) describes
> the resulting behaviour for a non-technical reader. Where this spec and the
> playbook disagree about the text of a field, the playbook wins.
>
> Two parts of the design landed after this spec was first written and are
> documented in the playbook: the **Tier 2 senior-leader shield** (the fifth
> calculated field, used on Manager Survey Reports, Manager Survey Rollup, and
> Leadership Development), and the fact that the shield and the entity gate are
> **coupled** — the shield is sufficient only because the entity gate excludes
> KTAF-on-KTAF. A shield inside one branch of an `OR` chain does nothing about
> the other branches.
>
> _Section 4_ below was added 2026-08-05 and covers the Intent to Return
> variant.

## Problem

KIPP Tableau Server is migrating identities from Active Directory usernames to
email addresses. Tableau's `USERNAME()` will return `mail` after cutover, which
breaks every row-level-security calculated field comparing it against a
`samaccountname`-style column.

An external audit surfaced 85 flagged content items network-wide. 21 belong to
cbaldor; 8 are already tagged `entra-broken-accepted` (TEMP and Archive
throwaways), leaving **13 Production workbooks**.

The identity break is the trigger, not the whole problem. Reading the flagged
calcs surfaced three compounding defects:

1. **Identity.** Comparisons resolve against `sam_account_name` /
   `report_to_sam_account_name`, and the backing extracts carry no email column
   to dual-match against.
1. **Stale org model.** Calcs reference retired locations and retired groups,
   and omit 5 currently-active locations entirely. `KIPP Paterson` appears in no
   entity gate anywhere, so the 96 active staff whose entity is `KIPP Paterson`
   resolve to deny regardless of group membership.
1. **Hardcoded individuals.** 12 individual usernames grant access directly,
   bypassing groups. (The list is held in `.claude/scratch/`, not committed —
   staff usernames are identifiers.)

## Goals

- Every gated workbook keeps working before **and** after cutover, with no
  coordination against IT's switch window.
- One canonical Permissions block, pasted unmodified across the 13 workbooks
  apart from documented per-workbook tiers.
- Location and department become separate access axes.
- Zero individual username grants remain.

## Non-goals

- The 64 flagged items owned by other authors.
- Renaming `location_clean_name` upstream (see _Follow-ups_).
- Normalizing role logic beyond the AP predicate. This is a migration, not an
  access redesign.
- Moving row-level decisions out of Tableau groups into the data. Considered and
  rejected: an entitlements join changes extract grain, and a Virtual Connection
  data policy needs Data Management licensing.

## Decisions

| Item                      | Decision                                                           |
| ------------------------- | ------------------------------------------------------------------ |
| Identity attribute        | `mail`, dual-matched with `sam_account_name` through cutover       |
| UPN hedge                 | Also match `user_principal_name` (differs from `mail` for 3 staff) |
| Individual grants         | Gut entirely, no replacement                                       |
| Access mechanism          | Tableau groups stay; the calc is restructured around them          |
| Location value source     | `int_people__location_crosswalk.location_clean_name`, unchanged    |
| Entity value source       | `int_people__staff_roster.home_business_unit_name`                 |
| Paterson entity group     | `KNJ-SG-Tableau All Staff Paterson`                                |
| Group naming rule         | `KNJ-SG-Tableau All Staff ` + exact location name                  |
| Rooms                     | Excluded from location scoping; central office is department-based |
| AP role predicate         | `job_function`, with a NULL fallback to `job_title`                |
| Tier 4 on norming / pulse | Left ungated — cross-region norming is deliberate                  |

## Section 1 — the dbt contract

Every model backing a gated workbook emits these columns under these names.
Contract columns always describe **the person whose access is being decided**;
anyone else on the row keeps a descriptive prefix (e.g. `respondent_*`).

Columns keep their **real source names** — no aliasing. Uniformity comes from
every model selecting the same source columns, so a rename in one place cannot
drift from another. Legacy aliases (`entity`, `` `location` ``, `legal_entity`,
`region`, `department`, `report_to_sam_account_name`) are deleted, not retained
for compatibility.

| Column                        | Source             | Purpose                      |
| ----------------------------- | ------------------ | ---------------------------- |
| `location_clean_name`         | location crosswalk | Location gate                |
| `campus_name`                 | location crosswalk | Available axis, not gated    |
| `home_business_unit_name`     | staff roster       | Entity gate                  |
| `home_department_name`        | staff roster       | Department axis              |
| `job_function`                | staff roster       | AP role predicate            |
| `job_title`                   | staff roster       | NULL-`job_function` fallback |
| `mail`                        | staff roster       | Post-cutover identity        |
| `user_principal_name`         | staff roster       | UPN hedge                    |
| `sam_account_name`            | staff roster       | Pre-cutover identity         |
| `reports_to_mail`             | staff roster       | Manager, post-cutover        |
| `reports_to_sam_account_name` | staff roster       | Manager, pre-cutover         |

Note the plural `reports_to_*`. The old extracts aliased these to singular
`report_to_*`; the real column is plural, and every calc referencing the
singular must be updated.

### Three rules the contract enforces

**Entity comes from the person, location from the place.** `location_region` is
a property of the location, not the viewer: Room 9's region is
`TEAM Academy Charter School`, but 130 of its 203 occupants are KTAF central
office. Using `location_region` for entity gating would hand central-office
staff a region's access.

This governs **person-grain** extracts, where the gated row describes a member
of staff. On an **event-grain** extract the row describes something that
happened at a place, and both gates come from that place, not from whoever
recorded it. `rpt_tableau__operations_ekg` is the case: a row is a walkthrough
of a school, so it gates on `school_clean_name` and `school_business_unit_name`,
both resolved from the walked school through `int_people__location_crosswalk`.
Gating it on the respondent instead shows a school leader the walkthroughs they
performed rather than the ones of their school, and no respondent on that form
is based in KIPP Paterson, so a Paterson leader sees nothing at all. The Room 9
failure above cannot reach an event-grain extract whose place is always a real
school — the walkthrough form's dropdown lists no Rooms — and the gate still
requires group membership, so sourcing entity from the place widens nothing.
Before applying this carve-out to another extract, confirm its place column
cannot resolve to a Room.

**Location and department stay separate columns.** This is the structural idea
borrowed from `dim_staff_cube_access` (#4269), and it is what stops Rooms from
granting location-wide visibility.

**`location_clean_name` values pass through untouched.** No renaming, no
override macro. The 5 naming mismatches are bridged in the Tableau block.

### Models in scope

Derived from `models/exposures/tableau.yml`, deduplicated across the 13
workbooks:

```text
rpt_tableau__leadership_development
rpt_tableau__schoolmint_grow_observation_details
rpt_tableau__schoolmint_grow_goals
rpt_tableau__teacher_observations
rpt_tableau__pm_outlier_detection   (DEFERRED - see below)
rpt_tableau__content_team
rpt_tableau__survey_responses
rpt_tableau__survey_completion
rpt_tableau__grants_timesheets
rpt_tableau__stipend_and_bonus_app
rpt_tableau__operations_pm
rpt_tableau__operations_ekg
rpt_tableau__manager_survey_details   (new)
```

Not every model is confirmed to carry location or entity today —
`__survey_completion`, `__grants_timesheets`, `__pm_outlier_detection` and
`__operations_ekg` are unaudited. Where a column is missing, add it by joining
`int_people__staff_roster`. That audit is task one of the implementation plan.

#### `rpt_tableau__pm_outlier_detection` is deferred, 2026-07-31

Dropped from scope by user decision after the contract work surfaced two
independent grain defects in it, one of them pre-existing and structural:
`score_dates` joins `stg_google_sheets__reporting__terms` with no region
predicate, while that sheet holds one row per region per term. The SchoolMint
Grow Dashboard will not be rebuilt for a while, so the model does not justify
holding up the other twelve. All of its changes were reverted to the merge base
and its remaining problems are tracked separately.

Twelve models carry the contract. The Permissions block still targets 13
workbooks — the SchoolMint Grow Dashboard reads three other contract-carrying
models alongside this one, so it is gated regardless; it simply cannot gate on
this model's rows until the deferred work lands.

### New extract and exposure work

- **`rpt_tableau__manager_survey_details`** — new. Manager Survey Reports and
  Manager Survey Rollup currently point at
  `int_surveys__manager_survey_details`, an intermediate model. The new extract
  wraps it, applies the contract, and adds `mail` (absent upstream). Both
  workbook data sources get repointed in Desktop.
- **Exposures added:** `content_team_dashboard` → `rpt_tableau__content_team`,
  and `manager_survey_rollup` → the new extract. Both omit `url` (only 3 of the
  file's 47 exposures carry one) and omit `cron_schedule`, since a cron there
  becomes a real Dagster refresh schedule and neither workbook is
  Dagster-refreshed today.
- **Exposure updated:** `manager_survey_reports`, repointed to the new extract.
- **`teacher_goals` — skipped by decision, 2026-07-30.** All 13 workbooks use
  embedded extracts rather than published datasources, and the read-only Tableau
  MCP exposes no workbook-to-table mapping, so its model could not be
  determined. The workbook was last modified 2024-09-19 and drew 3 views in a
  month. Guessing would have created a false lineage edge and a wrong Dagster
  dependency. Not deferred — declined.

## Section 2 — the Permissions block

Five tiers in one `OR` chain, same order in every workbook so they diff by eye.

### Tier 1 — self and manager

The only tier that changes at cutover, and the reason deployment needs no
coordination with IT: both the old and new identity forms match.

```text
LOWER(USERNAME()) = LOWER([sam_account_name])
OR LOWER(USERNAME()) = LOWER([mail])
OR LOWER(USERNAME()) = LOWER([user_principal_name])
OR LOWER(USERNAME()) = LOWER([reports_to_sam_account_name])
OR LOWER(USERNAME()) = LOWER([reports_to_mail])
```

`user_principal_name` is a hedge, not a widening. `mail` is the expected value
of `USERNAME()` after cutover, but that is an expectation rather than a
confirmation, and Entra sign-in commonly presents UPN. For 1,623 of 1,627 active
staff the two agree; for 3 they do not, and those 3 would silently fail a
mail-only match if Server presents UPN. One of them is in the validation matrix.

### Tier 2 — all-access functional groups

`All Data`, `TC`, `All HR`, `All T&L`, `Recruiting`, `New Teacher Development`,
`Leadership Development`. Membership varies per workbook; this is the only tier
that legitimately differs across the 13. `Syndicate` is removed. **No individual
usernames** — this tier is where all 12 hardcoded grants used to live.

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
    AND [the Tier 5 entity gate, reproduced below])
```

**Two documented variants.** On main `Permissions` blocks the entity gate
applies. On `Permissions - Norming*` and `Permissions - PulseChecker` blocks the
tier is **ungated and additionally includes `KNJ-SG-Tableau All SL`**, because
cross-region norming is intentional. Both variants must carry an inline comment
saying which they are and why — an undocumented difference is what gets
"corrected" by the next reader.

### Tier 5 — school-based

Requires all three of location, entity, and role.

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

The Paterson branch is new and unblocks 96 staff (55 Prep Elementary, 33 Prep
Middle, 8 in Room 12). A further 3 staff sit in Room 12 under the
`TEAM Academy Charter School` entity and gate through that branch instead.

#### The KTAF branch is scoped to the regions

An earlier revision of this design kept the KTAF branch unconditional to
preserve existing behavior. **That was wrong.** Central office oversees the
regions; it does not get visibility into itself, and the unconditional form
returned TRUE on every row including other central office rows.

The leak was found live in Manager Survey Rollup: two senior leaders at the same
level, both KTAF, both reporting to the same manager, could see each other.
Tiers 1, 3, and 5 all correctly returned FALSE and the Tier 2 shield correctly
returned FALSE — Tier 4 was the sole TRUE, because the viewer sat in a
regional-leadership group and the unconditional branch made the entity gate TRUE
on every row.

The non-obvious part: KTAF staff sit in Rooms, Rooms are absent from the
location gate by design, so Tier 5 can never fire for them and **Tier 4 is their
only route**. That makes any regional-leadership group membership equal to
whole-extract access. Scoping the branch to the four regions closes it, and is a
no-op wherever there are no KTAF subjects — 0.0% in the three teacher-population
extracts.

#### Historical entity values are abbreviations

`int_people__staff_roster_history` carries pre-2021 abbreviations rather than
full entity names: `TEAM` (9,551 rows, 2002-2020), `KCNA` (2,328), `KNJ`
(1,486), and `MIA` (658). Any view that surfaces rows from 2020 or earlier will
fail the entity gate above, because none of those values match a full name.

The old calcs handled this by hand — several tested
`[home_business_unit_name] = 'TEAM' OR [home_business_unit_name] = 'TEAM Academy Charter Schools' OR [home_business_unit_name] = 'TEAM Academy Charter School'`.
That is why those triple comparisons exist; they were not redundancy.

**Superseded 2026-07-30: dbt now normalizes entity, so the Tableau gate compares
one form only.** Every one of the 13 extracts maps the abbreviations to full
names with a `case` in its select list, aliased back to
`home_business_unit_name`, so no extract can emit `TEAM`, `KCNA`, `MIA`, or
`KNJ` any more. Each entity branch therefore takes a single equality:

```text
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff TEAM Schools')
   AND [home_business_unit_name] = 'TEAM Academy Charter School' THEN TRUE
```

**Delete the triple comparisons rather than carrying them forward.** An
abbreviation branch cannot match anything post-normalization, and leaving one in
place tells the next reader the extracts still carry abbreviations.

This was not a cosmetic change.
`rpt_tableau__schoolmint_grow_observation_details` alone was emitting 276,048
un-normalized rows — `TEAM` 189,391, `KCNA` 79,525, `MIA` 7,132 — and its
`accepted_values` test was failing until the `case` was added. Any entity gate
on that data was matching nothing.

`KNJ` is different: it was the **network** entity, KIPP New Jersey, which is
today's KTAF rather than any region. Evidence, not inference: of the 327 staff
who ever carried `KNJ`, 262 (80%) next appear under
`KIPP TEAM and Family Schools Inc.`, and 1,204 of the 1,486 `KNJ` rows (81%) sit
at Room 9, the network office. The two figures agree.

**Decision: `KNJ` maps flatly to KTAF.** In practice that means adding it to no
region branch at all, so region viewers correctly do not see historical network
staff.

Note what scoping the KTAF branch to the four regions changed here. When that
branch was unconditional it also covered these rows for network viewers. It no
longer does: `KIPP TEAM and Family Schools Inc.` is not in the four-region list,
so historical `KNJ` rows now fail the entity gate for everyone, and reach a
viewer only through Tier 1 (self or manager) or a Tier 2 all-access group. That
follows directly from central office not getting visibility into central office
rows — these are network rows. It is a deliberate consequence, not an oversight.

Two things this deliberately accepts:

- The 64 staff who later moved to a region have their `KNJ`-era rows attributed
  to the network, so their own region cannot see them. 64 historical rows is a
  cheaper error than the alternative.
- The alternative — deriving entity from the location crosswalk — was rejected
  precisely because it fails the wrong way. Room 9's `location_region` is
  `TEAM Academy Charter School`, so a location-derived entity would put 1,204
  network-staff rows into TEAM and expose them to every TEAM region viewer. The
  flat map fails closed; the location map fails open.

In dbt this is the `KNJ` branch of the entity `case`, which rewrites it to
`KIPP TEAM and Family Schools Inc.`. Region branches then never match it — the
same outcome the flat map describes, reached in the view rather than in the
calc.

Because normalization happens in dbt, no workbook needs a second entity form
regardless of how far back its data reaches.

#### The entity gate reads group membership, not the viewer's own entity

`ISMEMBEROF('KNJ-SG-Tableau All Staff Paterson') AND [home_business_unit_name] = 'KIPP Paterson'`
asks whether the viewer is **in the Paterson staff group** — never whether the
viewer is a Paterson employee. Membership of an entity group is deliberately not
the same population as employment by that entity.

This is load-bearing, not incidental. It is how cross-entity supervision is
expressed: a TEAM employee who oversees Paterson schools gets Paterson
visibility by being added to the Paterson group, with **no calc change**. Dual
membership resolves correctly because the gate is an `IF`/`ELSEIF` chain of
`group AND matching-entity` pairs — a Paterson row falls through the TEAM branch
(entity does not match), then lands on the Paterson branch.

The tempting "cleanup" is to derive entity from the viewer's own roster row
instead of from group membership. **Do not.** It would silently revoke access
from every cross-entity supervisor, and silent revocation is the failure mode
this whole rebuild exists to eliminate.

Location gate — 26 explicit branches, one per school location:

```text
OR ([location_clean_name] = 'KIPP TEAM Academy' AND ISMEMBEROF('KNJ-SG-Tableau All Staff KIPP TEAM Academy'))
```

The one-line form
`ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])` was the
original hope. It does not work: `ISMEMBEROF()` takes a literal string only, so
the concatenation does not validate. A parameter does not rescue it either — a
parameter holds one value per view, so the calc would evaluate once instead of
per row and degenerate to all-rows-or-none, a bypass rather than a gate. The
same limitation is why subject-side seniority has to come from the data:
`ISMEMBEROF()` only ever answers for the current viewer, never for the row's
person.

The full 26-branch block, including the five retired-location bridges, is in the
playbook, `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`.

Rooms are absent by design. Central office reaches data through Tiers 2 and 4,
never through location.

Role gate:

```text
ISMEMBEROF('KNJ-SG-Tableau All DSO')
OR ISMEMBEROF('KNJ-SG-Tableau All SL')
OR (ISMEMBEROF('KNJ-SG-Tableau All AP')
    AND ([job_function] IN ('Teacher', 'Teacher in Residence')
         OR (ISNULL([job_function])
             AND (CONTAINS([job_title], 'Teacher') OR [job_title] = 'Learning Specialist'))))
```

Per-workbook role variants, both deliberate: Content Team and Miami
Instructional Rubrics add `TS-DL-NTN Coordinators`; Stipend and Bonus and
Operations Systems omit the AP branch entirely.

### Retired-location bridge

Five locations where the canonical clean name and the group name disagree. Each
bridge branch carries a comment referencing the follow-up issue that deletes it.

| `location_clean_name`             | Group                                        | Staff |
| --------------------------------- | -------------------------------------------- | ----- |
| `KIPP Hatch Middle`               | `...All Staff KIPP Hatch Academy`            | 33    |
| `KIPP Sumner Elementary`          | `...All Staff KIPP Sumner Academy`           | 48    |
| `Paterson Prep Elementary School` | `...All Staff KIPP Paterson Prep Elementary` | 55    |
| `Paterson Prep Middle School`     | `...All Staff KIPP Paterson Prep Middle`     | 33    |
| `KIPP Miami - Poinciana Campus`   | `...All Staff Poinciana Campus`              | 4     |

### Removed entirely

All individual usernames; `Syndicate` from all-access; the three campus groups
(`Norfolk St Campus`, `Lanning Sq Campus`, `18th Ave Campus`);
`Group Staff Hatch Middle`; `Group Staff Sumner Elementary`; every retired
location string; the dead `Learning Specialist Coordinator` title (0 active
staff); the redundant explicit `ESE Teacher`; and the
`KNJ-SG-Tableau All Staff KIPP Whittier MIddle` typo, which has never matched
anything.

`Group Staff NJ Regional` and `Group Staff MIA Regional` are kept.

## Section 3 — validation and rollout

### Invariant

**A `location_clean_name` change and a Tableau group rename must happen
together.** Once the calc compares clean-name values against group names, a
one-sided change breaks access silently. Worth a monitored check later.

### dbt tests

Column names below are the shipped contract names, not the working names this
spec used before Section 2 settled: `location_clean_name`, not `location_name`;
`home_business_unit_name`, not `entity`; `mail`, not `email`.

Per-column, on each of the 13 extracts:

- `location_clean_name` — `not_null`
- `home_business_unit_name` — `not_null`, plus `accepted_values` on the 5 real
  values including `KIPP Paterson`

Singular tests, in `src/dbt/kipptaf/tests/`, all three anchored on
`int_people__staff_roster` via `meta.dagster.ref` so each reports as one asset
check rather than observations across both parents:

- `int_people__staff_roster__locations_resolve_to_crosswalk` — every active
  roster location resolves to a canonical clean name. This is the 100%-coverage
  invariant, and it is what catches a new school before it silently denies
  staff.
- `int_people__staff_roster__tableau_location_set_expected` — the active
  clean-name set matches the 30 expected, so an addition surfaces rather than
  passing as a gap. Update the expected set in the same change that creates the
  group.
- `int_people__staff_roster__mail_populated_with_sam` — `mail` populated
  wherever `sam_account_name` is populated. Warn-level, via the project default
  rather than an override.

All three pass against production: 0 unresolved locations, exactly 30 locations,
0 records holding a `sam_account_name` without a `mail`.

The `not_null` tests are warn-level and 5 of the 13 extracts carry non-zero
counts, every one of them a roster-join miss rather than an unmapped location —
verified by the absence of any row where a location is null while a
roster-sourced column is populated. Shares: `operations_ekg` 6.57%,
`content_team` 1.60%, `teacher_observations` 0.55%, `leadership_development`
0.11%, `stipend_and_bonus_app` 0.01%, the rest zero.

### Preview as User personas

| Persona                         | Proves                                        |
| ------------------------------- | --------------------------------------------- |
| Teacher                         | self-only, Tier 1                             |
| Manager                         | self plus direct reports                      |
| Miami AP                        | the 9 ESE teachers are visible (job_function) |
| School Leader                   | cross-region norming access is present        |
| DSO                             | Tier 5 role gate                              |
| MDSO / MDO / HOS                | entity-wide, no location                      |
| Paterson school staff           | the new branch; currently denied entirely     |
| KTAF person sitting in Room 9   | entity from person, not location              |
| One of the 3 UPN-mismatch staff | the Tier 1 hedge                              |
| A NULL-`job_function` teacher   | the fallback clause                           |
| A formerly-hardcoded individual | still has access via groups                   |

### Blocking pre-check

**All 12 formerly-hardcoded individuals need their group coverage confirmed
before any edit lands.** Gutting an individual grant assumes the person is
covered by a group. If any were hardcoded _because_ they were not in the right
group, gutting silently removes their access. Tableau group membership is not
readable through the MCP — there is no group tool — so this is a manual check by
the author or IT.

### Rollout order

1. dbt merged and built first. A calc referencing `[mail]` before the column
   exists breaks the workbook.
1. The four simple workbooks — Teacher Goals, Manager Survey Reports, Manager
   Survey Rollup, Personalized Survey Links — to shake out the contract on
   low-risk surfaces.
1. The remaining complex ones, SchoolMint Grow (6 calcs) last.
1. Tag `entra-ready` per item. Completion is auditable read-only via the Tableau
   MCP with `tags:eq:entra-ready`.

### Federal Grants Timesheet Approval carries a defect, not a variant

Its `userattribute` field calls `USERATTRIBUTE('username')`. That is a mistake
in the workbook, not a deliberate embedding pattern — it should be `USERNAME()`
like every other item. Replace the call and apply the standard block; no
separate fix path is needed.

Worth verifying while in there: `USERATTRIBUTE()` returns NULL unless a
Connected App or JWT supplies that attribute, and a NULL comparison excludes the
row. If nothing has been supplying `username`, this field has been inert and
whatever it gates has been failing closed for ordinary viewers. Confirm with
Preview as User what the dashboard shows **before** the edit, so the change in
behavior is understood rather than discovered later.

### Rollback

Capture each workbook's current calc text before editing, so a bad publish has a
known-good string to restore. Tableau revision history is the backstop.

## Section 4 — the Intent to Return variant

Added 2026-08-05, when the design settled. The field text is in the playbook;
this section is why it has the shape it has.

The five tiers assume a viewer's group membership implies a legitimate interest
in everyone at their site or region. A confidential self-report survey breaks
that at one level only: a respondent's **peers**. So the variant keeps the
tiers, adds a peer exclusion per tier, and drops the network-wide groups that
exist for analysis rather than administration.

### Why title tests rather than `job_function`

This is the one place the design contradicts `RLS - Subject Is Senior Leader`,
and the reason is data rather than preference. `job_function` is populated on
**0.06%** of `rpt_tableau__survey_responses` and **0% for 2019 through 2024**.
`School Leader` appears on 63,644 rows of that extract with a job function set
on 34 of them. Keying these helpers on `job_function` would be a no-op dressed
as a principle.

`RLS - Subject Is Senior Leader` is also unusable here for a second, independent
reason: its `ISNULL` fallback matches the bare string `Executive`, which catches
an executive assistant. On an extract where the fallback fires on essentially
every row, that false positive would be the rule rather than the exception.

Revisit after [#4631](https://github.com/TEAMSchools/teamster/issues/4631)
backfills history, at which point every title test collapses to a job-function
test.

### Why one helper matches patterns and the other enumerates

The asymmetry is not an oversight. The two levels fail in opposite directions.

**Regional titles proliferate.** New chief and managing-director variants appear
regularly, and a list would be stale the week after it was written — the current
roster already holds eight distinct `Managing Director` forms and eleven `Chief`
forms. `CONTAINS` absorbs the next one automatically, and no non-leadership
title on the roster contains `CHIEF`, `PRESIDENT`, or `MANAGING DIRECTOR`, so it
over-reaches nowhere.

**School peer titles have near-miss neighbours that must stay visible.** Here
`CONTAINS` cannot express the policy without collapsing under exceptions.
`CONTAINS('SCHOOL LEADER')` catches `School Leader`, but also
`Assistant School Leader` and `School Leader in Residence`, so it needs
`AND NOT ... 'ASSISTANT' AND NOT ... 'RESIDENCE'`. The DSO clause is worse: the
title exists as both `Director School Operations` and
`Fellow School Operations Director`, so a phrase test misses one while a
two-word test catches both and then needs `NOT ... 'ASSOCIATE'` and
`NOT ... 'FELLOW'` bolted on. Four negations to express four titles, each one a
place to be wrong. Enumerated, the list reads as the policy and can be checked
against an org chart.

`HEAD OF SCHOOLS` uses `=` inside the pattern-matching helper for the same
reason: `CONTAINS('HEAD OF SCHOOL')` would catch `Head of Schools in Residence`,
which must stay visible. The cost is that a future variant such as
`Head of Schools, Elementary` would not be caught. If those appear, the robust
equivalent is
`CONTAINS(UPPER([job_title]), 'HEAD OF SCHOOL') AND NOT CONTAINS(UPPER([job_title]), 'RESIDENCE')`.

`SCHOOL LEADER` appears only in the school helper, and **the school helper
composes the regional one**. School leaders and DSOs are subordinates of
regional leadership, so putting them in the regional helper would hide the 2,003
rows regional leaders most need; composing the other way keeps a school leader
from seeing above their own level.

### Who the helpers deliberately leave visible

A viewer is blocked from their **own level only**. Every rank below a peer, and
every developing or associate version of a peer role, stays visible — those are
the people whose retention their leader is responsible for.

| Title                                          | ITR rows | People | Visible to                     |
| ---------------------------------------------- | -------- | ------ | ------------------------------ |
| `School Leader in Residence`                   | 96       | 6      | School leaders, DSOs, regional |
| `Head of Schools in Residence`                 | 16       | 1      | Regional leadership            |
| `Fellow School Operations Director`            | 48       | 2      | School leaders, DSOs, regional |
| `Associate Director of School Operations`      | 209      | 6      | School leaders, DSOs, regional |
| `Assistant School Leader` and its two variants | 4,568    | 149    | School leaders, DSOs, regional |
| `School Operations Manager`                    | 899      | 27     | School leaders, DSOs, regional |
| `Fellow` (unqualified)                         | 81       | 4      | School leaders, DSOs, regional |

### Why branch 3 splits into three

One shared exclusion helper cannot serve viewer groups that sit at different
levels. `RLS - ITR Respondent Is Regional Leadership` describes the MDSO / HOS /
MDO level, so applying it alone to the Syndicate and to School Support Directors
would have hidden the wrong people:

- **3a — MDSO / HOS / MDO** sit above every director, so directors stay visible.
  The helper alone is the right exclusion.
- **3b — The Syndicate** is at director rank, so director-rank peers are
  excluded too — except school operations directors, who are the Syndicate's own
  line of report and must stay visible. That is what
  `RLS - ITR Respondent Is a School Operations Director` exists for.
- **3c — School Support Directors** are at director rank with no line of report
  among directors, so every director rank is excluded.

`AcOps` was removed from this branch. `The Syndicate` appears here and nowhere
else — that reverses the migration's network-wide removal of the group, and this
paragraph is the record of that decision.

### Branch 6 — the two departmental director groups

`Special Education Directors` and `KIPP Forward Directors` are scoped by
**department and region**, and exclude director-rank peers while leaving
associate directors visible. `RLS - ITR Respondent Is a Department Director` is
exact rather than approximate here, because neither department contains a chief,
head of schools, managing director or executive director. The
`NOT ... 'ASSOCIATE'` clause keeps `Associate Director` visible — 112 rows from
6 people in KIPP Forward, and none in Special Education, which has no associate
directors.

| Department        | Region | Rows   | People | Peer rows excluded |
| ----------------- | ------ | ------ | ------ | ------------------ |
| Special Education | TEAM   | 11,161 | 327    | 144                |
| Special Education | KCNA   | 2,896  | 94     | 32                 |
| Special Education | Miami  | 627    | 20     | 48                 |
| KIPP Forward      | TEAM   | 896    | 28     | 96                 |
| KIPP Forward      | KCNA   | 451    | 13     | 48                 |
| KIPP Forward      | Miami  | 64     | 3      | 0                  |

If a third department group is added, it reuses
`RLS - ITR Respondent Is a Department Director` unchanged.

!!! warning "Miami KIPP Forward staff have no departmental viewer"

    Miami has 3 KIPP Forward respondents and **no** KIPP Forward director of its
    own — the zero in the last column is the tell. Before the entity gate was
    added, TEAM's and KCNA's directors covered them; now nobody in branch 6 does,
    and those 3 people reach only their manager and the three admin groups. Either
    add Miami's KIPP Forward lead to the group once one exists, or accept the gap
    knowingly.

    The same applies to the KIPP Forward `Achievement Director` row, which sits in
    the central office entity and so fails the four-region list.

### Branch 7 — the TEAM Council shield is approximate

The council sees every response network-wide except other chief-level
respondents. `RLS - ITR Respondent Is Chief Level` covers 64 rows from 4 people:
`Chief Academic Officer`, `Chief of Staff` and `Deputy Chief`. The `PRESIDENT`
clause matches nothing in the current waves and is there for the `Co-President`
title, which exists on the roster. `Deputy Chief` is included even though its
`job_function` is `EDs, HOSs, MDOs` rather than `Chief Level`, so this test is
marginally broader than the canonical shield — the safe direction for a
confidential survey.

!!! warning "The shield hides chief-level titles, not council membership"

    Tableau cannot ask whether **the respondent** belongs to a group, so council
    membership has to be approximated from the title. If the council includes heads
    of schools or managing directors, and it plausibly does, their responses stay
    visible to fellow council members: **720 rows from 23 people** hold a senior
    title that is not chief level (`Executive Director`, `Head of Schools`,
    `Head of Schools in Residence`, and five `Managing Director` variants).

    Widening the shield is one clause —
    `OR [RLS - ITR Respondent Is Regional Leadership]` — but it costs regional
    oversight nothing and council visibility a great deal, so it should be a
    decision rather than a default. Settle it by reading the council roster against
    that list of eight titles.

### What the extract looks like

63,648 Intent to Return rows across 2023–2025, roughly 1,250 respondents a year.

| Respondent level                  | Rows   | People | At a Room         |
| --------------------------------- | ------ | ------ | ----------------- |
| Regional leadership               | 784    | 27     | 784 — all of them |
| School leadership                 | 2,003  | 62     | 96                |
| Assistant school leaders          | 4,568  | 130    | 16                |
| Teachers and learning specialists | 34,928 | 1,049  | 497               |
| Everyone else                     | 21,365 | 598    | 3,156             |

Every regional-leadership response sits at a Room, and Rooms are absent from the
location gate, so branches 4 and 5 cannot reach them regardless. The composed
`OR [RLS - ITR Respondent Is Regional Leadership]` inside the school helper is
insurance against a leader later being assigned a school location, not a live
fix.

The extract also carries `respondent_name`, `race_ethnicity`, and `gender`. With
~1,250 respondents across 22 school locations, a single-school view plus a
demographic breakdown re-identifies people whether or not the name field is on
the sheet.

Two unresolved title cases, both from the 2026-08-05 audit:

- `Fellow` unqualified — 4 people, 81 rows, rank unresolvable from title.
- `Director` bare — 33 people, most in Special Education, Student Support, KIPP
  Forward and Teaching and Learning, who are not anyone's regional peer.

Both are why #4631 matters: it collapses every title test to
`job_function_code`.

Also worth confirming rather than assuming: `Chief of Staff` sits in the TEAM
entity (1 person, 16 rows), the only chief-level row inside a region's entity
gate. That may be roster drift rather than a real assignment.

### Re-audit after each survey wave

Both peer helpers fail silently in the unsafe direction — an uncaught peer title
is visible to that person's peers until someone notices. The school list goes
stale when a title is added; the regional patterns go stale if a peer title
arrives using none of their five markers. This returns every leadership-looking
title that **neither** helper catches:

```sql
select job_title, count(*) as rows_
from `teamster-332318.kipptaf_tableau.rpt_tableau__survey_responses`
where survey_title = 'Intent to Return Survey'
  and upper(job_title) != 'HEAD OF SCHOOLS'
  and not contains_substr(upper(job_title), 'MANAGING DIRECTOR')
  and not contains_substr(upper(job_title), 'CHIEF')
  and not contains_substr(upper(job_title), 'PRESIDENT')
  and not contains_substr(upper(job_title), 'EXECUTIVE DIRECTOR')
  and upper(job_title) not in (
    'SCHOOL LEADER',
    'DIRECTOR SCHOOL OPERATIONS',
    'DIRECTOR CAMPUS OPERATIONS',
    'DIRECTOR OF CAMPUS OPERATIONS'
  )
  and regexp_contains(
    upper(job_title), r'DIRECTOR|LEADER|HEAD|PRINCIPAL|SUPERINTENDENT'
  )
group by job_title
order by rows_ desc
```

Today every row it returns is a rank that should be visible. Anything in the
output that is a **full peer** is a live gap.

## Risks

| Risk                                                      | Mitigation                                   |
| --------------------------------------------------------- | -------------------------------------------- |
| Gutting individuals removes access someone needs          | Blocking pre-check above                     |
| A mistyped group name fails silently rather than erroring | Persona matrix; verify names against Server  |
| `ISMEMBEROF()` may reject a non-literal argument          | Fall back to 26 explicit branches            |
| Redesign compressed against the cutover date              | Dual-match lets workbooks ship one at a time |
| 25 teachers have NULL `job_function`                      | Documented fallback clause                   |

## Open questions

- Does `ISMEMBEROF()` accept an expression on this Server version? Two minutes
  in Desktop settles it.
- Confirm `KNJ-SG-Tableau All Staff Room 12` against Server. Rooms 9, 10 and 11
  use `KNJ-SG-Tableau All Room N`, so the `All Staff` form may be a typo. Rooms
  are not gated on, so this may be moot.
- Teacher Goals and Manager Survey Rollup datasources need confirming from the
  workbooks.
- 5 staff carry `job_function = 'Teacher'` with titles of Assistant School
  Leader, Dean, or Director of Orchestra and Music. Looks like an ADP mapping
  error that would expose an ASL's data to APs. Refer to People Operations.

## Follow-ups

- **Rename canonical clean names** to current school names, coordinated with the
  three lookup sheets that join on them —
  `stg_google_sheets__coupa__address_name_crosswalk`,
  `stg_google_sheets__egencia__traveler_groups`,
  `stg_google_sheets__zendesk_org_lookup`. When this lands, delete the five
  bridge branches. Deliberately excluded here: 33 models consume the crosswalk,
  which is too wide a blast radius for cutover week.
- **Populate `job_function`** for the 25 affected teachers, then delete the
  fallback clause.
- **Ops sheet fixes:** `KIPP Miami - Poinciana Campus` carries
  `campus_name = 'KIPP Miami - North Campus'`, which looks wrong.
  `N. 13th St. Campus` (Purpose and Upper Roseville, 131 staff) has no Tableau
  group.
