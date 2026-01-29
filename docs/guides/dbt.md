# dbt

## Adding a Google Sheets source to dbt

1. Create your sheet
   [Data Integration / Google Sheets / In](https://drive.google.com/drive/folders/18acMCDHzrU_yTFSFd46f7b7iGadIzWmr).

2. Add a **named range**. This should encompass the entirety of the tab.

3. Update `src/dbt/kipptaf/models/google/sheets/sources-drive.yml`. Add a new
   entry under the `tables` attribute. Use the example below, replacing the
   variables with your specific sheet's information.

   | Variable              | Description                                                     |
   | --------------------- | --------------------------------------------------------------- |
   | **SOURCE_NAME**       | The name of the collection for your source tables               |
   | **SOURCE_TABLE_NAME** | The name of the source table, as it will appear in the database |
   | **SHEET_URL**         | The full URL of the Google Sheet, including `https://...`       |
   | **NAMED_RANGE**       | The name of the range you defined in step 2.                    |

   ```yaml
   sources:
     - name: ...
       tables:
         ...
         - name: src_google_sheets__{SOURCE NAME}__{SOURCE TABLE NAME}
           external:
             options:
               format: GOOGLE_SHEETS
               uris:
                 - {SHEET URL}
               sheet_range: {NAMED RANGE}
               skip_leading_rows: 1
           meta:
             dagster:
               asset_key:
                 - kipptaf
                 - {SOURCE NAME}
                 - {SOURCE TABLE NAME}
   ```

4. Update the external source definition

   ```sh
   dbt run-operation stage_external_sources --vars "{'ext_full_refresh': 'true'}" --args "select: [model name(s)]"
   ```

5. Create a staging model. Create a simple `select *` statement--this will help
   catch unexpected changes to the table schema--and add any calculated fields
   you require.

   ```sql
   select *, spam + 1 as eggs, from {{ source("{SOURCE NAME}", "{SOURCE TABLE NAME}") }}
   ```

6. Create a corresponding properties file for the staging model

   File name: `../properties/STAGING_MODEL_NAME.yml`

   | Variable         | Description                                                                                              |
   | ---------------- | -------------------------------------------------------------------------------------------------------- |
   | `models[].name`  | The exact name of your staging model                                                                     |
   | `columns[].name` | Column names are case-sensitive                                                                          |
   | `data_type`      | [BigQuery Data Type Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types) |

   ```yaml
   models:
     - name: {STAGING MODEL NAME}
       columns:
         - name: {COLUMN NAME 1}
           data_type: {COLUMN TYPE 1}
         - name: {COLUMN NAME 2}
           data_type: {COLUMN TYPE 2}
         ...
         - name: {COLUMN NAME N}
           data_type: {COLUMN TYPE N}
   ```

7. Build your staging model

## Updating a Google Sheets source

1. Duplicate the tab that you are modifying. If you will only be adding columns
   to the end of the sheet, you can skip this step.

2. Create a new named range. Use the same name but suffixed with something to
   make it unique (e.g. `_new`, `_v2`)

3. Update `src/dbt/kipptaf/models/google/sheets/sources-drive.yml`. Update the
   `sheet_range` attribute with the new named range.

4. Make your changes to the END of the sheet. Inserting columns between existing
   ones will break production. Columns can safely be rearranged after your
   changes are merged.

5. If necessary, update column definitions on the source YAML.

6. Update the external source definition

   ```sh
   dbt run-operation stage_external_sources --vars "{'ext_full_refresh': 'true'}" --args "select: [model name(s)]"
   ```

7. Update the data contract for your staging file
