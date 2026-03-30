# Component-Based Definitions Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all 5 code locations from manual `Definitions` assembly to
Dagster's component system using `load_from_defs_folder()` +
`TeamsterDbtProjectComponent`.

**Architecture:** Each code location gets a `defs/` package with YAML-configured
dbt components and `@definitions` wrappers for non-dbt integrations.
`definitions.py` becomes a thin merger via `Definitions.merge()`. A custom
`TeamsterDbtProjectComponent` subclass handles external source staging and
per-model automation conditions.

**Tech Stack:** Dagster 1.12.21, `dagster.components`, `dagster-dbt`
`DbtProjectComponent`, `load_from_defs_folder()`, `@definitions` decorator

**Spec:**
[docs/superpowers/specs/2026-03-30-component-based-definitions-design.md](../specs/2026-03-30-component-based-definitions-design.md)

---

## Task 1: Add `[tool.dg]` to `pyproject.toml`

**Files:**

- Modify: `pyproject.toml:51-53`

- [ ] **Step 1: Add the `[tool.dg]` section after `[tool.dagster]`**

In `pyproject.toml`, add the following after line 53
(`project_name = "teamster"`):

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

- [ ] **Step 2: Verify `dg` CLI recognizes the config**

Run: `uv run dg list components 2>&1 | head -20`

Expected: a table listing component types including
`dagster_dbt...DbtProjectComponent`. If it errors about missing
`directory_type`, the TOML section is malformed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add [tool.dg] config for component-based definitions"
```

---

## Task 2: Create `TeamsterDbtProjectComponent`

**Files:**

- Create: `src/teamster/libraries/dbt/components.py`
- Reference (read-only): `src/teamster/libraries/dbt/assets.py` (execute logic
  to port), `src/teamster/libraries/dbt/dagster_dbt_translator.py`
  (get_asset_spec logic to port), `src/teamster/core/automation_conditions.py`
  (automation condition builders)

- [ ] **Step 1: Create the component subclass**

Create `src/teamster/libraries/dbt/components.py`:

```python
import json
import re
from collections.abc import Iterator, Mapping
from typing import Any

import dagster as dg
from dagster_dbt import DbtProject
from dagster_dbt.components.dbt_project.component import DbtProjectComponent

from teamster.core.automation_conditions import (
    dbt_table_automation_condition,
    dbt_union_relations_automation_condition,
    dbt_view_automation_condition,
)


