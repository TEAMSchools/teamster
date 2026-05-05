# Ed-Fi Schema Profiling and Description Propagation

## Summary

Enrich the column naming audit inventory
([#3643](https://github.com/TEAMSchools/teamster/issues/3643)) with two new
signals: (1) automated Ed-Fi attribute matching against mart column names, and
(2) lineage-based propagation of source-system staging descriptions into
intermediate and mart YAML. Together these give reviewers a "from → to" picture
for each column — what it means in the source system, and what Ed-Fi calls it —
without requiring manual cross-referencing.

Builds on the data dictionary enrichment completed in
[#3516](https://github.com/TEAMSchools/teamster/issues/3516) / PR #3653, which
populated staging YAML descriptions for PowerSchool and ADP.

## Goals

- Every mart column with a traceable staging ancestor gets the source-system
  description, source system name, and original column name written into its dbt
  YAML `description` field.
- Every mart column in the audit inventory gets Ed-Fi attribute candidates
  (exact or fuzzy) surfaced in `proposed_name` and/or `reviewer_notes`.
- Reviewers see both signals inline in the inventory CSV without consulting
  external references.
- No changes to Dagster runtime behavior.

## Non-goals

- Enabling `with_column_lineage=True` in the Dagster dbt asset builder — this
  work uses the same sqlglot approach offline only.
- Descriptions for computed columns (CASE, COALESCE, aggregations) — these are
  untraceable and get documented by hand during audit review.
- Staging, extract, or rpt model YAML changes — staging is already enriched by
  #3516; extract and rpt models are out of scope per the audit spec.
- Curating or filtering the Ed-Fi attribute set — broad automated matching is
  preferred over introducing additional uncertainty via curation.

## Three-step pipeline

Three scripts, run sequentially, each producing a committed artifact:

1. **Extract Ed-Fi schema** — fetch and vendor a snapshot of Ed-Fi attribute
   names and descriptions.
2. **Propagate mart descriptions** — use `dbt compile` output and sqlglot to
   trace column lineage, then write staging descriptions into intermediate and
   mart YAML.
3. **Regenerate inventory** — enhanced inventory script loads the Ed-Fi extract,
   runs tiered matching, and emits the updated CSV. Mart descriptions (enriched
   by step 2) flow in automatically via `current_description`.

## Step 1: Vendored Ed-Fi extract

### Script

`scripts/extract_edfi_schema.py`

### Source

`Ed-Fi-Alliance-OSS/Ed-Fi-Data-Standard`, file
`Schemas/JSON/Ed-Fi-Resource-API-Specification.yaml` (v6.1.0).

### Extraction

- Fetch the OpenAPI spec via `gh api` (raw content download).
- Parse the YAML, walk the `components.schemas` section.
- For each schema/entity, extract every property:
  `(entity_name, attribute_name_camelCase, description)`.
- Convert each `attribute_name_camelCase` to `snake_case` for matching.
- Include descriptor-reference properties — reviewers decide relevance.

### Output

`docs/superpowers/specs/edfi-v6.1.0-attributes.csv`

| Column            | Example                                                     |
| ----------------- | ----------------------------------------------------------- |
| `entity`          | `edFi_student`                                              |
| `attribute_camel` | `birthDate`                                                 |
| `attribute_snake` | `birth_date`                                                |
| `description`     | `The month, day, and year on which an individual was born.` |

Version-pinned filename. Regenerating for a future Ed-Fi release means running
the script with a new tag and committing the updated file.

Size estimate: ~1,200 rows. Lightweight, readable, diffable.

## Step 2: Mart description propagation

### Script

`scripts/propagate_mart_descriptions.py`

### Inputs

- Compiled SQL from `dbt compile --project-dir src/dbt/kipptaf` (Jinja
  resolved).
- kipptaf manifest (`src/dbt/kipptaf/target/manifest.json`) — for source name →
  table reference mapping.
- Source-system package staging YAMLs (all 10 packages: powerschool, adp,
  deanslist, amplify, edplan, finalsite, iready, overgrad, pearson, renlearn,
  titan).
- kipptaf intermediate and mart YAML properties files (write targets).

### Description dict construction

Walk all source-system package staging YAML dirs (e.g.,
`src/dbt/powerschool/models/sis/staging/properties/*.yml`). Build a dict keyed
by `(package_name, model_name, column_name)` containing
`{description, contains_pii}`. Source system inferred from the package directory
name.

### Cross-project source boundary resolution

kipptaf references regional project outputs (kippnewark, kippcamden, kippmiami,
kipppaterson) via dbt sources. Regional projects install source-system packages
as local dependencies and materialize staging as tables. kipptaf unions these
via `union_relations()`.

The propagation script resolves this chain:

1. Parse the kipptaf manifest's `sources` section to build a mapping: compiled
   BigQuery table reference → `(source_name, table_name)`.
2. The source name encodes the regional project and package (e.g.,
   `kippnewark_powerschool`). The region prefix is one of `kippnewark_`,
   `kippcamden_`, `kippmiami_`, `kipppaterson_`. Strip it to get the package
   name (`powerschool`).
3. When the lineage trace hits a source table, use this mapping to look up the
   package and staging model, then fetch the description from the dict.

### Lineage extraction

- For each kipptaf intermediate and mart model, read the compiled SQL from
  `target/compiled/`.
- Parse with sqlglot (BigQuery dialect, v28.0.0, already a project dependency).
- Walk the AST to extract final SELECT column mappings:
  `output_alias → source_table.source_column`.
- Follow the chain through CTEs and upstream `ref()` models — no hop limit. The
  DAG guarantees termination.
- When the trace reaches a source table, use the boundary resolution mapping to
  look up the description.
- For computed expressions (CASE, COALESCE, aggregations, etc.), stop and mark
  as untraceable.

### Write behavior

- Strictly additive — only write where `description` is empty or absent.
- Format:
  `"{staging_description}. Source: {source_system} {model_name}.{original_column}."`
- Example: `"Date of Birth. Source: PowerSchool stg_powerschool__students.dob."`
- If the staging column has `contains_pii: true`, propagate into
  `meta.contains_pii` on the target column.
- No changes to column names, data types, constraints, or anything else.

### Scope

All intermediate and mart models under `src/dbt/kipptaf/models/` that have YAML
properties files. Excludes staging (already enriched by #3516), extracts, and
rpt models.

### Edge cases

- **Union columns** — kipptaf staging models union 4 regions of the same source
  table. Column names are identical across regions, so any region's YAML
  provides the description. The script picks the first match.
- **Multi-source columns** — if a column traces to multiple different staging
  columns (e.g., a COALESCE across sources), mark as untraceable rather than
  pick one.
- **kipptaf-only models** — some intermediates do not trace back to source
  packages (e.g., crosswalk tables, seed-derived models). These get skipped
  naturally when no source match is found.

### Expected coverage

~30–40% of intermediate and mart columns are simple passthroughs and will get
descriptions. The remainder are computed/joined and get skipped — those are
documented by hand during audit review.

## Step 3: Enhanced inventory generation

### Changes to `gen_column_naming_audit_inventory.py`

**Removed**: `_EDFI_COGNATES` dict and its lookup in `_check_naming_rules()`.

**Loading**: On startup, load the vendored Ed-Fi CSV into a dict:
`{attribute_snake: [(entity, attribute_camel, description), ...]}`. Multiple
entities may define the same snake_case attribute — store all as a list.

### Matching tiers

Applied after R1/R2/R7/R9/plumbing rules.

**Tier 1 — Exact token match**:

- Convert both names to token sets (`birth_date` → `{birth, date}`).
- If sets are equal → exact match.
- Result: `action: rename`, `proposed_name` populated, `rule_ref: R6`.
- `reviewer_notes` includes Ed-Fi entity, camelCase name, and description for
  each matching entity.
- Multiple entity matches listed — reviewer picks the relevant one.

**Tier 2 — Fuzzy match (SequenceMatcher)**:

- For columns with no exact match and no existing rule flag.
- Compare against all Ed-Fi `attribute_snake` values using
  `difflib.SequenceMatcher`, threshold ratio >= 0.6.
- Top 3 candidates above threshold.
- Result: `action: keep`, `rule_ref: R6`, candidates in `reviewer_notes`.

### Ed-Fi candidates as informational notes

When another rule already sets the `action` (R1, R2, R7, R9, plumbing), Ed-Fi
candidates are still appended to `reviewer_notes` — they suggest what to rename
to, even though the flagging came from a different rule. Example: R2 flags
`employee_number` as KIPP jargon; Ed-Fi fuzzy candidates are appended to help
the reviewer pick a replacement name.

### Priority order

For `action` assignment — first match wins:

1. Plumbing (`_dbt_source_relation`)
2. R9 (redundant — reachable via FK)
3. R1 (source-system prefix/term)
4. R2 (KIPP-specific jargon)
5. R7 (internal acronyms)
6. Ed-Fi exact token match
7. Ed-Fi fuzzy match (`keep` action, candidates in notes only)

Ed-Fi notes are always appended regardless of which rule set the action.

## Execution order and prerequisites

### Step 1: Compile dbt models

```bash
uv run dbt compile --project-dir src/dbt/kipptaf
```

Produces compiled SQL under `target/compiled/` with all Jinja resolved. Required
for the propagation script.

### Step 2: Extract Ed-Fi schema (can run in parallel with step 1)

```bash
uv run scripts/extract_edfi_schema.py
```

Fetches the OpenAPI spec from GitHub, writes
`docs/superpowers/specs/edfi-v6.1.0-attributes.csv`.

### Step 3: Propagate mart descriptions (depends on step 1)

```bash
uv run scripts/propagate_mart_descriptions.py
```

Reads compiled SQL + staging YAML → writes descriptions into intermediate and
mart YAML.

### Step 4: Regenerate inventory (depends on steps 2 and 3)

```bash
uv run scripts/gen_column_naming_audit_inventory.py
```

Reads mart YAML (now enriched) + Ed-Fi extract → writes updated inventory CSV.

### Step 5: Re-import to Google Sheet (manual)

Project owner imports the updated CSV into the existing sheet, replacing the
previous import.

### Artifacts committed to the branch

- `docs/superpowers/specs/edfi-v6.1.0-attributes.csv` (vendored Ed-Fi extract)
- `src/dbt/kipptaf/models/**/properties/*.yml` (enriched descriptions on
  intermediate and mart models)
- `docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv`
  (regenerated)

### Not committed

- `target/compiled/` (gitignored, ephemeral)

## Out of scope

- Dagster runtime changes (`with_column_lineage` stays `False`).
- Computed column descriptions — untraceable, documented by hand during review.
- Staging, extract, or rpt model YAML changes.
- Ed-Fi attribute curation or filtering.
- Modifying the existing audit spec rubric, acronym allow-list, or structural
  additions.
