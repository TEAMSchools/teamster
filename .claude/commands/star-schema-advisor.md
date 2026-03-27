# /star-schema-advisor

Triage a Tableau reporting view into dbt mart changes and a semantic layer
queue. Produces a field-by-field classification report, applies approved dbt
changes, and validates with `dbt show`.

**Design spec:**
`docs/superpowers/specs/2026-03-27-star-schema-advisor-design.md`

---

## Step 1 — Source the Workbook

Ask the analyst how they want to provide the workbook:

**Option A — Local file (default, recommended):**

1. List `.twb` and `.twbx` files in the `workbooks/` folder at the repo root.
2. If the folder is empty or missing, tell the analyst:
   > Download the workbook from Tableau Server and drop the `.twbx` file in
   > `workbooks/`. This folder is gitignored — workbook files are never
   > committed.
3. Ask which file to analyze.

**Option B — Tableau Server API:**

1. Warn: "This requires PAT credentials (`TABLEAU_TOKEN_NAME` and
   `TABLEAU_PERSONAL_ACCESS_TOKEN`) injected via devcontainer secrets. This path
   is currently not usable for the `kippnj` subsite on `tableau.kipp.org`."
2. Read `src/dbt/kipptaf/models/exposures/tableau.yml` and list available
   exposure names.
3. Ask which exposure to analyze.

---

## Step 2 — Run Extraction Script

Run the script to extract field metadata as JSON:

```bash
# Local file mode:
uv run scripts/tableau-analyze-workbook.py --file workbooks/<name>.twbx

# Or Tableau Server mode:
uv run scripts/tableau-analyze-workbook.py --exposure <name>
```

**After running:**

1. Parse the JSON output. Hold it in memory for the remainder of the session.
2. If the workbook contains **multiple datasources**, list them with field
   counts and ask which to analyze first.
3. Check `docs/superpowers/star-schema-reports/` for an existing report on this
   datasource. If one exists, warn the analyst and ask: "Update the existing
   report, or create a new one?"

---

## Step 3 — Read the Reporting View

Map the datasource caption to a dbt model:

1. Strip everything after the first space or `(` from the datasource caption.
   Example: `rpt_tableau__test_dashboard (kipptaf_tableau)` →
   `rpt_tableau__test_dashboard`.
2. Read the SQL model:
   `src/dbt/kipptaf/models/extracts/tableau/<model_name>.sql`
3. Read the YAML properties:
   `src/dbt/kipptaf/models/extracts/tableau/properties/<model_name>.yml`
4. Trace the `ref()` chain in the SQL to identify upstream intermediate and
   staging models. Read each upstream model to understand available columns.

---

## Step 4 — Scan Existing Marts

Build a column-to-mart lookup:

1. Read **all** files in `src/dbt/kipptaf/models/marts/properties/*.yml`.
2. For each model, extract all column names. Build a lookup:
   `column_name → [model_name, ...]`.
3. **Secondary alias check** (best-effort): For fields not matching by column
   name, use the dbt MCP tool `get_node_details_dev` to read compiled SQL of
   upstream models. Check if the field appears as an aliased column. Flag hits
   as "Possible match — verify alias" with the mart and upstream column name.

---

## Step 5 — Classify Every Field

For each field in the JSON output, apply the verdict rules below to assign it to
one of 4 top-level buckets with a sub-verdict.

### 4 Top-Level Buckets

| Bucket  | Label                    | Description                                                    |
| ------- | ------------------------ | -------------------------------------------------------------- |
| **(a)** | Move upstream            | Field belongs in a dbt model (`int_*`, `dim_*`, `fct_*`)       |
| **(b)** | Existing dim/fact → Cube | Semantic layer candidate; matching mart already exists         |
| **(c)** | New dim/fact → Cube      | Semantic layer candidate; no matching mart — new model needed  |
| **(d)** | Stay on Tableau          | Remains in the BI tool (parameters, display labels, ambiguous) |

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

**How to distinguish (b) vs (c):** After building the column-to-mart lookup in
Step 4, check if the field's source columns (from the formula or the reporting
view) already exist in a mart. If yes → (b). If no → (c).

**How to distinguish "simple" vs "complex" calculated fields:**

- **Simple** (→ dim): `DATETRUNC`, `DATENAME`, `DATEPART`, string concatenation,
  `IF`/`IIF` with one condition, `UPPER`/`LOWER`/`TRIM`, simple type cast
