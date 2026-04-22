# Column Naming Audit — Star Schema Mart Models

## Summary

Comprehensive naming review for all ~60 mart models. Supersedes the initial
67-column reactive audit with a proactive full-column review. Applies a
documented rubric to every column; adds structural columns (multi-ID on
students, split emails on staff); removes plumbing columns from mart SELECTs.
Single implementation PR after the audit inventory is approved.

Tracked on [#3643](https://github.com/TEAMSchools/teamster/issues/3643).

## Goals

- Every mart column name readable by both dimensional-modeling-fluent analysts
  and school-based SQL-comfortable analysts, without needing source-system
  jargon decoding.
- Students and staff expose the identifiers that matter for reporting
  cross-reference, including multi-state and external-system IDs where relevant.
- Plumbing columns do not leak into the mart SELECTs analysts consume.
- Naming decisions are durable — documented rubric, bounded acronym allow-list,
  explicit jargon exceptions.

## Non-goals

- Cube YAML model definitions and `title:` polish — follow-up to
  [#3591](https://github.com/TEAMSchools/teamster/issues/3591).
- Retiring existing `extracts/` models — separate future work.
- Non-mart reporting views (`rpt_*`).
- Google Group creation and Cube access policies —
  [#3591](https://github.com/TEAMSchools/teamster/issues/3591).
- Downstream consumer communication — Cube barely exists yet; no active consumer
  base to coordinate.

## Naming rubric

Applied to every column in every mart model during audit:

1. **Strip source-system prefixes/names** (`powerschool_`, `adp_`, `deanslist_`)
   unless disambiguating unified columns.
2. **No KIPP-specific language** (`teammate`, `employee_number`, `microgoal`).
3. **Boolean fields use `is_` / `has_` prefix**. On fact tables, countable 0/1
   flags may use `INT64` rather than `BOOLEAN` so analyst `SUM(is_x)` and
   `AVG(is_x)` aggregations read naturally without casting. Reserve `FLOAT64`
   for genuinely non-binary weighted measures (e.g., `present_weight`), and name
   those without the `is_` prefix.
4. **Dates end `_date`; timestamps end `_timestamp`**.
5. **Well-known external acronyms** allowed for specific-use IDs — bound list
   below.
6. **Ed-Fi Unified Data Model** nomenclature is the default for IDs, entity
   names, and standard attributes. Deviate toward plain English for awkward
   descriptive attributes (e.g., `family_name_1` → `last_name`). Document each
   deviation in the inventory `reviewer_notes` column.
7. **Keep ubiquitous acronyms** (`gpa`, `ada`, `fte`, `dob`, `ell`, `iep`,
   `sat`, `psat`, `act`, `ap`); spell out or remove internal ones (`dcid`,
   `oid`, `lep`, etc. — reviewed during audit).
8. **Plumbing columns removed** from mart SELECTs. They remain in intermediate
   layers where joins happen.
9. **Remove dimension attributes reachable via FK.** Facts and child dimensions
   carry only surrogate FKs, true degenerate dimensions (text attributes with no
   corresponding dim), and measures. Any column whose value is reachable by
   traversing an FK to a dimension is removed — Cube handles join traversal.
   This includes natural keys that duplicate a surrogate FK and date columns
   that duplicate a date-key FK.
10. **Entity qualification.** Qualify a descriptive column with the model's
    entity prefix (`student_`, `ticket_`, `term_`, etc.) **only** when removing
    the prefix would create a real ambiguity for a downstream consumer — e.g.
    `student_name` disambiguates from staff / contact names when joining across
    marts. Otherwise, let the model name provide the context; default to
    unqualified. Applies to descriptive attributes and degenerate dimensions.
    Primary keys (`<entity>_key`) and foreign keys (`<target>_key` /
    `<role>_<target>_key`) are governed by their own patterns and are not
    affected by R10. Added after the initial audit on review feedback that the
    qualifier question was never in R1–R9 scope, so any existing consistency was
    accidental. See the R10 sweep applied in the review follow-up commit.

Degenerate-dimension text columns (e.g., `incident_type`, `consequence_type`,
`assignment_type`) drop `_code` / `_name` suffixes unless a code AND a human
name coexist in the same table — in which case both suffixes stay. Under R10,
such code+name pairs also keep their entity prefix so both columns follow the
same shape within the pair.

### Acronym allow-list

User-facing acronyms explicitly preserved in column names:

| Acronym        | Meaning                                  | Context                                   |
| -------------- | ---------------------------------------- | ----------------------------------------- |
| `gpa`          | grade point average                      | student grades                            |
| `ada`          | average daily attendance                 | student attendance                        |
| `fte`          | full-time equivalent                     | staff assignments                         |
| `dob`          | date of birth                            | person attributes                         |
| `ell`          | English language learner                 | student attributes                        |
| `iep`          | individualized education plan            | student attributes                        |
| `sat` / `psat` | College Board assessments                | assessment scores                         |
| `act`          | ACT assessment                           | assessment scores                         |
| `ap`           | Advanced Placement                       | assessment scores                         |
| `lea`          | local education agency                   | KIPP-assigned student/staff identifiers   |
| `nces`         | National Center for Education Statistics | federal college/school cross-reference ID |
| `fleid`        | Florida Education Identifier             | Florida state identifier                  |
| `smid`         | State Management ID                      | New Jersey state identifier (if surfaced) |

Additional acronyms can be added to this list during audit review — each
addition requires a documented specific-use justification.

### Specific-use jargon exceptions

Business-significant terms kept verbatim despite being technically
source-system-specific:

- `salesforce_contact_id` on `dim_students` — KIPPADB integration uses this
  identifier across consumer tools, and no generic name would be clearer.

Additional exceptions require a documented justification during audit review
(entered in the inventory `reviewer_notes`).

### Plumbing definition

Removed from all mart SELECTs during this refactor:

- `_dbt_source_relation` — dbt internal, union-model metadata
- Source-system internal row IDs used only for upstream joins (DeansList `lid`,
  Amplify record IDs, iReady submission IDs, PowerSchool `dcid`, etc.)
- Any column whose only historical use was as a join key in intermediate layers

Plumbing columns remain in staging/intermediate models where joins are performed
— they are not deleted from the warehouse, only removed from the mart
presentation layer.

## Structural additions

### `dim_students` — multi-ID

KIPP is a charter-LEA operating within a host school district (Newark Public
Schools, Camden City SD, Paterson Public Schools, Miami-Dade County Public
Schools). Students have identifiers at four distinct issuer levels, each
surfaced as its own column on the dim:

| Column                        | Nullability | Issuer                      | Source                                                                                                                                                                             |
| ----------------------------- | ----------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lea_student_identifier`      | NOT NULL    | KIPP (the LEA)              | PowerSchool `student_number` for NJ; Focus local ID for Miami (future). Unified column. Maps to Ed-Fi `District` / CEDS `District-assigned number` from KIPP-as-LEA's perspective. |
| `district_student_identifier` | nullable    | Host public school district | MDCPS for Miami students; Newark/Camden/Paterson Public Schools IDs for NJ where surfaced. Generalizes beyond Miami.                                                               |
| `state_student_identifier`    | nullable    | State education agency      | PowerSchool `state_studentnumber` (SMID for NJ, FLEID for FL); Focus state ID for Miami. Unified column.                                                                           |
| `salesforce_contact_id`       | nullable    | External (KIPPADB)          | KIPPADB (Salesforce) contact ID, populated where the student has a KIPPADB record.                                                                                                 |

`lea_student_identifier` and `state_student_identifier` are unified across SIS
sources — one column each, values sourced from PowerSchool or Focus depending on
the student's region. This unification changes hash values for Focus students
when Focus lands (see [Hash-change posture](#hash-change-posture)).

Neither Ed-Fi nor CEDS V14 exposes "LEA's own ID" vs. "host district's ID" as
distinct canonical attributes — both standards model identifiers as a single
`PersonIdentifier` / `StudentIdentificationCode` collection keyed by a
`*IdentificationSystemDescriptor`. The four columns are a deliberate flattening
that makes the KIPP-specific LEA-within-host-district hierarchy explicit for
analysts.

### Model renames

Two model names carry KIPP-specific "microgoal" jargon (rubric rule R2). Renamed
as companion changes to the per-column decisions in the audit inventory — the
column-level audit surfaced the jargon, and leaving the model names unchanged
would leave the jargon half-removed.

| Current                                 | Renamed                            |
| --------------------------------------- | ---------------------------------- |
| `dim_staff_observation_microgoal_types` | `dim_staff_observation_goal_types` |
| `fct_staff_observation_microgoals`      | `fct_staff_observation_goals`      |

All `*_microgoal_*` column renames in the inventory derive from these model
renames.

### `dim_staff` — email addresses

The existing three-column split on `dim_staff` is the final state. No structural
additions needed:

| Column           | Nullability | Source                                                      |
| ---------------- | ----------- | ----------------------------------------------------------- |
| `work_email`     | nullable    | ADP HR record (`communication__work_email__email_uri`).     |
| `personal_email` | nullable    | ADP HR record (`communication__personal_email__email_uri`). |
| `google_email`   | nullable    | Google Workspace account email (from LDAP).                 |

Active Directory is KIPP's primary identity system; `active_directory_username`
(renamed from `sam_account_name`) carries the AD login. Google Workspace
accounts are supplementary for Google products, surfaced as `google_email`. An
earlier proposal to add a fourth `microsoft_365_email` column was dropped —
`work_email` from ADP already covers that role, and AD-vs-M365 distinction is a
deployment detail that does not need a dedicated column.

## Structural follow-ups (out of scope for column naming)

Surfaced during the audit and empirical null-rate scan; tracked for separate
implementation PRs.

### `dim_colleges` — source from KIPPADB, not NSC

`dim_colleges` currently blends three sources: NSC (`stg_nsc__student_tracker`),
a gsheet crosswalk, and KIPPADB Salesforce (`stg_kippadb__account`). NSC is the
wrong authoritative source for static college metadata — it is a per-student
search dataset with sparse coverage (e.g., the audit's empirical null-rate scan
found `two_year_four_year` 0/1919 populated upstream). KIPPADB Account carries
150+ authoritative college attributes (selectivity, HBCU flag, academic rigor,
ACT/SAT ranges, retention rates) and is the college master at KIPP.

Refactor so the dim sources college attributes from KIPPADB first and falls back
to NSC only for records with no Salesforce match. `account_type` already encodes
2yr/4yr (values: `Private 4 yr`, `Public 4 yr`, `Public 2 yr`, `Private 2 yr`),
which made the NSC-sourced `two_year_four_year` both dead and redundant —
removed during this audit.

### Model bugs discovered during dead-column scan

The empirical null-rate scan flagged several columns as 100% null in production
that should not be. These are model bugs, not dead columns; they are kept in the
dim and tracked for separate fixes.

| Model                         | Column           | Issue                                                                                                                                       |
| ----------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_student_contact_persons` | `email`, `phone` | Upstream `int_powerschool__student_contacts` has 72k `email` contacts and 120k `mobile`. Dim's pivot from the long-format source is broken. |
| `dim_college_enrollments`     | `degree_title`   | Upstream NSC has data (53/1919); dim has 0/74. Join issue.                                                                                  |
| `dim_staff_status`            | all columns      | Entire table has 0 rows in production. Model logic is broken.                                                                               |

### `stg_people__employee_numbers` — incremental MERGE-on-NULL duplication

`stg_people__employee_numbers` accumulates 16 duplicate rows per run for each of
91 `employee_number` values whose `adp_associate_id` is `NULL` (1,456 duplicate
rows total). The incremental MERGE predicate never matches when the merge key is
`NULL`, so those orphan rows re-insert on every run. All downstream ADP columns
(name, email, hire date, rehire date) are `NULL` on these rows — they are dead
weight, not real staff records. A further 7 rows have populated
`adp_associate_id` but `is_active = false` and likewise carry `NULL` ADP
columns.

**Why the fix is downstream, not upstream**: the staging model is the
employee-number provisioner — its incremental branch computes
`MAX(employee_number) FROM {{ this }}` to assign the next-available number for
new hires. The `--full-refresh` needed to clear the accumulated duplicates is
policy-denied on this table because it would break sequential provisioning.

**Downstream workaround**: the `dim_staff` consumer filters dead weight with
`WHERE adp_associate_id IS NOT NULL AND is_active`, which collapses the 91
orphan groups to zero rows and drops the 7 inactive-with-ADP rows. This removes
all 98 dead-weight rows and lets `dim_staff` pass its `unique` test without a
`SELECT DISTINCT` workaround.

Tracked in GitHub issue
[#3637](https://github.com/TEAMSchools/teamster/issues/3637) for a dedicated
operational-planning PR that addresses the upstream MERGE-on-NULL behavior.

### `dim_assessments` — `scope` vs `assessment_scope` untangling

`dim_assessments` currently has two columns that appear to represent overlapping
concepts:

- `scope` — values like `CMA - End-of-Module`, `CGI Quiz`, `Test Prep` for
  internal assessments, and `SAT` / `ACT` / `AP` / `PSAT NMSQT` for college
  assessments.
- `assessment_scope` — value is `"enrollment"` for all internal assessments
  inspected during the audit.

The planned rename `scope` → `assessment_category` (Ed-Fi R6) collides
semantically with the existing `assessment_scope` column. Before applying the
rename, audit `assessment_scope` to determine (a) what it represents across
internal, state, and college assessments; (b) whether it is redundant with
`scope`; (c) which column should survive and under what canonical name.

### Region traversal cascade — blocks multiple R9 removes

Empirical check during Staffing-domain review revealed three compounding data
issues that block planned R9 removes of `dim_staffing_positions.entity` and
`.grade_band`:

1. `dim_regions.legal_entity` is 100% null in production. The column exists but
   has never been populated.
2. `dim_locations.region` is populated with **legal-entity names** ("TEAM
   Academy Charter School", "KIPP Cooper Norcross Academy", "KIPP Miami", "KIPP
   Paterson") rather than region names (Newark / Camden / Miami / Paterson).
   This is a data bug, not just a naming inconsistency.
3. 1,849 rows on `dim_staffing_positions` link to **campus-level** locations
   (`is_campus = true`), which have null `grade_band` on `dim_locations`. To
   remove `grade_band` from the staffing positions dim, positions need to link
   to school-specific locations rather than campus rollups.

Fix order: (1) populate `dim_regions.legal_entity` from ADP; (2) correct
`dim_locations.region` values; (3) relink campus-level staffing positions to
school locations. Only then can the R9 removes of
`dim_staffing_positions.entity` and `.grade_band` ship without information loss.

**Resolution — canonical region derivation in staging.** The region cascade is
unblocked in this PR by deriving canonical region in `stg_people__locations`
from `dagster_code_location` (values `kippnewark` / `kippcamden` / `kippmiami` /
`kipppaterson`), not from the raw Google Sheet's `region` column. The existing
legal-entity values in that column ("TEAM Academy Charter School", "KIPP Cooper
Norcross Academy", etc., matching `dim_regions.legal_entity`) are preserved by
renaming the column to `business_unit`. This aligns with the ADP/staff-side
naming convention on `dim_work_assignment_organizational_units.business_unit_*`.

### Staff → region traversal via `dim_work_assignment_locations` — Group 3 deferral

Completing the
`dim_staff → dim_staff_work_assignments → dim_work_assignment_locations → dim_locations → dim_regions`
chain requires three coordinated structural changes, all deferred from this PR:

1. **`dim_locations` address unification.** Add `address_line_one`,
   `address_line_two`, `city`, `postal_code` to the conformed locations dim so
   downstream work-location dims can drop their copies and traverse via FK.
2. **`dim_work_assignment_locations.location_key` FK.** Remove the 8 ADP-sourced
   address columns (`line_one`/`two`/`three`, `city_name`, `postal_code`,
   `country_code`, `state_code`, `location_code`, `location_name`), add a
   `location_key` FK to `dim_locations`. Blocked by (1) and by a reliable
   mapping from ADP `home_work_location__name_code__code_value` to
   `dim_locations.location_name` (expected to surface the same name-mismatch
   class of problem as the Talent domain's `shared_with_location_key`).
3. **Business-unit / region FK parity.**
   `dim_work_assignment_organizational_units` exposes `business_unit_code` /
   `business_unit_name` as degenerate attributes (values `KCNA`, `KIPP_MIAMI`,
   `KIPP_TAF`, `KPAT`, `TEAM`; names identical to `dim_regions.legal_entity`).
   Adding `business_unit_code` to `dim_regions` would enable direct FK from
   staff to regions for staff not attached to a physical work location (HQ,
   remote, network roles). Requires alignment on canonical business-unit code
   values across ADP and the conformed region master.

Tracked in [#3631](https://github.com/TEAMSchools/teamster/issues/3631).

## Hash-change posture

This refactor is prerelease. No backward compatibility is preserved for
downstream consumers.

Hash values for surrogate keys change **only** when one of these causes applies:

- **Values unify** — consolidating two source columns into one canonical column
  changes the underlying value (e.g., PS + Focus IDs into one
  `lea_student_identifier`).
- **Types change** — casting `int64` to `string` alters the concatenation input.
- **Composition changes** — adding or removing a column from the input list of
  `dbt_utils.generate_surrogate_key()`.
- **Null handling changes** — wrapping a previously-unwrapped nullable key in
  the `if(x is not null, hash(x), null)` pattern.
- **Structural add** — a new FK/degenerate surrogate is introduced where none
  existed before (no "before" hash to compare).

**Pure renames** — same value, same type, same composition, just a new column
label — produce identical hashes. Most of the 168 in-scope renames fall here.

### Enumerated surrogate-key changes

| Model.Column                                                      | Before derivation                                                                                              | After derivation                                                                                                                                                                                                                                              | Cause                                              |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `dim_terms.region_key`                                            | not present                                                                                                    | `generate_surrogate_key(["t.city"])` (derived from canonical city column on the terms row)                                                                                                                                                                    | Structural add                                     |
| `dim_terms.location_key`                                          | not present                                                                                                    | `generate_surrogate_key(["ll.location_name"])` via left join to `stg_people__locations` on `(school_id, city → region)`                                                                                                                                       | Structural add                                     |
| `dim_locations.region_key`                                        | not present                                                                                                    | `generate_surrogate_key(["region"])` on canonical region from `stg_people__locations`                                                                                                                                                                         | Structural add                                     |
| `dim_student_attendance_intervention_types.region_key`            | not present                                                                                                    | `generate_surrogate_key(["region_name"])`                                                                                                                                                                                                                     | Structural add                                     |
| `dim_student_attendance_intervention_types.intervention_type_key` | `generate_surrogate_key(["region", "commlog_reason"])` with mixed-case region (legal-entity and city variants) | `generate_surrogate_key(["region_name", "family_communication_reason"])` with canonical city-only region                                                                                                                                                      | Composition changes (input value + column renamed) |
| `fct_student_attendance_interventions.intervention_type_key`      | `generate_surrogate_key([<regex on _dbt_source_relation without initcap>, "commlog_reason"])`                  | `generate_surrogate_key(["initcap(regexp_extract(ai._dbt_source_relation, r'kipp(\\w+)_'))", "ai.commlog_reason"])` to match the dim's canonical region form                                                                                                  | Values unify (region casing realigned)             |
| `fct_student_attendance_interventions.family_communication_key`   | not present                                                                                                    | `generate_surrogate_key(["c.record_id", "c._dbt_source_relation"])` via join to `int_deanslist__comm_log`, wrapped in null-guard                                                                                                                              | Structural add                                     |
| `fct_behavioral_incidents.referring_staff_key`                    | not present                                                                                                    | `generate_surrogate_key(["sr.employee_number"])` via DeansList email lookup chain, wrapped in null-guard                                                                                                                                                      | Structural add                                     |
| `fct_family_communications.staff_key`                             | not present                                                                                                    | `generate_surrogate_key(["sr.employee_number"])` via same DeansList chain, wrapped in null-guard                                                                                                                                                              | Structural add                                     |
| `fct_job_candidate_applications.shared_with_location_key`         | not present                                                                                                    | `generate_surrogate_key(["school_shared_with"])`, wrapped in null-guard; warn-severity relationships test per [#3672](https://github.com/TEAMSchools/teamster/issues/3672)                                                                                    | Structural add                                     |
| `dim_staff_work_assignments.time_service_supervisor_staff_key`    | not present                                                                                                    | `generate_surrogate_key(["sup.employee_number"])` via second self-join on `stg_people__employee_numbers`, null-guarded                                                                                                                                        | Structural add                                     |
| `dim_work_assignment_reporting_relationships.manager_staff_key`   | not present                                                                                                    | `generate_surrogate_key(["mgr.employee_number"])` via same pattern, null-guarded                                                                                                                                                                              | Structural add                                     |
| `fct_student_attendance_daily.term_key`                           | raw `ada.term` string exposed as `term_code`                                                                   | `generate_surrogate_key(["t.``type``", "t.code", "t.``name``", "t.``start_date``", "t.region", "t.school_id"])` via left join to `stg_google_sheets__reporting__terms` on `(school_id, code, academic_year)`; warn-severity relationships test to `dim_terms` | Structural add (replaces degenerate `term_code`)   |

### Unchanged surrogate keys (explicit confirmation)

Values preserved despite visible column renames elsewhere on the row:

- `dim_students.student_key` — still hashes `student_number`. Renames
  `local_student_identifier` → `lea_student_identifier`, `gender` →
  `gender_identity`, etc. are pure mart-layer aliases of pre-existing columns;
  they do not feed the hash.
- `dim_staff.staff_key` — still hashes `employee_number`. The `staff_unique_id`
  surface name is an alias of the same column the hash reads.
- `dim_regions.region_key` — still hashes the CTE-local `region` value inside
  the UNION ALL. The `region → region_name` output rename is a pure alias after
  the hash is computed.
- All Course, Talent, Survey, College, Gradebook, Assessment, Observation, and
  Staffing domain keys on models whose SQL was renamed only — the hash input
  columns were not touched. Scanned via compiled-SQL grep post-rebuild and
  confirmed identical derivations.

SCD2 dims renamed `is_current_record` → `is_current`, `is_current_record_group`
→ `is_current_group`, and similar — these are boolean flags on SCD output rows,
not surrogate-key hash inputs, so they are not in the list above even though
they were renamed in this PR.

## Audit inventory workflow

The audit inventory is a CSV kept under this spec's directory, imported into a
Google Sheet for review, and exported back on approval. The CSV is the durable
record; the sheet is ephemeral scaffolding.

### Generation

A one-off script reads every mart model's YAML contract (or
`INFORMATION_SCHEMA.COLUMNS` for any un-yaml'd columns) and emits a CSV with
these columns:

| Column                | Populated by                      | Editable in sheet |
| --------------------- | --------------------------------- | ----------------- |
| `domain`              | script                            | no                |
| `model`               | script                            | no                |
| `current_column`      | script                            | no                |
| `data_type`           | script                            | no                |
| `current_description` | script                            | no                |
| `action`              | script (initial guess) + reviewer | yes               |
| `proposed_name`       | script (initial guess) + reviewer | yes               |
| `rule_ref`            | script (initial guess) + reviewer | yes               |
| `review_status`       | reviewer                          | yes               |
| `reviewer_notes`      | reviewer                          | yes               |

Valid `action` values: `keep`, `rename`, `remove`, `add`.

Valid `review_status` values: `not_reviewed`, `approved`, `needs_discussion`.

Valid `rule_ref` values: `R1`–`R10` (rubric rules), `structural` (new column),
`plumbing` (removal), `exception` (specific-use jargon exception),
`acronym_allowlist` (acronym preserved via allow-list).

Initial CSV location:

```text
docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv
```

Structural-addition rows (new columns on `dim_students` and `dim_staff`) are
pre-populated in the inventory with `action: add`.

### Review

1. Project owner creates a Google Sheet and imports the generated CSV.
2. Owner shares the sheet with the project team (edit access) and adds the sheet
   URL to issue [#3643](https://github.com/TEAMSchools/teamster/issues/3643).
3. Reviewers annotate each row using the `review_status` and `reviewer_notes`
   columns. Proposed names are adjusted in place when needed.
4. When all rows reach `approved` status, export the sheet back to CSV and
   commit as the approved snapshot:

   ```text
   docs/superpowers/specs/2026-04-15-column-naming-audit-approved.csv
   ```

**Sheet URL**:
https://docs.google.com/spreadsheets/d/1-2HyPIJzaXMsIgY3e9rLOU4W0HLOk7foDKXFU0NCa-4

### Implementation

After the approved CSV lands in the repo, a second script reads the approved
actions and emits the SQL + YAML edits for a single PR covering all renames,
additions, and removals. See the implementation plan (writing-plans follow-up)
for script structure and edit mechanics.

## Execution

One PR covering:

- SQL renames across all ~60 mart models
- YAML contract updates (`data_type`, `description`, column `name`) for every
  renamed, added, or removed column
- Plumbing columns removed from mart `SELECT` clauses
- Structural additions (`dim_students` IDs, `dim_staff` emails) implemented in
  the relevant staging/intermediate layers and surfaced in the mart
- Refreshed column descriptions in plain analyst-facing language
- `trunk fmt` + `trunk check --ci` clean
- dbt Cloud CI validates contracts and tests pass

## Open questions

Resolved during audit review:

- **Focus local and state IDs** — confirm Focus API field names once Focus
  integration lands and decide whether unification under
  `local_student_identifier` / `state_student_identifier` is clean or requires a
  separate Focus-specific column.
- **Microsoft 365 email column name** — confirm exact name
  (`microsoft_365_email` vs. `m365_email` vs. `office_365_email`).
- **Internal acronyms** — each encountered acronym (`dcid`, `oid`, `lep`, and
  others discovered during audit) is reviewed. Default disposition is rename or
  remove; exceptions are added to the acronym allow-list with justification.
- **Code+name degenerate dimensions** — confirm whether any mart models ship
  both `_code` and `_name` variants today and should continue to.
- **Additional specific-use jargon exceptions** — any term surfaced during audit
  that warrants the same exception treatment as `salesforce_contact_id`.

## Out of scope

- Cube YAML files and `title:` polish
  ([#3591](https://github.com/TEAMSchools/teamster/issues/3591) follow-up)
- Retiring existing `extracts/` models
- Non-mart reporting views (`rpt_*`)
- Google Group creation and Cube access policies
  ([#3591](https://github.com/TEAMSchools/teamster/issues/3591))
- Downstream consumer communication
