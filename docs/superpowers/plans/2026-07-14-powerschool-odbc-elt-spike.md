# PowerSchool ODBC ELT Spike (dlt vs Sling) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run dlt and Sling head-to-head against Paterson's PowerSchool Oracle
instance (via SSH tunnel, landing in BigQuery) on three tables, fill in the
rubric from the spec, and decide which tool the network-wide pilot uses.

**Architecture:** Throwaway spike assets live in
`code_locations/kipppaterson/powerschool/sis/odbc_spike/` and run on a **branch
deployment** (the Codespace cannot reach the PowerSchool SSH host). dlt assets
wrap the existing `SSHResource.open_ssh_tunnel()` around a `sql_table` source;
Sling assets use Sling's native `ssh_tunnel` connection property. Each tool
writes to its own scratch dataset. Spike code is reverted before the PR merges —
only docs (spec, plan, results) land on `main`.

**Tech Stack:** dlt (`sql_database`/`sql_table`, `oracledb` thin dialect,
pyarrow backend), `dagster-dlt`, Sling CLI (free tier) via `dagster-sling`,
BigQuery, GKE branch deployment.

**Spec:**
`docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-design.md` (issue
[#4398](https://github.com/TEAMSchools/teamster/issues/4398), branch
`cbini/research/claude-powerschool-odbc-elt-spike`)

## Global Constraints

- **SSH tunnel is mandatory** for all Oracle connectivity (password auth, like
  Newark/Camden).
- **Spike code never merges.** Tasks 2–5 are reverted in Task 11; only
  `docs/superpowers/**` changes merge.
- **Test tables:** `students`, `storedgrades`, `assignmentscore` (exactly these
  three).
- **Scratch datasets:** `zz_spike_powerschool_dlt` and
  `zz_spike_powerschool_sling` in project `teamster-332318`.
- **Asset keys:** `kipppaterson/powerschool/spike/dlt/{table}` and
  `kipppaterson/powerschool/spike/sling/{table}`.
- **Sling free tier only** — no `SLING_STATE`, no parallel streams.
- All work happens in the worktree
  `.worktrees/cbini/research/claude-powerschool-odbc-elt-spike/` — use
  `git -C <worktree>` for git and worktree-absolute paths for edits.
- Python conventions: `uv run` only; `>=3.13` syntax; import-safe modules (no
  hard env-var reads at import time — use `os.getenv(..., "")` defaults so the
  Codespace can import the module without PowerSchool credentials).
- PII: run results (row counts, types, timings) are fine to publish; never paste
  student-level row values into the results doc, issues, or PR comments.

---

### Task 1: Confirm Paterson PowerSchool secrets exist (user gate)

**Files:** none (infrastructure prerequisite)

**Interfaces:**

- Produces: Kubernetes secrets `op-ps-db-kipppaterson` (keys: `server`,
  `database`, `port`, `username`, `password`) and `op-ps-ssh-kipppaterson`
  (keys: `host`, `port`, `username`, `remote-bind-host`, `password`) in the
  `dagster-cloud` namespace — the exact shape `op-ps-db-kippnewark` /
  `op-ps-ssh-kippnewark` have today.

- [ ] **Step 1: Ask the user to confirm/create the secrets**

The kippnewark pattern (from
`src/teamster/code_locations/kippnewark/dagster-cloud.yaml`) sources DB
credentials from `op-ps-db-kippnewark` and SSH credentials from
`op-ps-ssh-kippnewark`; these are 1Password-operator-managed secrets. Ask the
user (they may need Ops):

> Do `op-ps-db-kipppaterson` and `op-ps-ssh-kipppaterson` exist in the
> `dagster-cloud` namespace with the same keys as the kippnewark equivalents? If
> not, please create the 1Password items so the operator syncs them. The SSH
> secret must include a `password` key (used both as a mounted file for the
> dlt-side tunnel and as an environment variable for Sling's tunnel URL).

**Do not proceed to Task 3 until the user confirms.** Tasks 2 can proceed in
parallel with the wait.

- [ ] **Step 2: Record the confirmed secret names in the results doc skeleton**

No commit; this is a checkpoint.

---

### Task 2: Add `dagster-sling` dependency

**Files:**

- Modify: `pyproject.toml` (dependencies array)
- Modify: `uv.lock` (regenerated)

**Interfaces:**

- Produces: importable `dagster_sling` package (provides `sling_assets`,
  `SlingResource`, `SlingConnectionResource`, `DagsterSlingTranslator`) and the
  `sling` Python package, which vendors the platform Sling binary into the
  Docker image (hermetic — no runtime binary download).

- [ ] **Step 1: Add the dependency**

Run from inside the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike
uv add dagster-sling
```

Expected: `pyproject.toml` gains `"dagster-sling"` in `[project.dependencies]`
and `uv.lock` updates, pulling `sling` as a transitive dependency.

- [ ] **Step 2: Verify the import and binary**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run python -c "
from dagster_sling import SlingResource, SlingConnectionResource, sling_assets, DagsterSlingTranslator
from sling import Sling
print('ok')
"
```

Expected: `ok`. If `from sling import Sling` fails, inspect what the `sling`
distribution actually exposes
(`uv run python -c "import sling; print(sling.__file__)"`) — the import that
matters is `dagster_sling`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add pyproject.toml uv.lock
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "build(spike): add dagster-sling for powerschool odbc spike

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire Paterson PowerSchool credentials into `dagster-cloud.yaml`

**Files:**

- Modify: `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml`

**Interfaces:**

- Consumes: secrets confirmed in Task 1.
- Produces: environment variables `PS_DB_USERNAME`, `PS_DB_PASSWORD`,
  `PS_DB_HOST`, `PS_DB_PORT`, `PS_DB_DATABASE`, `PS_SSH_HOST`, `PS_SSH_PORT`,
  `PS_SSH_USERNAME`, `PS_SSH_PASSWORD`, `PS_SSH_REMOTE_BIND_HOST` plus the
  mounted file `/etc/secret-volume/powerschool_ssh_password.txt` in both server
  and run pods of the kipppaterson location. Tasks 4–5 read these.

- [ ] **Step 1: Add the secret volume**

In `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml`, extend
`container_context.k8s.volume_mounts` and `volumes` (kippnewark is the
template):

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
            name: op-ps-ssh-kipppaterson
            items:
              - key: password
                path: powerschool_ssh_password.txt
  - name: deanslist-keys
    projected:
      sources:
        - secret:
            name: op-deanslist-api-kipppaterson
```

- [ ] **Step 2: Add the environment variables to BOTH `server_k8s_config` and
      `run_k8s_config`**

Append to each `container_config.env` list (all ten entries, in both sections —
run pods execute the assets, server pods import the definitions):

```yaml
- name: PS_DB_USERNAME
  valueFrom:
    secretKeyRef:
      name: op-ps-db-kipppaterson
      key: username
- name: PS_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: op-ps-db-kipppaterson
      key: password
- name: PS_DB_HOST
  valueFrom:
    secretKeyRef:
      name: op-ps-db-kipppaterson
      key: server
- name: PS_DB_PORT
  valueFrom:
    secretKeyRef:
      name: op-ps-db-kipppaterson
      key: port
- name: PS_DB_DATABASE
  valueFrom:
    secretKeyRef:
      name: op-ps-db-kipppaterson
      key: database
- name: PS_SSH_HOST
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-kipppaterson
      key: host
- name: PS_SSH_PORT
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-kipppaterson
      key: port
- name: PS_SSH_USERNAME
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-kipppaterson
      key: username
- name: PS_SSH_PASSWORD
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-kipppaterson
      key: password
- name: PS_SSH_REMOTE_BIND_HOST
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-kipppaterson
      key: remote-bind-host
```

Note: `PS_SSH_PASSWORD` as an environment variable is NEW (prod locations only
mount the file) — Sling's tunnel URL needs the value inline. This is spike-only
and gets reverted in Task 11.

- [ ] **Step 3: Validate YAML parses**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run python -c "
import yaml, pathlib
p = pathlib.Path('/workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike/src/teamster/code_locations/kipppaterson/dagster-cloud.yaml')
d = yaml.safe_load(p.read_text())
k8s = d['locations'][0]['container_context']['k8s']
server_env_names = [e['name'] for e in k8s['server_k8s_config']['container_config']['env']]
run_env_names = [e['name'] for e in k8s['run_k8s_config']['container_config']['env']]
required = ['PS_DB_USERNAME','PS_DB_PASSWORD','PS_DB_HOST','PS_DB_PORT','PS_DB_DATABASE','PS_SSH_HOST','PS_SSH_PORT','PS_SSH_USERNAME','PS_SSH_PASSWORD','PS_SSH_REMOTE_BIND_HOST']
assert all(n in server_env_names for n in required), [n for n in required if n not in server_env_names]
assert all(n in run_env_names for n in required), [n for n in required if n not in run_env_names]
assert any(v['name'] == 'secret-volume' for v in k8s['volumes'])
print('ok')
"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add src/teamster/code_locations/kipppaterson/dagster-cloud.yaml
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "chore(spike): wire paterson powerschool credentials for odbc spike

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: dlt spike assets

**Files:**

- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/__init__.py`
- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/dlt_assets.py`
- Test: `tests/spike/test_odbc_spike_defs.py`

**Interfaces:**

- Consumes: environment variables from Task 3; `SSHResource` from
  `teamster.libraries.ssh.resources`.
- Produces: `DLT_SPIKE_ASSETS` (list of three multi-asset defs, keys
  `kipppaterson/powerschool/spike/dlt/{table}`), each requiring resources `dlt`
  (`DagsterDltResource`) and `ssh_powerschool` (`SSHResource`).
  `SPIKE_TABLES: dict[str, str]` maps table name → primary key column. Task 5
  reuses `SPIKE_TABLES`; Task 6 wires resources.

- [ ] **Step 1: Write the failing test**

Create `tests/spike/test_odbc_spike_defs.py`:

```python
"""Definition-time checks for the throwaway PowerSchool ODBC spike assets.

These run in the Codespace with no PowerSchool credentials — they only assert
that the modules import cleanly (lazy env reads) and produce the expected
asset keys.
"""

from dagster import AssetKey


def test_dlt_spike_asset_keys():
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
        DLT_SPIKE_ASSETS,
        SPIKE_TABLES,
    )

    assert set(SPIKE_TABLES) == {"students", "storedgrades", "assignmentscore"}

    keys = {key for a in DLT_SPIKE_ASSETS for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", "spike", "dlt", t])
        for t in SPIKE_TABLES
    }
```

- [ ] **Step 2: Run it to verify it fails**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run pytest tests/spike/test_odbc_spike_defs.py -v
```

Expected: FAIL with `ModuleNotFoundError` (odbc_spike does not exist).

- [ ] **Step 3: Create the package and dlt assets**

`src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/__init__.py`:

```python
"""Throwaway dlt-vs-Sling spike assets. Never merge to main. Refs #4398."""
```

`src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/dlt_assets.py`:

```python
"""dlt side of the PowerSchool ODBC spike (#4398). Throwaway — never merge.

Loads three PowerSchool tables from Oracle (via the existing sshpass tunnel)
into BigQuery dataset zz_spike_powerschool_dlt using dlt's sql_table source
with the oracledb thin dialect and pyarrow backend. Incremental on
whenmodified with merge write disposition; the first run of an empty dataset
is effectively a full load.
"""

import os
from collections.abc import Iterator
from urllib.parse import quote

import dlt
from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import sql_table

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.ssh.resources import SSHResource

# table name -> primary key column (PowerSchool dcid is the stable unique id)
SPIKE_TABLES: dict[str, str] = {
    "students": "dcid",
    "storedgrades": "dcid",
    "assignmentscore": "dcid",
}

CURSOR_COLUMN = "whenmodified"


def _oracle_connection_url() -> str:
    """Build the SQLAlchemy URL at call time (env vars exist only in pods).

    The sshpass tunnel forwards localhost:1521 -> PS_SSH_REMOTE_BIND_HOST:1521,
    so the DB host here is the tunnel-local endpoint (PS_DB_HOST, normally
    localhost), matching the existing ODBC resource's connection shape.
    """
    user = os.getenv("PS_DB_USERNAME", "")
    password = quote(os.getenv("PS_DB_PASSWORD", ""), safe="")
    host = os.getenv("PS_DB_HOST", "localhost")
    port = os.getenv("PS_DB_PORT", "1521")
    service_name = os.getenv("PS_DB_DATABASE", "")

    return (
        f"oracle+oracledb://{user}:{password}@{host}:{port}"
        f"/?service_name={service_name}"
    )


class SpikeDltTranslator(DagsterDltTranslator):
    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        return asset_spec.replace_attributes(
            key=AssetKey(
                [
                    CODE_LOCATION,
                    "powerschool",
                    "spike",
                    "dlt",
                    data.resource.name,
                ]
            ),
            deps=[],
        )


def build_dlt_spike_asset(table_name: str, primary_key: str):
    dlt_source = sql_table(
        # placeholder credentials at import time; real values resolve in the
        # run pod because sql_table defers connection until extraction
        credentials=_oracle_connection_url(),
        table=table_name,
        backend="pyarrow",
        reflection_level="full_with_precision",
        defer_table_reflect=True,
        incremental=dlt.sources.incremental(CURSOR_COLUMN),
    )
    dlt_source.apply_hints(primary_key=primary_key)

    dlt_pipeline = dlt.pipeline(
        pipeline_name=f"powerschool_spike_{table_name}",
        destination=bigquery(),
        dataset_name="zz_spike_powerschool_dlt",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{CODE_LOCATION}__powerschool__spike__dlt__{table_name}",
        dagster_dlt_translator=SpikeDltTranslator(),
        group_name="powerschool_odbc_spike",
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        ssh_tunnel = ssh_powerschool.open_ssh_tunnel()

        try:
            yield from dlt.run(context=context, write_disposition="merge")
        finally:
            ssh_tunnel.kill()

    return _assets


DLT_SPIKE_ASSETS = [
    build_dlt_spike_asset(table_name=t, primary_key=pk)
    for t, pk in SPIKE_TABLES.items()
]
```

Notes for the implementer:

- `sql_table(credentials=...)` builds the URL at module import; in the run pod
  the env vars are present so the URL is real. In the Codespace it's an inert
  string — nothing connects until extraction (`defer_table_reflect=True`).
- If at runtime reflection fails with a "table not found" error, the DB user's
  default schema doesn't expose the table directly — retry with `schema="ps"`
  added to `sql_table(...)` (PowerSchool's owner schema). Record whichever works
  in the results doc; the Sling streams (Task 5) must use the same
  qualification.
- `dlt.run(write_disposition="merge")` + `primary_key` hint = upsert; the
  incremental cursor keeps state in `_dlt_pipeline_state` in the destination
  dataset.

- [ ] **Step 4: Run the test to verify it passes**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run pytest tests/spike/test_odbc_spike_defs.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/ tests/spike/test_odbc_spike_defs.py
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "feat(spike): dlt assets for powerschool odbc spike

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Sling spike assets and definitions wiring

**Files:**

- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/sling_assets.py`
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`
- Modify: `tests/spike/test_odbc_spike_defs.py` (add Sling + definitions tests)

**Interfaces:**

- Consumes: `SPIKE_TABLES` from Task 4's `dlt_assets.py`; env vars from Task 3.
- Produces: `SLING_SPIKE_ASSETS` (one multi-asset, keys
  `kipppaterson/powerschool/spike/sling/{table}`) requiring resource `sling`
  (`SlingResource`); `SLING_SPIKE_RESOURCE` (the configured `SlingResource`).
  `definitions.py` registers the spike assets + resources `sling`,
  `ssh_powerschool` (an `SSHResource` inlined with import-safe env defaults),
  and `dlt`.

- [ ] **Step 1: Add failing tests**

Append to `tests/spike/test_odbc_spike_defs.py`:

```python
def test_sling_spike_asset_keys():
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
        SPIKE_TABLES,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.sling_assets import (
        SLING_SPIKE_ASSETS,
    )

    keys = {key for a in SLING_SPIKE_ASSETS for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", "spike", "sling", t])
        for t in SPIKE_TABLES
    }
```

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run pytest tests/spike/test_odbc_spike_defs.py -v
```

Expected: new test FAILS with `ModuleNotFoundError` (sling_assets missing); the
dlt test still passes.

- [ ] **Step 2: Create the Sling assets**

`src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/sling_assets.py`:

```python
"""Sling side of the PowerSchool ODBC spike (#4398). Throwaway — never merge.

Replicates the same three tables through Sling's native SSH tunnel into
BigQuery dataset zz_spike_powerschool_sling. mode: incremental with
update_key whenmodified — on an empty target this performs the initial full
load; subsequent runs are incremental from max(whenmodified) in the target.
"""

import os
from collections.abc import Iterator
from urllib.parse import quote

from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_sling import (
    DagsterSlingTranslator,
    SlingConnectionResource,
    SlingResource,
    sling_assets,
)

from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
    CURSOR_COLUMN,
    SPIKE_TABLES,
)

# Oracle table qualification: the ODBC user's default schema resolves
# unqualified names today; Sling streams are qualified explicitly. If runtime
# errors show "table not found", change to the owner schema discovered in
# Task 4 (expected: ps).
ORACLE_SCHEMA = "ps"


def _ssh_tunnel_url() -> str:
    """ssh://user:password@host:port — password auth, no key file."""
    user = os.getenv("PS_SSH_USERNAME", "")
    password = quote(os.getenv("PS_SSH_PASSWORD", ""), safe="")
    host = os.getenv("PS_SSH_HOST", "")
    port = os.getenv("PS_SSH_PORT", "22")

    return f"ssh://{user}:{password}@{host}:{port}"


SLING_SPIKE_RESOURCE = SlingResource(
    connections=[
        SlingConnectionResource(
            name="PS_ORACLE",
            type="oracle",
            host=os.getenv("PS_SSH_REMOTE_BIND_HOST", ""),
            port=1521,
            user=os.getenv("PS_DB_USERNAME", ""),
            password=os.getenv("PS_DB_PASSWORD", ""),
            sid=os.getenv("PS_DB_DATABASE", ""),
            ssh_tunnel=_ssh_tunnel_url(),
        ),
        SlingConnectionResource(
            name="BIGQUERY_SPIKE",
            type="bigquery",
            project=GCS_PROJECT_NAME,
            dataset="zz_spike_powerschool_sling",
            gc_bucket="teamster-test",
            location="US",
        ),
    ]
)

REPLICATION_CONFIG = {
    "source": "PS_ORACLE",
    "target": "BIGQUERY_SPIKE",
    "defaults": {
        "mode": "incremental",
        "update_key": CURSOR_COLUMN,
        "object": "zz_spike_powerschool_sling.{stream_table}",
        "target_options": {"column_casing": "snake"},
    },
    "streams": {
        f"{ORACLE_SCHEMA}.{table}": {"primary_key": [pk]}
        for table, pk in SPIKE_TABLES.items()
    },
}


class SpikeSlingTranslator(DagsterSlingTranslator):
    def get_asset_spec(self, stream_definition) -> AssetSpec:
        asset_spec = super().get_asset_spec(stream_definition)

        # stream name is "<schema>.<table>" — key on the bare table name
        table_name = stream_definition["name"].split(".")[-1]

        return asset_spec.replace_attributes(
            key=AssetKey(
                [CODE_LOCATION, "powerschool", "spike", "sling", table_name]
            ),
            deps=[],
        )


@sling_assets(
    replication_config=REPLICATION_CONFIG,
    dagster_sling_translator=SpikeSlingTranslator(),
    name=f"{CODE_LOCATION}__powerschool__spike__sling",
)
def sling_spike_assets(
    context: AssetExecutionContext, sling: SlingResource
) -> Iterator:
    yield from sling.replicate(context=context)

    for row in sling.stream_raw_logs():
        context.log.info(row)


SLING_SPIKE_ASSETS = [sling_spike_assets]
```

Notes for the implementer:

- `SlingConnectionResource` passes arbitrary keyword properties through to the
  Sling connection env config — `sid`, `ssh_tunnel`, `gc_bucket` are Sling
  connection properties, not Dagster ones. If Sling rejects `sid` for a
  service-name connect at runtime, replace the Oracle connection's discrete
  properties with a single
  `url=f"oracle://{user}:{quote(password)}@{host}:1521/{service_name}"` property
  (keeping `ssh_tunnel`), and record which form worked in the results doc.
- The `os.getenv` values are captured at import time in the run pod (env is
  present there); Codespace imports get empty strings, which is fine because
  nothing connects at import.
- Materializing a subset of the multi-asset passes only the selected streams to
  Sling — per-table timing comes from one-table-at-a-time materializations.

- [ ] **Step 3: Wire into `definitions.py`**

In `src/teamster/code_locations/kipppaterson/definitions.py`:

Add imports:

```python
from dagster_dlt import DagsterDltResource

from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
    DLT_SPIKE_ASSETS,
)
from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.sling_assets import (
    SLING_SPIKE_ASSETS,
    SLING_SPIKE_RESOURCE,
)
from teamster.libraries.ssh.resources import SSHResource
```

Add the spike assets to the `Definitions` `assets` argument (after
`load_assets_from_modules(...)`, convert to a list and extend):

```python
    assets=[
        *load_assets_from_modules(
            modules=[
                dbt,
                amplify,
                deanslist,
                finalsite,
                pearson,
                powerschool,
            ]
        ),
        *DLT_SPIKE_ASSETS,
        *SLING_SPIKE_ASSETS,
    ],
