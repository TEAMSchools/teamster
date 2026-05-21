# CLAUDE.md — `dbt/powerschool/`

Source-system staging project for **PowerSchool SIS** data. Produces clean,
contract-enforced staging models consumed by all district-specific dbt projects
(`kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`) and `kipptaf`.

## Model Structure

```text
models/
  sis/
    base/        # base models (light renaming, no logic)
    staging/
      odbc/      # models sourced from live Oracle ODBC connection (enabled by default)
      sftp/      # models sourced from SFTP file extracts (disabled by default)
    intermediate/
```

All staging models have `contract: enforced: true`. Each district project
overrides `odbc.+enabled` and `sftp.+enabled` in its own `dbt_project.yml` to
select the ingestion method.

## Key Variables

| Variable                            | Default | Notes                                          |
| ----------------------------------- | ------- | ---------------------------------------------- |
| `current_academic_year`             | `0`     | Overridden per district project                |
| `local_timezone`                    | `UTC`   | Overridden per district project                |
| `bigquery_external_connection_name` | `null`  | Set to BigLake connection in district projects |

## Cross-Project Usage

This project is never run standalone in production. District-specific projects
reference it as a dbt package and override variables and enabled flags. When a
district project runs, it resolves `ref('stg_powerschool__*')` models from this
project.

The `odbc/` vs `sftp/` split exists because some schools pull data via live
Oracle ODBC tunnel and others via SFTP file drops. Only one should be enabled
per deployment.

## GPA Gotchas

- **`storecode = 'Y1'` only**: Q1–Q4 records have `gpa_points = 0` by design —
  only `storecode = 'Y1'` rows are used in GPA calculations.
- **`districtentrydate` null placeholder**: PowerSchool stores null/missing
  dates as `1899-xx-xx`. Derive network tenure from `MIN(academic_year)` in
  storedgrades instead.