class TeamsterDbtProjectComponent(DbtProjectComponent):
    """DbtProjectComponent with external source staging and custom asset specs."""

    code_location: str

    def get_asset_spec(
        self,
        manifest: Mapping[str, Any],
        unique_id: str,
        project: DbtProject | None,
    ) -> dg.AssetSpec:
        base_spec = super().get_asset_spec(manifest, unique_id, project)
        props = self.get_resource_props(manifest, unique_id)

        # asset key: prefix with code_location unless meta.dagster.asset_key is set
        dbt_meta = props.get("config", {}).get("meta", {}) or props.get("meta", {})
        if not dbt_meta.get("dagster", {}).get("asset_key", []):
            base_spec = base_spec.replace_attributes(
                key=base_spec.key.with_prefix(self.code_location),
            )

        # group name: package_name (cross-project) or fqn[1] (directory)
        group = base_spec.group_name
        if group is None:
            package_name = props["package_name"]
            if package_name is not None and package_name != self.code_location:
                group = package_name
            else:
                group = props["fqn"][1]
            base_spec = base_spec.replace_attributes(group_name=group)

        # tags: add materialized type
        materialized = props.get("config", {}).get("materialized", "view")
        base_spec = base_spec.replace_attributes(
            tags={**base_spec.tags, "dagster/materialized": materialized},
        )

        # automation condition: branch on materialized type
        if materialized == "view" and "union_relations" in props.get(
            "raw_code", ""
        ):
            condition = dbt_union_relations_automation_condition()
        elif materialized in ["view", "ephemeral"]:
            condition = dbt_view_automation_condition()
        else:
            condition = dbt_table_automation_condition()

        base_spec = base_spec.replace_attributes(automation_condition=condition)

        return base_spec

    def execute(
        self,
        context: dg.AssetExecutionContext,
        dbt: dg.DbtCliResource,
    ) -> Iterator:
        manifest = self._validated_manifest
        sources = manifest["sources"]

        # find upstream nodes for selected assets
        selection_depends_on_nodes = [
            node
            for node_props in manifest["nodes"].values()
            for node in node_props["depends_on"]["nodes"]
            if self.get_asset_spec(manifest, node_props["unique_id"], None).key
            in context.selected_asset_keys
        ]

        # filter for external sources
        external_sources = [
            sources[node]
            for node in selection_depends_on_nodes
            if sources.get(node, {}).get("external")
        ]

        if external_sources:
            # stage external sources
            select = " ".join(
                {f"{s['source_name']}.{s['name']}" for s in external_sources}
            )

            stage_result = dbt.cli(
                args=[
                    "run-operation",
                    "stage_external_sources",
                    "--args",
                    json.dumps({"select": select}),
                    "--vars",
                    json.dumps({"ext_full_refresh": "true"}),
                ],
            )

            for event in stage_result.stream_raw_events():
                context.log.info(msg=event)

            # refresh BigLake metadata cache
            relation_names: list[str] = list(
                {
                    s["relation_name"]
                    for s in external_sources
                    if s["external"]["options"].get("connection_name") is not None
                }
            )

            if relation_names:
                refresh_result = dbt.cli(
                    args=[
                        "run-operation",
                        "refresh_external_metadata_cache",
                        "--args",
                        json.dumps({"relation_names": relation_names}),
                    ],
                    raise_on_error=False,
                )

                for event in refresh_result.stream_raw_events():
                    context.log.info(msg=event)

                if error := refresh_result.get_error():
                    if re.search(
                        r"Another metadata cache refresh job with id [\w-]+ "
                        r"is ongoing for table",
                        str(error),
                    ):
                        context.log.warning(msg=str(error))
                    else:
                        raise error

        # delegate to parent for the actual dbt build
        yield from super().execute(context, dbt)
```

**Important**: The `execute()` method's upstream-node lookup calls
`self.get_asset_spec()` to resolve asset keys for comparison against
`context.selected_asset_keys`. This is necessary because the component prefixes
keys with `code_location`, so raw manifest keys won't match. Verify during
testing that this does not cause excessive overhead -- `get_asset_spec()` is
called per node per execution. If it does, cache the key mapping during
`build_defs_from_state()`.

- [ ] **Step 2: Verify the component is discoverable**

Run: `uv run dg list components 2>&1 | grep -i teamster`

Expected: A row showing
`teamster.libraries.dbt.components.TeamsterDbtProjectComponent`.

- [ ] **Step 3: Commit**

```bash
git add src/teamster/libraries/dbt/components.py
git commit -m "feat: add TeamsterDbtProjectComponent subclass"
```

---

## Task 3: Migrate kipppaterson (prototype)

**Files:**

- Create: `src/teamster/code_locations/kipppaterson/defs/__init__.py`
- Create: `src/teamster/code_locations/kipppaterson/defs/defs.yaml`
- Create: `src/teamster/code_locations/kipppaterson/defs/dbt/defs.yaml`
- Create: `src/teamster/code_locations/kipppaterson/defs/amplify.py`
- Create: `src/teamster/code_locations/kipppaterson/defs/finalsite.py`
- Create: `src/teamster/code_locations/kipppaterson/defs/pearson.py`
- Create: `src/teamster/code_locations/kipppaterson/defs/powerschool.py`
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`
- Modify: `src/teamster/code_locations/kipppaterson/__init__.py:12`

- [ ] **Step 1: Create `defs/__init__.py`**

Create an empty file at
`src/teamster/code_locations/kipppaterson/defs/__init__.py`.

- [ ] **Step 2: Create `defs/defs.yaml`**

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kipppaterson
```

- [ ] **Step 3: Create `defs/dbt/defs.yaml`**

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

- [ ] **Step 4: Create `@definitions` wrapper files**

Each wrapper imports assets from the existing module. Create these 4 files:

`src/teamster/code_locations/kipppaterson/defs/amplify.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipppaterson import amplify


@definitions
def defs():
    return Definitions(assets=amplify.assets)
```

`src/teamster/code_locations/kipppaterson/defs/finalsite.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipppaterson import finalsite


@definitions
def defs():
    return Definitions(assets=finalsite.assets)
