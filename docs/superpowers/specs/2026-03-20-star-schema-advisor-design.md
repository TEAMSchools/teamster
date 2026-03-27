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
parsing and emits structured JSON.

**Implementation patterns:**

- Use `defusedxml.ElementTree` for all XML parsing (not stdlib `xml`)
- Read PAT credentials from environment variables `TABLEAU_SERVER_ADDRESS`,
  `TABLEAU_SITE_ID`, `TABLEAU_TOKEN_NAME`, `TABLEAU_PERSONAL_ACCESS_TOKEN` (the
  same vars consumed by Dagster in production via `EnvVar()` in
  `src/teamster/code_locations/kipptaf/resources.py`, injected locally by
  `.devcontainer/scripts/inject-secrets.sh`). The script must exit gracefully
  with a clear error message if any are missing, rather than failing
  mid-execution
- For `.twbx` files (zip archives): extract the inner `.twb` using `zipfile`,
  reading into memory rather than extracting to disk
- Deduplicate datasources by caption — Tableau duplicates a datasource element
  once per worksheet; keep only the first occurrence
- Filter internal/system fields: skip any `column` element where `caption` is
  empty, `name` starts with `[:`, or `name` equals `[Number of Records]`
- Use `uv run` inline script header (`# /// script`) with pinned dependencies
  (`defusedxml`, `requests`, `pyyaml`), matching the style of other `scripts/`
  files. Example header:

  ```python
  # /// script
  # requires-python = ">=3.13"
  # dependencies = ["defusedxml", "requests", "pyyaml"]
  # ///
  ```

- **Auth**: prefer PAT via `TABLEAU_TOKEN_NAME` +
  `TABLEAU_PERSONAL_ACCESS_TOKEN`; fall back to username/password prompt via
  `getpass` only when `--username` is passed and PAT vars are absent; raise
  `SystemExit` with a clear message if neither method is available. Enforce
  HTTPS — raise `SystemExit` before sending any credentials if the server URL
  does not start with `https://`. Always call signout in a `finally` block
  (best-effort: swallow `RequestException`, optionally log to stderr when
  `TABLEAU_DEBUG` is set).
- **Zip extraction from memory**: when a workbook is downloaded from Tableau
  Server it arrives as raw `.twbx` bytes — wrap in `io.BytesIO`, open with
  `zipfile.ZipFile`, find the first entry ending in `.twb`, and read it without
  extracting to disk. For local files, use `zipfile.ZipFile(path)` directly for
  `.twbx` or `path.read_bytes()` for `.twb`.
- **Datasource deduplication**: track seen captions in a `set`; skip any
  `datasource` element whose caption has already been seen. Also skip the
  `"Parameters"` datasource — it is handled separately via the `parameters` key
  in the JSON output.
- **Calc name resolution**: before emitting formulas, build a map of internal
  Tableau IDs (`Calculation_*`, `*(copy)_*`) to human captions, then rewrite
  `[Calculation_*]` references in each formula via regex substitution.
  Unrecognised references are left unchanged.
- **Filter injection prevention**: when passing user-supplied workbook names
  into Tableau REST API filter query params, strip `:` and `,` first — they are
  Tableau filter syntax delimiters.

**Inputs (mutually exclusive):**

- `--exposure <name>` — pulls the workbook from Tableau Server using the
  workbook ID at `config.meta.dagster.asset.metadata.id` in
  `src/dbt/kipptaf/models/exposures/tableau.yml`. Not all exposures have this
  field populated — the script must exit with a clear error if the selected
  exposure has no ID
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
  min/max bounds. The `allowed_values`/`min`/`max` fields are extracted for
  analyst reference only — they describe what existed in Tableau and must not be
  hardcoded in Cube config. Both types map to "Recreate in BI (dynamic filter)";
  the distinction helps analysts understand what kind of user control to build.
- `lod_expressions` — standalone named LOD calculated fields. Fields with
  `contains_lod: true` in the `fields` array may reference these or embed LOD
  syntax directly.

This script is reusable by `/cube-measure-generator` in the second phase.

