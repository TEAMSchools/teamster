# Amplify PM Student Summary Aimline Integration

**Issue:** [#3463](https://github.com/TEAMSchools/teamster/issues/3463)
**Date:** 2026-03-30

## Summary

Integrate a new Amplify mClass SFTP file (`dibels8_PM_CUSTOM_*`) into the data
platform. The file is a weekly "PM custom Aimline DYD" report dropped into the
existing `/PM` folder on the Amplify SFTP server. It follows the same delivery
pattern as the existing `pm_student_summary` asset but has distinct columns.

The work is split into two automated batches with developer gates between them:

- **Batch 1** — reusable SFTP inspection script
- **Dev gate 1** — run the script, review CSV headers and codegen output
- **Batch 2** — all pipeline code (Dagster asset, integration test, dbt source +
  staging model)
- **Dev gate 2** — run integration test to materialize data, then `dbt build`

## Context

- Two Amplify SFTP instances: `kippnewark` (all regions except Paterson) and
  `kipppaterson` (Paterson only).
- Existing pipeline: SFTP sensor detects new files, `build_sftp_file_asset()`
  downloads CSV and writes Avro to GCS, dbt staging model casts types and adds
  derived columns.
- All SFTP columns are ingested as `str` — type correction is deferred to dbt.
- Daily exports accumulate; the asset loads only the most recent file per
  partition (`ignore_multiple_matches=True`, sorted by `st_mtime` descending).

## Naming

| Layer            | Name                                                    |
| ---------------- | ------------------------------------------------------- |
| Pydantic class   | `PMStudentSummaryAimline`                               |
| Dagster asset    | `pm_student_summary_aimline`                            |
| dbt source table | `amplify_mclass_sftp.pm_student_summary_aimline`        |
| dbt staging      | `stg_amplify__mclass__sftp__pm_student_summary_aimline` |

Example source filename:

```
dibels8_PM_CUSTOM_2025-2026_BOY-MOY_MOY-EOY_AfterEOY_grades-KG-01-02-03-04-05-06-07-08-09-10-11-12_2026-03-29_07-33-35.csv
```

## Batch 1: `scripts/init_sftp_integration.py`

A reusable SFTP inspection script for exploring new file drops before building
pipelines. Standard first step for any future SFTP integration.

### Interface

```bash
# List files in a remote directory
uv run scripts/init_sftp_integration.py amplify list /PM

# List with filename filter
uv run scripts/init_sftp_integration.py amplify list /PM --pattern "PM_CUSTOM"

# Download a sample file
uv run scripts/init_sftp_integration.py amplify download /PM --pattern "PM_CUSTOM" --output /tmp/sample.csv

# Generate Pydantic class from CSV headers (from SFTP or local file)
uv run scripts/init_sftp_integration.py amplify codegen /PM --pattern "PM_CUSTOM" --class-name PMStudentSummaryAimline
uv run scripts/init_sftp_integration.py amplify codegen --local /tmp/sample.csv --class-name PMStudentSummaryAimline

# Scaffold full pipeline from CSV headers
uv run scripts/init_sftp_integration.py amplify scaffold /PM --pattern "PM_CUSTOM" \
  --class-name PMStudentSummaryAimline \
  --asset-name pm_student_summary_aimline \
  --code-locations kippnewark kipppaterson
```

### Design decisions

- **First positional arg is the resource name** — maps to `<NAME>_SFTP_HOST`,
  `<NAME>_SFTP_USERNAME`, `<NAME>_SFTP_PASSWORD` env vars (uppercased). Works
  for any SFTP integration (amplify, iready, renlearn, etc.)
- **Credentials via `os.environ`** — env vars are injected by 1Password at
  devcontainer start. No dotenv or Dagster `EnvVar` needed.
- **Subcommands** (`list`, `download`, `codegen`) keep the tool composable.
- **Codegen output** — Pydantic class with all fields as `str | None = None`.
  Field names are normalized: lowercased, spaces/special chars replaced with
  `_`. Printed to stdout (pipe to file as needed). Supports both SFTP source
  (downloads, reads headers, cleans up) and `--local` for an already-downloaded
  CSV.
- **Scaffold subcommand** — generates all pipeline boilerplate from CSV headers.
  Writes files directly to the repo. Developer fills in placeholders afterward.
  Generates:
  - **Pydantic schema** — `PMStudentSummaryAimline(SFTPFile)` class appended to
    the library's `schema.py`. All fields `str | None = None`.
  - **Avro schema** — `PM_STUDENT_SUMMARY_AIMLINE_SCHEMA` added to each code
    location's `schema.py`.
  - **Asset definition** — `build_sftp_file_asset()` call added to each code
    location's `assets.py`. `remote_file_regex` set to `...` (ellipsis
    placeholder) for the developer to fill in.
  - **Integration test** — test functions added to
    `tests/assets/test_assets_amplify_sftp.py`.
  - **dbt source** — external table entry added to `sources.yml`.
  - **dbt staging SQL** — `select * from {{ source(...) }}` with a
    `-- TODO: add type casts and derived columns` comment.
  - **dbt properties YAML** — boilerplate with model name, contract enforced,
    and a `-- TODO: add columns` placeholder.
- **PEP 723 inline metadata**, argparse, paramiko (already a transitive dep via
  dagster-ssh). Follows existing `scripts/` conventions.

### Files

| File                               | Action               |
| ---------------------------------- | -------------------- |
| `scripts/init_sftp_integration.py` | Create               |
| `scripts/CLAUDE.md`                | Update catalog table |

## Batch 2: Dagster asset + dbt staging model

