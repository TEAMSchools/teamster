# Paterson staff propagation — design

Issue: [#4239](https://github.com/TEAMSchools/teamster/issues/4239)

## Goal

Paterson staff (ADP business-unit code `KPAT`, "KIPP Paterson", ~90 active
workers across 4 work locations) are now fully incorporated into ADP. Make them
propagate through the staff dbt models and downstream system extracts like every
other region, removing both the exclusion filters and the now-redundant
re-injection workarounds. Ship as a single PR, held until the two Ops data
dependencies below are satisfied.

## Background — two source systems

Staff Paterson handling splits across two lineages:

- **ADP/HRIS spine.** A single exclusion in `int_people__staff_roster_history`
  drops Paterson before it reaches `int_people__staff_roster`. Every ADP-derived
  extract inherits the exclusion implicitly.
- **PowerSchool/SIS.** `rpt_illuminate__users` and `rpt_clever__staff` are
  PowerSchool-sourced. Illuminate re-injects Paterson via a PS-direct union
  branch precisely because the ADP roster excluded it; Clever excludes Paterson
  schools outright.

## Verified facts (prod, 2026-06-22)

- Paterson = `KPAT` / "KIPP Paterson", ~90 active employees, 4 work locations.
- **Coupa** crosswalks cover `KPAT`: school-name lookup (41 rows), intacct
  fund/program/dept/location lookups, and all 4 Paterson work locations in the
  address-name crosswalk. No code change, no Ops gap.
- **Egencia** `traveler_groups` has 3 explicit `KPAT` rows and a
  `'General Traveler Group'` Default fallback. Functional; Paterson travelers
  default to the generic group until Ops adds rows (optional).
- **Zendesk** `zendesk_org_lookup` has 0 rows for `KPAT`; both Paterson schools
  are absent from the location crosswalk. Paterson staff would land with NULL
  org. **Ops gate.**
- **Illuminate / Clever** key on the real PowerSchool teacher number. The roster
  derives `powerschool_teacher_number` as
  `coalesce(people__powerschool_crosswalk.ps_teacher_number, employee_number)`.
  Only **1 of 90** Paterson staff is in that crosswalk, and there are **132**
  Paterson PS users with access vs. 90 ADP staff. **Ops gate + reconciliation.**

## Changes

### 1. ADP spine — `int_people__staff_roster_history`

Remove the two Paterson conditions in the ADP Workforce Now branch and collapse
the now-vestigial `coalesce(...)` wrappers that only existed to guard the
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
every ADP-derived extract: Coupa, Egencia, Zendesk, Lattice, AppSheet stipend
roster, survey links, PM assignment roster, staff info feed.

### 2. Coupa / Egencia — no code change

`rpt_coupa__users` and `rpt_egencia__users` read the roster and have no explicit
Paterson filter. They flow once the spine filter is gone. Crosswalk coverage is
verified (Coupa) / fallback-safe (Egencia).

### 3. Zendesk — no code change, Ops gate

`rpt_zendesk__users` flows once the spine filter is gone, but
`zendesk_org_lookup` must carry Paterson rows first (`KPAT` business unit + the
two Paterson school `location_clean_name` values) or Paterson staff get a NULL
organization. Hold merge until the sheet is populated; re-verify coverage.

### 4. Illuminate — `rpt_illuminate__users`, Ops gate + reconciliation

Remove the PowerSchool-direct Paterson union branch (the
`stg_powerschool__users where _dbt_source_relation like '%kipppaterson%'` block
that hardcodes `'KIPP Paterson'`). After removal, Paterson teachers come from
the roster branch like every other region. Pre-merge gates:

- Ops populates `people__powerschool_crosswalk` for Paterson staff so
  `powerschool_teacher_number` resolves to the real PS teacher number, not the
  `employee_number` fallback.
- Reconcile the 132-vs-90 gap: confirm the PS users not present in ADP are
  non-staff / historical and acceptable to drop (consistent with how other
  regions source Illuminate from the roster), or document why any must be
  retained.

### 5. Clever staff — `rpt_clever__staff`, depends on PS readiness

Remove the `and _dbt_source_relation not like '%kipppaterson%'` condition in the
`schools` CTE so Paterson schools are assignable. Paterson staff enter via the
roster once the spine filter is gone. Pre-merge verification:

- Paterson schools present in `stg_powerschool__schools` with
  `state_excludefromreporting = 0`.
- Paterson coverage in `people__campus_crosswalk` so staff resolve to a
  `powerschool_school_id`.

### 6. Lattice — no change

`rpt_lattice__users` already includes a
`home_business_unit_name = 'KIPP Paterson'` clause and a Paterson region
mapping. This is inclusion logic, dead today because the roster excludes
Paterson. It starts receiving data once the spine filter is gone. Do not remove
it — removing it would re-exclude Paterson.

## Pre-merge gates (single PR held until all satisfied)

1. `zendesk_org_lookup` populated for Paterson; coverage re-verified.
2. `people__powerschool_crosswalk` populated for Paterson staff; teacher-number
   resolution re-verified.
3. Illuminate 132-vs-90 PS-user gap reconciled and documented.
4. Clever PS-school + campus-crosswalk coverage verified.

## Verification

Rebuild the staff-roster subgraph and affected extracts in dev/CI:

```bash
uv run dbt build --select int_people__staff_roster_history+ \
  --project-dir src/dbt/kipptaf
```

Confirm with new Paterson rows present:

- Uniqueness / PK tests on `int_people__staff_roster`, `rpt_coupa__users`,
  `rpt_egencia__users`, `rpt_zendesk__users`, `rpt_illuminate__users`,
  `rpt_clever__staff` hold (no Paterson-driven duplication).
- Contract enforcement holds on the contracted extracts.
- Null-coverage checks: Paterson staff resolve non-NULL school/address/intacct
  (Coupa), traveler group (Egencia), org (Zendesk), PS teacher number
  (Illuminate/Clever).

## Out of scope

- Student-facing Paterson filters (Clever students/schools/sections/enrollments,
  Tableau gradebook/assessment/sight-words, gsheets student feeds,
  `rpt_google_directory__users_import` student email import,
  `stg_people__student_logins`). These are student models, not staff.
- Populating the Ops-owned Google Sheets — tracked as dependencies, executed by
  Ops, not in this PR.
