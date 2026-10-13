# Plan: Cube Access — Individual Exceptions Redesign (Additive Location Grants)

**Branch:** `kverhoff/feat/cube-individual-access-layer` (building directly on
this branch — no tracking issue opened, per author's direction).

**Related spec:**
[`2026-06-03-cube-security-redesign.md`](../specs/2026-06-03-cube-security-redesign.md)
— this plan implements a redesign of that spec's "individual exception" tier
only. The role crosswalk (`cube_access_role`) and department override
(`cube_access_department_override`) sheets, and their coalesce mechanism, are
**unchanged**.

**Date:** 2026-07-29 (revised same-day: multiple rows per employee now allowed,
the `'All'` sentinel removed entirely — see §3.3 and §3.7 below, which supersede
the initial draft's single-row / `'All'`-supporting design).

## 1. Problem statement

### 1.1 Current-state bug

`dim_staff_cube_access.sql` already left-joins
`stg_google_sheets__people__cube_access_individual_exceptions` as `exc`, but the
`coalesce()` chain that resolves each scope column never references `exc.*` —
only `ovr` (department override) and `rl`/`rp` (role). **Individual exceptions
currently have zero effect.** This plan fixes that as part of the redesign.

### 1.2 Why a redesign, not just wiring the existing columns in

The sheet's current columns (`student_location_scope`, `staff_location_scope` as
full-value overrides) can only ever **replace** a person's location scope with a
single new tier. That can't express the actual request: "give this one person
access to _one or more extra_ schools/regions on top of whatever their role
already grants, without touching anyone else's role-based access or downgrading
anything." The new column set
(`additional_location_type`/`additional_location_name`/`include_student_data`)
plus an approval-workflow audit trail
(`business_justification`/`requested_by`/`approved_by`/`grant_date`/`expiry_date`/`status`)
replaces the override mechanism for location only; the five `staff_*_scope`
remit columns keep the existing override/coalesce mechanism.

## 2. Design summary

`cube_access_individual_exceptions` is keyed on `employee_number`, but **an
employee may now have more than one row.** Each row grants **one** additional
location (a network, a named region, or a named school); a person who needs
access to two schools gets **two rows**, one per school — not one row with a
combined value. This is a deliberate change from the initial draft of this plan
(which assumed one row per employee); see §3.7 for why the original design was
one row, and what changed to allow more.

Each live row (`status = 'active'`, not past `expiry_date`, not before
`grant_date` — see §3.5) can do two independent things:

1. **Override** any of the five staff sensitive-field scopes
   (`staff_department_scope`, `staff_pii_scope`, `staff_compensation_scope`,
   `staff_observations_scope`, `staff_benefits_scope`) — same mechanism as
   today, same vocabulary, now actually wired into the coalesce chain as the
   highest-priority tier. **At most one live row per employee may set these**
   (enforced by a new test — see §3.7); they describe the person, not a specific
   location, so they don't multiply across rows the way location grants do.
2. **Grant** one additional location (a network, a named region, or a named
   school) that is **unioned into** — not substituted for — the person's
   existing location remit. `include_student_data` decides whether that specific
   grant also widens student-data visibility, or is staff-only — this flag is
   **per-row**, so one person's two location grants can differ (e.g., staff-only
   for one school, staff+student for another).

The union requires Cube's row-level security to move from a single per-viewer
tier (today: `network`/`region`/`school`, always "mine") to an
**array-of-allowed-locations** remit — a pattern that already exists for
`staff_pii` (`securityContext.allowed_abbreviations`) but does not yet exist for
students. This plan generalizes it to cover both, and additionally generalizes
it to accept **N** location grants per person, not just one.

There is no `'All'` value anywhere in `additional_location_name`. To grant
literally everything, use `additional_location_type = network` (one row —
`network` already means "the whole network," no enumeration needed). To grant
several specific regions or schools, add one row per region/school. See §3.3 for
why the `'All'` shortcut was removed, and §11 for the user-guide task that will
document this for the data team.

## 3. Trade-offs considered

Each of these was surfaced during planning and confirmed with the branch author
before writing this document.

### 3.1 Additive grant vs. full override

- **Chosen: additive** (union with existing scope).
- **Alternative:** override — same coalesce pattern as the five remit columns,
  reusing `student_location_scope`/`staff_location_scope` as-is.
- **Why additive:** an override can only replace a person's whole location scope
  with one new tier — it cannot express "your normal region scope, PLUS one
  specific other school," which is the actual ask (a temporary or cross-region
  project grant that doesn't touch the person's home-region access).
- **Cost:** override would have been a same-shape column swap with no
  architecture change. Additive requires generalizing Cube's row-level security
  (see 3.2) — a materially larger change (`access.js`, `cube.js`, 4 view YAML
  files, unit tests).