```

Add resources to the `resources` dict:

```python
        "dlt": DagsterDltResource(),
        "sling": SLING_SPIKE_RESOURCE,
        "ssh_powerschool": SSHResource(
            remote_host=os.getenv("PS_SSH_HOST", ""),
            remote_port=int(os.getenv("PS_SSH_PORT", "22")),
            username=os.getenv("PS_SSH_USERNAME", ""),
            tunnel_remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST", ""),
        ),
```

with `import os` at the top. Deliberately NOT
`core.resources.get_powerschool_ssh_resource()` — that helper hard-fails on
unset `PS_SSH_PORT` at import, which would break Codespace imports of this
definitions module (a documented pain point for the ODBC districts).

- [ ] **Step 4: Add a definitions-level test and run all spike tests**

Append to `tests/spike/test_odbc_spike_defs.py`:

```python
def test_kipppaterson_definitions_include_spike_assets():
    from teamster.code_locations.kipppaterson.definitions import defs

    for table in ("students", "storedgrades", "assignmentscore"):
        for tool in ("dlt", "sling"):
            key = AssetKey(
                ["kipppaterson", "powerschool", "spike", tool, table]
            )
            assert defs.get_assets_def(key) is not None
```

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike run pytest tests/spike/test_odbc_spike_defs.py -v
```

