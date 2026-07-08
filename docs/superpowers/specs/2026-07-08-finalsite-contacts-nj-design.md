# Finalsite Student Contacts for NJ Regions — Design

- **Issue**: [#4346](https://github.com/TEAMSchools/teamster/issues/4346)
- **Date**: 2026-07-08
- **Status**: Approved design; discovery-dependent details flagged inline

## Problem

Student contact reporting for the NJ regions (Newark, Camden, Paterson) is
sourced from PowerSchool contact tables. Finalsite is becoming the source of
truth for student contacts in those regions. The PowerSchool contact models must
be deprecated as the reporting source and replaced with Finalsite data.

Contact reporting requirements for the new source:

1. Only the **top-ranked contact** from the Finalsite contacts module is
   reported.
2. The remaining reported contacts are **emergency contacts**, sourced from 4
   sets of custom fields on the student contact record — not the contacts
   module.

Constraints:

- Finalsite Contacts API ingestion currently exists only for `kippmiami`. API
  credentials exist only for Newark's Finalsite instance today; Camden and
  Paterson are pending.
- Miami's contact **sourcing** is out of scope — it is handled by the Focus
  migration work. Miami's PowerSchool data is mapped into the new surface shape
  in the interim.

## Decisions (from brainstorming)

| Question                   | Decision                                                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Downstream surface         | Swap the source under the existing surfaces (dim, bridge, enrollment contact columns, extracts)                           |
| Surface shape              | **Redefine** around the 1+4 model — `contact_1` + `emergency_1..4`; `contact_2` and `pickup_*` slots removed network-wide |
| Miami                      | Sourcing out of scope; PS data mapped into the new 1+4 shape via an inline CTE (temporary until Focus contacts)           |
| Rank field                 | Not in our current schema — discover from the Newark API payload                                                          |
| Emergency field sets       | Discover names from Newark data                                                                                           |
| Phasing                    | Newark first, per-region cutover as credentials arrive                                                                    |
| Finalsite shaping location | Finalsite package `api/intermediate` (SIS-agnostic), following the existing convention                                    |

## New contact shape (1+4)

- `contact_1` — the top-ranked relationship from the Finalsite contacts module.
  Person details (name/email/phones/address) resolved by joining `rel_id` back
  to the contact's own record.
- `emergency_1` … `emergency_4` — from 4 sets of custom fields on the student
  contact record. These are field values, **not** linked person records — they
  carry only what the field sets contain.
- `contact_2` and `pickup_{n}` slots are removed from all surfaces, network-wide
  (including Miami's PS-mapped rows).

## Architecture

```text
Dagster (per NJ region, Newark first)
  <region>/finalsite/contacts  ──►  GCS Avro  ──►  BQ external

dbt finalsite package (api/, enabled per region as ingestion lands)
  stg_finalsite__contacts
  stg_finalsite__contact_relationships   (+ rank field — discovery)
  int_finalsite__contact_custom_attributes (+ emergency field sets — discovery)
  int_finalsite__student_contacts        (NEW — 1+4 long format, SIS-agnostic)

kipptaf
  int_students__contacts (NEW — union; name settled in planning)
    ├─ NJ finalsite branches via source(), joined to student_number
    │    through int_finalsite__contact_id_attributes
    └─ inline PS-mapped CTE (regions not yet cut over + Miami)  -- TODO(focus)
    ──► redefined pivot (NEW kipptaf model, 1 row per student)
    ──► dim_student_contact_persons  (redefined)
    ──► bridge_student_contacts     (redefined)
```

### Finalsite package (`api/`)

1. **`stg_finalsite__contact_relationships`** — add the rank field (exact name
   pending discovery) surfaced from the extended `Relationship` Pydantic schema.
2. **`int_finalsite__contact_custom_attributes`** — extend the explicit PIVOT
   field list with the 4 emergency-contact field sets (names pending discovery).
3. **`int_finalsite__student_contacts`** (new) — 1+4 long format.
   - Grain: `(finalsite_enrollment_id, contact_slot)`,
     `contact_slot ∈ ('contact_1', 'emergency_1'..'emergency_4')`.
   - `contact_1` rows: pick the top-ranked relationship; join `rel_id` back to
     `stg_finalsite__contacts` for person details.
   - `emergency_n` rows: from the pivoted custom fields.
   - Slots with no data are omitted (sparse long format).
   - SIS-agnostic: no PowerSchool references; the `student_number` join happens
     downstream.

### kipptaf

1. **`int_students__contacts`** (new; final name settled during planning against
   existing `kipptaf/models/powerschool/intermediate/` naming) — union of:
   - Per-NJ-region `int_finalsite__student_contacts` via `source()`, joined to
     `student_number` through the id-attributes pivot
     (`powerschool_student_number`).
   - One inline PS-mapped CTE covering regions not yet cut over plus Miami,
     marked `-- TODO(focus): remove when Focus contacts land`. Mapping:
     - `contact_1` ← top-priority PS contact (`contactpriorityorder = 1`,
       `person_type != 'self'`)
     - `emergency_1..4` ← PS contacts with `isemergency = 1`, ranked by
       `contactpriorityorder`, capped at 4
     - Phone/email/address resolution follows the current
       `dim_student_contact_persons` logic (mobile→home→daytime→work primary
       phone; current email; home address).
   - Grain: `(student_number, _dbt_source_project, contact_slot)`.
   - The CTE's region list shrinks as each region cuts over; the mapping is
     intentionally lossy — non-top-priority, non-emergency PS contacts (today's
     `contact_2`, `pickup_*`) drop out of the surface.
2. **Redefined pivot** — a NEW kipptaf model that replaces the powerschool
   package's `int_powerschool__student_contacts_pivot` as the reporting source.
   One row per student; `contact_1_*` and `emergency_1_*`..`emergency_4_*`
   column sets. Exact sub-columns pinned after discovery (emergency field sets
   may carry fewer attributes than the contacts module).
3. **`dim_student_contact_persons` / `bridge_student_contacts` redefined** from
   the long model.
   - `contact_1` rows key on the real contact identity (Finalsite contact id for
     NJ; `personid` for PS-mapped rows).
   - Emergency rows have no person record — person key =
     `surrogate_key(source, student, slot)`.
   - Dim slims to name/phone/email/address; bridge carries student ↔ person
     links with slot and `is_emergency`.
   - Cube does NOT consume these marts (see addendum) — no Cube change needed.
4. **Contact columns move out of the powerschool package** — drop the `scw.*`
   pivot columns from `base_powerschool__student_enrollments` (the package
   cannot reference finalsite models); `int_extracts__student_enrollments` joins
   the new kipptaf pivot instead. Downstream consumers updating to the 1+4
   columns:
   - `int_extracts__student_enrollments` (+ `_subjects_weeks`)
   - `rpt_deanslist__student_misc`
   - `rpt_gsheets__kfwd_taf_contact_feed`, `rpt_gsheets__kippfwd_collab_roster`,
     `rpt_gsheets__kippfwd_miami_roster`,
     `rpt_gsheets__njsmart_transfer_unverified`,
     `rpt_gsheets__student_contact_info`
   - `rpt_tableau__next_year_status`
   - `int_kippadb__roster`
   - `rpt_clever__students`
   - `int_powerschool__student_contacts` /
     `int_powerschool__student_contacts_pivot` (package level) and the kipptaf
     union wrapper are deprecated as reporting sources once no consumer reads
     them (full deletion waits for Miami/Focus).

### Dagster ingestion (per NJ region)

- `code_locations/kippnewark/finalsite/`: add `contacts` asset via
  `build_finalsite_asset(..., params={"includes": "contacts.relationships"})`,
  `CONTACTS_SCHEMA` in `schema.py` (generated from the shared library Pydantic
  models), and a daily schedule mirroring Miami's (4am local).
- `code_locations/kippnewark/resources.py`: `FinalsiteResource` instance for
  Newark's Finalsite instance (server / credential id / secret via the same
  secret-management path as Miami's).
- Library change: extend the `Relationship` Pydantic model with the rank field
  once discovered (regenerates every region's Avro schema; the Avro check warns
  on drift, and the fix is declaring the field — one edit covers all regions).
- Camden/Paterson: identical wiring when credentials arrive. No other library
  changes expected.
- dbt gating: flip `finalsite: api: +enabled: true` in the region's
  `dbt_project.yml` when its ingestion lands (Newark in this effort); the
  external source must be staged with `--target staging` before dbt Cloud CI
  passes.

## Rollout phases

| Phase | Work                                                                                                            | Gate                  |
| ----- | --------------------------------------------------------------------------------------------------------------- | --------------------- |
| 1     | Newark ingestion (resource, asset, schedule); raw data in BQ                                                    | Credentials (in hand) |
| 2     | Discovery: rank field, emergency field-set names, `rel_id` resolution shape; documented as spec addendum        | Phase 1 data          |
| 3     | `Relationship` schema extension + finalsite package models; enable `api` for kippnewark                         | Phase 2 findings      |
| 4     | kipptaf layer: union (Newark = Finalsite; Camden/Paterson/Miami = PS CTE), pivot, dim, bridge, consumer updates | Phase 3               |
| 5+    | Per region (Camden, Paterson): repeat Phase 1 + 3 wiring; move region from the PS CTE to a Finalsite branch     | Credentials           |

## Discovery checklist (Phase 2)

Blocks final SQL shape; answers recorded as a spec addendum:

- [ ] Rank field on relationships: name, type, semantics (is `primary` a
      separate concept?)
- [ ] Whether the contacts endpoint returns non-student contact records
      (parents) that `rel_id` can join to, and which detail fields they carry
- [ ] The 4 emergency-contact custom field sets: field names and attributes per
      set (name / phone / relationship / …?)
- [ ] Whether emergency custom fields are track-siloed (`track_attributes`) or
      global (`custom_attributes`)

## Testing & data quality

- Standard layer requirements: contracts + uniqueness tests on all new models.
  Grain tests:
  - `int_finalsite__student_contacts`: `(finalsite_enrollment_id, contact_slot)`
  - kipptaf union: `(student_number, _dbt_source_project, contact_slot)`
- **Cutover validation per region** (plan-time query, not a permanent test):
  compare Finalsite-sourced vs PS-sourced coverage — % of enrolled students with
  `contact_1`, % with ≥1 emergency contact. A material coverage drop blocks the
  region's flip.
- Warn-level coverage test on the pivot (`contact_1_name` not null, scoped to
  enrolled students) to surface silent feed breakage.
- Match-rate check on the `student_number` join: unmatched Finalsite records are
  expected for prospects/applicants; unmatched **enrolled** students should be
  ~0.

## Error handling

- Finalsite API: `FinalsiteResource` already handles 429 retry-after; JWT window
  (55 min) already handled. No new library error paths.
- Empty-region builds: package `api/` models build empty in regions without
  ingestion — gated by `+enabled: false`, per the existing convention.
- Union during transition mixes sources by region; `_dbt_source_project`
  discriminates, matching the existing cross-district pattern.

## Out of scope

- Miami contact sourcing (Focus migration owns it; the PS-mapped CTE is the
  interim bridge)
- Finalsite → SIS enrollment integration (`int_finalsite__enrollment_lifecycle`
  — separate, existing work)
- Deleting the PowerSchool contact staging/int models (raw PS contact tables
  keep loading; deletion waits for Miami/Focus)

## Addendum: Discovery findings (2026-07-08, Newark)

Sourced from 23,585 Newark contacts (materialization run `df1a3807`, commit
`22e7461`), queried via a dev-staged external over the prod GCS Avro. Resolves
the Phase 2 discovery checklist and pins the Phase 3 model shape.

### Top-ranked contact (contacts module)

- No explicit rank field on `relationships`; the Avro schema-drift check is
  clean at top level (no hidden field). The ranking signal is
  `relationships[].primary`.
- `primary` is **at most one true per contact** (never multiple).
- The `contacts` dataset mixes **student** and **parent/prospect** records. On
  student records (those carrying `emrg_*` fields), `primary` is set on
  **94.7%** (6,389 / 6,740 with relationships); on non-student records only
  22.3% (parent records point back at the student, primary unset).
- **Rule:** `contact_1` = the `relationships` element with `primary = true` on
  the student record. **Fallback (resolved):** for the ~5.3% of students with
  relationships but no `primary`, use the **first array element**
  (`relationships[0]`) — justified because when `primary` IS set it sits at
  offset 0 in 79.1% of cases (offset 1: 15.4%, tail after), so array order
  tracks rank.

### contact_1 detail resolution

- The primary relationship's `rel_id` resolves to another Contact record's `id`
  in the same dataset **100%** of the time (when `primary` set).
- That resolved (parent) record carries `email` 99.5%, `phone_1.number` 99.9%,
  `households[0]` address 96.5%.
- **So** `contact_1` details = student → primary `rel_id` → contact record
  (`email`, `phone_1/2/3`, `households[0]`); `rel_name` / `rel_type` on the
  relationship give the display name and relationship label.

### Emergency contacts — 4 custom-field sets

- Global `custom_attributes` (NOT `track_attributes`); field-name pattern
  `emrg_<N>_<attr>`; exactly **4 sets** (`emrg_1`..`emrg_4`).
- Per-set fields:
  - `emrg_N_name_first_name`, `emrg_N_name_last_name`
  - `emrg_N_email`
  - `emrg_N_phone_1_number` / `_phone_1_type` / `_phone_1_opt_in`, plus
    `_phone_2_*` and `_phone_3_*`
  - `emrg_N_relationship_ss` (single-select), `emrg_N_relationship_txt` (free
    text)
  - `emrg_N_priority_ss`
  - `emrg_N_custody_yn`, `emrg_N_lives_with_yn`, `emrg_N_pickup_yn`
- Value subtypes: names/email/phone/relationship/priority = `string_value`;
  `_yn`/`_opt_in` = `boolean_value`. No arrays.
- Fill tapers: set 1 ~6,748, set 2 ~6,604, set 3 ~1,734, set 4 ~441.

### SIS join

- Student records carry `emrg_*`; join to PowerSchool via
  `id_attributes.powerschool_student_number` (existing
  `int_finalsite__contact_id_attributes` pivot).

### Phone typing (for the downstream surface)

- The existing pivot surface exposes typed phone columns (`*_phone_mobile` /
  `_home` / `_daytime` / `_work` / `_primary`). Finalsite `phone_type`
  vocabulary is **`Cell` / `Home` / `Work`** (plus blank). Mapping:
  `phone_mobile`←Cell, `phone_home`←Home, `phone_work`←Work,
  `phone_daytime`←null (no Finalsite equivalent), `phone_primary`←`phone_1`
  (first listed, ~32% are blank-type so only `_primary` catches them). Both
  `contact_1` (parent `phone_1/2/3`) and `emergency_N` (`emrg_N_phone_1/2/3`)
  carry `_type` per phone. So `int_finalsite__student_contacts` emits the typed
  phone columns, not a single `phone`.

### Consumers of the marts

- `dim_student_contact_persons` / `bridge_student_contacts` are **not**
  referenced by Cube (`grep src/cube` empty) — the spec's "ship a Cube update"
  step does not apply. Their consumers are the enrollment-pivot chain
  (`base_powerschool__student_enrollments` → `int_extracts__student_enrollments`
  (+`_subjects_weeks`) → the extract feeds) and `int_kippadb__roster`;
  `rpt_clever__students` reads the LONG contact model (person_type-keyed), not
  the pivot.

### Model-shape implications (Phase 3)

- `contact_1`: primary-relationship join (details from the resolved parent
  record), plus a fallback-pick rule for no-primary students.
- `emergency_1..4`: direct from `emrg_N_*` fields; no `rel_id` join. Emergency
  ordering (**resolved**): order by `emrg_N_priority_ss` (numeric string) asc,
  tiebreak on natural set order (`emrg_1`..`emrg_4`), nulls last. `priority_ss`
  values run 1-8 and appear to be a **global family ranking** (priority 1 is
  typically the primary guardian in the contacts module, so emergency sets
  usually start at 2 — emrg_1 is modally priority 2, emrg_2 priority 3, etc.);
  values collide across sets, hence the natural-order tiebreaker.
- Contacts-module shape (**resolved**): strict **1+4** — `contact_1` only from
  the module (no `contact_2`), ranked over **any** relationship type (no
  guardian-type filter; `primary` is ~99% a parent so contact_1 is a parent in
  practice, and the first-element fallback may occasionally be a sibling —
  accepted). The `relationships` array mixes parents with siblings/relatives, so
  array position is not a reliable second-parent selector — which is why no
  `contact_2` is derived.
- Consumer parent2 (**resolved**): the ~5 feeds that read the old PS
  `contact_2_*` (parent2/father) and `pickup_*` columns **drop those columns**
  under the 1+4 surface — they report `contact_1` + emergencies only. Affected:
  `rpt_deanslist__student_misc`, `rpt_gsheets__kfwd_taf_contact_feed`,
  `rpt_gsheets__kippfwd_miami_roster`,
  `rpt_gsheets__njsmart_transfer_unverified`,
  `rpt_gsheets__student_contact_info`.
- Bridge flags (**resolved**): `emrg_N_pickup_yn` / `_custody_yn` /
  `_lives_with_yn` map to the redefined bridge's `is_pickup` / `is_custodial` /
  `is_household_member`. `contact_1` (primary relationship) carries no such
  flags — they are **null/false** for the top contact (the two sources don't
  share these flags; no fuzzy matching between them).
