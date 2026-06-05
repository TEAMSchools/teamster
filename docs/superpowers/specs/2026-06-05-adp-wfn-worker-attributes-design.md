# Capture additional ADP WFN worker attributes (curated `$select`)

- **Issue:** [#4106](https://github.com/TEAMSchools/teamster/issues/4106)
- **Date:** 2026-06-05
- **Status:** Design approved; ready for implementation plan

## Problem

The ADP WFN workers asset under-captures the API's worker representation, so
attributes the API returns are silently dropped. Two distinct mechanisms cause
this:

1. **Model gate (the dominant cause).** The landing Avro is shaped by
   `WORKER_SCHEMA`, generated from the `Worker` pydantic model
   (`src/teamster/libraries/adp/workforce_now/api/schema.py`). The asset's
   `$select` already requests `workAssignments`, `workerDates`, `workerStatus`,
   `businessCommunication`, and `customFieldGroup` **as whole objects**, so
   their subfields already arrive in the API response — but any subfield the
   pydantic model doesn't declare is dropped by `fastavro` at write time. The
   `check_avro_schema_valid` asset check only **warns** on extras; it does not
   capture them. Confirmed missing on `workAssignments` in live data:
   `jobFunctionCode` (present on 64 assignments, **absent from
   `workers/meta`**), `customCountryInputs`, `rehireEligibleIndicator`.
2. **`$select` gate (only for `person`).** `person` is enumerated by explicit
   sub-path in `$select`, so any `person` field not named there is never
   requested and never returned (the pydantic model declares several such
   fields, e.g. `socialInsurancePrograms` / `tobaccoUserIndicator`, which are
   therefore **declared but always null**).

## Decided approach

Keep a **curated `$select`** (do **not** drop it) and expand it — plus the
pydantic model — to capture everything retrievable **except** the sensitive PII
we don't already sync.

### Why keep `$select` rather than drop it

- Dropping `$select` captures nothing on its own — the pydantic model is the
  real gate, so the model must be widened either way. Dropping `$select` saves
  no modeling work.
- **Minimum PII on the wire.** A curated `$select` means SSN / identity
  documents never leave ADP. ADP's own guide recommends retrieving "the minimum
  amount of worker information needed" (Worker Management API Guide, p.9).
- **Clean checks.** A `$select` that mirrors the model keeps
  `check_avro_schema_valid` meaningful instead of warning on dozens of
  unrequested fields every run.
- OData `$select` has no "all except" operator (inclusion-only; `$select=*` or
  omission are the only "everything" forms), so an inclusion list is the only
  way to express "everything except SSN."

### Minimal-curation rule

Capture **every retrievable field** the enumeration confirms, **minus exactly
two PII fields** we don't sync today:

| Cut field                         | Basis                                                                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `person/governmentIDs` (SSN/ITIN) | Direct identifier; in ADP's masked PII/SPI set (guide p.9); no warehouse consumer (`workers_sync` writes `employee_number`, not SSN). |
| `person/identityDocuments`        | Work-authorization document numbers (passport/visa/etc.); in ADP's masked PII/SPI set (guide p.9); no consumer.                       |

Everything else retrievable is captured — including `socialInsurancePrograms`,
`deathDate`, `tobaccoUserIndicator` (none are in ADP's PII/SPI set) and
`payGradePayRange` (in ADP's PII set, but **less** sensitive than
`baseRemuneration`, which we already sync — cutting it would be incoherent).

Fields in the guide's **Appendix B (Not Supported for Data Retrieval)** —
`Payroll Name`, `# of Dependents`, `Works from Home`, `Annual salary`,
retirement-plan eligibility dates, etc. — are excluded automatically (the API
won't return them).

WFN **Next-Gen-only** fields (`workAgreementRef`, `bargainingUnit`, etc.) are
omitted; KTAF is on WFN Classic and the enumeration's live-data leg confirms
they don't return.

## Components

### 1. Enumeration script (throwaway, discovery-only)

A one-off local script (lives in `.claude/scratch/`, gitignored; **you** run it
with ADP credentials). It does the only `$select`-dropped pull in the whole
effort, for discovery — the production asset keeps its curated `$select`.

- Pull the **full worker population** with `$select` dropped (ADP's full default
  representation, ~43 MB local PII; kept local only).
- Compute the field-path set as: `{live field paths}` ∪
  `{guide Appendix A Data Dictionary}` ∪ `{current pydantic model}`, then
  subtract `{Appendix B not-retrievable}` and `{cut list}`.
  - Live data catches fields absent from `meta`/docs (`jobFunctionCode`,
    `customCountryInputs`).
  - The guide's Appendix A catches documented fields that are sparse/null for
    every current KTAF worker today (would otherwise silently break later).
  - Cross-check `workers/meta` as a documented baseline (known incomplete).
- Output two artifacts: (a) the exact field set to add to the model, and (b) the
  BigQuery `STRUCT` DDL for the regenerated staging contract `data_type`
  strings.
- Note masking: pay/DOB/pay-range fields return masked unless the request sends
  `Accept: application/json;masked=false` and the WFN API-Central profile is
  configured to unmask. `birthDate` is already partially masked today (year can
  arrive as `0000`). Masking does not block capture (the field/struct still
  lands); flag any field where unmasked values are wanted as a separate config
  item.

### 2. Pydantic schema (`libraries/adp/workforce_now/api/schema.py`)

Expand to the enumerated set. Anchored on the guide's Data Dictionary (the
enumeration is authoritative for the final list, especially
`customCountryInputs` whose shape is not documented):

- **`WorkAssignment`** (already requested whole — model-only additions):
  `jobFunctionCode`, `customCountryInputs` (shape per enumeration),
  `rehireEligibleIndicator`, `payGradeCode`, `payGradePayRange`
  (`minimumRate`/`medianRate`/`maximumRate` → `amountValue`), `laborUnion`
  (`laborUnionCode`), `workShiftCode`.
- **`WorkerDates`**: `adjustedServiceDate`, `retirementDate` (keep whichever the
  enumeration confirms returns data).
- **`CustomFieldGroup`**: `amountFields`, `percentFields`, `telephoneFields`.
- **`Communication`**: `faxes`, `pagers`.
- **`Address`**: `deliveryPoint`.
- **`Person`**: add `deathDate`. (`maritalStatusCode`,
  `preferredGenderPronounCode`, `otherPersonalAddresses`, `birthName`,
  `disabilityTypeCodes`, `socialInsurancePrograms`, `tobaccoUserIndicator`,
  `militaryDischargeDate` are already declared — they only need the `$select`
  paths below to populate.)
- **Remove** `Person.governmentIDs` (declared but cut) so `model = $select`.
  `identityDocuments` is not declared today; do not add it. The `GovernmentID`
  class can be removed if unused elsewhere.

### 3. Asset `$select` (`code_locations/kipptaf/.../api/assets.py`)

Add **only** the new `person` sub-paths; whole-object requests are unchanged
(new `workAssignments` / `workerDates` / `customFieldGroup` / communication
subfields arrive automatically once modeled):

```text
workers/person/birthName
workers/person/deathDate
workers/person/disabilityTypeCodes
workers/person/maritalStatusCode
workers/person/militaryDischargeDate
workers/person/otherPersonalAddresses
workers/person/preferredGenderPronounCode
workers/person/socialInsurancePrograms
workers/person/tobaccoUserIndicator
```

Do **not** add `workers/person/governmentIDs` or
`workers/person/identityDocuments`.

### 4. Staging (`stg_adp_workforce_now__workers` + properties YAML)

Staging is contract-enforced, so the properties YAML must match the new external
columns exactly.

- **Regenerate the struct `data_type` contract strings** (from the enumeration
  DDL) for every nested/repeated column that gains subfields — notably the large
  `work_assignments` `ARRAY<STRUCT<...>>` (gains `jobFunctionCode`,
  `customCountryInputs`, `rehireEligibleIndicator`, `payGradeCode`,
  `payGradePayRange`, `laborUnion`, `workShiftCode`) and the `workerDates`-
  derived fields.
- **New columns** (preserve structs; flatten only where step 5 requires):
  - New array columns: `business_communication__faxes` / `__pagers`,
    `person__communication__faxes` / `__pagers`,
    `(person__)?custom_field_group__amount_fields` / `__percent_fields` /
    `__telephone_fields`.
  - New scalar columns: `person__death_date`,
    `person__legal_address__delivery_point`.
- **Already-present, currently-empty flattened columns simply start populating**
  once their `$select` paths are added (e.g. `person__marital_status_code__*`,
  `person__preferred_gender_pronoun_code__*`, `person__birth_name__*`,
  `person__social_insurance_programs`, `person__tobacco_user_indicator`) — no
  schema change, just data. **No column drops** are required (the only cut
  field, `governmentIDs`, is not staged today).
- **Descriptions** on every genuinely new column (per dbt conventions); profile
  values via BigQuery MCP after staging rebuilds.
- **Surrogate key**: keep the whole-struct hash (`to_json_string(person)` /
  `to_json_string(workassignments)` / etc.). Because the structs widen, the hash
  recomposes once → a one-time SCD2 re-key per worker, rippling into `int` and
  downstream marts. This is a **deliberate hash-change event** per the marts
  hash-change discipline.

### 5. Intermediate (`int_l__work_assignments` + properties YAML)

Flatten **only** the issue's three motivating fields (preserve structs
otherwise): `jobFunctionCode`, `customCountryInputs`, `rehireEligibleIndicator`.
Add them to the parsed CTE and the final `SELECT`, with `description:` on each
and the model's existing uniqueness test retained. Any further flattening is a
separate follow-up driven by a concrete consumer.

### 6. Rollout / sequencing

- New external Avro columns require
  `stage_external_sources --select adp_workforce_now.src_adp_workforce_now__workers --target staging`
  before dbt Cloud CI will pass.
- New partitions carry the wide schema automatically once the asset deploys; a
  **recent-window re-pull** of the workers asset is the deploy step that brings
  the current SCD2 segment of every active worker up to the full field set
  (exact window decided at execution time).
- Order Python (schema + `$select`) and dbt (contract + int) so CI sees the
  regenerated external columns; bundle CI-fix commits per the repo's dbt Cloud
  CI conventions.

## Out of scope

- Cut PII: `governmentIDs` (SSN/ITIN), `identityDocuments`.
- Jobs validation table (tracked in
  [#4071](https://github.com/TEAMSchools/teamster/issues/4071)).
- The `workers_sync` (update) asset.
- Flattening any captured field beyond the three named in step 5.

## Divergence from issue #4106 (update the issue)

The issue's original "Decided approach" said **drop `$select`** and **capture
everything including `governmentIDs` (SSN/ITIN)**. This design intentionally
diverges:

- **Keep a curated `$select`** (minimum PII on the wire; clean checks; same
  modeling work).
- **Exclude `governmentIDs` and `identityDocuments`** (ADP-classified masked
  PII/SPI, no consumer).

Update #4106's body to match before/at implementation.

## Open items to resolve during execution

- `customCountryInputs` structure (undocumented) — defined by the enumeration
  pull.
- Whether `retirementDate` / `adjustedServiceDate` actually return data for KTAF
  (guide marks support inconsistently) — confirmed by the enumeration pull.
- Unmask config (`masked=false` + WFN profile) needed for any pay-range / DOB
  field wanted unmasked — out of band with the API-Central project owner.
