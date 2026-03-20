# Design: `/star-schema-advisor` Slash Command

**Date:** 2026-03-20 **Status:** Approved

## Problem

The team is actively converting Tableau reporting views (`rpt_tableau__*`) to a
star schema (dims and facts in `models/marts/`) and eventually moving away from
Tableau toward a BI-as-code tool backed by a Cube Cloud semantic layer. Each
reporting view contains a mix of fields that belong in different places: some
should be promoted to dims or facts, some should become Cube measures, some
encode Tableau-specific logic (LODs, parameters, server functions) that must be
recreated in the new BI tool, and some are display-only noise that belongs
nowhere but the extract layer.

Currently there is no tooling to triage these fields systematically. Analysts
either promote everything (cluttering the marts with Tableau-specific
calculations) or promote nothing (leaving the semantic layer incomplete).

There is also no persistent record of which fields have been reviewed and are
ready for the next step (Cube measure generation), making it difficult to break
the work across sessions or share decisions with teammates.

## Goal

A Claude Code slash command (`/star-schema-advisor`) that:

1. Accepts a Tableau workbook (from Tableau Server or a local file)
2. Parses every field in a chosen reporting view alongside how it is actually
   used in viz (as a dimension or an aggregated measure)
3. Produces a field-by-field verdict: dim, fact, semantic layer, recreate in BI,
   ambiguous (analyst decides), or skip
4. Writes a shareable markdown report that serves as both the analyst review
   artifact and a persistent semantic layer queue for `/cube-measure-generator`
5. Applies approved dbt mart changes (adding columns to existing models or
   drafting new ones), leaving all mart files unstaged for analyst review

---

## Components

### `scripts/tableau-analyze-workbook.py`

A standalone Python script with no Claude reasoning. Handles all Tableau XML
parsing and emits structured JSON. **Replaces
`scripts/tableau-extract-calcs.py`** — the new script is a strict superset of
the old one's capabilities.

**Implementation patterns:**

- Use `defusedxml.ElementTree` for all XML parsing (not stdlib `xml`)
- Read PAT credentials from the environment variables defined by
  `TableauServerResource` in `src/teamster/libraries/tableau/resources.py` —
  match those names exactly
- For `.twbx` files (zip archives): extract the inner `.twb` using `zipfile`,
  reading into memory rather than extracting to disk
- Deduplicate datasources by caption — Tableau duplicates a datasource element
  once per worksheet; keep only the first occurrence
- Filter internal/system fields: skip any `column` element where `caption` is
  empty, `name` starts with `[:`, or `name` equals `[Number of Records]`
- Use `uv run` inline script header (`# /// script`) with pinned dependencies
  (`defusedxml`, `requests`, `pyyaml`), matching the style of other `scripts/`
  files
- Reference
  `origin/claude/feat/tableau-upstream-tool:scripts/tableau-extract-calcs.py`
  for the complete auth, zip-extraction, and deduplication patterns to replicate

**Inputs (mutually exclusive):**

- `--exposure <name>` — pulls the workbook from Tableau Server using the LSID
  from `src/dbt/kipptaf/models/exposures/tableau.yml`
- `--file <path>` — reads a local `.twb` or `.twbx` file directly

**Output (JSON to stdout):**

```json
{
  "datasources": [
    {
      "caption": "rpt_tableau__attendance_dashboard (kipptaf_tableau)",
      "fields": [
        {
          "name": "Attendance Rate",
          "datatype": "real",
          "formula": "SUM([is_present]) / COUNT([student_number])",
          "is_calculated": true,
          "contains_lod": false,
          "viz_usage": [
            {
              "worksheet": "Overview",
              "role": "measure",
              "aggregation": "SUM"
            },
            { "worksheet": "Trend", "role": "measure", "aggregation": "AVG" }
          ]
        },
        {
          "name": "school_name",
          "datatype": "string",
          "formula": null,
          "is_calculated": false,
          "contains_lod": false,
          "viz_usage": [
            {
              "worksheet": "Overview",
              "role": "dimension",
              "aggregation": null
            }
          ]
        }
      ],
      "parameters": [
        {
          "name": "Academic Year",
          "datatype": "integer",
          "value_type": "discrete",
          "allowed_values": [2023, 2024, 2025]
        },
        {
          "name": "Date Range",
          "datatype": "date",
          "value_type": "range",
          "min": "2020-01-01",
          "max": "2026-12-31"
        }
      ],
      "lod_expressions": [
        {
          "name": "School Avg Attendance",
          "formula": "{ FIXED [school_id] : AVG([is_present]) }"
        }
      ]
    }
  ]
}
```