- **Complex** (→ semantic layer): multi-step logic, nested `IF`/`CASE`,
  aggregation functions, table calculations, `WINDOW_*`, `RUNNING_*`, `LOOKUP`,
  multiple field references with arithmetic

---

## Step 6 — Write and Display Report

Write the report to:
`docs/superpowers/star-schema-reports/<workbook-slug>-<datasource-slug>-YYYY-MM-DD.md`

Use this template:

```markdown
# Star Schema Report: <Workbook Name>

**Datasource:** <caption from JSON> **Source:** <file path or exposure name>
**Date:** YYYY-MM-DD **Reporting view:** <path to rpt_tableau\_\_\*.sql>

## (a) Move Upstream

| Field | Type | Viz Usage | Sub-Verdict | Target Model | Notes |
| ----- | ---- | --------- | ----------- | ------------ | ----- |

## (b) Eligible for Existing Dim/Fact → Cube

| Field | Formula | Viz Usage | Sub-Verdict | Source Model | Notes |
| ----- | ------- | --------- | ----------- | ------------ | ----- |

## (c) Eligible for New Dim/Fact → Cube

| Field | Formula | Viz Usage | Sub-Verdict | Proposed Model | Notes |
| ----- | ------- | --------- | ----------- | -------------- | ----- |

## (d) Stay on Tableau

| Field | Formula | Viz Usage | Sub-Verdict | Reason |
| ----- | ------- | --------- | ----------- | ------ |

## Semantic Layer Queue

Fields for `/cube-measure-generator`:

| Field | Source Model | Viz Aggregation | Tableau Formula |
| ----- | ------------ | --------------- | --------------- |

## BI Migration Notes

- **Parameters**: <list with migration guidance>
- **LOD Expressions**: <list with grain analysis>
- **Display Labels**: <list>
```

**After writing the report:**

1. Display the full report inline in the chat.
2. Tell the analyst: "Review the verdicts above. You can edit the report file
   directly or reply in chat with changes. Say **go ahead** when you're ready
   for me to apply the dbt changes."
3. **STOP and WAIT.** Do NOT proceed to Step 7 until the analyst explicitly
   approves. This is a hard gate.

---

## Step 7 — Apply Approved Changes

Write dbt files but do **not** stage or commit. Follow these conventions from
`src/dbt/kipptaf/CLAUDE.md`:

### Adding to an existing mart

1. Read the target model SQL and YAML.
2. Add the new column to the SQL `SELECT` following column ordering:
   enumerations → constants → simple functions → nested functions → logicals →
   CASE statements → window functions.
3. Add a YAML entry with `name` and `data_type` (optional `description`).
4. Follow `.sqlfluff` style: trailing commas, single quotes, max 88 chars.

### Creating a new mart

1. Propose the grain columns and surrogate key to the analyst first.
2. Draft `dim_<name>.sql` or `fct_<name>.sql` with `WITH` + `SELECT` skeleton.
3. Include surrogate key:
   `{{ dbt_utils.generate_surrogate_key([grain_cols]) }} as <name>_key,`
4. Draft YAML with `contract: enforced: true` and `unique:` test on the
   surrogate key column.
5. Show the full draft to the analyst and wait for approval before writing.

### Validate

```bash
# Always run (no credentials needed):
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py

# If BigQuery credentials are available:
uv run dbt show --project-dir src/dbt/kipptaf --select <model_name> --limit 5
```

If validation fails, diagnose and fix before continuing.

---

## Step 8 — Wrap Up

1. List all files modified or created.
2. List any skipped fields with reasons.
3. Confirm the `## Semantic Layer Queue` section is populated in the report.
4. If more datasources exist in the workbook, ask: "Continue to next datasource,
   or stop here?" If continuing, loop back to Step 3 (do NOT re-run the script).
5. When all done, print a consolidated summary and suggest:
   > Run `git diff` to review all changes, then commit when satisfied.

---

## Important Conventions

- Always use `uv run` — never bare `python`, `dbt`, or `dagster`.
- Single quotes in SQL, trailing commas, max 88 chars per line.
- Use `current_date('{{ var("local_timezone") }}')` — never `TODAY()` or
  `CURRENT_DATE`.
- Column ordering in `SELECT`: enumerations → constants → simple functions →
  nested → logicals → CASE → window functions.
- For union models: use `{{ union_dataset_join_clause() }}` macro — do NOT join
  on `_dbt_source_relation` directly.
- No `SELECT *` in final reporting-view `SELECT`.
- No `GROUP BY ALL` — list columns explicitly.
- No `ORDER BY` in models (belongs in reporting layer only).