### 3.2 Student RLS: keep 3 tier-groups vs. collapse to 1 array-based group

- **Chosen: collapse** `student-region`/`student-school`/`student-network` into
  a single `student` group whose `row_level` filters on
  `abbreviation IN { securityContext.allowed_student_abbreviations }` —
  mirroring the `staff_pii` precedent exactly.
- **Alternative:** keep the 3 tier-groups; additive grants only take effect when
  they resolve to a whole tier the existing groups already support (i.e.,
  `network`-wide grants work, but "add this one specific extra school" silently
  no-ops for students).
- **Why collapse:** the tier-group model has no way to express "my region, plus
  one named school in a different region" — tiers are single-valued. An
  array-based remit is the only mechanism that supports an arbitrary extra
  location, and it's already proven (staff_pii ships it today).
- **Cost:** this is the largest single piece of this plan. It changes
  `buildGroups`'s emitted group set (breaking change to `access.js` and its unit
  tests), requires a new `allowed_student_abbreviations` field on
  `securityContext`, and touches **all 4 student views**
  (`student_enrollments_view`, `student_section_enrollments_view`,
  `student_attendance_view`, `student_assessment_scores_view`). It also changes
  runtime behavior for **every** viewer, not just those with exceptions: a
  `network`-scope viewer's query now compiles with an `IN (...)` filter over the
  full location universe instead of no filter at all. Functionally equivalent,
  non-zero but immaterial compile/perf cost.
- **Now must also handle N grants per person, not 1** — see §3.7's mart-shape
  change. `access.js` doesn't call the union logic once per viewer; it loops
  over every live grant row for that viewer and unions all of them, per-grant
  `includes_student_data` deciding whether each one also feeds the student
  array.

### 3.3 `'All'` was removed entirely — not just made asymmetric