```

`src/teamster/code_locations/kipppaterson/defs/pearson.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipppaterson import pearson


@definitions
def defs():
    return Definitions(assets=pearson.assets)
```

`src/teamster/code_locations/kipppaterson/defs/powerschool.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipppaterson import powerschool


@definitions
def defs():
    return Definitions(assets=powerschool.assets)
```

Note: `couchdrop` has no assets (sensors only) -- no wrapper needed.

- [ ] **Step 5: Remove `DBT_PROJECT` from `__init__.py`**

In `src/teamster/code_locations/kipppaterson/__init__.py`, remove the
`from dagster_dbt import DbtProject` import (line 4) and the
`DBT_PROJECT = DbtProject(...)` line (line 12). The file should become:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kipppaterson"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")

CURRENT_FISCAL_YEAR = FiscalYear(datetime=datetime.now(LOCAL_TIMEZONE), start_month=7)
```

- [ ] **Step 6: Rewrite `definitions.py`**

Replace the entire contents of
`src/teamster/code_locations/kipppaterson/definitions.py`:

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

- [ ] **Step 7: Validate**

Run:

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipppaterson.definitions
```

Expected:
`Validation successful for code location teamster.code_locations.kipppaterson.definitions`

If validation fails, check error messages -- common issues: duplicate asset keys
(component + old module both loading), missing resource keys, YAML parse errors.

- [ ] **Step 8: Run existing tests**

Run:
`uv run pytest tests/test_dagster_definitions.py::test_definitions_kipppaterson -v`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -u
git add src/teamster/code_locations/kipppaterson/defs/
git commit -m "feat(kipppaterson): migrate to component-based definitions"
```

---

## Task 4: Migrate kippcamden

**Files:**

- Create: `src/teamster/code_locations/kippcamden/defs/__init__.py`
- Create: `src/teamster/code_locations/kippcamden/defs/defs.yaml`
- Create: `src/teamster/code_locations/kippcamden/defs/dbt/defs.yaml`
- Create wrappers: `deanslist.py`, `edplan.py`, `extracts.py`, `finalsite.py`,
  `overgrad.py`, `pearson.py`, `powerschool.py`, `titan.py`
- Modify: `src/teamster/code_locations/kippcamden/definitions.py`
- Modify: `src/teamster/code_locations/kippcamden/__init__.py`

- [ ] **Step 1: Create `defs/` structure**

Create `defs/__init__.py` (empty).

Create `defs/defs.yaml`:

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kippcamden
```

Create `defs/dbt/defs.yaml`:

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kippcamden"
  code_location: kippcamden
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

- [ ] **Step 2: Create `@definitions` wrappers**

Create one wrapper per asset-producing module (same pattern as kipppaterson):

```python
from dagster import Definitions, definitions

from teamster.code_locations.kippcamden import <module>


@definitions
def defs():
    return Definitions(assets=<module>.assets)
```

Create files for: `deanslist.py`, `edplan.py`, `extracts.py`, `finalsite.py`,
`overgrad.py`, `pearson.py`, `powerschool.py`, `titan.py`.

Note: `couchdrop` and `asset_checks` have no assets -- they stay in
`definitions.py` only.

- [ ] **Step 3: Remove `DBT_PROJECT` from `__init__.py`**

Remove the `from dagster_dbt import DbtProject` import and the
`DBT_PROJECT = DbtProject(...)` line.

- [ ] **Step 4: Rewrite `definitions.py`**

```python
from pathlib import Path

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
)
from dagster.components import load_from_defs_folder
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    asset_checks,
    couchdrop,
    deanslist,
    edplan,
    extracts,
    overgrad,
    powerschool,
    titan,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    OVERGRAD_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_TITAN,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_powerschool_ssh_resource,
)

component_defs = load_from_defs_folder(
    path_within_project=Path(
        "src/teamster/code_locations/kippcamden/defs"
    ),
)

