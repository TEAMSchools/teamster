# Tableau RLS rebuild for the Entra ID identity migration

Refs #4638

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
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KTAF') THEN TRUE
ELSE FALSE END
```

The Paterson branch is new and unblocks 96 staff (55 Prep Elementary, 33 Prep
Middle, 8 in Room 12). A further 3 staff sit in Room 12 under the
`TEAM Academy Charter School` entity and gate through that branch instead. The
KTAF branch stays unconditional, preserving current behavior.

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
region branch at all — the unconditional
`ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KTAF') THEN TRUE` branch already
covers those rows for network viewers, and region viewers correctly do not see
historical network staff.

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
`KIPP TEAM and Family Schools Inc.`. Region branches then never match it, and
the unconditional KTAF branch covers it for network viewers — the same outcome
the flat map describes, reached in the view rather than in the calc.

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

Location gate — one line if `ISMEMBEROF()` accepts a non-literal argument on
this Server version, otherwise 26 explicit branches:

```text
ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])
```

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