Expected: 3 tests PASS (imports work in the Codespace because every env read has
a default).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/sling_assets.py src/teamster/code_locations/kipppaterson/definitions.py tests/spike/test_odbc_spike_defs.py
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "feat(spike): sling assets and definitions wiring for powerschool odbc spike

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Draft PR and branch deployment

**Files:** none (GitHub/Dagster Cloud operations)

**Interfaces:**

- Consumes: all commits from Tasks 2–5 pushed to
  `cbini/research/claude-powerschool-odbc-elt-spike`.
- Produces: a kipppaterson **branch deployment** in Dagster Cloud with the six
  spike assets visible; draft PR number recorded for Task 11.

- [ ] **Step 1: Push and open a DRAFT PR**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike push origin cbini/research/claude-powerschool-odbc-elt-spike
```

Create a **draft** PR via `mcp__github__create_pull_request` (base `main`, head
`cbini/research/claude-powerschool-odbc-elt-spike`, `draft: true`), body per
`.github/pull_request_template.md` with `Refs #4398`, stating clearly: "Spike PR
— code will be reverted before merge; only docs land."

- [ ] **Step 2: Verify the branch deployment loads**

Wait for the Actions build, then confirm via
`mcp__dagster__get_location_load_history` (branch deployment) that
`kipppaterson` shows `loadStatus: LOADED` at the PR's commit hash. If the
location errors, read the load error — the most likely failures are a missing
k8s secret (back to Task 1) or an import error (fix, recommit, push).