defs = Definitions.merge(
    component_defs,
    Definitions(
        executor=k8s_job_executor,
        asset_checks=asset_checks.freshness_checks,
        schedules=[
            *extracts.schedules,
            *deanslist.schedules,
            *overgrad.schedules,
            *powerschool.schedules,
        ],
        sensors=[
            *couchdrop.sensors,
            *edplan.sensors,
            *powerschool.sensors,
            *titan.sensors,
            AutomationConditionSensorDefinition(
                name=f"{CODE_LOCATION}__automation_condition_sensor",
                target=AssetSelection.all(),
            ),
        ],
        resources={
            "db_bigquery": BIGQUERY_RESOURCE,
            "db_powerschool": DB_POWERSCHOOL,
            "deanslist": DEANSLIST_RESOURCE,
            "gcs": GCS_RESOURCE,
            "google_drive": GOOGLE_DRIVE_RESOURCE,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
            "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
            "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
            "overgrad": OVERGRAD_RESOURCE,
            "ssh_couchdrop": SSH_COUCHDROP,
            "ssh_edplan": SSH_EDPLAN,
            "ssh_powerschool": get_powerschool_ssh_resource(),
            "ssh_titan": SSH_TITAN,
        },
    ),
)
```

- [ ] **Step 5: Validate and test**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kippcamden.definitions
uv run pytest tests/test_dagster_definitions.py::test_definitions_kippcamden -v
```

Expected: Both pass.

- [ ] **Step 6: Commit**

```bash
git add -u
git add src/teamster/code_locations/kippcamden/defs/
git commit -m "feat(kippcamden): migrate to component-based definitions"
```

---

## Task 5: Migrate kippnewark

**Files:**

- Create: `src/teamster/code_locations/kippnewark/defs/__init__.py`
- Create: `src/teamster/code_locations/kippnewark/defs/defs.yaml`
- Create: `src/teamster/code_locations/kippnewark/defs/dbt/defs.yaml`
- Create wrappers: `amplify.py`, `deanslist.py`, `edplan.py`, `extracts.py`,
  `finalsite.py`, `iready.py`, `overgrad.py`, `pearson.py`, `powerschool.py`,
  `renlearn.py`, `titan.py`
- Modify: `src/teamster/code_locations/kippnewark/definitions.py`
- Modify: `src/teamster/code_locations/kippnewark/__init__.py`

- [ ] **Step 1: Create `defs/` structure**

Create `defs/__init__.py` (empty).

Create `defs/defs.yaml`:

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kippnewark
```

Create `defs/dbt/defs.yaml`:

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kippnewark"
  code_location: kippnewark
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

- [ ] **Step 2: Create `@definitions` wrappers**

Create wrappers for: `amplify.py`, `deanslist.py`, `edplan.py`, `extracts.py`,
`finalsite.py`, `iready.py`, `overgrad.py`, `pearson.py`, `powerschool.py`,
`renlearn.py`, `titan.py`.

Note: `couchdrop` and `asset_checks` stay in `definitions.py` only.

- [ ] **Step 3: Remove `DBT_PROJECT` from `__init__.py`**

Same pattern as previous locations.

- [ ] **Step 4: Rewrite `definitions.py`**

```python
from pathlib import Path

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
)
from dagster.components import load_from_defs_folder
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    amplify,
    asset_checks,
    couchdrop,
    deanslist,
    edplan,
    extracts,
    iready,
    overgrad,
    powerschool,
    renlearn,
    titan,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    OVERGRAD_RESOURCE,
    SSH_COUCHDROP,
    SSH_EDPLAN,
    SSH_IREADY,
    SSH_RENLEARN,
    SSH_RESOURCE_AMPLIFY,
    SSH_TITAN,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_powerschool_ssh_resource,
)

component_defs = load_from_defs_folder(
    path_within_project=Path(
        "src/teamster/code_locations/kippnewark/defs"
    ),
)

