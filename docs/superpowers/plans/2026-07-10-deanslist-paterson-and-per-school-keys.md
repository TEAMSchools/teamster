# DeansList Paterson and Per-School API Keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure DeansList school API keys into per-school 1Password fields
loaded from a mounted directory, and extend the DeansList integration to
Paterson end-to-end (Dagster ingestion, district dbt, kipptaf unions).

**Architecture:** `DeansListResource` stops parsing a YAML blob and instead
reads one shared, mounted secret directory: the subdomain from a `subdomain`
file and the `{school_id: key}` map from numeric-named files. All four API
districts share this resource, so PR 1 migrates them together and adds Paterson
ingestion. PR 2 wires the dbt side (Paterson district project plus kipptaf
cross-district unions), which depends on Paterson Avro already existing in GCS.

**Tech Stack:** Python 3.13 + Dagster (`ConfigurableResource`), Kubernetes
projected secret volumes via the 1Password Operator, dbt (BigQuery) with
`dbt_utils.union_relations`.

**Spec:**
`docs/superpowers/specs/2026-07-10-deanslist-paterson-and-per-school-keys-design.md`

**Issue:** [#4367](https://github.com/TEAMSchools/teamster/issues/4367)

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/deanslist-paterson` on branch
  `cbini/feat/claude-deanslist-paterson-integration`. Prefix every git call with
  `git -C /workspaces/teamster/.worktrees/deanslist-paterson`. Run `uv`/`pytest`
  and `dbt` from inside the worktree (or pass `--project-dir`).
- **Python:** `requires-python >=3.13`. Always `uv run`; never bare `python`.
  Built-in generics, `X | None`, return-type annotations on resource methods.
- **Trunk:** do not run `trunk fmt`/`check` casually — the pre-commit hook runs
  `fmt`. Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` from **inside
  the worktree** (the binary lives only in the main repo).
- **dbt targets:** `stage_external_sources --target staging` and `--target prod`
  builds are classifier-blocked — **hand them to the user**.
  `dbt parse`/`compile` and `dbt build --target dev` are runnable locally.
- **Mount path:** the DeansList key directory mounts at **`/etc/deanslist`** (a
  dedicated, non-nested volume — chosen over the spec's illustrative
  `/etc/secret-volume/deanslist` to avoid mounting one projected volume inside
  another).
- **PR boundary:** Tasks 1-8 are PR 1 (Python + K8s, no dbt). Tasks 9-11 are PR
  2 (dbt only). Do not mix dbt changes into PR 1.
- **Markdown/YAML/SQL:** fenced blocks need a language (MD040); headings
  increment by one (MD001); backtick identifiers in prose. SQL follows
  `.trunk/config/.sqlfluff` (BigQuery, trailing commas, single quotes, 88 cols).

## Human-gated prerequisites (not code tasks)

These are owner actions in 1Password / the cluster. They gate specific tasks;
the plan notes where.

- **P1 (before PR 1 merges):** In the `DeansList API` 1Password item (vault
  `Data Team`), add one text field per school — label = DeansList `school_id`
  (e.g. `121`), value = that school's API key — for **all** existing districts
  (re-entered from the current YAML blob) **plus Paterson's schools**. Leave the
  existing YAML blob field in place for now.
- **P2 (verify before merging Task 1):** Confirm the numeric fields sync to
  secret keys under their labels:
  `kubectl -n dagster-cloud get secret op-deanslist-api -o jsonpath='{.data}' | jq keys`.
  Expected keys include `subdomain`, `121`, `122`, …. If labels are remapped,
  use the fallback in Task 1's note (`school_id|key` in the value).
- **P3 (after PR 1 deploys and is verified):** Delete the old YAML blob field
  from the `DeansList API` item.
- **P4 (inputs):** Paterson's DeansList `school_id` list (for Task 4) and the
  set of endpoints Paterson pulls (for Tasks 4 and 9-11). Default assumption if
  unspecified: the same core endpoints as Newark (`users`, `terms`, `rosters`,
  `roster-assignments`, `students`, `incidents`, `comm-log`).

---

## PR 1 — Keys plus Paterson ingestion (Python and K8s)

### Task 1: `DeansListResource` loads from a mounted directory

**Files:**

- Modify: `src/teamster/libraries/deanslist/resources.py`
- Test: `tests/resources/test_resource_deanslist.py` (create)

**Interfaces:**

- Produces: `DeansListResource(api_key_dir: str, request_timeout: float = 60.0)`
  — the `subdomain` and `api_key_map` config fields are removed. Module-level
  helper
  `load_deanslist_config(key_dir: pathlib.Path) -> tuple[str, dict[int, str]]`
  returns `(subdomain, api_key_map)`.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

Create `tests/resources/test_resource_deanslist.py`:

```python
import pathlib

from teamster.libraries.deanslist.resources import load_deanslist_config


def test_load_deanslist_config(tmp_path: pathlib.Path):
    (tmp_path / "subdomain").write_text("kippnj\n")
    (tmp_path / "121").write_text("key-121\n")
    (tmp_path / "122").write_text("key-122")
    # projected-secret volumes stage data behind dot-prefixed entries
    (tmp_path / "..data").mkdir()
    (tmp_path / ".hidden").write_text("ignore-me")

    subdomain, api_key_map = load_deanslist_config(tmp_path)

    assert subdomain == "kippnj"
    assert api_key_map == {121: "key-121", 122: "key-122"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run pytest tests/resources/test_resource_deanslist.py -v`
Expected: FAIL with `ImportError` /
`cannot import name 'load_deanslist_config'`.

- [ ] **Step 3: Write the minimal implementation**

In `src/teamster/libraries/deanslist/resources.py`: remove `import yaml`; add
the helper; swap the config fields; rewrite `setup_for_execution`. The full head
of the file becomes:

```python
import pathlib

import fastavro
import fastavro.types
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Session
from requests.exceptions import HTTPError


def load_deanslist_config(
    key_dir: pathlib.Path,
) -> tuple[str, dict[int, str]]:
    subdomain = (key_dir / "subdomain").read_text().strip()

    api_key_map = {
        int(f.name): f.read_text().strip()
        for f in key_dir.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name.isdigit()
    }

    return subdomain, api_key_map


class DeansListResource(ConfigurableResource):
    api_key_dir: str
    request_timeout: float = 60.0

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr()
    _api_key_map: dict = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)

        subdomain, self._api_key_map = load_deanslist_config(
            pathlib.Path(self.api_key_dir)
        )

        self._base_url = f"https://{subdomain}.deanslistsoftware.com/api"
```

Leave `_get_url`, `_request`, `get`, and `list` unchanged (they already read
`self._api_key_map[school_id]`).

> **Fallback (only if P2 shows remapped keys):** change the dict comprehension
> to parse the value instead of the filename — each file's contents are
> `"<school_id>|<key>"`; split on `|`, cast the left side to `int`. Keep the
> `subdomain` read as-is (its key is already proven).

- [ ] **Step 4: Run the test to verify it passes**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run pytest tests/resources/test_resource_deanslist.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/libraries/deanslist/resources.py \
  tests/resources/test_resource_deanslist.py
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "refactor(deanslist): load api keys from mounted directory"
```

### Task 2: Update the shared resource instantiation

**Files:**

- Modify: `src/teamster/core/resources.py:86-90`

**Interfaces:**

- Consumes: `DeansListResource(api_key_dir=...)` from Task 1.

- [ ] **Step 1: Edit the instantiation**

Replace lines 86-90 of `src/teamster/core/resources.py`:

```python
DEANSLIST_RESOURCE = DeansListResource(
    api_key_dir="/etc/deanslist",
    request_timeout=90.0,
)
```

- [ ] **Step 2: Verify the module imports**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run python -c "import teamster.core.resources"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add src/teamster/core/resources.py
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "refactor(deanslist): point shared resource at key directory"
```

### Task 3: Migrate Newark, Camden, and Miami deploy config

Each of the three files has an identical DeansList block. For each district, (a)
move the `op-deanslist-api` secret out of the shared `secret-volume` into its
own `deanslist-keys` volume mounted at `/etc/deanslist`, and (b) remove the
`DEANSLIST_SUBDOMAIN` environment-variable mapping from **both** the
`server_k8s_config` and `run_k8s_config` blocks.

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/dagster-cloud.yaml`
- Modify: `src/teamster/code_locations/kippcamden/dagster-cloud.yaml`
- Modify: `src/teamster/code_locations/kippmiami/dagster-cloud.yaml`

- [ ] **Step 1: Rework the volume block (each district)**

In each file, replace the `volume_mounts:` + `volumes:` block (near the top,
under `k8s:`) so `op-deanslist-api` becomes its own volume. Newark example — the
`op-ps-ssh-kippnewark` source stays; `op-ps-ssh-<district>` differs per
district:

```yaml
volume_mounts:
  - name: secret-volume
    readOnly: true
    mountPath: /etc/secret-volume
  - name: deanslist-keys
    readOnly: true
    mountPath: /etc/deanslist
volumes:
  - name: secret-volume
    projected:
      sources:
        - secret:
            name: op-ps-ssh-kippnewark
            items:
              - key: password
                path: powerschool_ssh_password.txt
  - name: deanslist-keys
    projected:
      sources:
        - secret:
            name: op-deanslist-api
```

Camden uses `op-ps-ssh-kippcamden`; Miami uses `op-ps-ssh-kippmiami`. The
`deanslist-keys` volume is identical in all three (no `items:` — every key
becomes a file).

- [ ] **Step 2: Remove the `DEANSLIST_SUBDOMAIN` env mapping (each district)**

In each file, delete this block from **both** the `server_k8s_config` and
`run_k8s_config` `env:` lists (two occurrences per file):

```yaml
- name: DEANSLIST_SUBDOMAIN
  valueFrom:
    secretKeyRef:
      name: op-deanslist-api
      key: subdomain
```

- [ ] **Step 3: Verify no stray references remain**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && grep -rn "DEANSLIST_SUBDOMAIN\|deanslist_api_key_map" src/teamster/code_locations/kippnewark src/teamster/code_locations/kippcamden src/teamster/code_locations/kippmiami`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/code_locations/kippnewark/dagster-cloud.yaml \
  src/teamster/code_locations/kippcamden/dagster-cloud.yaml \
  src/teamster/code_locations/kippmiami/dagster-cloud.yaml
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "chore(deanslist): mount key directory for nj and miami locations"
```

### Task 4: Create the Paterson DeansList Dagster module

**Files:**

- Create: `src/teamster/code_locations/kipppaterson/deanslist/__init__.py`
- Create: `src/teamster/code_locations/kipppaterson/deanslist/schema.py`
- Create: `src/teamster/code_locations/kipppaterson/deanslist/assets.py`
- Create: `src/teamster/code_locations/kipppaterson/deanslist/schedules.py`
- Create:
  `src/teamster/code_locations/kipppaterson/deanslist/config/static-partition-assets.yaml`
- Create:
  `src/teamster/code_locations/kipppaterson/deanslist/config/multi-partition-monthly-assets.yaml`
- Create:
  `src/teamster/code_locations/kipppaterson/deanslist/config/multi-partition-fiscal-assets.yaml`

**Interfaces:**

- Produces: `assets` (list) and `schedules` (list) exported from the module
  `__init__.py`, consumed by Task 5.
- Consumes: `build_deanslist_*` factories from
  `teamster.libraries.deanslist.assets` and `build_deanslist_job_schedule` from
  `teamster.libraries.deanslist.schedules`.

- [ ] **Step 1: Copy the schema module verbatim**

`kippnewark/deanslist/schema.py` has no code-location-specific code (it only
generates Avro from the shared library models). Copy it unchanged:

```bash
cp /workspaces/teamster/.worktrees/deanslist-paterson/src/teamster/code_locations/kippnewark/deanslist/schema.py \
   /workspaces/teamster/.worktrees/deanslist-paterson/src/teamster/code_locations/kipppaterson/deanslist/schema.py
```

- [ ] **Step 2: Write `config/` files**

Enable only the endpoints Paterson pulls (P4). Using the Newark default set:

`config/static-partition-assets.yaml`:

```yaml
endpoints:
  - endpoint: users
    api_version: v1
    params:
      IncludeInactive: Y
  - endpoint: terms
    api_version: v1
  - endpoint: rosters
    api_version: v1
    params:
      show_inactive: Y
  - endpoint: roster-assignments
    api_version: beta
  - endpoint: students
    api_version: v1
    params:
      IncludeCustomFields: Y
      IncludeUnenrolled: Y
      IncludeParents: Y
```

`config/multi-partition-monthly-assets.yaml`:

```yaml
endpoints:
  - endpoint: incidents
    params:
      IncludeDeleted: Y
      cf: Y
      attachments: Y
```

`config/multi-partition-fiscal-assets.yaml`:

```yaml
endpoints:
  - endpoint: comm-log
    params:
      IncludeSentReports: "yes"
      IncludeTwoWayTexts: "yes"
```

- [ ] **Step 3: Write `assets.py`**

Identical to Newark's except the code-location import and the school-id list.
Replace `PATERSON_SCHOOL_IDS_HERE` with the P4 list (strings):

```python
import pathlib

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.deanslist.schema import (
    ASSET_SCHEMA,
    BEHAVIOR_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_paginated_multi_partition_asset,
    build_deanslist_static_partition_asset,
)

DEANSLIST_STATIC_PARTITIONS_DEF = StaticPartitionsDefinition(
    [PATERSON_SCHOOL_IDS_HERE]
)

DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    partitions_defs={
        "school": DEANSLIST_STATIC_PARTITIONS_DEF,
        "date": FiscalYearPartitionsDefinition(
            start_date="2016-07-01",
            start_month=7,
            timezone=str(LOCAL_TIMEZONE),
            end_offset=1,
        ),
    }
)

