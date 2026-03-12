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
