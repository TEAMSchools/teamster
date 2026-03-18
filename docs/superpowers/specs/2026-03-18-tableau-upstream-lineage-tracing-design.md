# Design: Upstream Lineage Tracing for Tableau Calculated Fields

**Date:** 2026-03-18 **Status:** Draft

## Problem

When an analyst moves a Tableau calculated field upstream into a dbt model, the
current workflow defaults to adding the calculation to the Tableau extract view
(`rpt_tableau__*`). This is often not the right place — if all of a field's
input columns already exist at an intermediate model, adding the calculation
there avoids duplicating logic across multiple extract views and places it where
it can be reused by other models.

There is currently no tooling to identify the best insertion point in the DAG,
draft SQL in that model's context, or give the analyst the choice to push
further upstream.

## Goal

Extend the `/tableau-upstream` slash command to trace each calculated field's
column references through the dbt DAG, identify the closest-to-extract model
where all inputs are available, draft BigQuery SQL at that layer, and let the
analyst choose where in the pipeline to add the field.

---

## Section 1 — How Lineage Tracing Works

For each calculated field being moved upstream, Claude makes two types of dbt
MCP calls:

1. **`get_lineage_dev`** on the target Tableau extract model (e.g.
   `rpt_tableau__gradebook_gpa_cumulative`) — returns the full upstream DAG as a
   list of model nodes. If this returns an empty list or fails, treat the field
   as having no better insertion point and note this to the analyst.
2. **`get_node_details_dev`** on each upstream node — returns the compiled SQL
   for that model

**Column origin map:** For each upstream model, Claude inspects the compiled SQL
to find which of the field's `[Field]` references appear in named `SELECT`
column expressions. This builds a mapping from each Tableau ref to the
closest-to-extract model where that column is available.

**Handling wildcard and macro-generated columns:** Many models in this project
use `dbt_utils.union_relations` or `dbt_utils.star()`, which compile to
wildcard-style SELECT patterns (e.g. `ar.*`) rather than explicit column lists.
When a model's compiled SQL contains wildcard expansions, Claude cannot reliably
determine which columns it exposes by reading SQL alone. In this case:

1. Fall back to querying BigQuery `INFORMATION_SCHEMA.COLUMNS` for that model's
   schema:
   ```sql
   select column_name
   from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
   where table_name = '<model_name>'
   order by ordinal_position
   ```
2. If a column is found there, the model exposes it; trace continues
3. If not found, continue tracing to the next upstream node

See `src/dbt/kipptaf/CLAUDE.md` ("Selecting from models that use
`dbt_utils.star()`") for background on this pattern.

**Scope:** Lineage tracing only traverses models within the same dbt project
(`src/dbt/kipptaf/`). It does not trace into source tables or cross-project
packages.

**Recommended insertion point:** The model closest to the extract (shortest path
from the terminal `rpt_tableau__*` node) where _all_ of the field's input
columns are simultaneously present — meaning no new joins are needed to compute
the calculation. Concretely: find the set of models that contain each input
column; the recommended point is the one in that intersection that appears
earliest in a breadth-first traversal starting from the extract.

---

## Section 2 — SQL Drafting at Each Layer

Once the recommended insertion point is identified, Claude translates the
Tableau formula to BigQuery SQL using **column names as they exist at that
layer** — not the Tableau display names.

For example, a Tableau field referencing `[GPA Y1]` may map to
`cumulative_y1_gpa` at the intermediate layer. The draft SQL uses the dbt column
name:

```sql
CASE WHEN cumulative_y1_gpa >= 3.5 THEN 'Honor Roll' ELSE 'Standard' END
    AS gpa_label,
```

**When pushing further upstream:** If the analyst chooses to push to the next
upstream model, Claude must re-derive the correct column names at that layer.
The procedure is:

1. In the compiled SQL of the intermediate model, look for
   `<upstream_name> as cumulative_y1_gpa` — the alias source reveals the
   upstream column name
2. If no alias is found (column is passed through unchanged), the name is the
   same at the upstream layer
3. If the model uses wildcard expansion, query `INFORMATION_SCHEMA.COLUMNS` on
   the upstream model to confirm the column exists there under the same name

Claude applies this procedure for each input column before re-drafting SQL at
the new layer.

Draft SQL follows existing project conventions: trailing commas, single quotes
for string literals, BigQuery dialect.

---

## Section 3 — User Decision Flow

For each field being moved upstream, Claude:

1. **Presents the lineage path** — compact list of model names from the extract
   back to the recommended insertion point:

   ```text
   rpt_tableau__gradebook_gpa_cumulative
     ← int_extracts__student_enrollments  ← recommended (all inputs here)
       ← stg_powerschool__students
       ← stg_powerschool__cohort
   ```

2. **States the reason** for the recommendation — e.g. "all input columns
   (`cumulative_y1_gpa`, `expected_credits`) are already present here"

3. **Shows the draft SQL** at the recommended layer

4. **Asks the analyst to decide:**

   > Add here, push further upstream, or keep in the Tableau extract?

5. **If pushing upstream:** Claude shows the next node up, re-drafts SQL using
   that model's column names (following the alias-resolution procedure in
   Section 2), and repeats the question

