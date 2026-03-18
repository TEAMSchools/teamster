# /tableau-upstream

Guide the user through moving Tableau calculated fields upstream into a dbt
model. Drive the whole workflow through chat — the user should not need to know
any CLI flags.

---

## Step 1 — Pick a workbook

Read `src/dbt/kipptaf/models/exposures/tableau.yml` and extract all exposure
names and labels. Present them as a numbered list and ask the user to pick one:

> Here are the Tableau workbooks tracked in dbt:
>
> 1. Dashboard A Label (`exposure_name_a`)
> 2. Dashboard B Label (`exposure_name_b`) …
>
> Which workbook do you want to work with?

Wait for the user's answer. **Validate the response:** if the user enters a
number outside the range 1–N or a name that doesn't match any exposure, reply:

> That number isn't in the list (valid choices are 1–N). Which workbook do you
> want to work with?

Re-prompt until a valid selection is made.

---

## Step 2 — List data sources

Run the extraction script in datasource-picker mode:

```bash
uv run scripts/tableau-extract-calcs.py --exposure <chosen_exposure_name>
```

The script prints a table of unique data sources and their calc counts. Present
the list to the user and ask which one they want to analyze:

> This workbook has the following data sources:
>
> 1. \<datasource caption A\> — N calcs
> 2. \<datasource caption B\> — N calcs …
>
> Which data source contains the calculations you want to move upstream?

Wait for the user's answer. **Validate the response:** if the user enters a
number outside the range 1–N (where N is the number of data sources listed), or
a name that does not match any datasource, reply:

> That number isn't in the list (valid choices are 1–N). Which data source do
> you want to work with?

Re-prompt until a valid selection is made.

---

## Step 3 — Extract calculated fields

Run the script filtered to the chosen datasource (use a substring of the caption
— the `-d` flag does a case-insensitive match):

```bash
uv run scripts/tableau-extract-calcs.py --exposure <name> -d <datasource_substring>
```

Show the user how many fields were found and the full table. Then ask:

> Found **N calculated fields** in \<datasource\>. Here they are: [show the > >
>
> > markdown table from the script output]
>
> Which of these do you want to move upstream into dbt? You can say "all of
> them" or name specific ones.

Wait for the user's answer before continuing.

---

## Step 4 — Identify the target dbt model

The script output includes the `depends_on` list from the exposure. The
datasource caption also contains the model name — e.g. a caption like
`rpt_tableau__some_model (kipptaf_tableau)` maps to the model
`rpt_tableau__some_model`.

Read the model's files:

- SQL: `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__<name>.sql`
- YAML:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__<name>.yml`

Note:

- Which columns already exist (skip those)
- Whether the model is `enabled: false` (flag to user, ask if they want to
  re-enable)
- Any duplicate column entries in the YAML (clean up while editing)

---

## Step 5 — Translate and confirm each field

For each field the user wants to move, propose the BigQuery SQL translation and
show it to the user before writing anything:

> **\<Field Name\>** (`<datatype>`):
>
> Tableau formula: `<original formula>`
>
> Proposed SQL: `<translated expression>`
>
> Does this look right? Any changes?

**Common Tableau → BigQuery SQL translations:**

| Tableau                     | BigQuery SQL                         |
| --------------------------- | ------------------------------------ |
| `IF … ELSEIF … ELSE … END`  | `CASE WHEN … THEN … ELSE … END`      |
| `ISNULL([x])`               | `x IS NULL`                          |
| `ZN([x])`                   | `COALESCE(x, 0)`                     |
| `STR([x])`                  | `CAST(x AS STRING)`                  |
| `INT([x])`                  | `CAST(x AS INT64)`                   |
| `FLOAT([x])`                | `CAST(x AS FLOAT64)`                 |
| `TODAY()`                   | `CURRENT_DATE()`                     |
| `NOW()`                     | `CURRENT_TIMESTAMP()`                |
| `DATEADD('day', N, [d])`    | `DATE_ADD(d, INTERVAL N DAY)`        |
| `DATEDIFF('day', [a], [b])` | `DATE_DIFF(b, a, DAY)`               |
| `DATETRUNC('month', [d])`   | `DATE_TRUNC(d, MONTH)`               |
| `DATEPART('year', [d])`     | `EXTRACT(YEAR FROM d)`               |
| `LEN([x])`                  | `LENGTH(x)`                          |
| `CONTAINS([x], 'y')`        | `x LIKE '%y%'`                       |
| `IIF(cond, a, b)`           | `IF(cond, a, b)`                     |
| `USERNAME()`                | _(skip — Tableau-only)_              |
| `{FIXED …}`                 | _(flag to user — LOD, needs review)_ |
| `[Parameters].[…]`          | _(skip — parameter, Tableau-only)_   |

**Bare string literals that look like org/entity names** (e.g. `"KTAF"`,
`"KIPP"`, `"Newark"`) are often hardcoded substitutes for a real column. Before
marking these as SKIP, check `int_extracts__student_enrollments` for a
`district` or equivalent column. If one exists upstream but is missing from the
extract model, propose adding it instead of replicating the literal.

---

## Step 6 — Update the model files

After all translations are confirmed:

**SQL file** — add new columns to the `SELECT` before the `from` clause:

- Trailing commas (comma at END of each line, per `.sqlfluff`)
- Column ordering from `src/dbt/CLAUDE.md`: plain refs → simple functions →
  nested functions → logicals → CASE statements → window functions

**YAML properties file** — add one entry per new column:

- `- name: <column_name>`
- `data_type: <bigquery_type>` (string → string, integer → int64, real →
  float64, boolean → boolean, date → date, datetime → datetime)
- Remove any duplicate column entries found in Step 4

---

## Step 7 — Validate

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

Then via dbt MCP or terminal:

```bash
dbt show --select <model_name> --limit 5 --project-dir src/dbt/kipptaf
```

Confirm new columns appear and values look correct.

---

## Step 8 — Summary and next steps

Report back:

- Model(s) updated and columns added
- Columns skipped (already existed, Tableau-only, or LOD expressions flagged for
  discussion)
- YAML duplicates cleaned up
- Whether the model needs to be re-enabled
- If the exposure `depends_on` needs updating, offer to do it