The initial draft of this plan gave `additional_location_name` an `'All'`
sentinel value (`region + All` → network-wide; `school + All` → all schools in
the viewer's own region) to cover "grant everything at this tier." **That value
is removed.** If a TEAM (Newark) employee needs access to all three other
regions, the data team adds **three rows** — one per region — not one row with
`additional_location_name = 'All'`.

- **Chosen: no `'All'` value; list every additional location as its own row.**
- **Alternative (the initial draft):** keep `'All'`, with the asymmetric
  resolution described above.
- **Why removed:** two reasons.
  1. **It was a genuine UX trap.** `region + All` and `school + All` looked
     parallel but resolved to very different breadths (every region vs. only the
     viewer's own region) — exactly the kind of asymmetry that gets misread by
     whoever is filling in the sheet, with a security consequence if misread
     toward the broader reading.
  2. **It bought no expressiveness once multiple rows are allowed (§3.7).**
     `region + All` (network-wide) is already fully covered by
     `additional_location_type = network` on a single row. `school + All` (all
     schools in one's own region) is already fully covered by
     `additional_location_type = region` naming that same region by its
     `legal_entity` — which was already a supported case, "All" was never
     required to reach it. So removing `'All'` loses nothing; it only removes a
     shortcut that was more confusing than it was worth.
- **Cost:** the data team must enumerate multiple rows for a multi-region grant
  instead of writing one row with `'All'`. This is more sheet rows for the
  (presumably rare) "give this person several specific regions" case, traded for
  zero ambiguity about what any single row means. A user guide (§11) will
  document this explicitly, including the "just use `network`" shortcut for the
  true "everything" case.
- **Resolution logic simplification**: removing `'All'` also removes the
  self-referential "join to the viewer's own region" case entirely — see the
  simplified §5.1 (the initial draft's `school + All → e.region_key` branch is
  gone).

### 3.4 PR scope — full stack vs. dbt-only now, Cube follow-up later

- **Chosen: full stack, one PR** — sheet, staging, mart, `access.js`, `cube.js`,
  and all 4 view YAML files land together.
- **Alternative:** ship the dbt/mart side first; defer `cube.js`/view changes to
  a follow-up.
- **Why full stack:** a dbt-only PR would leave the mart's new columns fully
  resolved but **completely unenforced** — any exception the data team adds in
  the interim silently does nothing, which is worse than the current
  dead-`exc`-join bug because it would look configured and live.
- **Cost:** one larger PR spanning two projects (`src/dbt/kipptaf`, `src/cube`)
  instead of two smaller reviewable ones.

### 3.5 Status/expiry/grant-date gating — enforced in dbt vs. sheet-only governance

- **Chosen: enforce `status`, `expiry_date`, AND `grant_date` in dbt.** The join
  predicate to the exceptions staging model requires:

  ```sql
  status = 'active'
  and (expiry_date is null or expiry_date >= current_date('America/New_York'))
  and (grant_date is null or grant_date <= current_date('America/New_York'))
  ```

  A `revoked` row, a past-`expiry_date` row, or a **future-dated** `grant_date`
  row is excluded from the live set — a grant does not take effect before its
  `grant_date`, and stops applying once past `expiry_date`, regardless of
  `status` still saying `active` (both conditions gate independently; either one
  failing excludes the row).

- **This revises the initial draft**, which treated `grant_date` as audit-only
  (matching `notes`/`business_justification`). The branch author confirmed:
  **future grant dates take effect on the grant date, not before** — so
  `grant_date` is now a real gate, symmetric with `expiry_date` (both default to
  "no constraint" when blank: a null `grant_date` means "already in effect"; a
  null `expiry_date` means "never expires").
- **Why enforce:** a revocation/scheduling workflow that doesn't actually gate
  on dates until someone manually flips `status` is a real gap — a row entered
  ahead of time for a grant starting next month would otherwise apply
  immediately.
- **Cost:** two extra join predicates (now `status` + `expiry_date` +
  `grant_date`, all three gating the same live-row set); negligible.

### 3.6 Where the abbreviation-set union is computed — dbt vs. `access.js`

- **Chosen: `access.js`.** `dim_staff_cube_access` only resolves **scalars per
  grant** (a scope tier + `region_key`/`abbreviation` identity + a per-grant
  `includes_student_data` flag), packaged as an array of structs (one struct per
  live grant row — see §3.7); `resolveAccess` loops over that array and calls
  the existing pure `computeAllowedAbbreviations` helper once per grant,
  unioning the results.
- **Alternative:** precompute the final unioned array of abbreviations in dbt.
- **Why `access.js`:** the "universe" of all locations
  (`loadUniverses`/`computeAllowedAbbreviations`) is already a single source of
  truth living in `access.js`, refreshed independent of dbt builds. Duplicating
  it in dbt would mean re-materializing `dim_staff_cube_access` every time a
  location is added/renamed just to keep the array current, and would fork the
  "what does `network` mean" logic across two languages. This isn't a live open
  question — it's documented here because it's the reason the mart's new column
  is an array of small scalar structs, not a precomputed abbreviation array.

### 3.7 Why one row per employee originally, and what changes to allow more

**Why the initial draft assumed one row per employee:** the original design
carried the additive grant as four scalar columns
(`additional_location_scope`/`additional_region_key`/
`additional_location_abbreviation`/`grants_student_data`) on
`dim_staff_cube_access`, joined via a plain `LEFT JOIN` to the exceptions
staging model. A plain scalar `LEFT JOIN` assumes at most one matching row per
join key — if two rows matched the same `employee_number`, the join would fan
out `dim_staff_cube_access` to more than one row per `staff_key`, breaking its
`unique`/`not_null` primary-key contract (every mart consumer, including the
Cube `staff` cube's join, assumes exactly one row per `staff_key`). The staging
model's `unique` test on `employee_number` existed specifically to guarantee
that scalar join stayed safe.

**Confirmed: multiple rows per employee are now allowed** — e.g., an
expired/superseded grant kept as history alongside a current one, or two
simultaneous grants to two different schools/regions. This requires:

1. **Drop the `unique` test on `employee_number`** in the staging model's
   properties YAML (keep `not_null`).
2. **Add a new data-quality test**: at most one _live_ row per employee may set
   a non-null value in any of the five `staff_*_scope` remit columns. Without
   this, two live rows disagreeing on (say) `staff_pii_scope` would need an
   arbitrary precedence rule — the test instead makes that ambiguity a caught
   data-entry error rather than a silent pick. See the illustrative singular
   test in §8.
3. **Restructure `dim_staff_cube_access`'s join** from a single scalar
   `LEFT JOIN` to two aggregations, both grouped by `employee_number`:
   - one that resolves the (at-most-one) remit-override row per employee (safe
     to pick via `max()` once the test in step 2 holds — see §5.1);
   - one that `ARRAY_AGG`s every live location-grant row into a struct array,
     preserving `dim_staff_cube_access`'s 1-row-per-`staff_key` grain while
     carrying however many grants that person has.
4. **Change the mart's exposed column shape** from four scalars to one
   `additional_location_grants ARRAY<STRUCT<...>>` column (§4.3).
5. **`access.js` iterates the array** instead of reading one grant — calling
   `computeAllowedAbbreviations` once per element and unioning everything;
   `includes_student_data` is read per-element, not once per viewer.

## 4. Schema changes — before / after

### 4.1 Sheet & source (`sources-external.yml`)

```text
BEFORE (src_google_sheets__people__cube_access_individual_exceptions):
  employee_number          STRING
  student_location_scope   STRING   <- removed
  staff_location_scope     STRING   <- removed
  staff_department_scope   STRING
  staff_pii_scope          STRING
  staff_compensation_scope STRING
  staff_observations_scope STRING
  staff_benefits_scope     STRING
  notes                    STRING

AFTER:
  employee_number           STRING
  additional_location_type  STRING    <- new
  additional_location_name  STRING    <- new
  include_student_data      BOOLEAN   <- new
  staff_department_scope    STRING    (unchanged)
  staff_pii_scope           STRING    (unchanged)
  staff_compensation_scope  STRING    (unchanged)
  staff_observations_scope  STRING    (unchanged)
  staff_benefits_scope      STRING    (unchanged)
  business_justification    STRING    <- new
  requested_by              STRING    <- new
  approved_by                STRING   <- new
  grant_date                DATE      <- new
  expiry_date                DATE     <- new
  status                    STRING    <- new
  notes                     STRING    (unchanged)
```

### 4.2 Staging model

SQL unchanged
(`select *, from {{ source(...) }} where employee_number is not null`).
Properties YAML gains the new columns; `not_null` stays on `employee_number` but
**`unique` is dropped** (§3.7); adds `not_null`/ `accepted_values` on `status`,
`accepted_values` on `additional_location_type`, a new singular test for "at
most one live remit-override row per employee" (§3.7, §8), a warn-level
`expiry_date >= grant_date` check, a check that `additional_location_name` is
populated whenever `additional_location_type` is `region` or `school`, and
`config.meta.contains_pii: true` (see §1 — `requested_by`/`approved_by` are
employee numbers, a direct identifier under FERPA per root `CLAUDE.md`'s PII
reference).

### 4.3 `dim_staff_cube_access` mart — new column

```text
additional_location_grants   ARRAY<STRUCT<
    location_scope             STRING,   -- network / region / school
    region_key                 STRING,   -- populated only when location_scope = 'region'
    location_abbreviation      STRING,   -- populated only when location_scope = 'school'
    includes_student_data      BOOL
>>
```

One struct per **live** location-grant row for that person (empty array, never
NULL, when they have none). This supersedes the initial draft's four scalar
columns (`additional_location_scope`/`additional_region_key`/
`additional_location_abbreviation`/`grants_student_data`) — those assumed
exactly one grant per person; an array is required now that a person can have
any number (§3.7).

The existing `student_location_scope` / `staff_location_scope` columns are
**unchanged** — they still resolve from department override → role only
(exceptions no longer participate in that coalesce; they participate in the new
additive column instead). The five `staff_*_scope` remit columns keep their
existing coalesce chain, with the individual-exception tier now actually wired
in (the bug fix), sourced from the at-most-one live remit-override row per
employee (§3.7).

### 4.4 `access.js` / `cube.js` `securityContext` — shape change

```text
BEFORE:
  allowed_abbreviations        -- staff remit array (role/dept ∩ location)
  student_location_scope       -- single tier, consumed by 3 view groups

AFTER:
  allowed_abbreviations         -- staff remit array, now UNIONED with the
                                   abbreviations from EVERY live grant in
                                   row.additional_location_grants (always,
                                   regardless of includes_student_data)
  allowed_student_abbreviations -- NEW: base student-scope array, UNIONED
                                   with the abbreviations from only the
                                   grants where includes_student_data = true
  (student_location_scope removed from securityContext — superseded by the
   array)
```

### 4.5 View `access_policy` — student views (×4)

```yaml
# BEFORE (student_enrollments_view.yml, and identically in the other 3):
access_policy:
  - group: student-region
    row_level:
      filters:
        - member: locations_region_key
          operator: equals
          values: ["{ securityContext.region_key }"]
  - group: student-school
    row_level:
      filters:
        - member: locations_abbreviation
          operator: equals
          values: ["{ securityContext.location_abbreviation }"]
  - group: student-network
    # no row_level

# AFTER:
access_policy:
  - group: student
    member_level:
      includes: "*"
    row_level:
      filters:
        - member: locations_abbreviation
          operator: equals
          values: "{ securityContext.allowed_student_abbreviations }"
```

Each view's actual flat member name for the abbreviation
(`locations_abbreviation` vs. an unprefixed `abbreviation`, etc.) must be
verified per-view from its own `includes:`/`prefix:` block before writing the
filter — do not assume it matches `student_enrollments_view`.

## 5. Column reference — possible values & resolution rules

| Column                     | Type    | Possible values                                                                                                                                                                                                                                                                                                                             | Enforced in dbt?                                                                                                     |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `employee_number`          | STRING  | any valid staff ID (repeatable — an employee may have multiple rows)                                                                                                                                                                                                                                                                        | `not_null` (error); **no longer `unique`** (§3.7)                                                                    |
| `additional_location_type` | STRING  | `network`, `region`, `school`, or blank (no grant on this row)                                                                                                                                                                                                                                                                              | `accepted_values` (error) when present                                                                               |
| `additional_location_name` | STRING  | any entry from the `Region`/`Name` values on the locations sheet, or blank when `type` is blank/`network`. For `additional_location_type` = `school` the value must match the `name` from `kipptaf_marts.dim_locations`. For `additional_location_type` = `region` the value must match the `legal_entity` from `kipptaf_marts.dim_regions` | no enum test; required (not-null) when `type` is `region` or `school`; matched against `dim_regions`/`dim_locations` |
| `include_student_data`     | BOOLEAN | `true`, `false`, blank (→ `false`)                                                                                                                                                                                                                                                                                                          | none — read per-row                                                                                                  |
| `staff_department_scope`   | STRING  | `all`, `own_group`, `none`, blank                                                                                                                                                                                                                                                                                                           | `accepted_values` (error) — unchanged from today                                                                     |
| `staff_pii_scope`          | STRING  | `none`, `all_in_scope`, `reporting_chain_or_below_rank`, `reporting_chain`, `teaching_staff`, blank                                                                                                                                                                                                                                         | `accepted_values` (error) — unchanged                                                                                |
| `staff_compensation_scope` | STRING  | same 5-value vocabulary as `staff_pii_scope`                                                                                                                                                                                                                                                                                                | `accepted_values` (error) — unchanged                                                                                |
| `staff_observations_scope` | STRING  | same 5-value vocabulary                                                                                                                                                                                                                                                                                                                     | `accepted_values` (error) — unchanged                                                                                |
| `staff_benefits_scope`     | STRING  | same 5-value vocabulary                                                                                                                                                                                                                                                                                                                     | `accepted_values` (error) — unchanged                                                                                |
| `business_justification`   | STRING  | free text                                                                                                                                                                                                                                                                                                                                   | none — audit only, never read by `dim_staff_cube_access`                                                             |
| `requested_by`             | STRING  | any valid staff ID                                                                                                                                                                                                                                                                                                                          | none — audit only                                                                                                    |
| `approved_by`              | STRING  | any valid staff ID                                                                                                                                                                                                                                                                                                                          | none — audit only                                                                                                    |
| `grant_date`               | DATE    | any date, or blank (→ already in effect)                                                                                                                                                                                                                                                                                                    | gates whether the row is live (§3.5); warn: `expiry_date >= grant_date`                                              |
| `expiry_date`              | DATE    | any date, or blank (→ never expires)                                                                                                                                                                                                                                                                                                        | gates whether the row is live (§3.5); warn: `expiry_date >= grant_date`                                              |
| `status`                   | STRING  | `active`, `expired`, `revoked`                                                                                                                                                                                                                                                                                                              | `accepted_values` + `not_null` (error) — gates whether the row is live                                               |
| `notes`                    | STRING  | free text                                                                                                                                                                                                                                                                                                                                   | none — audit only, unchanged from today                                                                              |

### 5.1 Resolving each live row into a grant struct

```sql
-- illustrative; final column/join names settle at implementation time.
-- No 'All' branch anymore (§3.3) -- each type maps to exactly one scope.
case
    when exc.additional_location_type = 'network' then 'network'
    when exc.additional_location_type = 'region' then 'region'
    when exc.additional_location_type = 'school' then 'school'
    else 'none'
end as location_scope,

case
    when exc.additional_location_type = 'region'
        then reg.region_key                 -- dim_regions.legal_entity match
    else cast(null as string)
end as region_key,

case
    when exc.additional_location_type = 'school'
        then loc.abbreviation               -- dim_locations.name match
    else cast(null as string)
end as location_abbreviation,

coalesce(exc.include_student_data, false) as includes_student_data
```

Join targets: `reg` = `dim_regions` on
`exc.additional_location_name = reg.legal_entity` (matches values like
`TEAM Academy Charter School`, `KIPP Cooper Norcross Academy`, `KIPP Miami`,
`KIPP TEAM and Family Schools Inc.`). `loc` = `dim_locations` on
`exc.additional_location_name = loc.name` (matches individual school/campus/room
names like `KIPP Rise Academy`, `Room 9`, `18th Ave Campus`). Rows where
`additional_location_type` is blank are excluded before this resolution runs
(they contribute no grant — see Example F in §6) and are handled purely through
the remit-override aggregation instead.

## 6. Worked examples

**A — Network-wide grant** (e.g., a central Data Team analyst staffed on a
cross-region project — one row, no enumeration needed):

```text
employee_number=012345, additional_location_type=network,
additional_location_name=(blank), include_student_data=TRUE,
staff_pii_scope=all_in_scope, status=active, expiry_date=2026-12-31

→ location_scope = network, includes_student_data = true
→ allowed_abbreviations         = every abbreviation in the network
→ allowed_student_abbreviations = every abbreviation in the network
```

**B — Named region grant, staff-only** (a Newark-based coach picking up a Camden
project, no student-data need):

```text
employee_number=023456, additional_location_type=region,
additional_location_name='KIPP Cooper Norcross Academy',
include_student_data=FALSE, status=active, expiry_date=2026-09-01

→ location_scope = region, region_key = <Camden's region_key>,
  includes_student_data = false
→ allowed_abbreviations         = base (their own Newark-region set) ∪ every Camden abbreviation
→ allowed_student_abbreviations = base only (Camden students NOT added)
```

**C — Named school grant, both staff and student data**:

```text
employee_number=034567, additional_location_type=school,
additional_location_name='KIPP Life Academy', include_student_data=TRUE,
status=active

→ location_scope = school, location_abbreviation = <KIPP Life Academy's abbreviation>,
  includes_student_data = true
→ allowed_abbreviations and allowed_student_abbreviations both gain
  exactly that one school's abbreviation, on top of the person's base scope
```

**D — Two additional schools for the same employee** (demonstrates the multi-row
model — no combined value on one row; one row per school):

```text
Row 1: employee_number=045678, additional_location_type=school,
       additional_location_name='KIPP BOLD Academy', include_student_data=TRUE,
       status=active
Row 2: employee_number=045678, additional_location_type=school,
       additional_location_name='KIPP THRIVE Academy', include_student_data=FALSE,
       status=active

→ additional_location_grants = [
      { location_scope: school, location_abbreviation: <BOLD's abbreviation>,   includes_student_data: true  },
      { location_scope: school, location_abbreviation: <THRIVE's abbreviation>, includes_student_data: false }
  ]
→ allowed_abbreviations         = base ∪ {BOLD's abbreviation} ∪ {THRIVE's abbreviation}
→ allowed_student_abbreviations = base ∪ {BOLD's abbreviation}      (THRIVE excluded — includes_student_data=false on that row)
```

**E — Multiple regions instead of `'All'`** (a TEAM/Newark employee needing
access to every other region — three rows, since `'All'` no longer exists; see
§3.3):

```text
Row 1: employee_number=056789, additional_location_type=region,
       additional_location_name='KIPP Cooper Norcross Academy', status=active
Row 2: employee_number=056789, additional_location_type=region,
       additional_location_name='KIPP Miami', status=active
Row 3: employee_number=056789, additional_location_type=region,
       additional_location_name='KIPP TEAM and Family Schools Inc.', status=active

→ three grant structs, one per named region
→ allowed_abbreviations = base (Newark) ∪ every Camden abbreviation
                                ∪ every Miami abbreviation
                                ∪ every KTAF/central-office abbreviation
(Note: if this person actually needs literally everything, a single
 additional_location_type=network row is simpler than enumerating every
 region — this example is for "several specific regions," not "everything.")
```

**F — Remit-only row, no location grant** (demonstrates the two mechanisms are
independent):

```text
employee_number=067890, additional_location_type=(blank),
staff_compensation_scope=reporting_chain_or_below_rank, status=active

→ this row contributes NOTHING to additional_location_grants (excluded —
  additional_location_type is blank)
→ staff_compensation_scope IS overridden to reporting_chain_or_below_rank
  (via the now-fixed coalesce chain), independent of the (absent) location grant
```

**G — Expired grant (no effect)**:

```text
employee_number=078901, additional_location_type=school,
additional_location_name='KIPP Truth Academy', status=active,
expiry_date=2026-01-01   -- already past

→ excluded from the live-row set entirely (expiry_date < current_date)
→ contributes nothing to additional_location_grants
→ if this employee has no OTHER live rows, they fall through to
  department override → role exactly as if this row never existed
```

**H — Revoked grant (no effect)**:

```text
employee_number=089012, additional_location_type=network, status=revoked

→ excluded from the live-row set (status != 'active'), regardless of
  expiry_date/grant_date
→ contributes nothing, same as G
```

**I — One expired row and one active row for the same employee** (demonstrates
that rows are evaluated independently — an old grant rolling off doesn't affect
a separate current one):

```text
Row 1 (historical): employee_number=090123, additional_location_type=school,
                     additional_location_name='KIPP Sunrise Academy',
                     status=active, expiry_date=2025-06-30   -- expired
Row 2 (current):     employee_number=090123, additional_location_type=school,
                     additional_location_name='KIPP Seek Academy',
                     status=active, expiry_date=2026-12-31   -- still live

→ Row 1 excluded (past expiry_date); Row 2 included
→ additional_location_grants = [ { location_scope: school,
     location_abbreviation: <Seek's abbreviation>, includes_student_data: ... } ]
  (Sunrise is NOT present — its row is retained in the sheet for audit
  history, but contributes nothing once expired)
```

## 7. Decisions finalized this revision

1. **§3.7 — multiple rows per employee: RESOLVED, allowed.** The
   `employee_number` uniqueness test is dropped; the mart moves to an
   array-of-structs column; `access.js` unions across all live grants. See §3.7
   for the full "why one row originally, what changes" answer and §8 for the
   concrete task list.
2. **§3.5 — `grant_date`: RESOLVED, enforced.** A future `grant_date` now delays
   the grant — it does not apply before that date, reversing the initial draft's
   "audit-only" treatment.
3. **§3.3 — `'All'`: RESOLVED, removed entirely** (not just made asymmetric, as
   the initial draft proposed). Sheet instructions (the user guide, §11) will
   tell the data team to list every additional location as its own row;
   `additional_location_type = network` remains the one-row path for "grant
   literally everything."
4. **Sheet migration: DONE.** The data team has already migrated the live sheet
   to the new header set / re-authored existing rows. No outstanding migration
   task in §10.

5. **§7 (prior revision) — remit-column conflict across multiple rows: RESOLVED,
   confirmed.** At most one _live_ row per employee may set any of the five
   `staff_*_scope` remit columns; a dbt test hard-fails (`severity: error`,
   matching repo convention for staging-layer tests) if two live rows for the
   same employee disagree. The mental model this matches: remit-scope overrides
   are a per-person setting entered once (on whichever one row the data team
   chooses); every other row for that same person is purely a location grant.
   The alternatives considered and rejected — a "most recent `grant_date` wins"
   precedence rule, and splitting remit overrides and location grants into two
   separate row-types or sheets — are documented in §3.7 for context but are not
   being pursued.

## 8. Implementation task list

1. `models/google/sheets/sources-external.yml` — column set change (§4.1).
1. `models/google/sheets/staging/stg_google_sheets__people__cube_access_individual_exceptions.sql`
   — no change expected; confirm after columns land.
1. `models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_individual_exceptions.yml`
   — new column docs/tests; **drop `unique` on `employee_number`** (keep
   `not_null`); `status`/`additional_location_type` `accepted_values`;
   `expiry_date >= grant_date` warn check; `additional_location_name` required
   when `additional_location_type` in (`region`, `school`);
   `contains_pii: true`; and the new singular test (illustrative SQL below)
   enforcing "at most one live row per employee sets a remit-override column":

   ```sql
   -- tests/test_cube_access_individual_exceptions_single_remit_row.sql
   select employee_number, count(*) as n_remit_rows
   from {{ ref('stg_google_sheets__people__cube_access_individual_exceptions') }}
   where status = 'active'
       and (expiry_date is null or expiry_date >= current_date('America/New_York'))
       and (grant_date is null or grant_date <= current_date('America/New_York'))
       and (
           staff_department_scope is not null
           or staff_pii_scope is not null
           or staff_compensation_scope is not null
           or staff_observations_scope is not null
           or staff_benefits_scope is not null
       )
   group by employee_number
   having count(*) > 1
   ```

1. `models/marts/dimensions/dim_staff_cube_access.sql` — gate the exceptions
   join on `status`/`expiry_date`/`grant_date` (§3.5); restructure into two
   aggregations grouped by `employee_number` (§3.7): one resolving the
   at-most-one remit-override row (wire into the five coalesce chains — the bug
   fix), one `ARRAY_AGG`-ing every live location-grant row into the
   `additional_location_grants` struct array (§5.1), joining `dim_regions` and
   `dim_locations`.
1. `models/marts/dimensions/properties/dim_staff_cube_access.yml` — document the
   new `additional_location_grants` array column (pull the exact
   `ARRAY<STRUCT<...>>` contract syntax from a real build's
   `INFORMATION_SCHEMA.COLUMNS`, per `src/dbt/CLAUDE.md`'s guidance on large
   struct types — don't hand-transcribe).
1. `src/cube/access.js` — extend `buildSecurityContext` to iterate
   `row.additional_location_grants`, calling `computeAllowedAbbreviations` once
   per grant and unioning into `allowed_abbreviations` (always) and
   `allowed_student_abbreviations` (only for grants where
   `includes_student_data` is true); collapse `buildGroups`'s student tiers into
   a single `student` group with the same empty-array guard used for
   `staff-pii-*`.
1. `src/cube/access.test.js` — update unit tests for the new `buildGroups` /
   `buildSecurityContext` shapes, including a multi-grant case (mirroring
   Example D).
1. `src/cube/cube.js` — `resolveAccess` selects the new mart column and calls
   the extended `access.js` helpers.
1. `src/cube/cube.test.js` — update as needed.
1. Four student view YAMLs — collapse 3-group policy to 1 (§4.5), verifying each
   view's own `prefix:`/member-name convention before writing the filter:
   - `model/views/students/student_enrollments_view.yml`
   - `model/views/students/student_section_enrollments_view.yml`
   - `model/views/student_attendance/student_attendance_view.yml`
   - `model/views/student_assessments/student_assessment_scores_view.yml`
1. `src/cube/CLAUDE.md` — update the "View access policies" section's
   description of student RLS (3 tier-groups → 1 array-based group), matching
   the existing `staff_pii` description style.
1. **User guide (new — Ops-facing)**: see §11.
1. `docs/superpowers/specs/2026-06-03-cube-security-redesign.md` — optionally
   append a dated revision-history entry pointing to this plan (existing
   convention in that file); not required to implement the code change.

## 9. Validation plan

1. `node --test src/cube/access.test.js` (and `cube.test.js`) after the JS
   changes, including a multi-grant test case.
1. `uv run dbt build --select stg_google_sheets__people__cube_access_individual_exceptions+ dim_staff_cube_access --target dev --defer --state src/dbt/kipptaf/target/prod`
   — the sheet has already been migrated (§7.4), so this should be runnable
   directly.
1. Confirm `dim_staff_cube_access` stays 1:1 on `staff_key` (the array column
   must not fan out the grain) and every `accepted_values`/`not_null` test
   passes, including the new single-remit-row singular test.
1. Cube Dev Mode / SQL API RLS validation per `src/cube/CLAUDE.md`'s "Testing
   row-level security locally" section, across a viewer matrix: no exception
   (baseline unchanged), network grant, named-region grant (staff-only and
   staff+student), named-school grant, two simultaneous school grants (Example
   D), several-regions-via-multiple-rows (Example E), expired / revoked /
   not-yet-granted rows (confirm no effect), and the expired+active-together
   case (Example I). Requires the local dev server, which must be run by the
   branch author — not runnable from this session.

## 10. Rollout / sequencing

1. ~~Ship the header change to the Google Sheet~~ — **done** (§7.4); the data
   team has already migrated the sheet to the new schema.
1. Re-stage: `stage_external_sources --target staging` / `--target dev` as
   appropriate (classifier-blocked for `staging` — needs direct user
   authorization).
1. Land this plan's code changes on this branch.
1. Publish the user guide (§11) so the data team has the "no `'All'`, one row
   per location, `network` for everything" convention documented before they add
   further exception rows.
1. Validate end-to-end per §9, then merge.

## 11. User guide (Ops-facing) — new task

A short guide for whoever maintains the sheet (the data team / Ops), separate
from this engineering plan. Recommend a new file,
`docs/guides/cube-access-individual-exceptions.md` (added to `mkdocs.yml`
`nav:`, per `docs/CLAUDE.md`), rather than folding it into the existing
`docs/guides/google-sheets.md` — this sheet has enough dedicated structure (two
independent mechanisms, a lifecycle) to warrant its own page, cross-linked from
the general Google Sheets guide.

Must cover, in plain non-engineering language:

- **One row per additional location.** Need access to two schools? Two rows,
  same `employee_number`, one `additional_location_name` each — never combine
  two locations into one row.
- **No `'All'` option.** List every additional region/school you're granting,
  one row each. If someone genuinely needs the whole network, use
  `additional_location_type = network` on a single row instead of listing every
  region.
- **The two independent things a row can do**: grant a location (additive — on
  top of the person's normal access, never replacing it) and/or override one of
  the five sensitive-field visibility settings (replaces their normal setting
  for that field). A row can do either, both, or neither meaningfully (a row
  with neither is inert).
- **Lifecycle columns**: `status` (`active`/`expired`/`revoked`), `grant_date`
  (starts applying on this date, blank = immediately), `expiry_date` (stops
  applying after this date, blank = never). To revoke early, set
  `status = revoked` rather than deleting the row (keeps the audit trail).
- **Audit columns** (`business_justification`, `requested_by`, `approved_by`,
  `notes`) are for the data team's own record-keeping — worked examples should
  show a filled-in row so the expectation is clear.
- Worked examples mirroring §6 (A–I), in plain language rather than SQL.