6. **If keeping in the extract:** Claude proceeds with the original Step 5
   translation workflow (no lineage-driven change)

The analyst can stop at any point and confirm a layer. Once confirmed, the
target model for that field is updated — this may differ per field (one field
might go to the intermediate layer, another to staging).

**Multi-field grouping:** When multiple fields share the same recommended
insertion point, Claude presents them together as a group for the initial
recommendation to reduce repetition. However, the push-upstream decision is
always per-field — if the analyst wants to push some fields further but keep
others at the recommended point, Claude handles them individually from that
point on.

---

## Section 4 — Integration with the Existing Slash Command

The lineage trace inserts as **Step 4b**, between the current Step 4 (identify
target model) and Step 5 (translate and confirm each field).

**Which fields get a lineage trace:**

| Category   | Lineage trace?           | Reason                                                                              |
| ---------- | ------------------------ | ----------------------------------------------------------------------------------- |
| READY      | Yes                      | Full trace + draft SQL at recommended layer                                         |
| NEEDS WORK | Yes, after refs resolved | Trace runs once unresolved refs are mapped to model columns                         |
| LOD        | No                       | These go to the semantic layer (`fct_*`/`dim_*` marts), not upstream extract models |
| SKIP       | No                       | No SQL equivalent                                                                   |

**Step 4b prompt structure:**

Step 4b opens with a resolution sub-step for any NEEDS WORK fields before
tracing begins:

> Before tracing lineage, I need to resolve the unresolved references in these
> fields: [list of NEEDS WORK fields + their unresolved refs]. Please tell me
> which dbt column each maps to. Once resolved, I'll include these in the
> lineage trace alongside the READY fields.

After NEEDS WORK refs are resolved (or if there are none), the trace proceeds:

> Now let's find the best place in the pipeline for each field. I'll trace the
> inputs through the dbt DAG and suggest where to add each one.
>
> [For fields sharing the same recommended layer: grouped presentation] [For > >
>
> > each field: lineage path → recommendation → draft SQL → ask]

**When no better insertion point is found** (recommended model is the Tableau
extract itself, `get_lineage_dev` returns empty, or all inputs only exist at the
extract layer), Claude skips the trace for that field and notes: "All inputs are
only available at the extract layer — adding here is correct."

---

## Files Changed

| File                                   | Change                                                                                                            |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `.claude/commands/tableau-upstream.md` | Add Step 4b: lineage trace, SQL drafting at recommended layer, NEEDS WORK resolution sub-step, user decision flow |

No changes to `scripts/tableau-extract-calcs.py` — lineage tracing uses the dbt
MCP server interactively and requires no script-level DAG traversal.
