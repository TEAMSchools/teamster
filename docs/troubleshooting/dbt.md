# Troubleshooting dbt

## Contract violations

Contract enforcement is on for all `staging/`, `extracts/`, and `marts/` models.
A contract violation means the compiled model's column names or types don't
match what's declared in the properties file.

**`Contract violated` on build** — the model compiled successfully but a column
is missing or has the wrong type:

1. Run `uv run dbt show --select {model}` to inspect actual output columns.
2. Compare against the properties file (`models/.../{model}.yml`).
3. Fix the mismatch — either update the SQL or update `data_type` in the YAML.

**`Column not found in contract` after adding a column** — you added a column to
the SQL but forgot to add it to the properties file. Add the column definition
with the correct `data_type`.

**`data_type` mismatch** — BigQuery type names are case-insensitive in SQL but
must be lowercase in the contract YAML (`string`, `int64`, `date`, etc.). See
the
[BigQuery data type reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types).

!!! note

    `contract: enforced: true` and `materialized: table` are inherited from
    `dbt_project.yml` at the directory level — do not repeat them per-model.

## Compilation errors

**`Relation not found`** — the `ref()` or `source()` target doesn't exist or
hasn't been parsed:

- Run `uv run dbt parse --project-dir=src/dbt/{project}` to refresh the
  manifest.
- For cross-project refs (e.g. `kipptaf` referencing `powerschool`), confirm the
  source project's manifest is also up to date.

**`dbt deps` required** — if you see missing package errors, install
dependencies first:

```bash
uv run dbt deps --project-dir=src/dbt/{project}
```

**`Macro not found`** — usually means `dbt_utils` or another package isn't
installed. Run `dbt deps`.

## Test failures

**Uniqueness test failure** — a `unique:` or
`dbt_utils.unique_combination_of_columns` test is failing:

1. Query the model directly to find duplicates.
2. If the source data is genuinely duplicated, add deduplication logic to the
   model (e.g. `qualify row_number() over (...) = 1`).
3. If the test grain is wrong, update the test definition.

**`not_null` failure** — check whether the null is expected (bad source data) or
a join/logic error. Do not remove the test — fix the model or add a `where`
clause to the test.

## Running dbt locally

The `DBT_PROFILES_DIR` environment variable is set to
`/workspaces/teamster/.dbt` in the devcontainer. If your profile isn't loading:

```bash
echo $DBT_PROFILES_DIR   # should be /workspaces/teamster/.dbt
ls $DBT_PROFILES_DIR     # should contain profiles.yml
```

Always prefix dbt commands with `uv run` and pass `--project-dir`:

```bash
uv run dbt build --select {model} --project-dir=src/dbt/kipptaf
```

## dbt Power User extension

**"No dbt project found"** — the extension needs the project directory set
explicitly. Open the VS Code command palette and run
`dbt Power User: Select dbt project`. Choose the project directory under
`src/dbt/`.

**Lineage panel is blank** — the manifest may be stale. Run
`uv run dbt parse --project-dir=src/dbt/{project}` to regenerate it, then reload
the lineage panel.

**Extension not activating** — confirm `innoverio.vscode-dbt-power-user` is
installed. In the devcontainer it is installed automatically; outside the
devcontainer you must install it manually.
