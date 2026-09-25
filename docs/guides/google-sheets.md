# Google Sheets & Forms

## Adding a Google Sheets source

1. Create your sheet in
   [Data Integration / Google Sheets / In](https://drive.google.com/drive/folders/18acMCDHzrU_yTFSFd46f7b7iGadIzWmr).

2. Add a **named range** covering the entire data tab (header row + data).

3. Update `src/dbt/kipptaf/models/google/sheets/sources-drive.yml`. Add a new
   entry under `tables`:

   | Variable              | Description                                  |
   | --------------------- | -------------------------------------------- |
   | **SOURCE_NAME**       | Collection name for your source tables       |
   | **SOURCE_TABLE_NAME** | Table name as it will appear in BigQuery     |
   | **SHEET_URL**         | Full URL of the Google Sheet (`https://...`) |
   | **NAMED_RANGE**       | The named range defined in step 2            |

   ```yaml
   sources:
     - name: ...
       tables:
         ...
         - name: src_google_sheets__{SOURCE_NAME}__{SOURCE_TABLE_NAME}
           external:
             options:
               format: GOOGLE_SHEETS
               uris:
                 - {SHEET_URL}
               sheet_range: {NAMED_RANGE}
               skip_leading_rows: 1
           meta:
             dagster:
               asset_key:
                 - kipptaf
                 - {SOURCE_NAME}
                 - {SOURCE_TABLE_NAME}
   ```

4. Stage the external source definition. See the
   [dbt Development guide](dbt-development.md#staging-external-sources) for
   details on using the VS Code task or terminal command.

5. Create a staging model. A simple `select *` is the starting point — it
   surfaces unexpected schema changes. Add any calculated fields you need:

   ```sql
   select
       *,
       spam + 1 as eggs,
   from {{ source("{SOURCE_NAME}", "{SOURCE_TABLE_NAME}") }}
   ```

6. Write the properties file by hand as
   `../properties/{STAGING_MODEL_NAME}.yml`. Staging models inherit
   `contract: enforced: true` from `dbt_project.yml`, so every column must have
   a `data_type`:

   ```yaml
   models:
     - name: { STAGING_MODEL_NAME }
       columns:
         - name: column_name
           data_type: string # see BigQuery data type reference
   ```

   See the
   [BigQuery data type reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types)
   for valid type names.

7. Build and validate:

   ```bash
   uv run dbt build --select {STAGING_MODEL_NAME}
   ```

   A successful build confirms the contract is satisfied and all column types
   are correct.

### Verifying changes against production

The dbt Core Tools extension's `--defer` mode automatically resolves unchanged
upstream models to production. Build your modified staging model and downstream
consumers will reference prod data for anything you haven't changed. See the
[dbt Development guide](dbt-development.md#defer-to-production) for details.

## Updating a Google Sheets source

1. Duplicate the tab you are modifying. Skip this step only if you are adding
   columns to the **end** of the sheet — inserting columns between existing ones
   will break production.

2. Create a new named range using the same name with a suffix (e.g. `_v2`).

3. Update `src/dbt/kipptaf/models/google/sheets/sources-drive.yml` — change
   `sheet_range` to the new named range.

4. Make your changes to the **end** of the sheet. Columns can be rearranged
   after the PR merges.

5. If you added or renamed columns, update the source YAML and the staging
   model's properties file with the new column definitions.

6. Stage the updated source. See the
   [dbt Development guide](dbt-development.md#staging-external-sources) for
   details.

7. Rebuild and verify the contract still passes:

   ```bash
   uv run dbt build --select {STAGING_MODEL_NAME}
   ```

## Publishing a warehouse view to a Google Sheet

The sections above cover sheets coming **in** as dbt sources. This one covers
the other direction: an `rpt_gsheets__*` model going **out** to someone who
reads it in Sheets.

Every published view takes two sheets, in two folders of the Data Integration
shared drive.

| Folder                                                                                          | Holds                                                                                                            | Named                                                                |
| ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| [IMPORTRANGE Sources](https://drive.google.com/drive/folders/1kwng_xGxQzIRNTVueiJqa_VHsd1tSQgO) | The Connected Sheets extraction. Refresh schedules are programmed here.                                          | Exactly the model name, e.g. `rpt_gsheets__gradebook_audit_template` |
| [Reports](https://drive.google.com/drive/folders/17PG7aMo6f3JxqtSvx7bm0w7FESf0Qbpy)             | What the user opens. Pulls from the source sheet with `IMPORTRANGE` and contains no Connected Sheets of its own. | A friendly name, e.g. `Gradebook Audit Template`                     |

### Why two

The split exists so a user cannot break the pipeline. Editing a Connected Sheets
range, renaming a tab, or deleting a column in the source sheet breaks the
refresh for everybody. The report sheet is downstream of that: a user who breaks
their own copy breaks only their own copy, and the source keeps refreshing for
every other consumer.

### Rules

1. **Share the Reports link, never the source link.** This is the whole point of
   the split. A source-sheet link handed to a user defeats it.
2. **Program refreshes only in the source sheet.** The report sheet has no
   Connected Sheets and nothing to schedule.
3. **The report sheet uses `IMPORTRANGE` only.** No formulas that reshape data,
   and no second data path — anything the user needs computed belongs in the dbt
   model.
4. **Every change is made in both sheets.** See below — this is the step people
   miss.
5. **The exposure `url` points at the source sheet**, not the report. The
   exposure tracks the sheet dbt actually feeds. Do not "correct" it to the
   report link.

### Changing a published view

**Both sheets need the change. Doing only one is the common failure.**

Dagster's exposure asset is a marker that writes nothing, so nothing in the
pipeline creates a tab, widens a range, or renames anything in either sheet. The
dbt model landing in BigQuery is the start of the job, not the end of it.

| What changed in the model   | Source sheet                      | Report sheet                                                                              |
| --------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------- |
| A new model on the exposure | Add a Connected Sheets tab for it | Add a tab with an `IMPORTRANGE` to the new source tab                                     |
| A column added or removed   | Refresh picks it up               | **Widen or narrow the `IMPORTRANGE` range** — a fixed range silently drops the new column |
| A tab renamed               | Rename it                         | Update every `IMPORTRANGE` naming that tab, or it returns `#REF!`                         |
| A model retired             | Remove the tab                    | Remove the tab                                                                            |

The column case is the dangerous one. The source sheet refreshes and looks
correct, the report sheet keeps working, and the user simply never sees the new
column. Nothing errors.

After any change, open the report sheet and confirm it shows what you expect.
That check takes seconds and is the only thing standing between a silent
mismatch and a user acting on stale columns.

## Adding a Google Form source

Google Forms feed data into Teamster via a linked Google Sheet (Forms
automatically appends responses to a connected sheet). Once the response sheet
exists, follow the
[Adding a Google Sheets source](#adding-a-google-sheets-source) steps — the form
sheet is treated identically to any other Google Sheet source.

The model config must include the `google_sheet` tag so Dagster assigns it to
the correct asset group:

```yaml
models:
  - name: stg_google_sheets__{source_name}__{table_name}
    config:
      contract:
        enforced: true
      tags: google_sheet
    columns: ...
```

## Maintaining the Cube access sheet

For guidance on filling in the `cube_access_individual_exceptions` tab
specifically (how rows, additional location grants, and the approval lifecycle
work), see the
[Cube Access: Individual Exceptions guide](cube-access-individual-exceptions.md).