**Notes on the JSON schema:**

- `contains_lod` — `true` if `formula` contains `{ FIXED`, `{ INCLUDE`, or
  `{ EXCLUDE` as a substring. Catches LOD logic embedded inside other calculated
  fields, not just standalone LOD fields listed in `lod_expressions`.
- `parameters[].value_type` — `"discrete"` for a fixed list; `"range"` for
  min/max bounds. Both map to "Recreate in BI" but the distinction helps
  analysts understand what to rebuild.
- `lod_expressions` — standalone named LOD calculated fields. Fields with
  `contains_lod: true` in the `fields` array may reference these or embed LOD
  syntax directly.

This script is reusable by `/cube-measure-generator` in the second phase.

### `.claude/commands/star-schema-advisor.md`

The slash command file. Contains the complete 8-step workflow as prose
instructions that Claude follows. All reasoning about field classification, mart
placement decisions, and dbt SQL/YAML conventions lives here. Updated as the
team learns new best practices — no code changes required.

**Structural pattern:** Numbered steps, each specifying what to read or gather,
what action to take, and what to show the analyst before proceeding.

### `docs/superpowers/star-schema-reports/<exposure-name>-<YYYY-MM-DD>.md`

Per-run markdown report written during Step 6. Stored under `docs/superpowers/`
(consistent with the working-docs convention for specs and plans) rather than
the root `docs/` directory (the MkDocs engineering site).

Serves three purposes:

1. **Review artifact** — shareable with teammates who know a domain best
2. **Approval mechanism** — analyst confirms or overrides verdicts by editing
   the file directly or replying in chat
3. **Semantic layer queue** — the `## Semantic Layer Queue` section persists
   approved semantic layer fields across sessions for `/cube-measure-generator`

---

## Workflow

### Step 1 — Source the workbook

Ask the analyst: do you have a local `.twb`/`.twbx` file, or should I pull from
Tableau Server? Warn that workbook files should not be placed inside the
repository directory — they can be large, may contain embedded data, and must
not be committed.

- **Local file:** ask for the path
- **Tableau Server:** list exposures from `tableau.yml` (name + label), ask
  analyst to pick one; validate the selection before proceeding

### Step 2 — Run the extraction script

```bash
uv run scripts/tableau-analyze-workbook.py --exposure <name>
# or
uv run scripts/tableau-analyze-workbook.py --file <path>
```

If the workbook has multiple datasources, list them with field counts and ask
which to analyze. Only one datasource per run.

If the same workbook needs multiple datasources analyzed, each run produces a
separate report. Include a datasource slug in the filename to avoid collisions:
`<exposure-name>-<datasource-slug>-<YYYY-MM-DD>.md`.

### Step 3 — Read the reporting view

Map the datasource caption to the dbt model name by stripping everything from
the first space or opening parenthesis onward:
`"rpt_tableau__attendance_dashboard (kipptaf_tableau)"` →
`rpt_tableau__attendance_dashboard`.

Read the target model:

- SQL: `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__<name>.sql`
- YAML:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__<name>.yml`

Note any columns already present to avoid duplicate promotion.

### Step 4 — Read existing marts

Scan all `src/dbt/kipptaf/models/marts/properties/*.yml` files and build a
lookup: column name → mart model name. Include the matched mart name in the
Notes column for every "Already in marts" hit so the analyst can verify the
match is semantically correct — a name match does not guarantee the same grain
or join key.

### Step 5 — Classify every field

Apply verdict rules to every field in the datasource JSON. Also check each
field's `contains_lod` flag — if `true`, treat it as an LOD expression
regardless of `is_calculated`.

For fields that appear in multiple viz roles across worksheets (e.g. both SUMmed
and used as a filter), assign **Ambiguous — analyst decision**.

**Verdict rules:**

| Condition                                                                      | Verdict                          |
| ------------------------------------------------------------------------------ | -------------------------------- |
| Column name matches an existing mart column                                    | **Already in marts**             |
| Plain column, used as a dimension in viz (rows/cols/filters/pages)             | **→ dim**                        |
| Plain column, aggregated in viz (SUM/AVG/COUNT/etc.)                           | **→ fact**                       |
| Calculated field, aggregated in viz                                            | **→ semantic layer**             |
| Calculated field, used as dimension (simple/stable: date trunc, string concat) | **→ dim**                        |
| Calculated field, used as dimension (complex business logic)                   | **→ semantic layer**             |
| Plain or calculated field used as both dimension and measure across worksheets | **Ambiguous — analyst decision** |
| Field with `contains_lod: true` OR standalone LOD expression                   | **Recreate in BI**               |
| Parameter reference                                                            | **Recreate in BI**               |
| Formula uses `USERNAME()` or other server-side Tableau function                | **Skip / investigate**           |
| Formatting / display-only label (tooltip string concatenation, etc.)           | **Extract-only / skip**          |

### Step 6 — Write and display the report

Write the report to `docs/superpowers/star-schema-reports/` with the structure
below. Display it inline in chat.

Ask the analyst to review:

> "Report written to `docs/superpowers/star-schema-reports/<name>-<date>.md`.
> Please review the Field Verdicts table — you can override any verdict by
> editing the file directly or telling me the changes in chat. When you're
> ready, say 'go ahead' and I'll apply the approved dim and fact changes."

Wait for confirmation before writing any dbt files.

### Step 7 — Apply approved changes

For each `→ dim` or `→ fact` field the analyst has approved, write the dbt
changes but **do not stage or commit anything**. After writing, tell the analyst
exactly which files changed:

> "I've updated the following files — review them with `git diff` before
> staging:
>
> - `src/dbt/kipptaf/models/marts/dim_students.sql`
> - `src/dbt/kipptaf/models/marts/properties/dim_students.yml`
>
> The report file at `docs/superpowers/star-schema-reports/<name>-<date>.md` is
> ready to commit now as an audit trail."

**Adding to an existing mart:**

- Add the column to the SQL `SELECT` clause following the column ordering in
  `src/dbt/CLAUDE.md` (plain refs → simple functions → nested functions →
  logicals → CASE → window functions)
- Add a corresponding entry to the properties YAML (`name`, `data_type`,
  optional `description`)
- Follow `.sqlfluff` style: trailing commas, single quotes, max 88 chars

**Creating a new mart:**

- Draft `dim_<name>.sql` / `fct_<name>.sql` with a skeleton `SELECT` and `WITH`
  structure following existing mart patterns
- Include a surrogate key column using `dbt_utils.generate_surrogate_key()`
  based on the natural grain implied by the fields being promoted; propose the
  key columns to the analyst before writing
- Draft the corresponding properties YAML with `contract: enforced: true` and a
  `dbt_utils.unique_combination_of_columns` test on the surrogate key
- Surface the complete draft to the analyst for review before writing the file

**Prepare manifest then validate:**

First, rebuild the dbt manifest so the dbt MCP server reflects the changes:

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

Then validate data via dbt MCP:

```
dbt show --select <model_name> --limit 5
```

Confirm new columns appear and values look plausible.

### Step 8 — Wrap up

Report back:

- Files modified or created (already listed in Step 7)
- Fields skipped and why
- Confirm the `## Semantic Layer Queue` section is populated

Tell the analyst:

> "When you're ready to generate Cube measures for these fields, run
> `/cube-measure-generator` and point it at this report file."

---

## Report Structure

```markdown
# Star Schema Analysis: <Workbook Label>

**Date:** YYYY-MM-DD **Reporting view:** `rpt_tableau__<name>` **Source:**
<Tableau Server exposure name> OR <local file path> **Datasource analyzed:**
<datasource caption>

---

## Field Verdicts

| Field           | Datatype | Viz Usage           | Aggregation | Verdict          | Notes                                           |
| --------------- | -------- | ------------------- | ----------- | ---------------- | ----------------------------------------------- |
| school_name     | string   | dimension           | —           | → dim            | Add to `dim_locations` (matched — verify grain) |
| is_present      | integer  | measure             | SUM, AVG    | → fact           | Add to `fct_attendance`                         |
| Attendance Rate | real     | measure             | SUM         | → semantic layer | Calc field                                      |
| Grade Band      | string   | dimension           | —           | → dim            | Simple calc: CASE on grade_level                |
| school_id       | integer  | dimension + measure | SUM         | **Ambiguous**    | Used as filter and summed — analyst to decide   |

---

## Fields Requiring Analyst Decision

| Field     | Dimension Usage          | Measure Usage      | Proposed Verdict     |
| --------- | ------------------------ | ------------------ | -------------------- |
| school_id | filter (Overview, Trend) | SUM (Totals sheet) | _(analyst fills in)_ |

---

## Proposed Mart Changes

### Additions to existing models

- `dim_locations`: `school_name` (string)
- `fct_attendance`: `is_present` (int64)

### New models required

_(none)_

---

## Semantic Layer Queue

Fields ready for `/cube-measure-generator`:

| Field           | Source Model                        | Viz Aggregation | Tableau Formula                             |
| --------------- | ----------------------------------- | --------------- | ------------------------------------------- |
| Attendance Rate | rpt_tableau\_\_attendance_dashboard | SUM, AVG        | SUM([is_present]) / COUNT([student_number]) |

---

## BI Migration Notes

### LOD Expressions

| Field                 | Formula                                     |
| --------------------- | ------------------------------------------- |
| School Avg Attendance | `{ FIXED [school_id] : AVG([is_present]) }` |

### Parameters

| Name          | Datatype | Type     | Values / Range          |
| ------------- | -------- | -------- | ----------------------- |
| Academic Year | integer  | discrete | 2023, 2024, 2025        |
| Date Range    | date     | range    | 2020-01-01 – 2026-12-31 |

### Skip / Investigate

| Field              | Reason                                                    |
| ------------------ | --------------------------------------------------------- |
| Current User Label | Uses USERNAME() — server function, no BigQuery equivalent |
```

---

## Files Changed / Created

| File                                            | Action                                              |
| ----------------------------------------------- | --------------------------------------------------- |
| `scripts/tableau-analyze-workbook.py`           | **New** — replaces `tableau-extract-calcs.py`       |
| `.claude/commands/star-schema-advisor.md`       | **New** — slash command workflow                    |
| `docs/superpowers/star-schema-reports/`         | **New directory** — per-run reports                 |
| `src/dbt/kipptaf/models/marts/*.sql`            | **Modified per run** — columns added, left unstaged |
| `src/dbt/kipptaf/models/marts/properties/*.yml` | **Modified per run** — YAML updated, left unstaged  |

---

## Relationship to Other Tools

**Upstream (existing):**

- `src/dbt/kipptaf/models/exposures/tableau.yml` — source of truth for exposure
  names and Tableau Server LSIDs
- `src/teamster/libraries/tableau/resources.py` — `TableauServerResource`
  defines the authentication environment variable conventions the script must
  match

**Retired (do not merge to main):**

- `scripts/tableau-extract-calcs.py` — superseded by this script
- `.claude/commands/tableau-upstream.md` — superseded by `/star-schema-advisor`;
  the workflow of moving calculated fields into dbt is now handled as part of
  the mart triage process

**Downstream (planned):**

- `/cube-measure-generator` — reads the `## Semantic Layer Queue` section from
  the report file; generates Cube YAML for approved measures. Out of scope for
  this spec.

---

## Decisions

- **Reports committed, mart changes left unstaged.** The report file is
  committed immediately — it is the audit trail and the queue for the next tool.
  Mart SQL/YAML files are written but not staged; the analyst reviews the diff,
  makes any adjustments, then commits when satisfied.
- **One script, not two.** `tableau-analyze-workbook.py` replaces
  `tableau-extract-calcs.py`. The JSON output is a strict superset of what the
  old script produced.
- **One datasource per run.** Multi-datasource workbooks are handled by running
  the command multiple times; each run produces a separate report with a
  datasource slug in the filename.
