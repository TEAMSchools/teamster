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
      dlt/       # models sourced from dlt (Oracle over SSH tunnel → BigQuery); disabled by default
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

The `odbc/` / `sftp/` / `dlt/` split exists because districts pull PowerSchool
via a live Oracle ODBC tunnel, SFTP file drops, or dlt (Oracle over an SSH
tunnel → BigQuery). Only one variant is enabled per district.

## dlt staging variant (#3807)

`kipppaterson` ingests PowerSchool via dlt; `staging/dlt/` is the template for
migrating the ODBC districts. A dlt model = its **odbc** sibling minus the
struct-unwrap: dlt lands raw Oracle scalars, so drop the
`.int_value`/`.double_value`/`coalesce(... .bytes_decimal_value ...)` accessors,
the `dbt_utils.deduplicate` (native table, no `_file_name` dupes), and any
`_dagster_partition_*`; explicitly project the shared contract columns and cast
to the contract type (`NUMERIC(10)`→int, `NUMERIC(38,9)`→float64,
`TIMESTAMP`→date, `STRING`→bare). Watch native-type divergence per column: a
date Oracle stores as DATE lands `TIMESTAMP` (use `cast(x as date)`), one stored
as text lands `STRING` (keep the odbc `parse_date`) — check the landed type,
don't assume. Source is `sources-bigquery.yml` schema
`dagster_<district>_dlt_powerschool`, read in every target (dlt writes the prod
dataset even on branch deploys).

## GPA Gotchas

- **`storecode = 'Y1'` only**: Q1–Q4 records have `gpa_points = 0` by design —
  only `storecode = 'Y1'` rows are used in GPA calculations.
- **`districtentrydate` null placeholder**: PowerSchool stores null/missing
  dates as `1899-xx-xx`. Derive network tenure from `MIN(academic_year)` in
  storedgrades instead.

## FTE & Sentinel Gotchas

- **FTE scoping**: `stg_powerschool__fte` is per `(schoolid, yearid)`. An
  enrollment's `fteid` must reference an FTE whose `schoolid` and `yearid` match
  — otherwise `(fteid, attendance_conversion_id)` joins to nothing in
  `stg_powerschool__attendance_conversion_items` and `attendancevalue` is
  silently NULL in `int_powerschool__ps_adaadm_daily_ctod`. PS does not enforce;
  guarded by
  `test_int_powerschool__ps_enrollment_all__fteid_belongs_to_school_year`.
- **`schoolid = 999999`**: graduated-students sentinel, not a "no school"
  marker. Already excluded in `int_powerschool__district_entry_date`. Students
  at 999999 commonly retain a real-school FTE from prior placement — the
  fteid-belongs-to-school-year test treats this as a cleanup target.