config_dir = pathlib.Path(__file__).parent / "config"

static_partitioned_assets = [
    build_deanslist_static_partition_asset(
        code_location=CODE_LOCATION,
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_STATIC_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

month_partitioned_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        api_version="v1",
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "school": DEANSLIST_STATIC_PARTITIONS_DEF,
                "date": MonthlyPartitionsDefinition(
                    start_date="2016-07-01", timezone=str(LOCAL_TIMEZONE), end_offset=1
                ),
            }
        ),
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-monthly-assets.yaml"])[
        "endpoints"
    ]
]

year_partitioned_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        api_version="v1",
        schema=ASSET_SCHEMA[e["endpoint"]],
        partitions_def=DEANSLIST_FISCAL_MULTI_PARTITIONS_DEF,
        **e,
    )
    for e in config_from_files([f"{config_dir}/multi-partition-fiscal-assets.yaml"])[
        "endpoints"
    ]
]

assets = [
    *static_partitioned_assets,
    *month_partitioned_assets,
    *year_partitioned_assets,
]
```

> Note: the Newark `behavior` paginated asset and its midday `comm_log` schedule
> are only needed if Paterson pulls those endpoints. The config above omits
> `behavior`; do not append the paginated asset unless P4 includes it.

- [ ] **Step 4: Write `schedules.py`**

Identical to Newark's, minus the `midday_commlog` schedule (add it back only if
Paterson pulls `comm-log` on that cadence):

```python
from teamster.code_locations.kipppaterson import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kipppaterson.deanslist.assets import (
    month_partitioned_assets,
    static_partitioned_assets,
    year_partitioned_assets,
)
from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