Batch 2 is generated by the `scaffold` subcommand from Batch 1. The scaffold
writes all files directly to the repo. The developer then fills in placeholders.

### What `scaffold` generates

**Pydantic schema** — appends `PMStudentSummaryAimline(SFTPFile)` to
`src/teamster/libraries/amplify/mclass/sftp/schema.py`. All fields
`str | None = None`, derived from CSV headers.

**Avro schema** — adds `PM_STUDENT_SUMMARY_AIMLINE_SCHEMA` to each code
location's `schema.py`, using the existing `build_avro_schema()` pattern.

**Asset definition** — adds `build_sftp_file_asset()` call to each code
location's `assets.py` and appends to the `assets` list. The `remote_file_regex`
is set to `...` (ellipsis) as a placeholder:

```python
pm_student_summary_aimline = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "amplify", "mclass", "sftp", "pm_student_summary_aimline"],
    remote_dir_regex=r"/PM",
    remote_file_regex=...,  # TODO: fill in regex pattern
    ssh_resource_key="ssh_amplify",
    avro_schema=PM_STUDENT_SUMMARY_AIMLINE_SCHEMA,
    partitions_def=partitions_def,
    ignore_multiple_matches=True,
)
```

**Integration test** — adds test functions to
`tests/assets/test_assets_amplify_sftp.py` for each code location.

**dbt source** — adds `pm_student_summary_aimline` external table entry to
`src/dbt/amplify/models/sources.yml` following the existing pattern (GCS Avro,
BigLake connection, 7-day staleness, dagster asset_key metadata).

**dbt staging SQL** — creates a minimal passthrough model:

```sql
select *
from {{ source("amplify_mclass_sftp", "pm_student_summary_aimline") }}
-- TODO: add type casts and derived columns
```

**dbt properties YAML** — creates boilerplate with model name and contract:

```yaml
models:
  - name: stg_amplify__mclass__sftp__pm_student_summary_aimline
    config:
      contract:
        enforced: true
    # TODO: add columns
```

### Sensor

No changes. The existing `build_amplify_mclass_sftp_sensor()` in each code
location scans `/` recursively and matches against all assets in its selection.
Adding the new asset to the `assets` list is sufficient.

### Developer fills in

After running `scaffold`, the developer must:

1. Set `remote_file_regex` in both code locations' `assets.py` (e.g.,
   `r"dibels8_PM_CUSTOM_(?P<school_year>[\d-]+)_[-\w]+\.csv"`)
2. Add type casts and derived columns to the dbt staging SQL
3. Add column definitions to the dbt properties YAML

### Files changed (Batch 2 — all generated by `scaffold`)

| File                                                                                                              | Action                        | Developer action required |
| ----------------------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------- |
| `src/teamster/libraries/amplify/mclass/sftp/schema.py`                                                            | Add `PMStudentSummaryAimline` | None                      |
| `src/teamster/code_locations/kippnewark/amplify/mclass/sftp/schema.py`                                            | Add Avro schema               | None                      |
| `src/teamster/code_locations/kippnewark/amplify/mclass/sftp/assets.py`                                            | Add asset                     | Fill in regex             |
| `src/teamster/code_locations/kipppaterson/amplify/mclass/sftp/schema.py`                                          | Add Avro schema               | None                      |
| `src/teamster/code_locations/kipppaterson/amplify/mclass/sftp/assets.py`                                          | Add asset                     | Fill in regex             |
| `src/dbt/amplify/models/sources.yml`                                                                              | Add source table              | None                      |
| `src/dbt/amplify/models/mclass/sftp/staging/stg_amplify__mclass__sftp__pm_student_summary_aimline.sql`            | Create                        | Add type casts            |
| `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__pm_student_summary_aimline.yml` | Create                        | Add columns               |
| `tests/assets/test_assets_amplify_sftp.py`                                                                        | Add test functions            | None                      |

## Regex overlap check

The existing PM asset regex `dibels8_PM_(?P<school_year>[\d-]+)_[-\w]+\.csv`
does NOT match the new `dibels8_PM_CUSTOM_*` files. The `[\d-]+` named group
only matches digits and hyphens, so it fails on the `C` in `CUSTOM`. No changes
to the existing asset are needed.

## Dev workflow

After Batch 2, the developer validates the full pipeline:

1. **Fill in `remote_file_regex`** in both code locations' `assets.py`.
2. **Materialize the asset** via the integration test:
   `uv run pytest tests/assets/test_assets_amplify_sftp.py -k pm_student_summary_aimline -v`.
   This writes to the `teamster-test` GCS bucket using
   `get_io_manager_gcs_avro(code_location="test", test=True)`.
3. **Stage the external source** per district (creates BigQuery external table):
   `uv run scripts/dbt-sxs.py kippnewark --test --select amplify_mclass_sftp.pm_student_summary_aimline`
   `uv run scripts/dbt-sxs.py kipppaterson --test --select amplify_mclass_sftp.pm_student_summary_aimline`
4. **Add type casts and columns** to the dbt staging model.
5. **Build the dbt model** per district:
   `uv run dbt build -s stg_amplify__mclass__sftp__pm_student_summary_aimline --project-dir src/dbt/kippnewark`
   `uv run dbt build -s stg_amplify__mclass__sftp__pm_student_summary_aimline --project-dir src/dbt/kipppaterson`

This avoids the branch deployment round-trip and keeps the dev cycle fast.

## Out of scope

- Downstream dbt models (intermediate, marts) — separate work once staging is
  validated
- Backfilling historical data — start with current school year
- Scaffold support for non-SFTP integrations (REST API, framework-based)
