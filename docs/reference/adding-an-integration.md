# Adding an Integration

Most integrations in Teamster follow a two-layer **Library + Config** pattern
that separates reusable asset logic from per-school configuration.

## Pattern overview

```
src/teamster/libraries/<integration>/assets.py   ← reusable factory function
src/teamster/code_locations/<school>/
  <integration>/
    config/
      assets-<name>.yaml                         ← per-school asset parameters
    assets.py                                    ← calls factory with config
```

## Step 1 — Write the library factory

Create `src/teamster/libraries/<integration>/assets.py` with a
`build_<integration>_asset()` factory function. The factory accepts asset
parameters and returns a Dagster asset or list of assets.

```python
# src/teamster/libraries/myintegration/assets.py
from dagster import asset

def build_myintegration_asset(name: str, endpoint: str, ...):
    @asset(name=name, ...)
    def _asset(context, myintegration_resource):
        ...

    return _asset
```

## Step 2 — Write the YAML config

Create one or more YAML files under
`src/teamster/code_locations/<school>/<integration>/config/`. Each file lists
the asset parameters for that school.

```yaml
# config/assets-reports.yaml
assets:
  - name: my_report
    endpoint: /api/reports/my_report
    ...
```

## Step 3 — Wire up the code location

Create `src/teamster/code_locations/<school>/<integration>/assets.py` and call
the factory for each YAML config:

```python
# src/teamster/code_locations/kipptaf/myintegration/assets.py
from dagster import config_from_files

from teamster.libraries.myintegration.assets import build_myintegration_asset

assets = [
    build_myintegration_asset(**config)
    for config in config_from_files(
        ["src/teamster/code_locations/kipptaf/myintegration/config/assets-reports.yaml"]
    )["assets"]
]
```

## Step 4 — Add to definitions

Import the assets into the code location's `definitions.py` and add them to the
`Definitions` object along with any required resources.

```python
# src/teamster/code_locations/kipptaf/definitions.py
from teamster.code_locations.kipptaf.myintegration.assets import assets as myintegration_assets

defs = Definitions(
    assets=[..., *myintegration_assets],
    resources={..., "myintegration_resource": MYINTEGRATION_RESOURCE},
)
```

## Asset key convention

Asset keys follow the pattern `[code_location, integration, table_name]`, e.g.
`kippnewark/powerschool/students`. The `CustomDagsterDbtTranslator` in
`libraries/dbt/dagster_dbt_translator.py` automatically prefixes dbt asset keys
with the code location name.

## SFTP assets

SFTP-based ingestion uses three factory functions from
`teamster.libraries.sftp.assets`, all of which write Avro records to GCS via
`io_manager_gcs_avro`:

| Factory                      | Use case                                                      |
| ---------------------------- | ------------------------------------------------------------- |
| `build_sftp_file_asset()`    | Matches a single file; raises if multiple files match         |
| `build_sftp_archive_asset()` | Downloads a zip archive and extracts one file                 |
| `build_sftp_folder_asset()`  | Collects all matching files in a folder and concatenates rows |

All three share the same core parameters: `asset_key`, `remote_dir_regex`,
`remote_file_regex`, `ssh_resource_key`, `avro_schema`, and optionally
`partitions_def`.

### Partition key substitution

Named regex groups in `remote_dir_regex` and `remote_file_regex` are replaced
with partition key dimension values at runtime. For multi-partition assets, each
dimension name maps to a named group in the regex.

For example, an asset partitioned by `fiscal_year` with
`remote_dir_regex = r"/reports/(?P<fiscal_year>\d{4})/"` resolves the directory
to `/reports/2026/` when materializing the `2026` partition.

## Asset checks (Avro schema validation)

Every SFTP and API asset should declare an Avro schema validity check using the
two helpers in `teamster.core.asset_checks`:

```python
from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)

# In the factory — declare the check spec alongside the asset
check_specs = [build_check_spec_avro_schema_valid(asset_key)]

# In the asset body — run the check after yielding output
yield check_avro_schema_valid(asset_key, records, avro_schema)
```

The check **warns** (does not fail) when records contain fields not present in
the Avro schema. This surfaces schema drift in the Dagster UI without blocking
downstream assets.
