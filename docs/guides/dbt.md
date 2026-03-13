# dbt

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

4. Stage the external source definition:

   ```bash
   uv run dbt run-operation stage_external_sources \
     --vars "{'ext_full_refresh': 'true'}" \
     --args 'select: [model_name]'
   ```

5. Create a staging model. A simple `select *` is the starting point — it
   surfaces unexpected schema changes. Add any calculated fields you need:

   ```sql
   select
       *,
       spam + 1 as eggs,
   from {{ source("{SOURCE_NAME}", "{SOURCE_TABLE_NAME}") }}
   ```

6. Generate the properties file scaffold:

   ```bash
   uv run dbt run-operation generate_model_yaml \
     --args '{"model_names": ["{STAGING_MODEL_NAME}"]}'
   ```

   Save the output as `../properties/{STAGING_MODEL_NAME}.yml`. Staging models
   inherit `contract: enforced: true` from `dbt_project.yml`, so every column
   must have a `data_type`:

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

### Verifying a Google Sheets source against production

Use `scripts/dbt-sxs.py` to run a model against both your dev dataset and
production side-by-side, making it easy to spot regressions before merging:

```bash
uv run scripts/dbt-sxs.py kipptaf \
  --select google_sheets.src_google_sheets__kippfwd_expected_assessments
```

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

6. Stage the updated source:

   ```bash
   uv run dbt run-operation stage_external_sources \
     --vars "{'ext_full_refresh': 'true'}" \
     --args 'select: [model_name]'
   ```

7. Rebuild and verify the contract still passes:

   ```bash
   uv run dbt build --select {STAGING_MODEL_NAME}
   ```

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
