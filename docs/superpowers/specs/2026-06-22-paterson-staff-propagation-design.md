# Paterson staff propagation — design

Issue: [#4239](https://github.com/TEAMSchools/teamster/issues/4239)

## Goal

Paterson staff (ADP business-unit code `KPAT`, "KIPP Paterson") are now
incorporated into ADP. Make them propagate through the staff dbt models and
downstream system extracts like every other region — removing both the ADP-spine
exclusion filter and the PowerSchool-direct re-injection workarounds that only
existed because the spine excluded Paterson. Ship as a single PR, held until the
Ops data dependencies below are satisfied.

## Background — two lineages

Paterson staff handling splits across two source lineages:

- **ADP / HRIS spine.** A single exclusion in `int_people__staff_roster_history`
  drops Paterson before it reaches `int_people__staff_roster`. Every ADP-derived
  extract inherits the exclusion implicitly.
- **PowerSchool / SIS.** `rpt_illuminate__users`, `rpt_illuminate__roles`, and
  `rpt_clever__staff` re-inject Paterson (or exclude its schools) precisely
  because the ADP roster excluded it. Illuminate identifies teachers by the
  PowerSchool `teachernumber`; the roster resolves that same identifier via a
  crosswalk (below), so removing the workarounds is safe only once the crosswalk
  carries Paterson.

## Verified facts (prod, 2026-07-02)

- Paterson = `KPAT` / "KIPP Paterson", **94 current ADP workers**, 4 work
  locations: `KIPP Paterson Prep Elementary`, `KIPP Paterson Prep Middle`,
  `Room 12`, `Room 9`.
- **Full propagation, no employee-number gate.** `stg_people__employee_numbers`
  provisions a number for every current ADP worker (keyed on
  `worker_id__id_value`); all 94 Paterson workers have active provisioned rows.
  The roster's inner join uses this provisioned `employee_number`, so all 94
  propagate. (ADP's separate optional `custom_field__employee_number` is
  populated for only 21 of the 94, but nothing downstream depends on it for
  identity — it is not a gate.)
- **Illuminate teacher identity keys on the PowerSchool `teachernumber`.** The
  student-facing feeds `rpt_illuminate__mastschd` and `rpt_illuminate__roster`
  read `teachernumber` directly from PowerSchool, so a teacher's Illuminate
  `01 User ID` must equal their PS `teachernumber`. The roster derives
  `powerschool_teacher_number` as
  `coalesce(people__powerschool_crosswalk.powerschool_teacher_number, employee_number)`.
  The crosswalk is the **primary** mechanism network-wide (1,579 of 1,761 active
  rows carry a `powerschool_teacher_number` that differs from
  `employee_number`), not an exception patch. Paterson's PS `teachernumber`
  values are a disjoint ID space from employee numbers (zero-padded, four digits
  or fewer; 0 of the current Paterson employee numbers match any Paterson PS
  `teachernumber`), so Ops must add Paterson teachers to the crosswalk. **Ops
  gate.**
- **Coupa** crosswalks cover `KPAT`: school-name, Intacct fund / program /
  department / location lookups, and all 4 Paterson work locations in the
  address-name crosswalk. No code change, no Ops gap.
- **Egencia** `traveler_groups` has 3 explicit "KIPP Paterson" rows plus a
  `'General Traveler Group'` coalesce fallback (cannot NULL). No gap.
- **Zendesk** `zendesk_org_lookup` had 3 Paterson rows mis-keyed
  `adp_business_unit = 'KIPP_Paterson'` while the join expects the ADP code
  `KPAT` (every other region keys on `KCNA` / `KIPP_MIAMI` / `KIPP_TAF` /
  `TEAM`), so they did not join. Ops has re-keyed them to `KPAT`. **Re-verify
  after staging refresh**; confirm a `KPAT` + `Room 9` row exists (a 4th
  Paterson work location with no lookup row under any Paterson key).
- **`int_people__temp_staff`** carries 8 Paterson `TMP%` rows. These are an
  LDAP-side lag (LDAP still shows a `TMP` `employee_id` while ADP already holds
  the provisioned number). They drop out of `temp_staff` once LDAP `employee_id`
  is updated to the real number, at which point they arrive via the spine. **Ops
  gate** (LDAP update).

## Changes

### 1. ADP spine — `int_people__staff_roster_history`

Remove the two Paterson conditions in the ADP Workforce Now branch; that also
removes their `coalesce(..., '')` wrappers, which only existed to guard the
comparison:

```sql
-- before
where
    w.effective_date_end >= '2021-01-01'
    and coalesce(w.organizational_unit__home__business_unit__name, '')
    != 'KIPP Paterson'
    and coalesce(w.organizational_unit__assigned__business_unit__name, '')
    != 'KIPP Paterson'

-- after
where w.effective_date_end >= '2021-01-01'
```

This propagates Paterson into `int_people__staff_roster` and automatically into
every ADP-derived extract (see blast radius below).

### 2. Illuminate users — `rpt_illuminate__users`

Remove the PowerSchool-direct Paterson union branch (the
`stg_powerschool__users where _dbt_source_relation like '%kipppaterson%'` block
that hardcodes `'KIPP Paterson'`). After removal, Paterson teachers arrive via
the roster branch with `01 User ID = powerschool_teacher_number`, which resolves
to the PS `teachernumber` through the crosswalk and therefore matches the
`teachernumber` in `mastschd` / `roster`. Depends on the crosswalk Ops gate.

The `01 User ID` column has a `unique` (severity `error`) test; leaving the
PS-direct branch in place while Paterson also enters via the roster would
duplicate teachers (and collide on the one crosswalk-covered row), so this
removal is required, not optional, once the spine filter is gone.

### 3. Illuminate roles — `rpt_illuminate__roles`

Remove the Paterson PS-direct branch (the "Paterson = all schools in region"
`union all` reading `stg_powerschool__users ... '%kipppaterson%'`). Not named in
the issue's scope, but required: after the crosswalk resolves Paterson to the PS
`teachernumber`, this branch emits the same
`(01 Local User ID, 02 Site ID, ...)` keys as the surviving school/campus
branches and would fail the model's `dbt_utils.unique_combination_of_columns`
test.

**Open point to resolve in the plan.** The deleted branch grants Paterson staff
_region-wide_ roles (cross join to all Paterson schools). The surviving branches
grant _home-school_ (or campus) roles, and `roles` has no
`school_id = 0 → region` branch like Clever's `assignments` CTE. Paterson CMO /
regional staff at `Room 12` / `Room 9` carry
`home_work_location_powerschool_school_id = 0`, so the school-based branch would
emit `Site ID = 0`. Decide whether Paterson regional staff need a region-wide
roles branch or whether home-school assignment is acceptable.

### 4. Clever staff — `rpt_clever__staff`

Remove the `and _dbt_source_relation not like '%kipppaterson%'` condition in the
`schools` CTE so Paterson schools are assignable. Paterson staff enter via the
roster once the spine filter is gone. The Paterson location crosswalk already
carries `powerschool_school_id` (Prep Elementary `1234`, Prep Middle `2`,
`Room 12` / `Room 9` `0`), so staff resolve to a school via the existing school
/ campus assignment branches — no campus-crosswalk gap.

### 5. No code change

- **`int_people__temp_staff`** — self-resolves once the LDAP `employee_id`
  update lands (Ops gate). No edit.
- **`rpt_lattice__users`** — already carries a
  `home_business_unit_name = 'KIPP Paterson'` inclusion clause and Paterson
  region mapping, dead today because the roster excludes Paterson. It starts
  receiving data once the spine filter is gone. Do **not** remove it.
- **`rpt_coupa__users`, `rpt_egencia__users`, `rpt_zendesk__users`** — read the
  roster, no explicit Paterson filter. They flow once the spine filter is gone;
  crosswalk coverage is verified (Coupa) / fallback-safe (Egencia) /
  re-keyed-and-pending-verify (Zendesk).

## Auto-propagation blast radius

Removing the spine filter propagates Paterson into **every** model that reads
`int_people__staff_roster` — roughly 50 extracts, not only the handful named in
the issue. Beyond Coupa / Egencia / Zendesk / Lattice these include the AppSheet
rosters, all `rpt_gsheets__*` staff feeds, `rpt_clever__teachers`, `rpt_idauto`,
`rpt_blissbook`, `rpt_schoolmint_grow__users`, and the `rpt_tableau__*` staff
dashboards. Verification must rebuild that whole subgraph and confirm every
uniqueness / contract / not-null test holds with Paterson rows present — not
only the hand-edited models.

## Pre-merge Ops gates (single PR held until all satisfied)

1. **`people__powerschool_crosswalk`** populated for Paterson teachers
   (`employee_number → PS teachernumber`); teacher-number resolution re-verified
   after a staging refresh.
2. **`zendesk_org_lookup`** Paterson rows re-keyed to `KPAT` (done by Ops);
   re-verify the join resolves after a staging refresh, and confirm a `KPAT` +
   `Room 9` row exists.
3. **LDAP `employee_id`** updated to the provisioned number for the 8 Paterson
   `TMP%` records, so they leave `int_people__temp_staff`.

Ops-owned Google Sheet edits require re-staging
(`stage_external_sources --target staging`) and a staging rebuild before the
`zz_stg_*` / prod copies reflect them — verify against the rebuilt table, not
the current materialized copy.

## PR-description deliverable — Paterson crosswalk mapping table

Generate (after the spine change + staging refresh make the joins resolvable) a
distinct table of what each Paterson staff configuration resolves to across the
external crosswalks, and paste it into the PR description. Grain: one row per
distinct combination of the join keys occupied by Paterson staff.

Key fields (join grain): `home_business_unit_code`, `home_business_unit_name`,
`home_work_location_reporting_name`, `home_department_name`, `job_title`.

Value fields:

- **Coupa** — `coupa_school_name`, `sage_intacct_fund`, `sage_intacct_program`,
  `sage_intacct_department`, `sage_intacct_location`, `default_address_name`
- **Egencia** — `traveler_group`
- **Zendesk** — `zendesk_organization`, `zendesk_secondary_location`

Any NULL value is a crosswalk gap to fix before merge. These are config-level,
deidentified mappings (BU / location / role → external values) and are safe to
publish. The PowerSchool teacher-number crosswalk maps `employee_number` (a
direct identifier) and stays local — report it as a coverage count (e.g. "N of N
Paterson teachers mapped"), not as employee-level pairs.

## Verification

Rebuild the staff-roster subgraph and affected extracts in dev / CI:

```bash
uv run dbt build --select int_people__staff_roster_history+ \
  --project-dir src/dbt/kipptaf
```

Confirm with Paterson rows present:

- Uniqueness / PK tests hold (no Paterson-driven duplication) on
  `int_people__staff_roster`, `rpt_illuminate__users`, `rpt_illuminate__roles`,
  `rpt_clever__staff`, and the high-traffic ADP extracts (`rpt_coupa__users`,
  `rpt_egencia__users`, `rpt_zendesk__users`).
- Contract enforcement holds on the contracted extracts.
- Null-coverage: Paterson staff resolve non-NULL school / address / Intacct
  (Coupa), traveler group (Egencia), organization (Zendesk); Paterson teachers
  resolve to the real PS `teachernumber` (Illuminate / Clever) and their
  Illuminate `01 User ID` matches `mastschd` / `roster`.
- Approximately 94 Paterson staff appear in `int_people__staff_roster`.

## Out of scope

- **Student-facing Paterson filters** — Clever `students` / `schools` /
  `sections` / `enrollments`, Illuminate `roster` / `mastschd` / `studemo` and
  the other student feeds, Tableau gradebook / assessment feeds, gsheets student
  feeds, and `stg_people__student_logins`. These are student models gated on
  Paterson's PowerSchool readiness (#4193), not staff propagation.
- **Populating the Ops-owned Google Sheets** — tracked as the pre-merge gates
  above, executed by Ops, not in this PR.
