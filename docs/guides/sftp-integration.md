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

## Step 7 — Stage external sources

Create the BigQuery external table pointing at the GCS data:

```bash
uv run scripts/dbt-sxs.py <district_project> --test --select <source_name>.<asset_name>
```

Run this for each district project that consumes the source (e.g., `kippnewark`,
`kipppaterson`). The `--test` flag uses the `teamster-test` bucket.

## Step 8 — Build and validate the dbt model

```bash
uv run dbt build -s <model_name> --project-dir src/dbt/<district_project>
```

Review the output — check for contract violations, test failures, and data
quality warnings.

## Summary

| Phase                | What happens                                  | Who       |
| -------------------- | --------------------------------------------- | --------- |
| Inspect (Steps 1-3)  | Explore SFTP, download sample, preview schema | Developer |
| Scaffold (Step 4)    | Generate all pipeline boilerplate             | Script    |
| Customize (Step 5)   | Fill in regex, type casts, column definitions | Developer |
| Validate (Steps 6-8) | Materialize, stage, build                     | Developer |