defs = Definitions.merge(
    component_defs,
    Definitions(
        executor=k8s_job_executor,
        asset_checks=asset_checks.freshness_checks,
        schedules=[
            *extracts.schedules,
            *deanslist.schedules,
            *overgrad.schedules,
            *powerschool.schedules,
        ],
        sensors=[
            *amplify.sensors,
            *couchdrop.sensors,
            *edplan.sensors,
            *iready.sensors,
            *powerschool.sensors,
            *renlearn.sensors,
            *titan.sensors,
            AutomationConditionSensorDefinition(
                name=f"{CODE_LOCATION}__automation_condition_sensor",
                target=AssetSelection.all(),
            ),
        ],
        resources={
            "db_bigquery": BIGQUERY_RESOURCE,
            "db_powerschool": DB_POWERSCHOOL,
            "deanslist": DEANSLIST_RESOURCE,
            "gcs": GCS_RESOURCE,
            "google_drive": GOOGLE_DRIVE_RESOURCE,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
            "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
            "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
            "overgrad": OVERGRAD_RESOURCE,
            "ssh_amplify": SSH_RESOURCE_AMPLIFY,
            "ssh_couchdrop": SSH_COUCHDROP,
            "ssh_edplan": SSH_EDPLAN,
            "ssh_iready": SSH_IREADY,
            "ssh_powerschool": get_powerschool_ssh_resource(),
            "ssh_renlearn": SSH_RENLEARN,
            "ssh_titan": SSH_TITAN,
        },
    ),
)
```

- [ ] **Step 5: Validate and test**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kippnewark.definitions
uv run pytest tests/test_dagster_definitions.py::test_definitions_kippnewark -v
```

- [ ] **Step 6: Commit**

```bash
git add -u
git add src/teamster/code_locations/kippnewark/defs/
git commit -m "feat(kippnewark): migrate to component-based definitions"
```

---

## Task 6: Migrate kippmiami

**Files:**

- Create: `src/teamster/code_locations/kippmiami/defs/__init__.py`
- Create: `src/teamster/code_locations/kippmiami/defs/defs.yaml`
- Create: `src/teamster/code_locations/kippmiami/defs/dbt/defs.yaml`
- Create wrappers: `deanslist.py`, `extracts.py`, `finalsite.py`, `fldoe.py`,
  `iready.py`, `powerschool.py`, `renlearn.py`
- Modify: `src/teamster/code_locations/kippmiami/definitions.py`
- Modify: `src/teamster/code_locations/kippmiami/__init__.py`

- [ ] **Step 1: Create `defs/` structure**

Create `defs/__init__.py` (empty).

Create `defs/defs.yaml`:

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kippmiami
```

Create `defs/dbt/defs.yaml`:

```yaml
type: teamster.libraries.dbt.components.TeamsterDbtProjectComponent

attributes:
  project: "{{ context.project_root }}/src/dbt/kippmiami"
  code_location: kippmiami
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

- [ ] **Step 2: Create `@definitions` wrappers**

Create wrappers for: `deanslist.py`, `extracts.py`, `finalsite.py`, `fldoe.py`,
`iready.py`, `powerschool.py`, `renlearn.py`.

Note: `couchdrop` stays in `definitions.py` only (sensors only, no assets).
kippmiami has no `asset_checks`.

- [ ] **Step 3: Remove `DBT_PROJECT` from `__init__.py`**

Same pattern as previous locations.

- [ ] **Step 4: Rewrite `definitions.py`**

```python
from pathlib import Path

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
)
from dagster.components import load_from_defs_folder
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippmiami import (
    CODE_LOCATION,
    couchdrop,
    deanslist,
    extracts,
    iready,
    powerschool,
    renlearn,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_IREADY,
    SSH_RENLEARN,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
    get_powerschool_ssh_resource,
)

component_defs = load_from_defs_folder(
    path_within_project=Path(
        "src/teamster/code_locations/kippmiami/defs"
    ),
)

defs = Definitions.merge(
    component_defs,
    Definitions(
        executor=k8s_job_executor,
        schedules=[
            *extracts.schedules,
            *deanslist.schedules,
            *powerschool.schedules,
        ],
        sensors=[
            *couchdrop.sensors,
            *iready.sensors,
            *powerschool.sensors,
            *renlearn.sensors,
            AutomationConditionSensorDefinition(
                name=f"{CODE_LOCATION}__automation_condition_sensor",
                target=AssetSelection.all(),
            ),
        ],
        resources={
            "db_bigquery": BIGQUERY_RESOURCE,
            "db_powerschool": DB_POWERSCHOOL,
            "deanslist": DEANSLIST_RESOURCE,
            "gcs": GCS_RESOURCE,
            "google_drive": GOOGLE_DRIVE_RESOURCE,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
            "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
            "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
            "ssh_couchdrop": SSH_COUCHDROP,
            "ssh_iready": SSH_IREADY,
            "ssh_powerschool": get_powerschool_ssh_resource(),
            "ssh_renlearn": SSH_RENLEARN,
        },
    ),
)
```

