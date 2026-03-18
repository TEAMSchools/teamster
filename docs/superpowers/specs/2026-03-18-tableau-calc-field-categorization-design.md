# Design: Tableau Calculated Field Categorization

**Date:** 2026-03-18 **Status:** Draft

## Problem

`scripts/tableau-extract-calcs.py` currently dumps all calculated fields from a
Tableau workbook as a flat list. For workbooks with dozens of fields, this gives
analysts no guidance on which fields are safe to move upstream, which need
investigation, which belong in the semantic layer, and which should be skipped
entirely.

## Goal

Add smart field categorization to the script so analysts immediately see a
prioritized, actionable summary rather than a raw field dump. The
`/tableau-upstream` slash command adopts this structure to guide the
conversation accordingly.

---

## Section 1 — Four-Category Classification

Every calculated field is assigned one of four categories:

| Category       | Criteria                                                                                                | Action                                          |
| -------------- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **READY**      | All `[Field]` refs resolve to known model columns                                                       | Translate to BigQuery SQL                       |
| **NEEDS WORK** | One or more `[Field]` refs don't resolve                                                                | Flag unresolved refs, ask user to map them      |
| **LOD**        | Formula contains `{FIXED}`, `{INCLUDE}`, or `{EXCLUDE}`                                                 | Suggest semantic layer; do not embed in extract |
| **SKIP**       | Formula contains zero real column refs — uses only `USERNAME()`, bare literals, and/or `[Parameters].*` | No SQL equivalent; leave in Tableau             |

LOD check runs before SKIP and ref-resolution checks. A field with a LOD
expression is always LOD regardless of what else it contains.

**Edge case — LOD with unresolved refs:** If a LOD field's `[Field]` references
are not found in the model's known columns, mart matching (Branch A) cannot
proceed reliably. In this case, always output Branch B (proposed new model) and
note that refs were unresolved. Do not attempt Branch A matching on unknown
refs.

---

## Section 2 — LOD → Semantic Layer Recommendation

LOD fields generate a recommendation rather than a SQL translation. Two
branches:

**Branch A — existing mart match found:** The script matches the LOD field's
`[Field]` refs case-insensitively against column names in every model under
`src/dbt/kipptaf/models/marts/` (scan all YAML files in that directory at
runtime — do not hardcode the list). The mart with the most matching column
names wins. If two marts tie, pick the one whose name most closely resembles the
formula's subject (e.g., `absences` → prefer `fct_attendance`).

```
⚠ LOD — semantic layer candidate
   Formula: {FIXED [school_id] : SUM([absences])}
   Suggested mart: fct_attendance — add a pre-aggregated measure here,
   then reference it from the Tableau extract instead of computing inline.
```

**Branch B — no confident match found:**

```
⚠ LOD — semantic layer candidate
   Formula: {FIXED [student_id] : MAX([MAP Score])}
   No existing mart match found. A new fact table may be needed, e.g.:
     fct_assessment__map_scores (grain: student × test event)
     Potential measures: max_rit_score, growth_percentile
   Discuss with the data engineer before adding this to the extract.
```

The script names the proposed model (noun phrase from formula refs) and lists
candidate measures. It does not generate DDL.

---

## Section 3 — Script Changes

### `--model` / `-m` flag

Accepts a model name (e.g. `rpt_tableau__gradebook_gpa_cumulative`). The script
reads the model's YAML properties file at:

```
src/dbt/kipptaf/models/extracts/tableau/properties/<model>.yml
```

and builds a set of known column names used for ref resolution during
classification.

`--model` and `--datasource` are independent flags. `--model` controls which
YAML is loaded for column cross-referencing. `--datasource` filters which
datasource's fields are shown. Passing `--model` does not imply a datasource
filter — if `--datasource` is not also passed, the datasource picker is still
shown (or all datasources printed if only one exists). Conversely, passing
`--datasource` without `--model` still triggers auto-detection.

### Auto-detection

Auto-detection only applies in `--exposure` mode (where datasource captions
follow the `<model_name> (kipptaf_tableau)` convention). When `--model` is not
passed and a datasource is selected, the script strips ` (kipptaf_tableau)` from
the caption to derive the model name and checks if the YAML file exists. If
found, loads silently. If not found, skips classification and prints all fields
unclassified.

In `--file` mode (local `.twbx`), datasource captions may not follow this
convention. Auto-detection is not attempted; `--model` must be passed explicitly
to enable classification.

### Classification logic (per field)

1. Extract all `[Field Name]` references from the formula
2. **LOD check first** — if formula contains `{FIXED`, `{INCLUDE`, or `{EXCLUDE`
   → LOD
3. **SKIP check** — if the formula contains zero real column refs (i.e., every
   token is `USERNAME()`, a bare string/number literal, or a `[Parameters].*`
   reference) → SKIP. A formula that mixes `USERNAME()` with a real column ref
   is NOT SKIP.
4. **Ref resolution** — all refs resolve against known columns → READY; any
   unresolved → NEEDS WORK

### Output structure

Summary counts first, then grouped detail sections:

```text
## rpt_tableau__gradebook_gpa_cumulative — 9 fields
## 4 READY · 2 NEEDS WORK · 2 LOD · 1 SKIP

### ✓ READY (4)
| Field | Type | Formula |
| --- | --- | --- |
...

### ⚠ NEEDS WORK (2)
| Field | Type | Formula | Unresolved Refs |
| --- | --- | --- | --- |
...

### 🔷 LOD — semantic layer candidates (2)
[per-field recommendation blocks]

### ✗ SKIP (1)
| Field | Type | Reason |
| --- | --- | --- |
...
```

The script outputs the original Tableau formula for READY fields — not a SQL
translation. SQL translation is performed by Claude in the `/tableau-upstream`
slash command after the user confirms each field.

---

## Section 4 — Slash Command Changes

### Categorized summary after extraction

After the script runs (Step 3), Claude presents the count summary before any
detail — "9 fields: 4 READY · 2 NEEDS WORK · 2 LOD · 1 SKIP" — so the user knows
the scope before scrolling.

### Output format preference

Claude asks how to proceed before translating any READY fields:

> How do you want to work through these?
>
> 1. Walk through each READY field one at a time for confirmation
> 2. Propose all READY fields at once as a SQL diff — review together
> 3. Start with NEEDS WORK first — resolve unresolved refs

### LOD handling

For each LOD field, Claude presents the recommendation (Branch A or B) and asks:
defer as a GitHub issue, or skip for now?

### NEEDS WORK handling

Claude shows the unresolved `[Field]` references and asks the user to identify
which model column they map to. Once mapped, the field is reclassified as READY
and translated.

---

## Files Changed

| File                                   | Change                                                                                                         |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `scripts/tableau-extract-calcs.py`     | Add `--model`/`-m` flag, auto-detection, classification logic, LOD recommendation logic, grouped output format |
| `.claude/commands/tableau-upstream.md` | Add categorized summary display, output format preference question, LOD/NEEDS WORK handling steps              |
