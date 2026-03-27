# Star Schema Advisor — Consolidated Design Spec

**Date:** 2026-03-27 **Status:** Draft **Tracks:**
[#3513](https://github.com/TEAMSchools/teamster/issues/3513) **Supersedes:** All
prior specs on branches `claude/feat/tableau-upstream-tool` and
`claude/feat/star-schema-advisor`, plus `scripts/tableau-extract-calcs.py` on
main.

---

## Problem

The Data Team is migrating Tableau calculated fields upstream into the dbt model
lineage and eventually into a Cube semantic layer. Each Tableau reporting view
(`rpt_tableau__*`) contains a mix of fields that belong in different places —
some in existing marts, some in new marts, some in the semantic layer, and some
that should stay in the BI tool. There is no systematic way to extract,
classify, and route these fields today.

Three parallel efforts have attempted to solve this (two Claude Code branches
plus an uncommitted handoff session). This spec consolidates the best elements
into a single solution.

## Key Design Decisions

1. **Both extraction modes are supported.** The script provides two mutually
   exclusive ways to obtain workbook XML:
   - **`--file` (primary, recommended)**: User downloads `.twbx` from Tableau
     Server manually and drops it in the gitignored `workbooks/` folder. No
     credentials or network access required.
   - **`--exposure` (secondary, optional)**: Fetches directly from Tableau
     Server via REST API using PAT credentials. Currently unusable for the
     team's primary server (`kippnj` on `tableau.kipp.org`) due to MCP connector
     limitations, but preserved as a code path for future use or other
     environments.

2. **Thin script + rich slash command.** The Python script handles only XML
   parsing and JSON output (pure I/O). All classification, mart matching, report
   generation, and dbt changes are driven by the slash command (pure reasoning).

3. **4-bucket hybrid verdicts.** Fields are grouped into 4 top-level categories
   (move upstream / existing mart for Cube / new mart for Cube / stay on
   Tableau), each with granular sub-verdicts for precision.

4. **Report + apply + validate.** After analyst approval, the command writes dbt
   changes (unstaged), validates with `dagster-dbt prepare-and-package` and
   `dbt show`, then the analyst reviews via `git diff` before committing.

## Solution Overview

Two components:

1. **`scripts/tableau-analyze-workbook.py`** — Python script (pure I/O). Parses
   Tableau `.twb`/`.twbx` XML and emits structured JSON with every field's
   formula, datatype, and viz usage (which worksheets use it, as dimension or
   measure, with aggregation type).

2. **`.claude/commands/star-schema-advisor.md`** — Claude Code slash command
   (pure reasoning). Consumes the script's JSON, reads dbt models and mart
   property YAML, classifies every field into 4 buckets, writes a markdown
   report, applies approved dbt changes, and validates with `dbt show`.

```
User obtains .twbx (download or API)
        │
        ▼
 /star-schema-advisor  (slash command)
        │
        ▼
 tableau-analyze-workbook.py  →  JSON (fields + viz usage)
        │
        ▼
 reads rpt_tableau__*.sql + ref() chain
        │
        ▼
 scans models/marts/properties/*.yml  →  column→mart lookup
        │
        ▼
 classifies fields into 4 buckets (a/b/c/d)
        │
        ▼
 writes report to docs/superpowers/star-schema-reports/
        │
        ▼
 analyst reviews + approves
        │
        ▼
 applies changes to correct layer (int_*, dim_*, fct_*)
 validates with dbt show  →  analyst reviews git diff  →  commits
        │
        ▼
 Semantic Layer Queue  →  /cube-measure-generator (downstream)
```

---

## Component 1: `scripts/tableau-analyze-workbook.py`

### Two Extraction Modes

The script supports two mutually exclusive input methods for obtaining Tableau
workbook XML:

#### Primary: Local File (`--file`)

```bash
uv run scripts/tableau-analyze-workbook.py --file workbooks/MyWorkbook.twbx
```

Users download `.twbx` files from Tableau Server manually and drop them in
`workbooks/` at the repo root. This folder is gitignored — workbook files are
never committed.

- Reads `.twb` (plain XML) or `.twbx` (zip archive containing a `.twb`)
- No credentials or network access required
- This is the default and recommended path

#### Secondary: Tableau Server API (`--exposure`)

```bash
uv run scripts/tableau-analyze-workbook.py --exposure my_dashboard
```

Fetches a workbook directly from Tableau Server using the REST API. This path
exists for environments where direct API access is available, but is not
currently usable for the team's primary server (`kippnj` subsite on
`tableau.kipp.org`) due to MCP connector limitations.