deanslist_static_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__static_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=static_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_month_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__month_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=month_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

deanslist_year_partitioned_assets_job_schedule = build_deanslist_job_schedule(
    schedule_name=f"{CODE_LOCATION}__deanslist__year_partitioned_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=year_partitioned_assets,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

schedules = [
    deanslist_month_partitioned_assets_job_schedule,
    deanslist_static_partitioned_assets_job_schedule,
    deanslist_year_partitioned_assets_job_schedule,
]
```

- [ ] **Step 5: Write `__init__.py`**

```python
from teamster.code_locations.kipppaterson.deanslist.assets import assets
from teamster.code_locations.kipppaterson.deanslist.schedules import schedules

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 6: Verify the module imports**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run python -c "import teamster.code_locations.kipppaterson.deanslist"`
Expected: no output, exit 0. (A `KeyError` on `ASSET_SCHEMA[...]` means a config
endpoint name has no schema entry — fix the config.)

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/code_locations/kipppaterson/deanslist
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "feat(deanslist): add paterson deanslist ingestion module"
```

### Task 5: Wire DeansList into Paterson `definitions.py`

**Files:**

- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`

**Interfaces:**

- Consumes: `deanslist` module (Task 4), `DEANSLIST_RESOURCE` (Task 2).

- [ ] **Step 1: Add the import**

In the `from teamster.code_locations.kipppaterson import (...)` block, add
`deanslist` (alphabetical, after `couchdrop`). In the
`from teamster.core.resources import (...)` block, add `DEANSLIST_RESOURCE`.

- [ ] **Step 2: Register assets, schedules, and the resource**

- Add `deanslist,` to the `load_assets_from_modules(modules=[...])` list.
- Add a `schedules=[*deanslist.schedules],` argument to `Definitions(...)`.
- Add `"deanslist": DEANSLIST_RESOURCE,` to the `resources={...}` dict.

The resulting `Definitions(...)` call:

```python
defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            dbt,
            amplify,
            deanslist,
            finalsite,
            pearson,
            powerschool,
        ]
    ),
    schedules=[
        *deanslist.schedules,
    ],
    sensors=[
        *amplify.sensors,
        *couchdrop.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "ssh_amplify": SSH_RESOURCE_AMPLIFY,
        "ssh_couchdrop": SSH_COUCHDROP,
    },
)
```

- [ ] **Step 2b: Add the file IO manager if the paginated asset is used**

Only if Task 4 kept the `behavior` paginated asset: import
`get_io_manager_gcs_file` and add
`"io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),` to `resources`.
Otherwise skip.