- [ ] **Step 3: Confirm the six spike asset keys exist in the branch
      deployment**

`mcp__dagster__search_assets` with prefix `kipppaterson/powerschool/spike` on
the branch deployment. Expected: 6 assets.

---

### Task 7: Full-load runs

**Files:**

- Create:
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md`
  (skeleton with rubric table, filled progressively)

**Interfaces:**

- Consumes: branch deployment from Task 6.
- Produces: per-tool, per-table full-load wall-clock + row counts recorded in
  the results doc; populated `zz_spike_powerschool_dlt` and
  `zz_spike_powerschool_sling` datasets.

- [ ] **Step 1: Create the results doc skeleton and commit it**

Create the results file with the rubric table (rows = 7 rubric dimensions,
columns = dlt / Sling per table) plus sections "Run log", "Runtime errors and
config adjustments", and "Decision". Commit:

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "docs(spike): results skeleton

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Materialize dlt assets one table at a time**

Via `mcp__dagster__launch_run` against the **branch deployment**, one run per
asset, smallest first: `students`, then `storedgrades`, then `assignmentscore`
(preview each launch with `confirm=False` first). Sequential runs keep tunnel
contention out of the timing data.

For each run record in the results doc: run id, start→end wall-clock, rows
loaded (from dlt's LogCollector output in compute logs), and any retries or
tunnel errors. If reflection fails on schema qualification, apply the
`schema="ps"` fallback from Task 4, commit, push (this restarts the branch
deploy), and rerun.

- [ ] **Step 3: Materialize Sling assets one table at a time**

Same procedure for the three Sling asset keys (selecting one member of the
multi-asset per run). Record the same measurements from Sling's log output
(`stream_raw_logs` lands in the run's compute logs). Apply the `url=` fallback
from Task 5 if the Oracle connection is rejected; record any config change.

- [ ] **Step 4: Commit results-doc progress**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "docs(spike): full-load run results

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Incremental runs

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md`

