# Component-Based Definitions Loading

**Date**: 2026-03-30 **Issue**:
[#3375](https://github.com/TEAMSchools/teamster/issues/3375) **Status**: Design
approved

## Problem

Each code location's `definitions.py` manually imports modules and
hand-assembles the `Definitions` object. `kipptaf` wires 22 modules, 29
resources, 13 schedule lists, and 5 sensor sources. Every new integration
requires editing this central file. The dbt integration manually loads
manifests, constructs translators, and wires `DbtCliResource` — all of which the
built-in `DbtProjectComponent` handles automatically.

## Approach

Use `load_from_defs_folder()` (Dagster's standard component entry point) with
`Definitions.merge()`. Each code location gets a `defs/` package where:

- dbt assets are configured declaratively via `defs.yaml`
  (`TeamsterDbtProjectComponent`, a subclass of `DbtProjectComponent`)
- Non-dbt integrations are thin `@definitions` wrappers that bridge to existing
  modules (pending full component conversion in a follow-up)
- Resources, executor, and sensors remain manually wired via
  `Definitions.merge()`

Prototype on **kipppaterson** (smallest), then migrate all 5 code locations.

## Scope

This issue covers component infrastructure and migration of all 5 code
locations. Converting non-dbt integration libraries (SFTP, REST API) into full
components is a separate follow-up that depends on
[#3390](https://github.com/TEAMSchools/teamster/issues/3390) (base HTTP resource
extraction).

## Project Configuration

Add `[tool.dg]` to `pyproject.toml` (one-time, shared by all code locations):

```toml
[tool.dg]
directory_type = "project"

[tool.dg.project]
root_module = "teamster"
registry_modules = [
    "dagster.components",
    "dagster_dbt.components",
    "teamster.libraries.dbt",
]
```

This enables `load_from_defs_folder()` at runtime and `dg` CLI tooling
(`dg check defs`, `dg list defs`, `dg scaffold defs`). The
`teamster.libraries.dbt` entry exposes `TeamsterDbtProjectComponent` for YAML
`type:` resolution.

## `TeamsterDbtProjectComponent`

**New file**: `src/teamster/libraries/dbt/components.py`

Subclasses `DbtProjectComponent` (a `StateBackedComponent`) with two overrides
and one custom field.

### Custom field

`code_location: str` — required, provided via `defs.yaml`. Used by
`get_asset_spec()` for key prefixing and group logic.

### `get_asset_spec(self, manifest, unique_id, project) -> AssetSpec`

Replaces all `CustomDagsterDbtTranslator` logic. For each dbt node:

- **Asset key**: Calls `super().get_asset_spec()` for the base spec, then
  prefixes with `code_location` unless `meta.dagster.asset_key` is set.
- **Group name**: Falls back to `package_name` (cross-project refs), then
  `fqn[1]` (directory-based).
- **Tags**: Adds `dagster/materialized` tag from the node's
  `config.materialized`.
- **Automation condition**: Branches on materialized type:
  - `view` with `union_relations` in `raw_code` ->
    `dbt_union_relations_automation_condition()`
  - `view` or `ephemeral` -> `dbt_view_automation_condition()`
  - Everything else (tables) -> `dbt_table_automation_condition()`

Uses `self.get_resource_props(manifest, unique_id)` to access dbt node
properties — the component provides this as a convenience method.

### `execute(self, context, dbt) -> Iterator`

Preserves the existing `build_dbt_assets()` pre-execution logic:

1. Reads `self._validated_manifest` to find upstream `external` sources for the
   selected assets.
2. Runs `dbt run-operation stage_external_sources` for those sources.
3. Runs `dbt run-operation refresh_external_metadata_cache` for BigLake sources
   (with the concurrent-job regex warning handler).
4. Delegates to `super().execute(context, dbt)` for the actual `dbt build`
   (which handles `cli_args`, `include_metadata`, streaming, etc.).

### What it replaces

- `libraries/dbt/assets.py` (`build_dbt_assets()`) — superseded by `execute()`
- `libraries/dbt/dagster_dbt_translator.py` (`CustomDagsterDbtTranslator`) —
  superseded by `get_asset_spec()`

Both files are kept until all 5 code locations are migrated, then removed.

## `defs/` Package Structure

Each code location gets a `defs/` package. Auto-discovery handles two file
types:

- Directories with `defs.yaml` -> loaded as YAML components
- Python files with `@definitions` -> loaded as `PythonFileComponent`

### Single-dbt locations (kipppaterson, kippcamden, kippnewark, kippmiami)

```text
code_locations/<name>/
  __init__.py              # KEEP (remove DBT_PROJECT)
  definitions.py           # REWRITE
  defs/                    # NEW
    __init__.py            # Empty package marker
    defs.yaml              # Root DefsFolderComponent with post_processing
    dbt/
      defs.yaml            # TeamsterDbtProjectComponent
    <integration>.py       # @definitions wrappers
  <integration>/           # KEEP (existing modules, unchanged)
```

### kipptaf (multi-split dbt)

kipptaf uses 3 separate `build_dbt_assets()` calls with different
select/exclude/op_tags/partitions_def. Each becomes a separate `defs.yaml`:

```text
code_locations/kipptaf/
  defs/
    __init__.py
    defs.yaml              # Root DefsFolderComponent with post_processing
    dbt/
      defs.yaml            # DefsFolderComponent (recurses into children)
      core/defs.yaml       # Main run (exclude: "source:adp_payroll+ tag:google_sheet")
      google_sheets/defs.yaml  # Isolated (select: "tag:google_sheet")
    dbt_adp_payroll.py     # @definitions wrapper (needs dynamic partitions_def)
    exposures.py           # @definitions wrapper for non-Tableau exposure AssetSpecs
    adp.py
    airbyte.py
    collegeboard.py
    couchdrop.py
    coupa.py
    deanslist.py
    dlt.py
    extracts.py
    google.py
    knowbe4.py
    ldap.py
    level_data.py
    nsc.py
    overgrad.py
    performance_management.py
    powerschool.py
    smartrecruiters.py
    surveys.py
    tableau.py
    zendesk.py
```

**kipptaf special cases**:

- `adp_payroll` split uses a `partitions_def` from `adp.payroll.assets`. This
  partitions_def must be importable and passable to the component. If
  `DbtProjectComponent` does not support `partitions_def` as a YAML field, the
  adp_payroll split may need to remain a Python `@definitions` wrapper that
  constructs the component programmatically.
- `asset_specs` for non-Tableau dbt exposures depend on the manifest and
  translator. These move to a `defs/exposures.py` wrapper. The wrapper can
  access the manifest from the component's `dbt_project.manifest_path` or
  continue to read it from the `DbtProject` directly.
- `asset_checks` (freshness checks on ADP WFN models) stay in `definitions.py`
  via `Definitions.merge()`.

### Non-dbt wrapper pattern

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipppaterson import amplify


@definitions
def defs():
    return Definitions(assets=amplify.assets)
```

Sensors and schedules are **not** included in wrappers — they stay in
`definitions.py`.

## Sample `defs.yaml` Files

### Root `defs/defs.yaml` (all code locations)

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kipppaterson
```

Cross-cutting tag applied to all assets for UI filtering/grouping. Each code
location uses its own `code_location` value.

### `defs/dbt/defs.yaml` (single-dbt locations)

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kipppaterson"
  code_location: kipppaterson
  include_metadata:
    - column_metadata
  translation_settings:
    enable_code_references: true
  op:
    tags:
      dagster-k8s/config:
        container_config:
          resources:
            requests:
              cpu: "500m"
            limits:
              cpu: "1250m"
```

### `defs/dbt/defs.yaml` (kipptaf — parent folder)

```yaml
type: dagster.DefsFolderComponent
```

### `defs/dbt/core/defs.yaml` (kipptaf)

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kipptaf"
  code_location: kipptaf
  exclude: "source:adp_payroll+ tag:google_sheet"
  include_metadata:
    - column_metadata
  translation_settings:
    enable_code_references: true
  op:
    name: kipptaf__dbt_assets
    tags:
      dagster-k8s/config:
        container_config:
          resources:
            requests:
              cpu: "500m"
            limits:
              cpu: "2000m"
```

### `defs/dbt_adp_payroll.py` (kipptaf — Python wrapper)

The `adp_payroll` split requires `GENERAL_LEDGER_FILE_PARTITIONS_DEF` (built
dynamically from file data), which cannot be expressed in YAML. This split
constructs `TeamsterDbtProjectComponent` programmatically:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.dbt.components import TeamsterDbtProjectComponent


@definitions
def defs():
    # construct component programmatically for dynamic partitions_def
    ...
```

The exact construction API will be determined during implementation — the
component may accept `partitions_def` as an init parameter, or the wrapper may
need to call `build_defs()` and patch the partitions_def onto the resulting
asset specs.

### `defs/dbt/google_sheets/defs.yaml` (kipptaf)

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kipptaf"
  code_location: kipptaf
  select: "tag:google_sheet"
  include_metadata:
    - column_metadata
  translation_settings:
    enable_code_references: true
  op:
    name: kipptaf__dbt_assets__google_sheets
    tags:
      dagster-k8s/config:
        container_config:
          resources:
            requests:
              cpu: "500m"
            limits:
              cpu: "2000m"
```

## `definitions.py` Rewrite

Each code location's `definitions.py` becomes a thin merger.

### kipppaterson

```python
from pathlib import Path

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
)
from dagster.components import load_from_defs_folder
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson import amplify, couchdrop
from teamster.core.resources import (
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_RESOURCE_AMPLIFY,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_pickle,
)

component_defs = load_from_defs_folder(
    path_within_project=Path(
        "src/teamster/code_locations/kipppaterson/defs"
    ),
)

defs = Definitions.merge(
    component_defs,
    Definitions(
        executor=k8s_job_executor,
        sensors=[
            *amplify.sensors,
            *couchdrop.sensors,
            AutomationConditionSensorDefinition(
                name=f"{CODE_LOCATION}__automation_condition_sensor",
                target=AssetSelection.all(),
            ),
        ],
        resources={
            "gcs": GCS_RESOURCE,
            "google_drive": GOOGLE_DRIVE_RESOURCE,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
            "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
            "ssh_amplify": SSH_RESOURCE_AMPLIFY,
            "ssh_couchdrop": SSH_COUCHDROP,
        },
    ),
)
```

**Changes from current**:

- `load_assets_from_modules()` replaced by `load_from_defs_folder()`
- `dbt_cli` resource removed (component manages its own `DbtCliResource`)
- `DBT_PROJECT` import removed (component manages `DbtProject` from YAML)

Sensors, resources, and executor remain manually wired.

## Optimizations Over Current Pattern

The `DbtProjectComponent` gives these for free:

| Current (manual)                                                 | Component (automatic)                  |
| ---------------------------------------------------------------- | -------------------------------------- |
| `json.loads(DBT_PROJECT.manifest_path.read_text())` per location | State-backed manifest loading/caching  |
| `DBT_PROJECT = DbtProject(...)` in `__init__.py`                 | `project:` YAML attribute              |
| `dbt_cli` resource wired in `definitions.py`                     | Component creates own `DbtCliResource` |
| Manual `dagster-dbt project prepare-and-package`                 | `prepare_if_dev: true` (default)       |
| `select`/`exclude` as Python kwargs                              | Declarative YAML                       |
| `op_tags` as Python dict                                         | Declarative YAML                       |
| `.fetch_column_metadata(with_column_lineage=False)`              | `include_metadata: [column_metadata]`  |
| Code references off                                              | `enable_code_references: true`         |
| No cross-cutting tags                                            | `post_processing` on root `defs.yaml`  |

## Validation

Per code location, in order:

```bash
# 1. Validate component YAML schemas
uv run dg check defs --path src/teamster/code_locations/<name>/defs

# 2. List discovered defs to confirm parity
uv run dg list defs --path src/teamster/code_locations/<name>/defs

# 3. Full definitions validate
uv run dagster definitions validate \
  -m teamster.code_locations.<name>.definitions

# 4. Existing test suite
uv run pytest tests/test_dagster_definitions.py -v
```

## Migration Order

1. **kipppaterson** — smallest (6 modules, 7 resources, no schedules)
2. **kippcamden** — small school location, tests schedule patterns
3. **kippnewark** — larger, more integration variety
4. **kippmiami** — Florida-specific integrations (FLDOE)
5. **kipptaf** — largest (22 modules), multi-split dbt, exposure specs

## Cleanup After All 5 Migrated

- Remove `libraries/dbt/assets.py` (`build_dbt_assets()`)
- Remove `libraries/dbt/dagster_dbt_translator.py`
  (`CustomDagsterDbtTranslator`)
- Remove `DBT_PROJECT` from each code location's `__init__.py`
- Remove `dbt/assets.py` from code locations that don't have manifest-dependent
  modules (kipppaterson, kippcamden, kippnewark, kippmiami)
- kipptaf's `dbt/assets.py` stays (stripped to manifest + translator only) until
  manifest-dependent modules (`google/sheets`, `google/appsheet`, `tableau`,
  `exposures`) are converted to full components
- Remove `dbt_cli` resource from each `definitions.py`

## What Does Not Change

- `src/dbt/` — dbt projects stay where they are
- `src/teamster/core/` — shared resources, IO managers, utilities, automation
  conditions
- `src/teamster/libraries/` — integration libraries (wrappers import from them)
- `dagster-cloud.yaml` — each code location still loads from
  `teamster.code_locations.<name>.definitions`
- `Dockerfile` — no changes needed
- Non-dbt integration modules — unchanged (wrappers import from them)
- Sensors — stay manually wired in `definitions.py`
- Schedules — stay manually wired in `definitions.py`

## Resolved Questions

1. **`partitions_def` on `DbtProjectComponent`**: `AssetAttributesModel`
   supports `partitions_def` in YAML for standard types (daily, hourly, weekly,
   static). However, kipptaf's `adp_payroll` split uses
   `GENERAL_LEDGER_FILE_PARTITIONS_DEF`, which is built dynamically from file
   data and cannot be expressed in YAML. **Decision**: the `adp_payroll` split
   will be a Python `@definitions` wrapper (`defs/dbt_adp_payroll.py`) that
   constructs `TeamsterDbtProjectComponent` programmatically, rather than a
   `defs.yaml`. The other two splits (core, google_sheets) remain YAML.

2. **Automation condition branching**: The `translation` field and
   `post_processing` both support setting `automation_condition`, but only
   uniformly — they cannot branch per-model based on `raw_code` content (needed
   for `union_relations` detection). **Decision**: `get_asset_spec()` override
   remains the correct approach.

3. **kipptaf manifest-dependent modules**: Four kipptaf modules
   (`google/sheets`, `google/appsheet`, `tableau`, and `dbt/assets.py` itself)
   import the parsed manifest at module load time to build asset specs (Google
   Sheets sources, AppSheet sources, Tableau exposures, non-Tableau exposures).
   After migration, the component owns dbt execution, but these modules still
   need manifest access. **Decision**: Keep `dbt/assets.py` stripped down to
   just the manifest and `DbtProject` — remove the `build_dbt_assets()` calls
   but keep `manifest = json.loads(...)` and `dagster_dbt_translator`. Existing
   import paths (`from kipptaf.dbt.assets import manifest`) continue to work
   unchanged. `DBT_PROJECT` is removed from `__init__.py`. When these modules
   are converted to full components in the follow-up, the manifest import goes
   away and `dbt/` can be deleted entirely.