- [ ] **Step 3: Verify the submodule imports**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run python -c "import teamster.code_locations.kipppaterson.deanslist"`
Expected: exit 0. (The full `.definitions` module cannot import in the codespace
— `get_powerschool_ssh_resource()` reads unset env vars — so validate the
submodule, not `definitions`, per `src/teamster/CLAUDE.md`.)

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/code_locations/kipppaterson/definitions.py
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "feat(deanslist): register paterson deanslist assets and schedules"
```

### Task 6: Add the key-directory mount to Paterson deploy config

**Files:**

- Modify: `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml`

- [ ] **Step 1: Add `volume_mounts` and `volumes` under `k8s:`**

Paterson has no volume block today. Insert these two keys directly under
`container_context.k8s:` (as siblings of `server_k8s_config`, before it):

```yaml
container_context:
  k8s:
    volume_mounts:
      - name: deanslist-keys
        readOnly: true
        mountPath: /etc/deanslist
    volumes:
      - name: deanslist-keys
        projected:
          sources:
            - secret:
                name: op-deanslist-api
    server_k8s_config:
```

Do **not** add a `DEANSLIST_SUBDOMAIN` env variable — the subdomain is read from
the mounted `subdomain` file.

- [ ] **Step 2: Verify the YAML parses**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run python -c "import yaml; yaml.safe_load(open('src/teamster/code_locations/kipppaterson/dagster-cloud.yaml'))"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/code_locations/kipppaterson/dagster-cloud.yaml
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "chore(deanslist): mount key directory for paterson location"
```

### Task 7: Update Paterson code-location docs

**Files:**

- Modify: `src/teamster/code_locations/kipppaterson/CLAUDE.md`

- [ ] **Step 1: Add DeansList to Active Integrations**

Add a row to the Active Integrations table:

```markdown
| `deanslist` | API assets | schedule (nightly) |
```

- [ ] **Step 2: Remove DeansList from the "does not use" list**

In the "Critical Difference" consequences list, drop `deanslist` from the line
`No deanslist, edplan, iready, overgrad, renlearn, or titan`.

- [ ] **Step 3: Reconcile the "No Schedules" section**

The doc's "No Asset Checks, No Schedules" heading is now partly false. Change
the heading to "Schedules" and note that DeansList adds nightly data-pull
schedules while all other ingestion remains sensor-driven.

- [ ] **Step 4: Lint and commit**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && /workspaces/teamster/.trunk/tools/trunk check --force src/teamster/code_locations/kipppaterson/CLAUDE.md`

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/teamster/code_locations/kipppaterson/CLAUDE.md
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "docs(deanslist): note paterson deanslist integration"
```

### Task 8: Open PR 1

- [ ] **Step 1: Lint the whole change set**

Run (from inside the worktree):
`/workspaces/teamster/.trunk/tools/trunk check --force $(git -C /workspaces/teamster/.worktrees/deanslist-paterson diff --name-only origin/main)`
Fix anything flagged.

- [ ] **Step 2: Push and open the PR**

Push the branch (the user pushes if the classifier blocks it), then open a PR
with the `.github/pull_request_template.md` body, `Refs #4367`. Note in the PR
description that **P1 must be done and P2 verified before merge, and P3 after
deploy**.