- Reads exposure names and LSIDs from
  `src/dbt/kipptaf/models/exposures/tableau.yml`
- Auth: PAT via env vars (`TABLEAU_TOKEN_NAME` +
  `TABLEAU_PERSONAL_ACCESS_TOKEN`). Falls back to username/password via
  `getpass` only if `--username` flag is passed and PAT env vars are absent.
  Raises `SystemExit` if no credentials are available.
- Enforces HTTPS before sending credentials
- Downloads workbook bytes into memory (no disk write), extracts `.twb` via
  `io.BytesIO`
- Filter injection prevention: strips `:` and `,` from workbook names before
  REST API queries
- Cleanup: calls `signout()` in a `finally` block (swallows `RequestException`)

### JSON Output Schema

The script writes JSON to stdout. The slash command captures and parses it.

```json
{
  "workbook": "Student Grades Dashboard",
  "source": "workbooks/Student Grades Dashboard.twbx",
  "datasources": [
    {
      "caption": "rpt_tableau__student_grades (kipptaf_tableau)",
      "fields": [
        {
          "name": "gpa_points",
          "datatype": "real",
          "formula": null,
          "is_calculated": false,
          "contains_lod": false,
          "viz_usage": [
            {
              "worksheet": "GPA Summary",
              "role": "measure",
              "aggregation": "AVG"
            }
          ]
        },
        {
          "name": "GPA Weighted",
          "datatype": "real",
          "formula": "SUM([gpa_points] * [credit_hours]) / SUM([credit_hours])",
          "is_calculated": true,
          "contains_lod": false,
          "viz_usage": [
            {
              "worksheet": "GPA Summary",
              "role": "measure",
              "aggregation": "SUM"
            },
            {
              "worksheet": "Student Detail",
              "role": "measure",
              "aggregation": "AVG"
            }
          ]
        },
        {
          "name": "On Track",
          "datatype": "boolean",
          "formula": "[gpa_points] >= 2.0",
          "is_calculated": true,
          "contains_lod": false,
          "viz_usage": [
            {
              "worksheet": "GPA Summary",
              "role": "dimension",
              "aggregation": null
            }
          ]
        }
      ],
      "parameters": [
        {
          "name": "Selected School",
          "datatype": "string",
          "current_value": "KIPP Newark"
        }
      ],
      "lod_expressions": []
    }
  ]
}
```

### Implementation Details

Absorbs working, reviewed code from the `tableau-upstream-tool` branch's
`tableau-extract-calcs.py`:

- **Zip extraction**: `extract_twb_bytes()` for disk files,
  `extract_twb_bytes_from_bytes()` for in-memory server downloads
- **Datasource deduplication**: Track seen captions, skip duplicates and the
  `"Parameters"` pseudo-datasource
- **Internal field filtering**: Skip columns with empty caption, names starting
  with `[:`, or `[Number of Records]`
- **Calc name resolution**: Build `Calculation_*` → caption map, rewrite formula
  references via regex (`_build_calc_name_map`, `_resolve_calc_refs`)
- **Auth patterns**: PAT preference → getpass fallback → SystemExit

New functionality added:

- **Viz usage tracking**: Parse all `<worksheet>` elements to determine which
  worksheets use each field, whether as dimension or measure, and with what
  aggregation type
- **LOD detection**: Set `contains_lod: true` on any field whose formula
  contains `{ FIXED`, `{ INCLUDE`, or `{ EXCLUDE`; collect standalone LOD
  expressions in `lod_expressions` array
- **Parameter extraction**: Parse the `"Parameters"` datasource separately into
  the `parameters` array with name, datatype, and current value
- **Workbook metadata**: Include `workbook` name and `source` path in output

### Tech Stack

- Python ≥3.13 (inline script metadata for `uv run`)
- `defusedxml>=0.7` — safe XML parsing
- `requests>=2.32` — Tableau Server API (secondary mode)
- `pyyaml>=6.0` — read `tableau.yml` for exposure lookup
- stdlib `zipfile`, `io`, `json`, `re`, `argparse`

---

## Component 2: `.claude/commands/star-schema-advisor.md`

### 8-Step Workflow

#### Step 1: Source the Workbook

Ask the analyst how they want to provide the workbook:

- **Local file (default)**: List `.twb`/`.twbx` files in `workbooks/`. If empty,
  tell the analyst to download from Tableau Server and drop the file there.
- **Tableau Server API**: List exposures from `tableau.yml`, ask which one. Warn
  that this requires PAT credentials injected via devcontainer secrets.

#### Step 2: Run Extraction Script

```bash
uv run scripts/tableau-analyze-workbook.py --file workbooks/<name>.twbx
# or
uv run scripts/tableau-analyze-workbook.py --exposure <name>
```

