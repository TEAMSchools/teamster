# Tableau Workbook Remediation Runbook

> **For the human executing this:** every step happens in Tableau Desktop or on
> Tableau Server. There is no dbt work here — that shipped in PR #4656. Work one
> workbook at a time; each section below is self-contained and ends with its own
> verification.

**Goal:** every one of the 13 permission-gated workbooks keeps working before
**and** after the Entra ID identity cutover, with one canonical Permissions
block pasted across all of them apart from documented per-workbook variants.

**Design doc:**
`docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`. That
is the reasoning; this is the sequence. Where they disagree, the design doc is
authoritative and this file is stale.

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
1. **You have tested whether `ISMEMBEROF()` accepts a non-literal argument** on
   this Server version. Make a scratch calc:

   ```text
   ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])
   ```

   If it validates, the location gate is one line. If it does not, it becomes 26
   explicit `ISMEMBEROF` branches — one per school location, Rooms excluded.
   This single answer changes the size of every Tier 5 edit, so settle it first.

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
ELSEIF ISMEMBEROF('KNJ-SG-Tableau All Staff KTAF') THEN TRUE
ELSE FALSE END
```

The Paterson branch is new and unblocks 96 staff. The KTAF branch stays
unconditional, preserving current behaviour.

Two things not to "clean up" here. First, **single equality per branch** — dbt
now normalizes entity, so no extract can emit `TEAM`, `KCNA`, `MIA`, or `KNJ`
any more. Delete the old triple comparisons rather than carrying them forward;
an abbreviation branch cannot match anything and its presence implies the
extracts still emit abbreviations. Second, **the gate reads group membership,
not the viewer's own entity.** That is how cross-entity supervision works — a
TEAM employee who oversees Paterson gets Paterson visibility by being added to
the Paterson group, with no calc change. Deriving entity from the viewer's
roster row would silently revoke access from every cross-entity supervisor.

Location gate:

```text
ISMEMBEROF('KNJ-SG-Tableau All Staff ' + [location_clean_name])
```

Rooms are absent by design — central office reaches data through Tiers 2 and 4,
never through location. If prerequisite 3 failed, expand to 26 explicit
branches.

Role gate:

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
- **Verify:** a participant sees their own record; their manager sees it too

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
- **Location-gate variant on `operations_ekg`:** the Tier 5 location gate reads
  `[school_clean_name]`, not `[location_clean_name]`. Those are two different
  schools on this extract — `location_clean_name` comes from the roster join on
  the respondent, so gating on it shows a school leader the walkthroughs they
  **performed**, not the ones **of their school**. `school_clean_name` is the
  walked school, added in PR #4746; it must be merged and materialized before
  this workbook's Tier 5 edit.
- **Entity-gate variant on `operations_ekg`:** the Tier 5 entity gate reads
  `[school_business_unit_name]`, not `[home_business_unit_name]`, for the same
  reason — it is the entity of the walked school. Central-office staff walk
  schools in every region and would otherwise only ever match the unconditional
  KTAF branch, and no respondent on this form is based in KIPP Paterson, so the
  Paterson branch matches zero of the 25 Paterson Prep walkthroughs. **Drop the
  KTAF branch from this workbook's entity gate** — no school is owned by
  `KIPP TEAM and Family Schools Inc.`, so that branch can never match; central
  office reaches this data through Tiers 2 and 4. Column added in PR #4749.
- **Field the workbook loses:** `[School]` is removed from `operations_ekg` in
  PR #4749. Swap any use of it to `[school_clean_name]` in the same window, or
  the sheets referencing it break when the view rematerializes.
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
- **Verify:** a rated manager sees their own results; their manager sees them

### Manager Survey Rollup

- **Datasource change:** same repoint as Manager Survey Reports
- **Fields:** same seven `subject_*` repoints
- **Verify:** rollup totals match the pre-repoint numbers — the new extract
  wraps the same intermediate at the same grain, 175,670 rows, so any change in
  a total means a field was mapped wrong

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
| KTAF central office             | everything, via the unconditional KTAF branch         |
| Paterson school staff           | Paterson rows — this is the branch that did not exist |
| Room 12 staff under TEAM        | gates through the TEAM branch, not Paterson           |
| Cross-entity supervisor         | the supervised entity's rows, via group membership    |
| One of the 3 UPN-mismatch staff | self, proving the UPN hedge works                     |

### Cutover rehearsal

Tier 1 matches both identity forms, so it can be tested before IT switches
anything. Confirm a viewer resolves by `sam_account_name` today, and confirm the
same viewer's `mail` and `user_principal_name` values are present and correct in
the extract. If both hold, cutover needs no coordination.

### Confirm the individual grants are actually gone

Search each workbook's calcs for `USERNAME() =` comparisons against literal
strings. There should be none — Tier 1 compares against fields, never literals.
That search is the check that no individual grant survived.

Separately, confirm each of the 12 formerly-hardcoded individuals still has
access through a group. Losing them is the one regression this remediation could
plausibly introduce, and it is silent.

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