- [ ] **Step 3: Post-merge verification (owner-run)**

After deploy: materialize a sample DeansList partition for Newark, Camden, and
Miami (existing schools) and confirm non-zero rows plus a passing Avro schema
check. Then materialize Paterson's DeansList assets so Avro lands at
`gs://teamster-kipppaterson/dagster/kipppaterson/deanslist/...`. Then do P3.

---

## PR 2 — dbt (Paterson district plus kipptaf unions)

> Prerequisite: PR 1 deployed and Paterson DeansList assets materialized in prod
> (so the external sources stage against real data). Land the two projects
> together via the single-PR cross-project workflow in
> `src/dbt/kipptaf/CLAUDE.md`.

### Task 9: Add the `deanslist` package to the Paterson district project

**Files:**

- Modify: `src/dbt/kipppaterson/packages.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml`
- Modify: `src/dbt/kipppaterson/CLAUDE.md`

**Interfaces:**

- Produces: `kipppaterson_deanslist.stg_deanslist__*` and `int_deanslist__*`
  tables consumed by Task 10.

- [ ] **Step 1: Add the package dependency**

In `src/dbt/kipppaterson/packages.yml`, add under `packages:` (before the
`dbt-labs/dbt_external_tables` entry):

```yaml
- local: ../deanslist
```