**Interfaces:**

- Consumes: populated datasets from Task 7.
- Produces: incremental-correctness rubric cells (rows loaded on second run,
  duplicate check, watermark behavior in a fresh pod).

- [ ] **Step 1: Re-materialize all six assets (one run per table per tool)**

At least several hours after Task 7 (so PowerSchool has real `whenmodified`
churn — ideally the next morning). Each Dagster run is a fresh pod, which is
exactly the state-recovery test: dlt must restore cursor state from
`_dlt_pipeline_state` in BigQuery; Sling must derive it from `max(whenmodified)`
in the target table.

- [ ] **Step 2: Record incremental metrics**

For each run record: rows loaded (should be **far** less than full), wall clock,
and cursor evidence (dlt: `Bind incremental` / state-restore log lines; Sling:
the `where whenmodified >= ...` in its emitted SQL log line).

- [ ] **Step 3: Duplicate check via BigQuery MCP**

For each of the six tables:

```sql
select
    'dlt' as tool,
    count(*) as row_count,
    count(distinct dcid) as distinct_pk,
from zz_spike_powerschool_dlt.students
```

(and the `zz_spike_powerschool_sling` equivalent; repeat per table). Expected:
`row_count = distinct_pk` everywhere. A mismatch = failed merge/upsert — a
decisive rubric finding, record it.

