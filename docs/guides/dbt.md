# Adding a Google Sheet source to dbt

## 1. Create your sheet

[Data Integration / Google Sheets / In](https://drive.google.com/drive/folders/18acMCDHzrU_yTFSFd46f7b7iGadIzWmr).

## 2. Add a **named range**

This should encompass the entirety of the tab.

## 3. Create (or update) a `sources-drive.yml` file

Under the appropriate folder in the dbt project, make sure to replace the
following variables:

| Variable              | Description                                                     |
| --------------------- | --------------------------------------------------------------- |
| **SOURCE_NAME**       | The name of the collection for your source tables               |
| **SOURCE_TABLE_NAME** | The name of the source table, as it will appear in the database |
| **SHEET_URL**         | The full URL of the Google Sheet, including `https://...`       |
| **NAMED_RANGE**       | The name of the range you defined in step 2.                    |

```yaml
version: 2

sources:
  - name: SOURCE_NAME
    schema: |
      {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'dev' -%}z_dev_{%- endif -%}
      {{ project_name }}_SOURCE_NAME
    tables:
      - name: src_SOURCE_NAME__SOURCE_TABLE_NAME
        external:
          options:
            format: GOOGLE_SHEETS
            uris:
              - SHEET_URL
            sheet_range: NAMED_RANGE
            skip_leading_rows: 1
        meta:
          dagster:
            asset_key:
              - "{{ project_name }}"
              - SOURCE_NAME
              - SOURCE_TABLE_NAME
```

!!! tip

If updating an existing `sources-drive.yml`, you will only need to add new
records under the `table` attribute.

## 4. Create a staging model

Create a simple `select *` statement--this will help catch unexpected changes to
the table schema--and add any calculated fields you require.

```sql
select *, spam + 1 as eggs, from {{ source("SOURCE_NAME", "SOURCE_TABLE_NAME") }}
```

## 5. Create a corresponding properties file for the staging model

File name: `../properties/STAGING_MODEL_NAME.yml`

| Variable         | Description                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------- |
| `models[].name`  | The exact name of your staging model                                                                     |
| `columns[].name` | Column names are case-sensitive                                                                          |
| `data_type`      | [BigQuery Data Type Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types) |

```yaml
version: 2
models:
  - name: STAGING_MODEL_NAME
    config:
      contract:
        enforced: true
      tags: google_sheet
    columns:
      - name: COLUMN_NAME_1
        data_type: COLUMN_TYPE_1
      - name: COLUMN_NAME_2
        data_type: COLUMN_TYPE_2
      ...
      - name: COLUMN_NAME_N
        data_type: COLUMN_TYPE_N
```

## 6. Test your changes

### Update the external source definition

```sh
dbt run-operation stage_external_sources --vars "ext_full_refresh: true" --args "select: SOURCE_NAME.SOURCE_TABLE_NAME"
```

### Build your staging model