- [ ] **Step 5: Validate and test**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kippmiami.definitions
uv run pytest tests/test_dagster_definitions.py::test_definitions_kippmiami -v
```

- [ ] **Step 6: Commit**

```bash
git add -u
git add src/teamster/code_locations/kippmiami/defs/
git commit -m "feat(kippmiami): migrate to component-based definitions"
```

---

## Task 7: Migrate kipptaf

This is the most complex location -- 22 modules, multi-split dbt, manifest-
dependent modules.

**Files:**

- Create: `src/teamster/code_locations/kipptaf/defs/__init__.py`
- Create: `src/teamster/code_locations/kipptaf/defs/defs.yaml`
- Create: `src/teamster/code_locations/kipptaf/defs/dbt/defs.yaml`
- Create: `src/teamster/code_locations/kipptaf/defs/dbt/core/defs.yaml`
- Create: `src/teamster/code_locations/kipptaf/defs/dbt/google_sheets/defs.yaml`
- Create: `src/teamster/code_locations/kipptaf/defs/dbt_adp_payroll.py`
- Create: `src/teamster/code_locations/kipptaf/defs/exposures.py`
- Create wrappers: `adp.py`, `airbyte.py`, `collegeboard.py`, `coupa.py`,
  `deanslist.py`, `dlt.py`, `extracts.py`, `google.py`, `knowbe4.py`, `ldap.py`,
  `level_data.py`, `nsc.py`, `overgrad.py`, `performance_management.py`,
  `powerschool.py`, `smartrecruiters.py`, `tableau.py`, `zendesk.py`
- Modify: `src/teamster/code_locations/kipptaf/dbt/assets.py`
- Modify: `src/teamster/code_locations/kipptaf/definitions.py`
- Modify: `src/teamster/code_locations/kipptaf/__init__.py`

- [ ] **Step 1: Create `defs/` root structure**

Create `defs/__init__.py` (empty).

Create `defs/defs.yaml`:

```yaml
type: dagster.DefsFolderComponent
post_processing:
  assets:
    - target: "*"
      attributes:
        tags:
          dagster/code_location: kipptaf
```

- [ ] **Step 2: Create dbt component hierarchy**

Create `defs/dbt/defs.yaml` (parent folder, recurses into children):

```yaml
type: dagster.DefsFolderComponent
```

Create `defs/dbt/core/defs.yaml`:

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

Create `defs/dbt/google_sheets/defs.yaml`:

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

- [ ] **Step 3: Create `dbt_adp_payroll.py` wrapper**

This split needs a dynamic `partitions_def` that cannot be expressed in YAML.
Create `src/teamster/code_locations/kipptaf/defs/dbt_adp_payroll.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf import dbt


@definitions
def defs():
    return Definitions(assets=[dbt.adp_payroll_dbt_assets])
```

- [ ] **Step 4: Create `exposures.py` wrapper**

Create `src/teamster/code_locations/kipptaf/defs/exposures.py`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf import dbt


@definitions
def defs():
    return Definitions(assets=dbt.asset_specs)
```

- [ ] **Step 5: Create `@definitions` wrappers for non-dbt modules**

Create wrappers for all asset-producing modules. Each follows the pattern:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf import <module>


@definitions
def defs():
    return Definitions(assets=<module>.assets)
```

Create files for: `adp.py`, `collegeboard.py`, `coupa.py`, `deanslist.py`,
`dlt.py`, `extracts.py`, `knowbe4.py`, `ldap.py`, `level_data.py`, `nsc.py`,
`overgrad.py`, `performance_management.py`, `powerschool.py`,
`smartrecruiters.py`, `tableau.py`, `zendesk.py`.

Special wrappers:

`defs/google.py` -- has both `assets` and `asset_specs`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf import google


@definitions
def defs():
    return Definitions(assets=[*google.assets, *google.asset_specs])
```

`defs/airbyte.py` -- has `asset_specs` not `assets`:

```python
from dagster import Definitions, definitions

from teamster.code_locations.kipptaf import airbyte


@definitions
def defs():
    return Definitions(assets=airbyte.asset_specs)
```

Note: `couchdrop` and `surveys` have no assets -- they stay in `definitions.py`
only (sensors and schedules respectively).