### `.claude/commands/star-schema-advisor.md`

The slash command file. The `.claude/commands/` directory does not exist yet and
must be created during implementation.

Contains the complete 8-step workflow as prose instructions that Claude follows.
All reasoning about field classification, mart placement decisions, and dbt
SQL/YAML conventions lives here. Updated as the team learns new best practices —
no code changes required.

**Structural pattern:** Numbered steps, each specifying what to read or gather,
what action to take, and what to show the analyst before proceeding.

### `docs/superpowers/star-schema-reports/<exposure-name>-<datasource-slug>-<YYYY-MM-DD>T<HHMM>.md`

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

## Prerequisites: Mart Design Principles and Structure

The slash command classifies fields and proposes mart placements, so it depends
on a well-defined mart layer. The following foundational work should be
completed before or alongside implementation.

### Mart design principles in `src/dbt/CLAUDE.md`

Add a "Mart design principles" section to `src/dbt/CLAUDE.md` covering:

- **Dims vs facts** — dims hold descriptive attributes of a business entity (one
  row per entity or per historical period); facts hold events or transactions at
  the lowest useful grain with numeric measures or boolean flags that get
  aggregated in the semantic layer (Cube)
- **Conformed dimensions** — `dim_students`, `dim_staff`, `dim_locations`, and
  `dim_dates` are the conformed core; new dims should reuse their natural keys
  (`student_number`, `employee_number`, `school_id`, date columns)
- **Join strategy** — facts reference dims via natural keys at query time, not
  via explicit foreign key columns
- **Create vs extend** — add a column when the field shares the same grain and
  entity; create a new mart when the grain is different
- **Mart vs semantic layer boundary** — raw columns and simple transformations
  (rename, cast, coalesce) belong in dbt; aggregations, ratios, and
  context-dependent logic belong in Cube; Tableau-specific calculations, LOD
  expressions, and display formatting belong in neither

The slash command's verdict rules (Step 5) and placement logic (Step 7) should
reference this section.

### Missing dimensions

The following entities are referenced across multiple facts and reporting views
but lack dedicated dimension models. Without them, the slash command will
repeatedly propose adding these attributes to facts when they belong in dims.

| Candidate                  | Key columns                                                               | Referenced by                                                       | Priority |
| -------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------- |
| `dim_courses`              | course_number, course_name, discipline, subject_area, credit_type         | fct_student_course_enrollments, fct_internal_assessments, 6+ rpts   | High     |
| `dim_assessment_standards` | response_type_id, standard_code, standard_description, domain_description | fct_internal_assessments, fct_state_assessments, 10+ rpts           | High     |
| `dim_performance_bands`    | performance_band_set_id, band_label, band_level                           | fct_internal_assessments, fct_state_assessments, 9+ rpts            | Medium   |
| `dim_communication_types`  | commlog_reason, commlog_type, commlog_topic                               | fct_attendance_communications, fct_attendance_interventions, 6 rpts | Medium   |

### Misclassified facts

Several existing `fct_*` models carry mostly descriptive attributes with few or
no aggregatable measures, suggesting they should be reclassified:

- **`fct_student_course_enrollments`** — no measures; purely a student-course
  association. Better modeled as a dim or bridge table once `dim_courses`
  exists.
- **`fct_internal_assessments`** — thin measure core (points, percent_correct)
  buried under heavy assessment metadata (response_type, module_type,
  performance_band_label, scope). Extracting `dim_assessment_standards` and
  `dim_performance_bands` would leave a cleaner fact.
- **`fct_state_assessments`** — score and proficiency flag are measures, but
  test_name, subject, performance_band, and state-level demographics are
  descriptive. State demographics are explicitly noted in the SQL as potentially
  divergent from `dim_students`.

This restructuring is out of scope for the slash command — it should be
completed as separate mart development work. The slash command operates on
whatever mart structure exists at runtime.

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