- [ ] **Step 4: Commit results-doc progress**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "docs(spike): incremental run results

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Fidelity validation queries

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md`

**Interfaces:**

- Consumes: both datasets fully loaded (Tasks 7–8).
- Produces: row/type/value fidelity rubric cells.

- [ ] **Step 1: Row fidelity — cross-tool count and PK anti-join**

Per table, via BigQuery MCP:

```sql
select
    (select count(*) from zz_spike_powerschool_dlt.students) as dlt_rows,
    (select count(*) from zz_spike_powerschool_sling.students) as sling_rows,
    (
        select count(*)
        from zz_spike_powerschool_dlt.students as d
        left join zz_spike_powerschool_sling.students as s using (dcid)
        where s.dcid is null
    ) as dlt_only,
    (
        select count(*)
        from zz_spike_powerschool_sling.students as s
        left join zz_spike_powerschool_dlt.students as d using (dcid)
        where d.dcid is null
    ) as sling_only
```

Expected: equal counts, zero-only anti-joins. Investigate any diff (incremental
window skew from Task 8 timing is the benign explanation — rerun both
incrementals back-to-back and re-check). Cross-tool agreement plus each tool's
own loaded-row logs stand in for a direct Oracle-side `COUNT(*)` — there is no
query path to Oracle outside the two tools themselves.

- [ ] **Step 2: Type fidelity — INFORMATION_SCHEMA diff**

```sql
select
    coalesce(d.column_name, s.column_name) as column_name,
    d.data_type as dlt_type,
    s.data_type as sling_type,
