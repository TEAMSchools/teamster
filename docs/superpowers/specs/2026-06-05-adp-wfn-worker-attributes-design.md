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

Model the **complete retrievable Worker representation** in the pydantic schema,
and curate at **two points** — the `$select` (keeps PII off the wire) and the
**staging contract** (keeps PII columns out of the warehouse). The model itself
declares everything; only two sensitive PII fields are curated out at those two
points. Surfacing an omitted field later is then a one-line `$select` change —
no schema/Avro work.

### Why keep a curated `$select` (do not drop it)

- **Minimum PII on the wire.** A curated `$select` means SSN / identity
  documents never leave ADP, even though the model can represent them. ADP's own
  guide recommends retrieving "the minimum amount of worker information needed"
  (Worker Management API Guide, p.9).
- **Smaller payload.** No transferring (or holding in run memory) fields we
  don't warehouse.
- **Drop-in later.** Because the model is the complete representation, surfacing
  an omitted field is a one-line `$select` addition. The model being a superset
  of any response also keeps `check_avro_schema_valid` quiet (responses are
  always a subset of the schema).
- OData `$select` has no "all except" operator (inclusion-only; `$select=*` or
  omission are the only "everything" forms), so an inclusion list is the only
  way to express "everything except SSN."

### Minimal-curation rule

The pydantic model declares **every retrievable field** the enumeration
confirms. Curation removes **exactly two PII fields** at the `$select` **and**
staging layers (never requested, never warehoused); they stay declared in the
model for future use:

| Cut field                         | Basis                                                                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `person/governmentIDs` (SSN/ITIN) | Direct identifier; in ADP's masked PII/SPI set (guide p.9); no warehouse consumer (`workers_sync` writes `employee_number`, not SSN). |
| `person/identityDocuments`        | Work-authorization document numbers (passport/visa/etc.); in ADP's masked PII/SPI set (guide p.9); no consumer.                       |

Everything else retrievable is requested **and** staged — including
`socialInsurancePrograms`, `deathDate`, `tobaccoUserIndicator` (none are in
ADP's PII/SPI set) and `payGradePayRange` (in ADP's PII set, but **less**
sensitive than `baseRemuneration`, which we already sync — cutting it would be
incoherent).

**Model scope boundary.** "Complete representation" means everything retrievable
on **WFN Classic** (our platform): the guide's Appendix A minus two exclusions
that are dead weight in the model because they never reach it —

- **Appendix B (Not Supported for Data Retrieval)** — `Payroll Name`,
  `# of Dependents`, `Works from Home`, `Annual salary`, retirement-plan
  eligibility dates, etc. The API won't return them.
- **WFN Next-Gen-only** fields (`workAgreementRef`, `bargainingUnit`, etc.) —
  KTAF is on WFN Classic and the enumeration's live-data leg confirms they don't
  return. (A future WFN-NG migration is a separate, larger effort; modeling
  these now is premature.)

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

Model the **complete retrievable representation** (Appendix A minus Appendix B
minus WFN-NG-only, per the model-scope boundary above). The enumeration is
authoritative for the final list (especially `customCountryInputs`, whose shape
is undocumented). The model declares the two cut PII fields too — only `$select`
and staging omit them:

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
- **`Person` (cut PII — declared, not requested/staged):** keep `governmentIDs`;
  **add** `identityDocuments` (new `IdentityDocument` model class). The model
  represents them so a future need is a one-line `$select` change; `$select` and
  staging omit them.

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
- **Flatten every new worker-grain field** — scalars and single (non-repeated)
  nested objects — following the model's existing flatten pattern (`Code` →
  `__code_value` / `__long_name` / `__short_name` [+ `__effective_date`]). New
  flattened scalar columns: `person__death_date`,
  `person__legal_address__delivery_point`.
- **Repeated records stay nested** (finer grain than the worker): the new
  `business_communication__faxes` / `__pagers`, `person__communication__faxes` /
  `__pagers`, and `(person__)?custom_field_group__amount_fields` /
  `__percent_fields` / `__telephone_fields` land as `ARRAY<STRUCT<...>>` columns
  alongside the existing array columns.
