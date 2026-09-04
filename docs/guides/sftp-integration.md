# Adding an SFTP Integration

This guide walks through adding a new SFTP file drop to the data platform using
`scripts/init_sftp_integration.py`. The script handles inspection, codegen, and
full pipeline scaffolding.

## Prerequisites

- SFTP credentials loaded in your environment (injected from 1Password at
  devcontainer start)
- The credential env vars follow the naming convention: `<RESOURCE>_SFTP_HOST`,
  `<RESOURCE>_SFTP_USERNAME_<CODE_LOCATION>`,
  `<RESOURCE>_SFTP_PASSWORD_<CODE_LOCATION>`

## Step 1 — Inspect the SFTP server

List files in the remote directory to confirm the new file is being dropped:

```bash
uv run scripts/init_sftp_integration.py list <resource> <code_location> <path> --pattern "<filter>"
```

Example:

```bash
uv run scripts/init_sftp_integration.py list amplify kipptaf /PM --pattern "PM_CUSTOM"
```

The script connects using `<RESOURCE>_SFTP_HOST` and per-location credentials,
lists files matching the pattern, and shows file sizes. If no files match, it
prints a warning.

## Step 2 — Download a sample file

```bash
uv run scripts/init_sftp_integration.py download <resource> <code_location> <path> --pattern "<filter>" --output /tmp/sample.csv
```

The script downloads the most recent file (by modification time) matching the
pattern.

## Step 3 — Preview the Pydantic class

Generate a Pydantic schema class from the CSV headers:

```bash
uv run scripts/init_sftp_integration.py codegen --local /tmp/sample.csv --class-name <ClassName>
```

Review the output — field names are normalized using `python-slugify`
(lowercased, special characters replaced with underscores). All fields are
`str | None = None`, matching the project convention of deferring type
correction to dbt.

## Step 4 — Scaffold the pipeline

Generate all pipeline boilerplate in one command:

```bash
uv run scripts/init_sftp_integration.py scaffold <resource> \
  --local /tmp/sample.csv \
  --class-name <ClassName> \
  --asset-name <snake_case_name> \
  --source-subpath <subpath> \
  --code-locations <loc1> <loc2>
```

Example:

```bash
uv run scripts/init_sftp_integration.py scaffold amplify \
  --local /tmp/sample.csv \
  --class-name PMStudentSummaryAimline \
  --asset-name pm_student_summary_aimline \
  --source-subpath mclass/sftp \
  --code-locations kippnewark kipppaterson
```

### What `scaffold` generates

| File                                                               | Description                                |
| ------------------------------------------------------------------ | ------------------------------------------ |
| `src/teamster/libraries/<resource>/<subpath>/schema.py`            | Pydantic class appended                    |
| `src/teamster/code_locations/<loc>/<resource>/<subpath>/schema.py` | Avro schema constant added                 |
| `src/teamster/code_locations/<loc>/<resource>/<subpath>/assets.py` | Asset definition added (regex placeholder) |
| `tests/assets/test_assets_<resource>_sftp.py`                      | Integration test functions added           |
| `src/dbt/<resource>/models/sources.yml`                            | External table source entry added          |
| `src/dbt/<resource>/models/<subpath>/staging/stg_*.sql`            | Passthrough `SELECT *` stub                |
| `src/dbt/<resource>/models/<subpath>/staging/properties/stg_*.yml` | Contract disabled, placeholder for columns |
| `src/dbt/kipptaf/models/<resource>/.../sources-kipp*.yml`          | Source entries for union                   |
| `src/dbt/kipptaf/models/<resource>/.../staging/stg_*.sql`          | Union relations view                       |

The scaffold is idempotent — running it again skips files that already exist.

### Sensor

No sensor changes are needed. The existing SFTP sensor for the resource scans
recursively and matches against all assets in its selection. Adding the new
asset to the `assets` list is sufficient.

## Step 5 — Fill in placeholders