from zz_spike_powerschool_dlt.INFORMATION_SCHEMA.COLUMNS as d
full outer join zz_spike_powerschool_sling.INFORMATION_SCHEMA.COLUMNS as s
    on d.table_name = s.table_name
    and d.column_name = s.column_name
where
    coalesce(d.table_name, s.table_name) = 'students'
    and (d.data_type is distinct from s.data_type)
```

Repeat per table (paginate with `ordinal_position` if >50 rows). Record every
divergence, specifically: what `NUMBER` (no scale) became (`INT64`? `NUMERIC`?
`BIGNUMERIC`? `FLOAT64`?), what Oracle `DATE` became (`DATETIME` vs
`TIMESTAMP`), and CLOB columns (`students` has none; check
`assignmentscore.comment_value` >4k values arrive intact).

- [ ] **Step 3: Value fidelity — sampled cross-tool comparison**

Per table, compare decimal and date columns row-by-row (results stay local;
never paste row values into the doc — record only mismatch COUNTS):

```sql
select
    count(*) as compared,
    countif(d.gpa_points is distinct from s.gpa_points) as gpa_points_diff,
    countif(
        cast(d.whenmodified as string) != cast(s.whenmodified as string)
    ) as whenmodified_diff,
from zz_spike_powerschool_dlt.storedgrades as d
inner join zz_spike_powerschool_sling.storedgrades as s using (dcid)
```

Adapt column lists per table (`assignmentscore`: `scorepoints`, `scorepercent`;
`students`: `entrydate`, `exitdate`, `dob` — counts only, no values). Any
nonzero diff column: inspect types first (a NUMERIC-vs-FLOAT64 representation
diff is a type finding, not a value finding).

- [ ] **Step 4: Record everything and commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "docs(spike): fidelity validation results

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Decision write-up

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md`