- **Already-present, currently-empty flattened columns simply start populating**
  once their `$select` paths are added (e.g. `person__marital_status_code__*`,
  `person__preferred_gender_pronoun_code__*`, `person__birth_name__*`,
  `person__social_insurance_programs`, `person__tobacco_user_indicator`) — no
  schema change, just data.
- **Cut PII stays unstaged.** Because the model now declares `governmentIDs` /
  `identityDocuments`, they surface as **always-null** columns in the external
  table (the curated `$select` never populates them); the staging model does
  **not** project them into the contract, keeping SSN / identity-doc columns out
  of the warehouse. No column drops are needed.
- **Descriptions** on every genuinely new column (per dbt conventions); profile
  values via BigQuery MCP after staging rebuilds.
- **Surrogate key**: keep the whole-struct hash (`to_json_string(person)` /
  `to_json_string(workassignments)` / etc.). Because the structs widen, the hash
  recomposes once → a one-time SCD2 re-key per worker, rippling into `int` and
  downstream marts. This is a **deliberate hash-change event** per the marts
  hash-change discipline.

### 5. Intermediate (`int_l__work_assignments` + properties YAML)

Flatten **every new work-assignment-grain field** into the model, matching its
existing flatten pattern (scalar → one column; `Code` → `__code_value` /
`__long_name` / `__short_name` [+ `__effective_date`]; single nested struct →
its scalar leaves). New flattened columns:

- `jobFunctionCode` (`Code`), `rehireEligibleIndicator` (bool), `payGradeCode`
  (`Code`), `payGradePayRange` (→ `__minimum_rate__amount_value` /
  `__median_rate__amount_value` / `__maximum_rate__amount_value`), `laborUnion`
  (→ `labor_union_code__*`), `workShiftCode` (`Code`).
- `customCountryInputs` — flatten if the enumeration shows it is a single
  object; if it is a repeated record, keep it as an `ARRAY<STRUCT<...>>` column
  (finer grain).

Add each to the parsed CTE and the final `SELECT` with `description:`; retain
the model's existing uniqueness test. **Repeated sub-records stay nested**
(finer grain than the work assignment): `additionalRemunerations`,
`assignedOrganizationalUnits`, `occupationalClassifications`, `workerGroups`,
etc. remain `ARRAY` columns as today.

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

- Requesting or warehousing the two cut PII fields (`governmentIDs`,
  `identityDocuments`) — modeled for future use, but excluded from `$select` and
  staging.
- Jobs validation table (tracked in
  [#4071](https://github.com/TEAMSchools/teamster/issues/4071)).
- The `workers_sync` (update) asset.
- Flattening _repeated_ sub-records (arrays) into their own grain — they stay
  nested as `ARRAY<STRUCT<...>>` columns in both staging and int.

## Divergence from issue #4106 (update the issue)

The issue's original "Decided approach" said **drop `$select`** and **capture
everything including `governmentIDs` (SSN/ITIN)**. This design intentionally
diverges:

- **Keep a curated `$select`** (minimum PII on the wire) rather than dropping
  it.
- **Model the complete representation** but **exclude `governmentIDs` and
  `identityDocuments`** from `$select` and staging (ADP-classified masked
  PII/SPI, no consumer) — declared in the model so a future need is a one-line
  `$select` change.

Leave #4106's body as-is; the PR description carries this divergence note (no
issue-body edit).

## Open items to resolve during execution

- `customCountryInputs` structure (undocumented) — defined by the enumeration
  pull.
- Whether `retirementDate` / `adjustedServiceDate` actually return data for KTAF
  (guide marks support inconsistently) — confirmed by the enumeration pull.
- Unmask config (`masked=false` + WFN profile) needed for any pay-range / DOB
  field wanted unmasked — out of band with the API-Central project owner.