- [ ] **Step 2: Configure the package models**

In `src/dbt/kipppaterson/dbt_project.yml`, under the top-level `models:` map (as
a sibling of the existing `pearson:` / `powerschool:` package keys), add.
Disable the staging models for endpoints Paterson does **not** pull (mirror the
Newark pattern, which disables only `stg_deanslist__followups`):

```yaml
deanslist:
  +materialized: table
  staging:
    stg_deanslist__followups:
      +enabled: false
```

- [ ] **Step 3: Install the package and parse**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run dbt deps --project-dir src/dbt/kipppaterson`
then
`uv run dbt parse --target prod --project-dir src/dbt/kipppaterson --target-path target/prod`
Expected: parse succeeds; `deanslist` package models appear in the graph.

- [ ] **Step 4: Stage the external sources (owner-run — classifier-blocked)**

The external tables must be staged before dbt Cloud CI can read them, and
Paterson Avro must already exist (PR 1). The owner runs:
`uv run dbt run-operation stage_external_sources --target staging --project-dir src/dbt/kipppaterson --vars '{ext_full_refresh: true}'`

- [ ] **Step 5: Build the Paterson deanslist models (owner-run against
      staging)**

`uv run dbt build --select deanslist --target staging --project-dir src/dbt/kipppaterson`
Expected: `stg_deanslist__*` / `int_deanslist__*` build and their uniqueness
tests pass.

- [ ] **Step 6: Update the district CLAUDE.md**

In `src/dbt/kipppaterson/CLAUDE.md`, add `deanslist` to "Active Source Packages"
and note which endpoints/models are enabled.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/dbt/kipppaterson/packages.yml \
  src/dbt/kipppaterson/package-lock.yml \
  src/dbt/kipppaterson/dbt_project.yml \
  src/dbt/kipppaterson/CLAUDE.md
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "feat(deanslist): add deanslist package to paterson project"
```

### Task 10: Add Paterson to the kipptaf cross-district unions

**Files:**