If the workbook contains multiple datasources, list them with field counts and
ask which to analyze. Check `docs/superpowers/star-schema-reports/` for existing
reports on this datasource — warn if one exists (offer to update or skip).

Hold JSON in memory for the remainder of the session.

#### Step 3: Read the Reporting View

Map the datasource caption to a dbt model:

- Strip everything after the first space or `(` from the caption
- Read `src/dbt/kipptaf/models/extracts/tableau/<model_name>.sql`
- Read `src/dbt/kipptaf/models/extracts/tableau/properties/<model_name>.yml`
- Trace the `ref()` chain to identify upstream intermediate and staging models

#### Step 4: Scan Existing Marts

- Read all files in `src/dbt/kipptaf/models/marts/properties/*.yml`
- Build a lookup: `column_name → [model_name, ...]`
- **Secondary alias check** (best-effort, using dbt MCP `get_node_details_dev`):
  For fields not matching by name, read compiled SQL upstream to check if a
  source column is aliased. Flag hits as "Possible match — verify alias."

#### Step 5: Classify Every Field

Apply the verdict rules to assign each field to a bucket and sub-verdict.

#### Step 6: Write and Display Report

- Save to
  `docs/superpowers/star-schema-reports/<workbook-slug>-<datasource-slug>-YYYY-MM-DD.md`
- Display the full report inline in the chat
- **Wait for analyst approval** — do NOT proceed to Step 7 until the analyst
  says "go ahead." The analyst may edit verdicts in the file or reply in chat.

#### Step 7: Apply Approved Changes

Write dbt files but do **not** stage or commit:

**Adding to an existing mart:**

- Add column to SQL `SELECT` following column ordering convention (enumerations
  → constants → simple functions → nested → logicals → CASE → window functions)
- Add YAML entry with `name` and `data_type` (optional `description`)
- Follow `.sqlfluff` style: trailing commas, single quotes, max 88 chars

**Creating a new mart:**

- Draft `dim_<name>.sql` or `fct_<name>.sql` with `WITH` + `SELECT` skeleton
- Include surrogate key via `dbt_utils.generate_surrogate_key([grain_cols])` —
  propose grain columns for analyst approval first
- YAML: `contract: enforced: true` + `unique:` test on surrogate key
- Surface full draft for analyst review before writing to disk

**Validate:**

```bash
# Always (no credentials needed):
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py

# If BQ credentials available:
uv run dbt show --project-dir src/dbt/kipptaf --select <model_name> --limit 5
```

#### Step 8: Wrap Up

- List all files modified/created
- List skipped fields with reasons
- Confirm `## Semantic Layer Queue` is populated
- If more datasources in the workbook: "Continue to next, or stop here?" (loop
  to Step 3 without re-running the script)
- When done: consolidated summary with `git diff` suggestion

---

## Verdict Classification System

### 4 Top-Level Buckets

| Bucket  | Label                    | Description                                                                                  |
| ------- | ------------------------ | -------------------------------------------------------------------------------------------- |
| **(a)** | Move upstream            | Field belongs in an existing or new dbt model (`int_*`, `dim_*`, `fct_*`)                    |
| **(b)** | Existing dim/fact → Cube | Field is a semantic layer candidate and a matching mart already exists                       |
| **(c)** | New dim/fact → Cube      | Field is a semantic layer candidate but no matching mart exists — a new model is needed      |
| **(d)** | Stay on Tableau          | Field should remain in the BI tool (parameters, display labels, server functions, ambiguous) |

### Sub-Verdict Rules

| Condition                                                             | Bucket | Sub-Verdict                                |
| --------------------------------------------------------------------- | ------ | ------------------------------------------ |
| Column name matches existing mart column                              | (a)    | Already in marts                           |
| Plain column, dimension-only role                                     | (a)    | → dim                                      |
| Plain column, aggregated one way                                      | (a)    | → fact + queue Cube measure                |
| Plain column, aggregated multiple ways                                | (a)    | → fact + queue one measure per aggregation |
| Calculated field, simple logic (date trunc, string concat), dimension | (a)    | → dim                                      |
| Calculated field, aggregated, mart exists                             | (b)    | → semantic layer                           |
| LOD expression, mart exists                                           | (b)    | Semantic layer — review grain              |
| Calculated field, complex logic, dimension, mart exists               | (b)    | → semantic layer                           |
| Calculated field, aggregated, no mart match                           | (c)    | → semantic layer (new model)               |
| LOD expression, no mart match                                         | (c)    | Semantic layer — review grain (new model)  |
| Calculated field, complex logic, no mart match                        | (c)    | → semantic layer (new model)               |
| Parameter reference                                                   | (d)    | Recreate in BI (dynamic filter)            |
| `USERNAME()` or server-side function                                  | (d)    | Skip / investigate                         |
| Display/formatting label only                                         | (d)    | Recreate in BI                             |
| Used as both dimension AND measure across worksheets                  | (d)    | Ambiguous — analyst decision               |