**Interfaces:**

- Consumes: complete rubric from Tasks 7–9.
- Produces: a filled "Decision" section naming the pilot tool with rationale
  tied to rubric rows; reviewed by the user before Task 11.

- [ ] **Step 1: Fill the Decision section**

State the winner, the 2–3 rubric rows that decided it, the losing tool's
disqualifying/non-disqualifying findings, and any caveats to carry into the
pilot design (e.g. type-cast adapters needed, tunnel flakiness observed, schema
qualification discovered).

- [ ] **Step 2: Self-review the results doc, trunk check, commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike && /workspaces/teamster/.trunk/tools/trunk check --no-fix docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md </dev/null
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike add docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike commit -m "docs(spike): decision write-up

Refs #4398

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP — user reviews the decision**

Present the decision summary to the user and get explicit sign-off before Task
11 (it rewrites #3807 and dismantles the spike).

---

### Task 11: Rewrite #3807, strip spike code, merge docs

**Files:**

- Revert: all Task 2–5 commits (pyproject/uv.lock, dagster-cloud.yaml,
  odbc_spike package, definitions.py, tests/spike)
- Keep:
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-design.md`,
  `docs/superpowers/plans/2026-07-14-powerschool-odbc-elt-spike.md`,
  `docs/superpowers/specs/2026-07-14-powerschool-odbc-elt-spike-results.md`

**Interfaces:**

- Consumes: user-approved decision from Task 10.
- Produces: docs-only PR merged to `main`; #3807 rewritten; #4398 closed;
  scratch datasets cleaned up.

- [ ] **Step 1: Rewrite issue #3807**

Via `mcp__github__issue_write` (method `update`): new body reflecting the
winning tool, Paterson-first pilot (retire `sis/sftp/` + Couchdrop trigger for
PowerSchool), parity table scope, direct-to-BigQuery landing (a new non-external
source flavor in `src/dbt/powerschool`), the spike's caveats, and translation to
kippnewark/kippcamden/kippmiami as follow-up phases. Link the results doc.
Verify the stored body via
`gh api repos/TEAMSchools/teamster/issues/3807 --jq .body` (MCP read tools
sanitize output).

- [ ] **Step 2: Revert spike code commits**

List the code commits first —
`git -C <worktree> log --oneline origin/main..HEAD` — and revert every commit
whose diff touches paths outside `docs/superpowers/` (the Task 2–5 commits plus
any runtime-fix commits from Tasks 7–8), newest first:

````bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike revert --no-edit {sha-newest} {sha...} {sha-oldest}
``` Verify the
PR diff is docs-only:

```bash
git -C /workspaces/teamster/.worktrees/cbini/research/claude-powerschool-odbc-elt-spike diff origin/main --stat
````

Expected: only `docs/superpowers/**` paths.

- [ ] **Step 3: Mark PR ready, merge**

Push, mark the PR ready for review, confirm checks green (docs-only — dbt Cloud
CI and location deploys should be trivial), squash-merge per repo convention.

- [ ] **Step 4: Close #4398 and clean up**

- Close #4398 as completed with a comment linking the results doc and the
  rewritten #3807.
- Drop the scratch datasets — BigQuery MCP is SELECT-only, so hand the user:

```sql
drop schema if exists zz_spike_powerschool_dlt cascade;
drop schema if exists zz_spike_powerschool_sling cascade;
```

- Ask the user whether to also delete the Paterson PS k8s secrets or keep them
  for the pilot (recommend: keep — the pilot needs them within weeks).
- Remove the worktree:

```bash
git -C /workspaces/teamster worktree remove .worktrees/cbini/research/claude-powerschool-odbc-elt-spike
```