- [ ] **Step 6: Strip `dbt/assets.py` to manifest-only stub**

Rewrite `src/teamster/code_locations/kipptaf/dbt/assets.py` to keep only what
manifest-dependent modules and the adp_payroll wrapper need:

```python
import json

from dagster import AssetSpec
from dagster_dbt import DbtProject

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.dbt.assets import build_dbt_assets
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

DBT_PROJECT = DbtProject(project_dir=f"src/dbt/{CODE_LOCATION}")

manifest = json.loads(s=DBT_PROJECT.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

# partitioned -- cannot be expressed in YAML, stays as Python
adp_payroll_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets__adp_payroll",
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    select="source:adp_payroll+",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {
                    "requests": {"cpu": "500m"},
                    "limits": {"cpu": "1250m"},
                }
            }
        }
    },
)

# non-Tableau exposure specs (read by defs/exposures.py)
asset_specs = [
    AssetSpec(
        key=[CODE_LOCATION, "dbt", "exposures", exposure["label"]],
        deps=[
            dagster_dbt_translator.get_asset_key(
                next(
                    node
                    for node in manifest["nodes"].values()
                    if node["name"] == ref["name"]
                )
            )
            for ref in exposure["refs"]
        ],
        metadata={"url": exposure.get("url")},
        kinds=set(exposure["config"]["meta"]["dagster"]["kinds"]),
    )
    for exposure in manifest["exposures"].values()
    if "tableau" not in exposure["config"]["meta"]["dagster"]["kinds"]
]

assets = [adp_payroll_dbt_assets]
```

Note: `DBT_PROJECT` moves from `__init__.py` to `dbt/assets.py`. The `manifest`
and `dagster_dbt_translator` remain so that `google/sheets/assets.py`,
`google/appsheet/assets.py`, and `tableau/assets.py` continue importing them
unchanged. The `core_dbt_assets` and `google_sheet_dbt_assets` are removed --
those are now handled by the YAML components.

- [ ] **Step 7: Remove `DBT_PROJECT` from `__init__.py`**

In `src/teamster/code_locations/kipptaf/__init__.py`, remove the
`from dagster_dbt import DbtProject` import and the `DBT_PROJECT` line.

- [ ] **Step 8: Rewrite `definitions.py`**

```python
from pathlib import Path

from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
)
from dagster.components import load_from_defs_folder
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kipptaf import (
    CODE_LOCATION,
    adp,
    airbyte,
    asset_checks,
    coupa,
    couchdrop,
    deanslist,
    dlt,
    extracts,
    google,
    knowbe4,
    ldap,
    level_data,
    powerschool,
    resources,
    smartrecruiters,
    surveys,
    tableau,
    zendesk,
)
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DLT_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    GOOGLE_FORMS_RESOURCE,
    GOOGLE_SHEETS_RESOURCE,
    OVERGRAD_RESOURCE,
    SSH_COUCHDROP,
    ZENDESK_RESOURCE,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
)

component_defs = load_from_defs_folder(
    path_within_project=Path(
        "src/teamster/code_locations/kipptaf/defs"
    ),
)

defs = Definitions.merge(
    component_defs,
    Definitions(
        executor=k8s_job_executor,
        asset_checks=asset_checks.freshness_checks,
        schedules=[
            *dlt.schedules,
            *google.schedules,
            *adp.schedules,
            *airbyte.schedules,
            *coupa.schedules,
            *extracts.schedules,
            *knowbe4.schedules,
            *ldap.schedules,
            *level_data.schedules,
            *powerschool.schedules,
            *smartrecruiters.schedules,
            *surveys.schedules,
            *tableau.schedules,
            *zendesk.schedules,
        ],
        sensors=[
            *google.sensors,
            *adp.sensors,
            *couchdrop.sensors,
            *deanslist.sensors,
            AutomationConditionSensorDefinition(
                name=f"{CODE_LOCATION}__automation_condition_sensor",
                target=AssetSelection.all(),
            ),
        ],
        resources={
            "adp_wfn": resources.ADP_WORKFORCE_NOW_RESOURCE,
            "airbyte": resources.AIRBYTE_CLOUD_RESOURCE,
            "coupa": resources.COUPA_RESOURCE,
            "db_bigquery": BIGQUERY_RESOURCE,
            "dlt": DLT_RESOURCE,
            "email": resources.OUTLOOK_RESOURCE,
            "gcs": GCS_RESOURCE,
            "google_directory": resources.GOOGLE_DIRECTORY_RESOURCE,
            "google_drive": GOOGLE_DRIVE_RESOURCE,
            "google_forms": GOOGLE_FORMS_RESOURCE,
            "grow": resources.GROW_RESOURCE,
            "gsheets": GOOGLE_SHEETS_RESOURCE,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
            "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
            "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
            "knowbe4": resources.KNOWBE4_RESOURCE,
            "ldap": resources.LDAP_RESOURCE,
            "overgrad": OVERGRAD_RESOURCE,
            "ps_enrollment": resources.POWERSCHOOL_ENROLLMENT_RESOURCE,
            "smartrecruiters": resources.SMARTRECRUITERS_RESOURCE,
            "ssh_adp_workforce_now": resources.SSH_RESOURCE_ADP_WORKFORCE_NOW,
            "ssh_clever": resources.SSH_RESOURCE_CLEVER,
            "ssh_couchdrop": SSH_COUCHDROP,
            "ssh_coupa": resources.SSH_RESOURCE_COUPA,
            "ssh_deanslist": resources.SSH_RESOURCE_DEANSLIST,
            "ssh_egencia": resources.SSH_RESOURCE_EGENCIA,
            "ssh_idauto": resources.SSH_RESOURCE_IDAUTO,
            "ssh_illuminate": resources.SSH_RESOURCE_ILLUMINATE,
            "ssh_littlesis": resources.SSH_RESOURCE_LITTLESIS,
            "tableau": resources.TABLEAU_SERVER_RESOURCE,
            "zendesk": ZENDESK_RESOURCE,
        },
    ),
)
```