> **Note:** The Tableau Server path requires PAT credentials in the environment
> (`TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`, `TABLEAU_TOKEN_NAME`,
> `TABLEAU_PERSONAL_ACCESS_TOKEN`). These are only available after running
> `.devcontainer/scripts/inject-secrets.sh`. If secrets have not been injected,
> the `--exposure` flag will fail — only the `--file` path is available in that
> case. Remind the analyst to run secrets injection first, or fall back to a
> locally downloaded `.twb`/`.twbx` file.

### Step 2 — Run the extraction script

```bash
uv run scripts/tableau-analyze-workbook.py --exposure <name>
# or
uv run scripts/tableau-analyze-workbook.py --file <path>
```

If the workbook has multiple datasources, list them all with field counts and
ask which to start with. The script output is held in memory for the session —
do not re-run the script when moving between datasources.

Before listing datasources, check `docs/superpowers/star-schema-reports/` for
existing reports matching the exposure name. If any are found, tell the analyst:

> "I found existing reports for this workbook:
>
> - ✓ `<exposure>-<slug>-<YYYY-MM-DD>T<HHMM>.md`
>
> Remaining datasources: `rpt_tableau__foo`, `rpt_tableau__bar`. Pick up where
> you left off?"

Each datasource produces its own report file. Always include a datasource slug
in the filename to avoid collisions:
`<exposure-name>-<datasource-slug>-<YYYY-MM-DD>T<HHMM>.md` (the timestamp
prevents collisions when the same exposure+datasource is analyzed twice in one
day).

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

For fields that do **not** match by name, do a secondary check using the dbt MCP
`get_node_details_dev` tool on the rpt model (this runs against the local
project manifest, not dbt Cloud). This returns the compiled SQL and upstream
column lineage — use it to find the source expression for each unmatched field.
If the source expression is a direct column reference (no calculation), check
whether that upstream column name matches any mart column. Flag any hits as
**"Possible match — verify alias"** in the Notes column with the mart name and
upstream column name, so the analyst can confirm before approving. If the source
expression is a calculation rather than a direct ref, leave it unmatched — it
likely belongs in the semantic layer anyway.

> **Fallback:** If the dbt MCP server is unavailable or the model is not in the
> manifest, skip the lineage check. Note "MCP unavailable — lineage not checked"
> in the report and continue with name-only matching. The analyst can re-run the
> command after rebuilding the manifest with `prepare-and-package`.

When processing a second or later datasource in the same session (sequential
processing within a single Claude conversation), mart files may already have
been modified by Step 7 of an earlier datasource. The re-scan will pick these up
naturally since edits are written to disk. Use a distinct note for these hits —
**"Already in marts (promoted this session)"** — so the analyst can see what
came from prior datasources vs what was already there before the session
started.

### Step 5 — Classify every field

Apply verdict rules to every field in the datasource JSON. Also check each
field's `contains_lod` flag — if `true`, treat it as an LOD expression
regardless of `is_calculated`.

For fields that appear in multiple viz roles across worksheets (e.g. both SUMmed
and used as a filter), assign **Ambiguous — analyst decision**.

**Verdict rules:**

| Condition                                                                      | Verdict                                             |
| ------------------------------------------------------------------------------ | --------------------------------------------------- |
| Column name matches an existing mart column                                    | **Already in marts**                                |
| Plain column, used as a dimension in viz (rows/cols/filters/pages)             | **→ dim**                                           |
| Plain column, aggregated one way in viz                                        | **→ fact** + queue Cube measure                     |
| Plain column, aggregated multiple ways in viz (e.g. SUM and AVG)               | **→ fact** + queue one Cube measure per aggregation |
| Calculated field, aggregated in viz                                            | **→ semantic layer**                                |
| Calculated field, used as dimension (simple/stable: date trunc, string concat) | **→ dim**                                           |
| Calculated field, used as dimension (complex business logic)                   | **→ semantic layer**                                |
| Plain or calculated field used as both dimension and measure across worksheets | **Ambiguous — analyst decision**                    |
| Field with `contains_lod: true` OR standalone LOD expression                   | **Semantic layer — review grain**                   |
| Parameter reference (worksheet filters)                                        | **Recreate in BI (dynamic filter)**                 |
| Formula uses `USERNAME()` or other server-side Tableau function                | **Skip / investigate**                              |
| Formatting / display-only label (tooltip string concatenation, etc.)           | **Recreate in BI**                                  |