---

## Report Format

File:
`docs/superpowers/star-schema-reports/<workbook-slug>-<datasource-slug>-YYYY-MM-DD.md`

```markdown
# Star Schema Report: <Workbook Name>

**Datasource:** <caption from JSON> **Source:** <file path or exposure name>
**Date:** YYYY-MM-DD **Reporting view:** <rpt_tableau\_\_\*.sql path>

## (a) Move Upstream

| Field | Type | Viz Usage | Sub-Verdict | Target Model | Notes |
| ----- | ---- | --------- | ----------- | ------------ | ----- |
| ...   | ...  | ...       | ...         | ...          | ...   |

## (b) Eligible for Existing Dim/Fact → Cube

| Field | Formula | Viz Usage | Sub-Verdict | Source Model | Notes |
| ----- | ------- | --------- | ----------- | ------------ | ----- |
| ...   | ...     | ...       | ...         | ...          | ...   |

## (c) Eligible for New Dim/Fact → Cube

| Field | Formula | Viz Usage | Sub-Verdict | Proposed Model | Notes |
| ----- | ------- | --------- | ----------- | -------------- | ----- |
| ...   | ...     | ...       | ...         | ...            | ...   |

## (d) Stay on Tableau

| Field | Formula | Viz Usage | Sub-Verdict | Reason |
| ----- | ------- | --------- | ----------- | ------ |
| ...   | ...     | ...       | ...         | ...    |

## Semantic Layer Queue

Fields for `/cube-measure-generator`:

| Field | Source Model | Viz Aggregation | Tableau Formula |
| ----- | ------------ | --------------- | --------------- |
| ...   | ...          | ...             | ...             |

## BI Migration Notes

- **Parameters**: <list with migration guidance>
- **LOD Expressions**: <list with grain analysis>
- **Display Labels**: <list>
```

---

## Files to Create / Modify

| File                                             | Action        | Description                                |
| ------------------------------------------------ | ------------- | ------------------------------------------ |
| `scripts/tableau-analyze-workbook.py`            | Create        | Tableau XML parser → JSON                  |
| `.claude/commands/star-schema-advisor.md`        | Create        | 8-step slash command workflow              |
| `tests/scripts/test_tableau_analyze_workbook.py` | Create        | Unit + integration tests                   |
| `tests/scripts/fixtures/minimal.twb`             | Create        | Single-datasource test fixture             |
| `tests/scripts/fixtures/multi_datasource.twb`    | Create        | Multi-datasource test fixture              |
| `docs/superpowers/star-schema-reports/.gitkeep`  | Create        | Reports directory                          |
| `scripts/CLAUDE.md`                              | Modify        | Add catalog entry                          |
| `.gitignore`                                     | Modify        | Add `workbooks/` entries                   |
| `scripts/tableau-extract-calcs.py`               | Do not create | Superseded (exists only on feature branch) |

## Cleanup

- Delete branch `claude/feat/tableau-upstream-tool` (local + remote)
- Delete branch `claude/feat/star-schema-advisor` (remote)
- Do NOT create `scripts/tableau-extract-calcs.py` or
  `.claude/commands/tableau-upstream.md` (both superseded)

---

## Testing

### Script Tests (`tests/scripts/test_tableau_analyze_workbook.py`)

- **Fixtures**: Minimal `.twb` XML files with known fields, calc references, LOD
  expressions, parameters, and multi-datasource structures
- **Unit tests**: zip extraction, datasource dedup, internal field filtering,
  calc name resolution, viz usage parsing, LOD detection, parameter extraction
- **Integration test**: Full script run against fixture → validate JSON schema
  and field counts

### Slash Command Validation

- Run `/star-schema-advisor` on a real workbook (e.g., Gradebook and GPA
  Dashboard)
- Verify report is generated with correct bucket assignments
- Verify dbt changes compile with `dagster-dbt project prepare-and-package`
- Verify `dbt show` returns data for modified models (requires BQ credentials)

---

## Downstream Integration

The `## Semantic Layer Queue` section in each report serves as the input queue
for `/cube-measure-generator` (a follow-on slash command to be built by
Cristina). Each entry includes the source model, viz aggregation type(s), and
the original Tableau formula — enough context to generate Cube YAML measure
definitions.