- [ ] **Step 9: Validate and test**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipptaf.definitions
uv run pytest tests/test_dagster_definitions.py::test_definitions_kipptaf -v
```

- [ ] **Step 10: Commit**

```bash
git add -u
git add src/teamster/code_locations/kipptaf/defs/
git commit -m "feat(kipptaf): migrate to component-based definitions"
```

---

## Task 8: Full validation and cleanup

- [ ] **Step 1: Run all definitions tests**

```bash
uv run pytest tests/test_dagster_definitions.py -v
```

Expected: All 6 tests pass (5 individual + 1 combined).

- [ ] **Step 2: Remove unused `dbt/` directories from non-kipptaf locations**

Delete these files (they are no longer imported by anything):

- `src/teamster/code_locations/kipppaterson/dbt/assets.py`
- `src/teamster/code_locations/kippcamden/dbt/assets.py`
- `src/teamster/code_locations/kippnewark/dbt/assets.py`
- `src/teamster/code_locations/kippmiami/dbt/assets.py`

Verify nothing imports from them:

```bash
uv run python -c "
from teamster.code_locations.kipppaterson.definitions import defs
from teamster.code_locations.kippcamden.definitions import defs
from teamster.code_locations.kippnewark.definitions import defs
from teamster.code_locations.kippmiami.definitions import defs
print('All imports OK')
"
```

- [ ] **Step 3: Re-run full test suite**

```bash
uv run pytest tests/test_dagster_definitions.py -v
```

Expected: All pass.

- [ ] **Step 4: Commit cleanup**

```bash
git add -u
git commit -m "chore: remove unused dbt/assets.py from migrated code locations"
```

---

## Task 9: Update CLAUDE.md files

- [ ] **Step 1: Update `src/teamster/libraries/dbt/CLAUDE.md`**

Add a section documenting `components.py` and `TeamsterDbtProjectComponent`.
Note that `assets.py` and `dagster_dbt_translator.py` are superseded but kept
for kipptaf's manifest-dependent modules.

- [ ] **Step 2: Update `src/teamster/CLAUDE.md`**

Update the "Code Location Structure" section to reflect the new `defs/` package
pattern and `load_from_defs_folder()` approach.

- [ ] **Step 3: Update code location CLAUDE.md files**

For each of the 5 code locations, update the CLAUDE.md to mention the `defs/`
package and the component-based definitions pattern.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "docs: update CLAUDE.md files for component-based definitions"
```