### Step 6 — Write and display the report

Write the report to `docs/superpowers/star-schema-reports/` with the structure
below. Display it inline in chat.

Ask the analyst to review:

> "Report written to
> `docs/superpowers/star-schema-reports/<exposure>-<slug>-<YYYY-MM-DD>T<HHMM>.md`.
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
> The report file at
> `docs/superpowers/star-schema-reports/<exposure>-<slug>-<YYYY-MM-DD>T<HHMM>.md`
> is ready to commit now as an audit trail."

**Adding to an existing mart:**

- Add the column to the SQL `SELECT` clause following the column ordering in
  `src/dbt/CLAUDE.md`: plain refs (grouped by source table in join order,
  separated by blank lines) → constants → simple functions → nested functions →
  logicals → CASE → window functions
- Add a corresponding entry to the properties YAML (`name`, `data_type`,
  optional `description`)
- Follow `.trunk/config/.sqlfluff` style: trailing commas, single quotes, max 88
  chars

**Creating a new mart:**

- Draft `dim_<name>.sql` / `fct_<name>.sql` with a skeleton `SELECT` and `WITH`
  structure following existing mart patterns
- Include a surrogate key column using `dbt_utils.generate_surrogate_key()`
  based on the natural grain implied by the fields being promoted; propose the
  key columns to the analyst before writing
- Draft the corresponding properties YAML with `contract: enforced: true` and a
  simple `unique:` test on the surrogate key column (prefer this over
  `dbt_utils.unique_combination_of_columns` — the surrogate key already encodes
  the grain)
- Surface the complete draft to the analyst for review before writing the file

**Prepare manifest then validate:**

First, rebuild the dbt manifest so the dbt MCP server reflects the changes:

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

Then validate data via dbt MCP:

```text
dbt show --select <model_name> --limit 5
```

Confirm new columns appear and values look plausible.

> **Note:** `dbt show` requires a live BigQuery connection. GCP credentials must
> be present (via `.devcontainer/scripts/inject-secrets.sh`) for this step to
> succeed. `prepare-and-package` works without credentials and should always be
> run. If credentials are not available, skip the `dbt show` validation and tell
> the analyst to run it manually once secrets are injected.

### Step 8 — Wrap up

Report back:

- Files modified or created (already listed in Step 7)
- Fields skipped and why
- Confirm the `## Semantic Layer Queue` section is populated

Tell the analyst:

> "When you're ready to generate Cube measures for these fields, run
> `/cube-measure-generator` and point it at this report file."

If the workbook has additional datasources not yet analyzed, offer to continue:

> "This workbook has N more datasource(s) not yet analyzed:
>
> - `rpt_tableau__foo` — 22 fields
> - `rpt_tableau__bar` — 8 fields
>
> Continue to the next one, or stop here?"

If the analyst continues, loop back to Step 3 with the next datasource. The
script JSON is already in memory — do not re-run it. Each datasource gets its
own report file and its own mart changes, applied and left unstaged
independently.

When all datasources in the workbook are complete, give a consolidated session
summary before suggesting a `git diff`:

> "All datasources analyzed. Here's everything changed this session:
>
> **Mart changes** (all left unstaged — review with `git diff` before staging):
>
> - `dim_locations`: added `school_name`, `grade_band`
> - `fct_attendance`: added `is_present`, `membership_value`
>
> **New models drafted** (if any): `dim_grade_bands.sql` + YAML
>
> **Reports written** (commit these now):
>
> - `ops_dashboard-rpt-attendance-dashboard-2026-03-20T1430.md`
> - `ops_dashboard-rpt-ops-dashboard-2026-03-20T1445.md`
>
> **Semantic layer fields queued across all datasources:** N fields total — run
> `/cube-measure-generator` pointing at any report file when ready."

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

### LOD Expressions — Analyst Review Required

LOD expressions encode aggregation grain logic that must be preserved in the new
stack. For each one, decide:

- **Push to dbt** — if the grain is fixed and stable (e.g. always school-level),
  materialize it as a pre-aggregated column in a mart or intermediate model
- **Cube measure** — if the aggregation needs to remain dynamic or
  context-aware, define it as a measure on the appropriate semantic model
- **Both** — dbt provides the raw inputs; Cube defines the measure on top

| Field                 | Formula                                     | Grain  | Recommended approach |
| --------------------- | ------------------------------------------- | ------ | -------------------- |
| School Avg Attendance | `{ FIXED [school_id] : AVG([is_present]) }` | school | _(analyst fills in)_ |

---

## BI Migration Notes

### LOD Expressions

> Full analyst review table is in `## Semantic Layer Queue` above. This section
> is the raw formula reference only.

| Field                 | Formula                                     |
| --------------------- | ------------------------------------------- |
| School Avg Attendance | `{ FIXED [school_id] : AVG([is_present]) }` |

### Parameters

> Do not port these values directly — recreate as dynamic user-facing filters in
> Cube, not hardcoded constraints.

| Name          | Datatype | Type     | Tableau values (reference only) | Suggested Cube approach                         |
| ------------- | -------- | -------- | ------------------------------- | ----------------------------------------------- |
| Academic Year | integer  | discrete | 2023, 2024, 2025                | dimension filter on `fiscal_year`               |
| Date Range    | date     | range    | 2020-01-01 – 2026-12-31         | time dimension with user-controlled granularity |

### Display / Formatting Labels

Fields used only for tooltip text, concatenated labels, or other display
formatting. No mart promotion needed — recreate the equivalent formatting in the
BI tool.

| Field | Tableau Formula |
| ----- | --------------- |

### Skip / Investigate

| Field              | Reason                                                    |
| ------------------ | --------------------------------------------------------- |
| Current User Label | Uses USERNAME() — server function, no BigQuery equivalent |
```

---

## Files Changed / Created

| File                                            | Action                                              |
| ----------------------------------------------- | --------------------------------------------------- |
| `src/dbt/CLAUDE.md`                             | **Modified** — add mart design principles (prereq)  |
| `scripts/tableau-analyze-workbook.py`           | **New**                                             |
| `.claude/commands/star-schema-advisor.md`       | **New** — slash command workflow                    |
| `docs/superpowers/star-schema-reports/`         | **New directory** — per-run reports                 |
| `src/dbt/kipptaf/models/marts/*.sql`            | **Modified per run** — columns added, left unstaged |
| `src/dbt/kipptaf/models/marts/properties/*.yml` | **Modified per run** — YAML updated, left unstaged  |

---

## Relationship to Other Tools

**Upstream (existing):**

- `src/dbt/kipptaf/models/exposures/tableau.yml` — source of truth for exposure
  names and Tableau Server workbook IDs
  (`config.meta.dagster.asset.metadata.id`)
- `src/teamster/code_locations/kipptaf/resources.py` — wires
  `TableauServerResource` with `EnvVar()` calls that define the environment
  variable names the script reads

**Retired (do not merge to main):**

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
- **Standalone script.** `tableau-analyze-workbook.py` is a new standalone
  script with no Dagster dependencies. It reads credentials directly from
  environment variables.
- **One datasource at a time.** Multi-datasource workbooks are processed
  sequentially within a single session (see Step 8); each datasource produces
  its own report with a datasource slug in the filename.

---

## Testing

### `scripts/tableau-analyze-workbook.py`

The script performs non-trivial XML parsing, zip extraction, datasource
deduplication, and calc name resolution. At minimum:

- Include a sample `.twb` fixture (a minimal, hand-crafted Tableau workbook XML
  with representative fields, calculated fields, LOD expressions, and
  parameters) in `tests/fixtures/`
- Write a test that runs the script against the fixture and asserts the JSON
  output shape matches the schema documented above (datasources array, field
  keys, parameter keys, lod_expressions keys)
- Test edge cases: `.twbx` zip extraction, duplicate datasource deduplication,
  `[Calculation_*]` formula rewriting, internal/system field filtering
