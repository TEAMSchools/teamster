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
