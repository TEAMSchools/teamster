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
3. **Boolean fields use `is_` / `has_` prefix**.
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

Degenerate-dimension text columns (e.g., `incident_type`, `consequence_type`,
`assignment_type`) drop `_code` / `_name` suffixes unless a code AND a human
name coexist in the same table — in which case both suffixes stay.

### Acronym allow-list

User-facing acronyms explicitly preserved in column names:

| Acronym        | Meaning                          | Context                                   |
| -------------- | -------------------------------- | ----------------------------------------- |
| `gpa`          | grade point average              | student grades                            |
| `ada`          | average daily attendance         | student attendance                        |
| `fte`          | full-time equivalent             | staff assignments                         |
| `dob`          | date of birth                    | person attributes                         |
| `ell`          | English language learner         | student attributes                        |
| `iep`          | individualized education plan    | student attributes                        |
| `sat` / `psat` | College Board assessments        | assessment scores                         |
| `act`          | ACT assessment                   | assessment scores                         |
| `ap`           | Advanced Placement               | assessment scores                         |
| `mdcps`        | Miami-Dade County Public Schools | Miami student identifier                  |
| `fleid`        | Florida Education Identifier     | Florida state identifier                  |
| `smid`         | State Management ID              | New Jersey state identifier (if surfaced) |

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

Surface the identifiers analysts cross-reference against external systems. Four
ID columns total:

| Column                     | Nullability | Source                                                                                                   |
| -------------------------- | ----------- | -------------------------------------------------------------------------------------------------------- |
| `local_student_identifier` | NOT NULL    | PowerSchool `student_number` for NJ; Focus local ID for Miami (future). Unified column.                  |
| `state_student_identifier` | nullable    | PowerSchool `state_studentnumber` (SMID for NJ, FLEID for FL); Focus state ID for Miami. Unified column. |
| `mdcps_student_identifier` | nullable    | Miami-Dade County Public Schools ID, populated for Miami students only.                                  |
| `salesforce_contact_id`    | nullable    | KIPPADB (Salesforce) contact ID, populated where the student has a KIPPADB record.                       |

`local_student_identifier` and `state_student_identifier` are unified across SIS
sources — one column each, values sourced from PowerSchool or Focus depending on
the student's region. This unification changes hash values for Focus students
when Focus lands (see [Hash-change posture](#hash-change-posture)).

### `dim_staff` — email split

Replace the previously proposed single `organization_email` with two columns so
staff from Google Workspace regions and Microsoft 365 regions both have their
primary email surfaced:

| Column                | Nullability | Source                                             |
| --------------------- | ----------- | -------------------------------------------------- |
| `google_email`        | nullable    | Google Workspace email (from LDAP).                |
| `microsoft_365_email` | nullable    | Microsoft 365 email (from LDAP or directory sync). |

The exact name `microsoft_365_email` vs. alternatives (`m365_email`,
`office_365_email`) is confirmed during audit review.

## Hash-change posture

This refactor is prerelease. No backward compatibility is preserved for
downstream consumers.

Hash values for surrogate keys change **only** when:

- **Values unify** — e.g., consolidating PS and Focus IDs into one
  `local_student_identifier` column changes the underlying value for Focus
  students.
- **Types change** — e.g., casting `int64` to `string` alters the concatenation
  input.
- **Composition changes** — e.g., adding or removing a column from the composite
  surrogate-key input list of `dbt_utils.generate_surrogate_key()`.
- **Null handling changes** — e.g., wrapping a previously-unwrapped nullable key
  in the `if(x is not null, hash(x), null)` pattern.

**Pure renames** — same value, same type, same composition, just a new column
label — produce identical hashes. Most of the 67 originally flagged renames fall
here.

The audit inventory flags each row that affects surrogate keys with the specific
hash-change cause.

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

Valid `review_status` values: `not_reviewed`, `approved`, `needs_discussion`,
`rejected`, `alt_suggested`.

Valid `rule_ref` values: `R1`–`R8` (rubric rules), `structural` (new column),
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

**Sheet URL**: _TBD — added to this section when the sheet is created._

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
