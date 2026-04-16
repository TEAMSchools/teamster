# Source-System Data Dictionary Enrichment

## Summary

Two scripts that extract column descriptions and PII flags from PowerSchool and
ADP data dictionary PDFs, then write them into dbt staging YAML properties
files. Covers all staging models for both source systems in a single run. Review
via PR diff — no intermediate registry.

Tracked on [#3516](https://github.com/TEAMSchools/teamster/issues/3516). Feeds
into [#3643](https://github.com/TEAMSchools/teamster/issues/3643) (column naming
audit) by enriching the staging layer that the audit's staging-diff detection
will reference.

## Goals

- Populate `description:` on the ~99% of staging columns that currently lack
  one, using authoritative source-system documentation.
- Add `config.meta.contains_pii: true/false` on every enriched column,
  establishing a machine-readable PII inventory that Cube's `accessPolicy`
  generation can consume later
  ([#3591](https://github.com/TEAMSchools/teamster/issues/3591)).
- Surface unmatched columns in both directions (PDF entries with no YAML match,
  YAML columns with no PDF entry) so coverage gaps are visible.

## Non-goals

- Enriching non-PS/non-ADP staging models (DeansList, Amplify, etc.) — no
  source-system PDFs provided for those systems.
- Writing mart-layer descriptions — those are analyst-facing and belong in the
  #3643 naming audit workflow.
- Enforcing data masking — `contains_pii` is metadata for documentation and
  downstream policy generation, not enforcement. Cube accessPolicy and BigQuery
  policy tags handle enforcement separately.
- Describing ADP `ARRAY<STRUCT<...>>` columns — these are structural containers
  unpacked in intermediate models. Descriptions belong on the leaf fields
  downstream, not the array wrapper.

## Source PDFs

Both PDFs are stored locally at `.claude/scratch/` (gitignored, never
committed):

| PDF                                                     | Source system | Pages | Format                                                                         |
| ------------------------------------------------------- | ------------- | ----- | ------------------------------------------------------------------------------ |
| `PSDB_PSSISDD_20241701.pdf`                             | PowerSchool   | 808   | Table-per-page: table name, then rows of Column Name / Data Type / Description |
| `Worker_Management_API_Guide_for_ADP_Workforce_Now.pdf` | ADP           | 84    | Appendix data dictionary: Schema Location (JSON path) / Field Name / Note      |

## Architecture

Two scripts, run sequentially:

```text
PDF files (gitignored)
    │
    ▼
scripts/extract_pdf_dictionary.py
    │  Reads PDF, extracts field descriptions,
    │  matches to staging YAML column names
    ▼
.claude/scratch/<source>_dictionary.json (build artifact, gitignored)
    │
    ▼
scripts/enrich_staging_descriptions.py
    │  Reads JSON mapping(s), writes description
    │  and contains_pii to staging YAML files
    ▼
src/dbt/**/staging/properties/*.yml (modified in place)
    │
    ▼
PR diff (review surface)
```

### Script 1: `scripts/extract_pdf_dictionary.py`

**Input**: PDF file path + source system identifier (`powerschool` or `adp`).

**Output**: JSON mapping file at `.claude/scratch/<source>_dictionary.json`.

**Matching logic — PowerSchool**:

1. Parse PDF page by page. Each table section starts with a table name header
   and contains rows of
   `Column Name | InitialVersion | Data Type | Description`.
2. Convert table name to model name: `Students` → `stg_powerschool__students`
   (PascalCase → snake_case, prepend prefix).
3. Convert column name: `StudentNumber` → `student_number` (PascalCase →
   snake_case).
4. Match against actual YAML files under
   `src/dbt/powerschool/models/**/staging/properties/` and
   `src/dbt/kipptaf/models/powerschool/**/staging/properties/`.
5. Record match or add to unmatched list.

**Matching logic — ADP**:

1. Parse PDF appendix data dictionary pages. Each row has a Schema Location
   (JSON path like `/workers/person/birthDate`), Field Name (UI label), and
   Note.
2. Strip the `/workers/` prefix (root entity).
3. Convert remaining path segments from camelCase to snake_case, join with `__`:
   `/workers/person/birthDate` → `person__birth_date`.
4. Match against column names in ADP staging YAMLs under
   `src/dbt/kipptaf/models/adp/**/staging/properties/`.
5. Skip paths that resolve to `ARRAY<STRUCT<...>>` columns (structural
   containers, not leaf fields).
6. Record match or add to unmatched list.

**PII classification**: heuristic based on column name patterns and PDF
description content:

- `true`: names (first, last, middle, formatted), dates of birth, SSN/tax IDs,
  addresses (street, city, zip), phone numbers, email addresses, government IDs,
  emergency contacts.
- `false`: everything else.

Reviewer corrects misclassifications in the PR diff.

**Output JSON schema**:

```json
{
  "source": "powerschool",
  "extracted_at": "2026-04-16T12:00:00Z",
  "stats": {
    "pdf_entries": 5000,
    "yaml_columns": 3000,
    "matched": 2800,
    "unmatched_pdf": 2200,
    "unmatched_yaml": 200
  },
  "entries": [
    {
      "source_table": "Students",
      "source_column": "Student_Number",
      "model": "stg_powerschool__students",
      "column": "student_number",
      "description": "District-assigned student number.",
      "contains_pii": false
    }
  ],
  "unmatched_pdf": [{ "table": "TableX", "column": "ColumnY" }],
  "unmatched_yaml": [{ "model": "stg_powerschool__foo", "column": "bar" }]
}
```

**Stdout summary**: prints matched/unmatched counts and top unmatched entries
for quick inspection.

### Script 2: `scripts/enrich_staging_descriptions.py`

**Input**: one or more JSON mapping files from script 1.

**Output**: direct edits to staging YAML properties files.

**Per-column behavior**:

- `description:` absent or empty → write the PDF description.
- `description:` already exists and non-empty → skip (preserve hand-written
  descriptions).
- `config.meta.contains_pii:` → write from the JSON mapping. Overwrites if
  present (PII classification from the PDF is authoritative).

**YAML handling**: `pyyaml` (available transitively via dbt-core). Comments in
YAML files will be lost on rewrite — trunk fmt normalizes formatting afterward.
This is an accepted trade-off: commented-out columns in PowerSchool YAMLs (used
as informal documentation) will be removed, but the PDF-sourced descriptions are
a better documentation mechanism.

**Stdout summary**: prints per-file stats (columns enriched / skipped / total).

## Execution workflow

```bash
# 1. Extract from PDFs
uv run scripts/extract_pdf_dictionary.py \
    .claude/scratch/PSDB_PSSISDD_20241701.pdf powerschool
uv run scripts/extract_pdf_dictionary.py \
    .claude/scratch/Worker_Management_API_Guide_for_ADP_Workforce_Now.pdf adp

# 2. Inspect mappings (optional)
cat .claude/scratch/powerschool_dictionary.json | python3 -m json.tool | head

# 3. Apply to YAMLs (all source systems at once)
uv run scripts/enrich_staging_descriptions.py \
    .claude/scratch/powerschool_dictionary.json \
    .claude/scratch/adp_dictionary.json

# 4. Review and commit
git diff  # inspect YAML changes
git add -u
git commit -m "feat(dbt): enrich staging descriptions from source dictionaries"
```

## Scale

| Source      | YAML files                       | Columns | PDF pages | Expected match rate                                          |
| ----------- | -------------------------------- | ------- | --------- | ------------------------------------------------------------ |
| PowerSchool | ~81 (PS project) + ~34 (kipptaf) | ~3,000  | 808       | High — column names map directly from DB schema              |
| ADP         | ~8 (kipptaf)                     | ~200    | 84        | Moderate — path flattening has edge cases for nested structs |

## Testing

- Unit tests for case-conversion helpers (PascalCase → snake_case, camelCase →
  snake_case).
- Unit tests for PDF parsing functions with small fixture text blocks (extracted
  from the real PDFs).
- Unit tests for the YAML enrichment writer (round-trip: read YAML, enrich,
  verify output).
- Integration test: run extraction against a single-page PDF fixture, then
  enrichment against a single YAML fixture, verify end-to-end.

## Open questions

- **PowerSchool table-name casing**: are table names always PascalCase in the
  PDF, or do some use different conventions (e.g., `CC` for course-class,
  `StoredGrades` vs `STOREDGRADES`)? Affects matching robustness. Resolved
  during implementation by inspecting the full PDF.
- **ADP SFTP models**: the 4 SFTP staging models (`additional_earnings_report`,
  `employee_memberships`, `pension_and_benefits_enrollments`, `workers`) source
  from CSV files, not the API. The PDF covers the API only. Are there separate
  ADP SFTP field docs, or do we skip SFTP models?
- **kipptaf PowerSchool staging**: kipptaf has ~34 PS staging models that
  re-stage or extend the source-project models. Do we enrich those too, or only
  the source-project YAMLs?
