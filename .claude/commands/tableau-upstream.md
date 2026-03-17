# /tableau-upstream

Guide the user through moving Tableau calculated fields upstream into a dbt
model. Follow these steps exactly, in order.

---

## Step 1 — Get the workbook content

Ask the user: do you have a local `.twbx`/`.twb` file accessible in the
container, or should we pull it from Tableau Server using an exposure name?

**If local file:**

```bash
uv run scripts/tableau-extract-calcs.py --file path/to/workbook.twbx
```

**If pulling by exposure name (recommended — uses workbook ID from
tableau.yml):**

```bash
uv run scripts/tableau-extract-calcs.py \
  --exposure <exposure_name> \
  --server <tableau-server-url> \
  --site <site-name> \
  --username <email>
```

The exposure name is the snake_case key from
`src/dbt/kipptaf/models/exposures/tableau.yml` (e.g.
`gradebook_and_gpa_dashboard`). Use `--list-only` first to confirm the exposure
resolves correctly before downloading.

**If the exposure has no workbook ID yet:**

```bash
uv run scripts/tableau-extract-calcs.py \
  --workbook "Exact Workbook Name on Server" \
  --server <tableau-server-url> \
  --site <site-name> \
  --username <email>
```

Ask the user to paste the full script output before continuing.

---

## Step 2 — Identify the target dbt model(s)

- If `--exposure` was used, the script printed the `depends_on` model list — use
  those models directly.
- Otherwise ask: which `rpt_tableau__*` model should receive the new columns?

For each target model:

1. Read the SQL file:
   `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__<name>.sql`
2. Read the YAML properties file:
   `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__<name>.yml`
3. Note any columns already present — skip calculated fields that are already
   there.
4. Note if the model has `enabled: false` in the YAML config — flag this to the
   user and ask if they want to re-enable it.
5. Note any duplicate column entries in the YAML — plan to clean those up.

---

## Step 3 — Translate each calculated field to BigQuery SQL

For each calculated field in the script output that is not already in the model:

**Common Tableau → BigQuery SQL translations:**

| Tableau                                          | BigQuery SQL                                                         |
| ------------------------------------------------ | -------------------------------------------------------------------- |
| `IF condition THEN x ELSEIF y THEN z ELSE w END` | `CASE WHEN condition THEN x WHEN y THEN z ELSE w END`                |
| `ISNULL([Field])`                                | `[Field] IS NULL`                                                    |
| `ZN([Field])`                                    | `COALESCE([Field], 0)`                                               |
| `[Field Name]` reference                         | column name already in the model (map by matching caption to column) |
| `STR([Field])`                                   | `CAST([Field] AS STRING)`                                            |
| `INT([Field])`                                   | `CAST([Field] AS INT64)`                                             |
| `FLOAT([Field])`                                 | `CAST([Field] AS FLOAT64)`                                           |
| `TODAY()`                                        | `CURRENT_DATE()`                                                     |
| `NOW()`                                          | `CURRENT_TIMESTAMP()`                                                |
| `DATEADD('day', N, [Date])`                      | `DATE_ADD([Date], INTERVAL N DAY)`                                   |
| `DATEDIFF('day', [Start], [End])`                | `DATE_DIFF([End], [Start], DAY)`                                     |
| `DATETRUNC('month', [Date])`                     | `DATE_TRUNC([Date], MONTH)`                                          |
| `DATEPART('year', [Date])`                       | `EXTRACT(YEAR FROM [Date])`                                          |
| `LEN([Field])`                                   | `LENGTH([Field])`                                                    |
| `CONTAINS([Field], 'x')`                         | `[Field] LIKE '%x%'`                                                 |
| `IIF(cond, x, y)`                                | `IF(cond, x, y)`                                                     |

Confirm each translation with the user before writing it to the file.

---

## Step 4 — Update the model files

**SQL file** — add new columns to the `SELECT` clause:

- Place new columns after existing ones, before the `from` clause
- Use trailing commas (required by `.sqlfluff` — the comma goes at the END of
  each line, not the start)
- Follow the column ordering convention from `src/dbt/CLAUDE.md`:
  1. Plain column refs (grouped by source table)
  2. Simple functions (`coalesce`, `if`)
  3. Nested functions
  4. Logicals
  5. `CASE` statements
  6. Window functions

**YAML properties file** — add corresponding entries:

- Add `- name: <column_name>` + `data_type: <bigquery_type>` for each new column
- While editing, remove any duplicate column entries you identified in Step 2
- BigQuery type mapping from Tableau datatypes:
  - `string` → `string`
  - `integer` → `int64`
  - `real` → `float64`
  - `boolean` → `boolean`
  - `date` → `date`
  - `datetime` → `datetime`

---

## Step 5 — Validate

Run `dbt show` to preview the model output:

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

Then via the dbt MCP tool or terminal:

```
dbt show --select <model_name> --limit 5 --project-dir src/dbt/kipptaf
```

Check that:

- New columns appear in the output
- Values look correct (no unexpected nulls, correct data types)
- No SQL compilation errors

If the model was `enabled: false`, remind the user to update the YAML config
before running.

---

## Step 6 — Summarise changes

Report back:

- Which model(s) were updated
- How many columns were added and their names
- Any columns skipped (already existed)
- Any YAML duplicates cleaned up
- Whether the model needs to be re-enabled
- Next step: if the exposure `depends_on` list needs updating (e.g. to add a
  newly enabled model), note that and offer to update `tableau.yml`