The scaffold prints a numbered TODO checklist with file paths and exact
commands. You must fill in:

1. **`remote_dir_regex` and `remote_file_regex`** in each code location's
   `assets.py` — replace the `...` placeholders with the correct regex patterns.
   Use named groups for partition keys (e.g., `(?P<school_year>[\d-]+)`).

2. **Type casts and derived columns** in the dbt staging SQL — the scaffold
   generates a `SELECT *` passthrough. Add `* replace (...)` for type casts and
   additional computed columns as needed.

3. **Column definitions** in the dbt properties YAML — add all columns with
   `data_type`, `description`, and a uniqueness test. Then set
   `contract.enforced: true`.

## Step 6 — Materialize test data

Run the integration test to write data to the `teamster-test` GCS bucket:

```bash
uv run pytest tests/assets/test_assets_<resource>_sftp.py -k <asset_name> -v
```

This uses `get_io_manager_gcs_avro(code_location="test", test=True)` which
writes to `teamster-test` with a `test/` path prefix.

## Step 7 — Stage and build in your dev schema

Stage the external table and build the staging model in your personal dev schema
(`zz_<user>_*`). This is for local iteration — verifying type casts, column
definitions, and test results.

Stage with the **dbt: Stage External Sources** VS Code task (Terminal > Run
Task). It prompts for project, target, and source selector. `scripts/CLAUDE.md`
documents it in full.

The task always points the external table at the project's PRODUCTION GCS
bucket. Step 6 wrote your sample to `teamster-test`, so for a source whose
production data does not exist yet, run the operation directly and override
`cloud_storage_uri_base` to the test bucket:

```bash
uv run dbt run-operation stage_external_sources \
  --project-dir src/dbt/<district_project> \
  --target dev \
  --vars '{"ext_full_refresh": "true", "cloud_storage_uri_base": "gs://teamster-test/dagster/<district_project>"}' \
  --args 'select: <source_name>.<asset_name>'

uv run dbt build -s <model_name> --project-dir src/dbt/<district_project>
```

The path under the bucket is unchanged — the avro IO manager's `test=True` only
swaps the bucket and adds a local JSON copy, not the blob path.

`--target` controls the BigQuery schema: `dev` (personal `zz_<user>_*`) or
`staging` (shared, read by CI).

Review the output — check for contract violations, test failures, and data
quality warnings. Run this for each district project.

## Step 8 — Stage and build for CI

The kipptaf union model sources from district staging tables. In CI (dbt Cloud),
these resolve to the shared `z_dev_` schema. The district staging model must
exist there before kipptaf CI can build.

Re-run the stage and build with `--target staging`:

```bash
uv run dbt run-operation stage_external_sources \
  --project-dir src/dbt/<district_project> \
  --target staging \
  --vars '{"ext_full_refresh": "true", "cloud_storage_uri_base": "gs://teamster-test/dagster/<district_project>"}' \
  --args 'select: <source_name>.<asset_name>'

uv run dbt build -s <model_name> --project-dir src/dbt/<district_project> --target staging
```

!!! note Once the asset is materialized in production, re-stage without the
`cloud_storage_uri_base` override — the **dbt: Stage External Sources** task at
`--target staging` does exactly that — so the external table points at the
production bucket instead of `teamster-test`. Skip it and CI keeps reading your
test sample indefinitely.

## Summary

| Phase                | What happens                                  | Who       |
| -------------------- | --------------------------------------------- | --------- |
| Inspect (Steps 1-3)  | Explore SFTP, download sample, preview schema | Developer |
| Scaffold (Step 4)    | Generate all pipeline boilerplate             | Script    |
| Customize (Step 5)   | Fill in regex, type casts, column definitions | Developer |
| Validate (Steps 6-7) | Materialize, stage, build in personal dev     | Developer |
| CI Setup (Step 8)    | Stage and build in shared z*dev* schema       | Developer |