- Create: `src/dbt/kipptaf/models/deanslist/api/sources-kipppaterson.yml`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/staging/stg_deanslist__users.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/staging/stg_deanslist__behavior.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/staging/stg_deanslist__terms.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__roster_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__attachments.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__students__custom_fields__pivot.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__comm_log.sql`

- [ ] **Step 1: Create the Paterson source file**

Copy `sources-kippnewark.yml` and rename the district throughout:

```bash
sed 's/kippnewark/kipppaterson/g' \
  /workspaces/teamster/.worktrees/deanslist-paterson/src/dbt/kipptaf/models/deanslist/api/sources-kippnewark.yml \
  > /workspaces/teamster/.worktrees/deanslist-paterson/src/dbt/kipptaf/models/deanslist/api/sources-kipppaterson.yml
```

- [ ] **Step 2: Add the Paterson relation to each union model**

In each of the 9 SQL files above, add a
`source("kipppaterson_deanslist", "<M>")` line to the `relations=[...]` list of
the `dbt_utils.union_relations(...)` call, where `<M>` is that model's unioned
table name (it matches the model file name). Example —
`int_deanslist__comm_log.sql` becomes:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__comm_log"),
                    source("kippcamden_deanslist", "int_deanslist__comm_log"),
                    source("kippmiami_deanslist", "int_deanslist__comm_log"),
                    source("kipppaterson_deanslist", "int_deanslist__comm_log"),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
```

> Only add Paterson to a union whose model Paterson actually builds (Task 9). If
> Paterson omits an endpoint, skip that file and log the omission in the PR.

- [ ] **Step 3: Parse kipptaf**

Run:
`cd /workspaces/teamster/.worktrees/deanslist-paterson && uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod`
Expected: parse succeeds; the new source resolves.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/deanslist-paterson add \
  src/dbt/kipptaf/models/deanslist/api
git -C /workspaces/teamster/.worktrees/deanslist-paterson commit -m \
  "feat(deanslist): union paterson into kipptaf deanslist models"
```

### Task 11: Validate PR 2 and open it

- [ ] **Step 1: Seed staging for CI (single-PR cross-project workflow,
      owner-run)**

Per `src/dbt/kipptaf/CLAUDE.md`: add the `target=staging` branch to
`sources-kipppaterson.yml` if the copied file lacks it (it inherits Newark's dev
branch — confirm it routes to `zz_stg_kipppaterson_deanslist` under staging),
`dbt clone`/`build` the Paterson deanslist models into `zz_stg_kipppaterson_*`,
and clone+build `zz_stg_kipptaf` so kipptaf reads its own union models from
staging.

- [ ] **Step 2: Build the affected kipptaf models (owner-run against staging)**

`uv run dbt build --select +int_deanslist__comm_log +stg_deanslist__users --target staging --project-dir src/dbt/kipptaf`
(extend the selection to every modified union model). Expected: builds pass and
Paterson rows carry a `_dbt_source_project` of `kipppaterson`.

- [ ] **Step 3: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force $(git -C /workspaces/teamster/.worktrees/deanslist-paterson diff --name-only origin/main)`

- [ ] **Step 4: Push and open PR 2**

Push (user pushes if blocked); open the PR with the template body and
`Closes #4367`. Flag that CI needs the staged Paterson tables from Step 1.

---

## Self-Review

**Spec coverage:**

- Part 1 (per-school key fields to a mounted directory) → Tasks 1, 2, 3, 6.
- Part 1 risk (field label vs secret key) → prerequisite P2 + Task 1 fallback
  note.
- Part 2 (Paterson Dagster ingestion) → Tasks 4, 5, 6, 7.
- Part 3 (Paterson district dbt) → Task 9.
- Part 4 (kipptaf cross-district inclusion) → Task 10.
- Rollout / sequencing (two PRs, 1Password bracketing steps) → PR-section split,
  P1/P3, Tasks 8 and 11.
- Testing/validation → Task 1 unit test; import/parse/build checks per task;
  post-merge materialization in Task 8.

**Type consistency:** `DeansListResource(api_key_dir=...)` and
`load_deanslist_config(key_dir) -> tuple[str, dict[int, str]]` are used
identically in Tasks 1 and 2. `assets` / `schedules` exports (Task 4) match the
imports in Task 5.

**Open inputs (P4), not placeholders:** the Paterson `school_id` list (Task 4
Step 3) and the enabled-endpoint set (Tasks 4, 9, 10) are external data the
owner supplies; every task shows the exact shape and the one substitution point.
