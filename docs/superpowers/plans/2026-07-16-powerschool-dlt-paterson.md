# PowerSchool dlt Migration (kipppaterson pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace kipppaterson's Couchdrop-SFTP PowerSchool feed with dlt
syncing ~68 tables live from Paterson's Oracle, plus the dbt `staging/dlt`
variant, in a single PR validated on the branch deployment.

**Architecture:** New `libraries/dlt/powerschool/` factory (per-table
`@dlt_assets`, full-refresh `replace`, pyarrow, keyless ADC to BigQuery) + an
in-process paramiko SSH port-forward on `SSHResource`; code-location YAML drives
assets and two cron schedules; a generated `staging/dlt` dbt variant in the
shared `powerschool` package keeps the `stg_powerschool__*` contract so
downstream models are untouched.

**Tech Stack:** Dagster (`dagster-dlt`), dlt `sql_database`/`sql_table`
(oracledb thin dialect, SQLAlchemy reflection), paramiko, BigQuery, dbt.

**Spec:**
[2026-07-16-powerschool-dlt-paterson-design.md](../specs/2026-07-16-powerschool-dlt-paterson-design.md)

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson`.
  Every git call uses `git -C <worktree>`; every Read/Edit/Write targets the
  worktree path; Python runs use
  `VIRTUAL_ENV= uv --directory <worktree> run ...`.
- Python `>=3.13`: built-in generics, `X | None`, return type annotations on
  library methods, `check.not_none()` (never bare `assert isinstance`).
- Always `uv run` — never bare `python` or venv tools.
- Asset keys: `[code_location, "powerschool", <table>]` (no `dlt` layer, no
  `sis` layer).
- BigQuery landing dataset: `dagster_kipppaterson_dlt_powerschool`.
- Oracle owner schema: `ps` (SQLAlchemy reflection requires it explicitly).
- Pilot load strategy: `full_refresh` only (`write_disposition="replace"`). No
  incremental cursors, no merge.
- Conventional commits; commit after each task.
- PII stays local: parity validation outputs shared to the PR/issue must be
  aggregates (counts, mismatch tallies) — never row values.
- Markdown you write must pass
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <file> </dev/null`
  run from inside the worktree.
- The `claude` CLI and `gcloud` are unavailable via Bash. dbt Cloud job config
  and workflow dispatch are UI/user actions.

---

### Task 1: dlt library factory (`libraries/dlt/powerschool/`)

**Files:**

- Create: `src/teamster/libraries/dlt/powerschool/__init__.py` (empty)
- Create: `src/teamster/libraries/dlt/powerschool/assets.py`
- Test: `tests/libraries/test_dlt_powerschool_assets.py` (create; check `tests/`
  layout — unit tests for libraries live under `tests/`, see `tests/CLAUDE.md`
  before placing)

**Interfaces:**

- Consumes: `SSHResource.open_ssh_tunnel_paramiko()` (Task 2 — a
  `@contextmanager` yielding the bound local port; Task 1's asset body calls it,
  so write Task 1's test to not execute the asset body).
- Produces:
  `build_powerschool_dlt_assets(code_location: str, table_name: str, load_strategy: str = "full_refresh", op_tags: dict[str, object] | None = None)`
  returning the `@dlt_assets`-decorated multi-asset, with asset key
  `[code_location, "powerschool", table_name]`. Asset op requires resources
  `dlt` (`DagsterDltResource`) and `ssh_powerschool` (`SSHResource`). Pool:
  `dlt_powerschool_<code_location>`. Group: `powerschool`.

- [ ] **Step 1: Write the failing test**

```python
"""Definition-time checks for the PowerSchool dlt asset factory.

Run in the Codespace with no PowerSchool credentials — assert the module
imports cleanly (lazy env reads) and produces the expected asset keys.
"""

import pytest
from dagster import AssetKey


def test_powerschool_dlt_asset_key():
    from teamster.libraries.dlt.powerschool.assets import (
        build_powerschool_dlt_assets,
    )

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", table_name="students"
    )

    assert set(assets_def.keys) == {AssetKey(["kipppaterson", "powerschool", "students"])}
    assert assets_def.op.name == "kipppaterson__powerschool__students"


def test_powerschool_dlt_rejects_unknown_load_strategy():
    from teamster.libraries.dlt.powerschool.assets import (
        build_powerschool_dlt_assets,
    )

    with pytest.raises(ValueError, match="load_strategy"):
        build_powerschool_dlt_assets(
            code_location="kipppaterson",
            table_name="students",
            load_strategy="merge",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run (from main repo):

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run pytest /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/tests/libraries/test_dlt_powerschool_assets.py -v
```

Expected: FAIL with `ModuleNotFoundError: teamster.libraries.dlt.powerschool`

- [ ] **Step 3: Write the implementation**

`src/teamster/libraries/dlt/powerschool/assets.py` — adapted from the proven
spike code
(`git show 15f2f72a1^:src/teamster/code_locations/kipppaterson/powerschool/sis/odbc_spike/dlt_assets.py`)
and `libraries/dlt/focus/assets.py`:

```python
import os
from collections.abc import Iterator
from urllib.parse import quote

import dlt
from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter, sql_table
from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeEngine

from teamster.libraries.ssh.resources import SSHResource

# PowerSchool tables are owned by the `ps` schema. The ODBC pipeline reaches
# them via unqualified raw SQL (Oracle synonym/default-schema resolution), but
# SQLAlchemy reflection needs the owner schema explicitly or it raises
# NoSuchTableError.
ORACLE_SCHEMA = "ps"

LOAD_STRATEGIES = {"full_refresh": "replace"}


def oracle_number_adapter(col_type: TypeEngine) -> TypeEngine | None:
    """Keep Oracle NUMBER columns off FLOAT64 in BigQuery.

    Decimal Oracle NUMBER columns can reflect as Float (landing as FLOAT64 —
    float drift on GPA/balance columns) or as unbounded Numeric (landing as
    BIGNUMERIC via dlt's decimal128(38, 9+) default). Pin both to
    Numeric(38, 9), which dlt's BigQuery destination maps to NUMERIC.
    """
    if isinstance(col_type, Float):
        return Numeric(precision=38, scale=9)
    if isinstance(col_type, Numeric) and col_type.precision is None:
        return Numeric(precision=38, scale=9)
    return col_type


def _oracle_connection_url() -> str:
    """Build the SQLAlchemy URL at call time (env vars exist only in pods).

    The SSH tunnel forwards localhost:1521 -> PS_SSH_REMOTE_BIND_HOST:1521,
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


class PowerSchoolDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=AssetKey(
                [self.code_location, "powerschool", data.resource.name]
            ),
            deps=[],
        )

        return asset_spec.merge_attributes(kinds={"oracle"})


def build_powerschool_dlt_assets(
    code_location: str,
    table_name: str,
    load_strategy: str = "full_refresh",
    op_tags: dict[str, object] | None = None,
):
    if load_strategy not in LOAD_STRATEGIES:
        raise ValueError(
            f"load_strategy {load_strategy!r} not supported; "
            f"expected one of {sorted(LOAD_STRATEGIES)}"
        )

    write_disposition = LOAD_STRATEGIES[load_strategy]

    if op_tags is None:
        op_tags = {}

    # dagster-dlt's @dlt_assets requires a DltSource (it reads
    # .selected_resources); sql_table() alone returns a bare DltResource. Wrap
    # it in a @dlt.source generator — the same shape dlt's own sql_database()
    # and libraries/dlt/illuminate/assets.py use.
    @dlt.source(name=f"powerschool_{table_name}")
    def dlt_source():
        # placeholder credentials at import time; real values resolve in the
        # run pod because sql_table defers connection until extraction
        yield sql_table(
            credentials=_oracle_connection_url(),
            schema=ORACLE_SCHEMA,
            table=table_name,
            backend="pyarrow",
            reflection_level="full_with_precision",
            defer_table_reflect=True,
            table_adapter_callback=remove_nullability_adapter,
            type_adapter_callback=oracle_number_adapter,
        )

    dlt_pipeline = dlt.pipeline(
        pipeline_name=f"powerschool_{table_name}",
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_powerschool",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source(),
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__powerschool__{table_name}",
        dagster_dlt_translator=PowerSchoolDagsterDltTranslator(code_location),
        group_name="powerschool",
        pool=f"dlt_powerschool_{code_location}",
        op_tags=op_tags,
    )
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
    ) -> Iterator:
        with ssh_powerschool.open_ssh_tunnel_paramiko():
            yield from dlt.run(
                context=context, write_disposition=write_disposition
            )

    return _assets
```

Note: at this point `open_ssh_tunnel_paramiko` does not exist yet — the asset
body references it but definition-time tests never execute the body, so the test
passes. Task 2 adds the method (before anything runs the asset).

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson add src/teamster/libraries/dlt/powerschool/ tests/libraries/test_dlt_powerschool_assets.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson commit -m "feat(powerschool): add dlt asset factory for Oracle SIS tables

Refs #3807"
```

---

### Task 2: paramiko in-process SSH port forward on `SSHResource`

**Files:**

- Modify: `src/teamster/libraries/ssh/resources.py` (append; do not touch
  `open_ssh_tunnel`)
- Modify: `src/teamster/libraries/ssh/CLAUDE.md` (document the new method)
- Test: `tests/libraries/test_ssh_paramiko_tunnel.py` (create)

**Interfaces:**

- Consumes: existing `SSHResource.get_connection()` (already tenacity-retried;
  `enable_legacy_rsa=True` handles legacy `ssh-rsa` hosts),
  `self.tunnel_remote_host`, `dagster_shared.check`.
- Produces:
  `SSHResource.open_ssh_tunnel_paramiko(local_port: int = 1521, remote_port: int = 1521)`
  — a `@contextmanager` yielding the bound local port (`int`). Binds
  `127.0.0.1:<local_port>` (pass `local_port=0` for an ephemeral port in tests)
  and forwards each connection through a `direct-tcpip` channel to
  `(tunnel_remote_host, remote_port)`. On exit, shuts the listener and closes
  the SSH client.

- [ ] **Step 1: Write the failing test**

```python
import socket
from unittest.mock import MagicMock, patch


def _make_resource():
    from teamster.libraries.ssh.resources import SSHResource

    return SSHResource(
        remote_host="ssh.example.com",
        username="user",
        password="pw",  # fixture; add a trunk-ignore only if gitleaks flags it
        tunnel_remote_host="oracle.internal",
    )


def test_paramiko_tunnel_forwards_to_remote_bind():
    ssh_resource = _make_resource()

    channel = MagicMock()
    channel.recv.return_value = b""  # remote closes immediately

    transport = MagicMock()
    transport.open_channel.return_value = channel

    client = MagicMock()
    client.get_transport.return_value = transport

    with patch.object(ssh_resource, "get_connection", return_value=client):
        with ssh_resource.open_ssh_tunnel_paramiko(local_port=0) as local_port:
            assert isinstance(local_port, int) and local_port > 0

            with socket.create_connection(("127.0.0.1", local_port), timeout=5) as s:
                # drive one byte through so the handler opens the channel
                s.sendall(b"x")
                s.recv(1)  # returns b"" when the handler closes

    _, kwargs = transport.open_channel.call_args
    assert kwargs["dest_addr"] == ("oracle.internal", 1521)
    client.close.assert_called_once()


def test_paramiko_tunnel_listener_closes_on_exit():
    ssh_resource = _make_resource()

    client = MagicMock()
    client.get_transport.return_value = MagicMock()

    with patch.object(ssh_resource, "get_connection", return_value=client):
        with ssh_resource.open_ssh_tunnel_paramiko(local_port=0) as local_port:
            pass

    try:
        socket.create_connection(("127.0.0.1", local_port), timeout=1)
        connected = True
    except OSError:
        connected = False

    assert not connected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run pytest /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/tests/libraries/test_ssh_paramiko_tunnel.py -v
```

Expected: FAIL with
`AttributeError: ... has no attribute 'open_ssh_tunnel_paramiko'`

- [ ] **Step 3: Write the implementation**

Add to `src/teamster/libraries/ssh/resources.py`. New imports at top: `select`,
`socketserver`, `logging`, `from collections.abc import Iterator`,
`from contextlib import contextmanager`, `from paramiko import Transport` is
already imported (add `Channel` if you annotate). Implementation (classic
paramiko `forward.py` local-forward pattern):

```python
class _ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def _make_forward_handler(
    transport: Transport,
    remote_host: str,
    remote_port: int,
    log: logging.Logger,
) -> type[socketserver.BaseRequestHandler]:
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                channel = transport.open_channel(
                    kind="direct-tcpip",
                    dest_addr=(remote_host, remote_port),
                    src_addr=self.request.getpeername(),
                )
            except Exception as e:
                log.warning(
                    f"direct-tcpip channel to {remote_host}:{remote_port} "
                    f"failed: {e}"
                )
                return

            if channel is None:
                log.warning("direct-tcpip channel rejected by server")
                return

            try:
                while True:
                    r, _, _ = select.select([self.request, channel], [], [])
                    if self.request in r:
                        data = self.request.recv(16384)
                        if len(data) == 0:
                            break
                        channel.send(data)
                    if channel in r:
                        data = channel.recv(16384)
                        if len(data) == 0:
                            break
                        self.request.send(data)
            finally:
                channel.close()
                self.request.close()

    return Handler
```

And the method on `SSHResource`:

```python
    @contextmanager
    def open_ssh_tunnel_paramiko(
        self, local_port: int = 1521, remote_port: int = 1521
    ) -> Iterator[int]:
        """In-process SSH local port forward.

        Replaces the sshpass subprocess for the dlt PowerSchool path: no
        password file mount, no readiness race, host-key verification kept
        (get_connection handles legacy ssh-rsa and transient-failure retry).
        Yields the bound local port; pass local_port=0 for an ephemeral port.
        """
        client = self.get_connection()

        try:
            transport = check.not_none(value=client.get_transport())

            server = _ForwardServer(
                server_address=("127.0.0.1", local_port),
                RequestHandlerClass=_make_forward_handler(
                    transport=transport,
                    remote_host=check.not_none(value=self.tunnel_remote_host),
                    remote_port=remote_port,
                    log=self.log,
                ),
            )

            server_thread = threading.Thread(
                target=server.serve_forever, daemon=True
            )
            server_thread.start()

            try:
                yield server.server_address[1]
            finally:
                server.shutdown()
                server.server_close()
        finally:
            client.close()
```

Check `self.log` exists on `DagsterSSHResource` (`open_ssh_tunnel` already uses
it). Verify import list compiles:
`VIRTUAL_ENV= uv --directory <worktree> run python -c "import teamster.libraries.ssh.resources"`.

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: 2 PASSED. Also run the existing SSH tests to
confirm no regression:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run pytest /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/tests -k "ssh" -v
```

- [ ] **Step 5: Update `libraries/ssh/CLAUDE.md`** — add a bullet under _Notes_:
      `open_ssh_tunnel_paramiko()` is the in-process forward used by the dlt
      PowerSchool path (password from resource config / `PS_SSH_PASSWORD`);
      `open_ssh_tunnel()` (sshpass) remains for the incumbent ODBC districts
      until they migrate.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson add src/teamster/libraries/ssh/ tests/libraries/test_ssh_paramiko_tunnel.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson commit -m "feat(ssh): add in-process paramiko port forward for dlt powerschool

Refs #3807"
```

---

### Task 3: kipppaterson code location wiring

**Files:**

- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/__init__.py`
- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/assets.py`
- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/schedules.py`
- Create:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml`
- Modify: `src/teamster/code_locations/kipppaterson/powerschool/sis/__init__.py`
  and `powerschool/__init__.py` (expose the dlt module alongside sftp — sftp
  removal happens in Task 8)
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`
- Modify: `src/teamster/code_locations/kipppaterson/dagster-cloud.yaml`
- Test: `tests/assets/test_powerschool_dlt_paterson_defs.py` (create)

**Interfaces:**

- Consumes: `build_powerschool_dlt_assets` (Task 1), `SSHResource` +
  `open_ssh_tunnel_paramiko` (Task 2).
- Produces: `powerschool.sis.dlt.assets` (list of assets),
  `powerschool.sis.dlt.schedules` (list of 2 `ScheduleDefinition`s) — wired into
  `definitions.py`; resources `dlt: DagsterDltResource()` and
  `ssh_powerschool: SSHResource(...)`.

- [ ] **Step 1: Write `config/assets.yaml`** — the full-parity table set, tiered
      to match kippnewark's cadence groups (intraday = Newark's sensor-driven
      `assets-full` + `assets-nonpartition` + `assets-transactiondate` sets;
      nightly = `assets-gradebook-*`). `load_strategy` is explicit per entry
      (the template knob):

```yaml
assets:
  # intraday tier — kippnewark sensor-driven sets
  - {
      table_name: attendance,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: attendance_code,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: attendance_conversion_items,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: bell_schedule,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: calendar_day,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - { table_name: cc, load_strategy: full_refresh, schedule_tier: intraday }
  - {
      table_name: courses,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: cycle_day,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - { table_name: fte, load_strategy: full_refresh, schedule_tier: intraday }
  - { table_name: gen, load_strategy: full_refresh, schedule_tier: intraday }
  - { table_name: gpnode, load_strategy: full_refresh, schedule_tier: intraday }
  - {
      table_name: gpprogresssubject,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpprogresssubjectearned,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpprogresssubjectenrolled,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpprogresssubjectrequested,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpprogresssubjectwaived,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpprogresssubjwaivedapplied,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpselectedcrs,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpselectedcrtype,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpselector,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpstudentwaiver,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gptarget,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gpversion,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gradescaleitem,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: gradplan,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - { table_name: log, load_strategy: full_refresh, schedule_tier: intraday }
  - {
      table_name: pgfinalgrades,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: reenrollments,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: roledef,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: s_nj_crs_x,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: s_nj_ren_x,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: s_nj_stu_x,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: s_nj_usr_x,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: s_stu_x,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: schools,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: schoolstaff,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: sections,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: sectionteacher,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: spenrollments,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: storedgrades,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: studentcorefields,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: studentrace,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: students,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: studenttest,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: studenttestscore,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: termbins,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - { table_name: terms, load_strategy: full_refresh, schedule_tier: intraday }
  - { table_name: test, load_strategy: full_refresh, schedule_tier: intraday }
  - {
      table_name: testscore,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: u_clg_et_stu,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: u_clg_et_stu_alt,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: u_expectations,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: u_storedgrades_de,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - {
      table_name: u_studentsuserfields,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  - { table_name: users, load_strategy: full_refresh, schedule_tier: intraday }
  - {
      table_name: userscorefields,
      load_strategy: full_refresh,
      schedule_tier: intraday,
    }
  # nightly tier — kippnewark gradebook sets
  - {
      table_name: assignmentcategoryassoc,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: assignmentscore,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: assignmentsection,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: districtteachercategory,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradecalcformulaweight,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradecalcschoolassoc,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradecalculationtype,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradeformulaset,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradeschoolconfig,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradeschoolformulaassoc,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: gradesectionconfig,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
  - {
      table_name: teachercategory,
      load_strategy: full_refresh,
      schedule_tier: nightly,
    }
```

(56 intraday + 12 nightly = 68. Custom tables that may not exist in Paterson's
Oracle — `u_clg_et_stu`, `u_clg_et_stu_alt`, `u_expectations`,
`u_storedgrades_de` — get pruned in Task 5 if reflection fails.)

- [ ] **Step 2: Write the failing test**

```python
from dagster import AssetKey, ScheduleDefinition


def test_paterson_powerschool_dlt_asset_keys():
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import assets
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    assert len(config["assets"]) == 68

    keys = {key for a in assets.assets for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", a["table_name"]])
        for a in config["assets"]
    }


def test_paterson_powerschool_dlt_schedules():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules,
    )

    by_name = {s.name: s for s in schedules.schedules}

    intraday = by_name[
        "kipppaterson__powerschool__dlt__intraday_asset_job_schedule"
    ]
    nightly = by_name[
        "kipppaterson__powerschool__dlt__nightly_asset_job_schedule"
    ]

    assert isinstance(intraday, ScheduleDefinition)
    assert intraday.cron_schedule == "*/15 * * * *"
    assert nightly.cron_schedule == "0 2 * * *"
```

Run (same worktree pytest invocation), expected FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `assets.py`**

```python
import pathlib

import yaml

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import (
    build_powerschool_dlt_assets,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

assets = [
    build_powerschool_dlt_assets(
        code_location=CODE_LOCATION,
        table_name=a["table_name"],
        load_strategy=a["load_strategy"],
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
```

- [ ] **Step 4: Write `schedules.py`**

```python
import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())


def _tier_targets(tier: str) -> list[str]:
    return [
        f"{CODE_LOCATION}/powerschool/{a['table_name']}"
        for a in config["assets"]
        if a["schedule_tier"] == tier
    ]


powerschool_dlt_intraday_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__intraday_asset_job_schedule",
    cron_schedule="*/15 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("intraday"),
)

powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("nightly"),
)

schedules = [
    powerschool_dlt_intraday_asset_job_schedule,
    powerschool_dlt_nightly_asset_job_schedule,
]
```

`__init__.py` for the dlt module re-exports nothing (matches sftp module style);
update `powerschool/sis/__init__.py` / `powerschool/__init__.py` to whatever
aggregation style they currently use (read them first) so
`load_assets_from_modules(modules=[powerschool])` picks up BOTH sftp and dlt
assets for now.

- [ ] **Step 5: Wire `definitions.py`**

Follow the spike's definitions diff
(`git show 15f2f72a1^:src/teamster/code_locations/kipppaterson/definitions.py`)
minus everything Sling: add imports for `os`, `DagsterDltResource`,
`SSHResource`; add schedules `*powerschool.sis.dlt.schedules.schedules`; add
resources:

```python
        "dlt": DagsterDltResource(),
        "ssh_powerschool": SSHResource(
            remote_host=os.getenv("PS_SSH_HOST", ""),
            remote_port=int(os.getenv("PS_SSH_PORT", "22")),
            username=os.getenv("PS_SSH_USERNAME", ""),
            password=os.getenv("PS_SSH_PASSWORD", ""),
            tunnel_remote_host=os.getenv("PS_SSH_REMOTE_BIND_HOST", ""),
        ),
```

Check whether the PowerSchool SSH host needs `enable_legacy_rsa=True`: the
sshpass path passes `-oHostKeyAlgorithms=+ssh-rsa`, so set
`enable_legacy_rsa=True` on this resource. (If the branch-deployment connect in
Task 5 fails with `IncompatiblePeer`, this is the knob.)

- [ ] **Step 6: Restore the PS secret wiring in `dagster-cloud.yaml`**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson checkout 15f2f72a1^ -- src/teamster/code_locations/kipppaterson/dagster-cloud.yaml
```

Then edit (Read the file first; it contains the spike's full env wiring):

- Remove any Sling-specific entries.
- The spike mounted the SSH password as a secret-volume file for sshpass; the
  paramiko path reads it from config instead — replace the volume mount with a
  `PS_SSH_PASSWORD` entry in `container_config.env` sourced from
  `secretKeyRef: {name: op-ps-ssh-kipppaterson, key: password}`, alongside the
  existing `PS_DB_*` / `PS_SSH_*` secretKeyRef entries the spike added.
- Keep the DB env vars exactly as the spike had them (`PS_DB_USERNAME`,
  `PS_DB_PASSWORD`, `PS_DB_HOST`, `PS_DB_PORT`, `PS_DB_DATABASE`, `PS_SSH_HOST`,
  `PS_SSH_PORT`, `PS_SSH_USERNAME`, `PS_SSH_REMOTE_BIND_HOST`).

- [ ] **Step 7: Run tests + import checks**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run pytest /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/tests/assets/test_powerschool_dlt_paterson_defs.py -v
```

Expected: 2 PASSED. Then (needs the dbt manifest —
`uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipppaterson/__init__.py`
run inside the worktree first):

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run python -c "import teamster.code_locations.kipppaterson.definitions"
```

Expected: clean import (env vars default to empty strings in the codespace).

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson add src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/ tests/assets/test_powerschool_dlt_paterson_defs.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson commit -m "feat(kipppaterson): wire powerschool dlt assets, schedules, resources

Refs #3807"
```

---

### Task 4: draft PR + branch deployment

**Files:** none (operational).

- [ ] **Step 1: Push and open a draft PR** with
      `mcp__github__create_pull_request` (base `main`, draft, body from
      `.github/pull_request_template.md`, include `Closes #3807`). Verify the
      stored body via `gh api repos/TEAMSchools/teamster/pulls/<n> --jq .body`.
- [ ] **Step 2: Wait for the branch deployment**, then recover its name from the
      PR's `deploy` job log line `Deploying to branch deployment <hash>`
      (`gh run view`), since `mcp__dagster__list_deployments` may only show
      prod. First calls to a dormant deployment throw
      `DagsterUserCodeUnreachableError` — retry after ~90s.
- [ ] **Step 3: Smoke-run one small table**:
      `mcp__dagster__launch_run(deployment=<hash>, asset_keys=[["kipppaterson","powerschool","schools"]], confirm=False)`
      to preview, then `confirm=True`. Watch with `get_run_logs`; on failure
      read `error.errorChain[-1].error.message`. Likely first-run knobs:
      `enable_legacy_rsa` (Task 3 Step 5), tunnel connect, `NoSuchTableError`.
- [ ] **Step 4: Verify the landed table** via BigQuery MCP:
      `select count(*) from dagster_kipppaterson_dlt_powerschool.schools` and
      compare against the SFTP-fed staging count
      (`select count(*) from kipppaterson_powerschool.stg_powerschool__schools`).

---

### Task 5: full materialization and prune

> **Decision (2026-07-16):** `student_email` is **retired**, not rebuilt from a
> dlt source. It was a Paterson-only Couchdrop CSV with no Oracle counterpart;
> the discovery step below is removed and Task 8 retires the model + its
> `kipptaf` consumer.

**Files:**

- Modify:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml`
  (prune tables missing from Paterson's Oracle; update the count in the Task 3
  test)

**Steps:**

- [ ] **Step 1: Launch the full set** in batches with
      `mcp__dagster__launch_multiple_runs` (preview `confirm=False` first;
      non-empty `asset_keys` per run; deployment=<hash>). The
      `dlt_powerschool_kipppaterson` pool bounds Oracle concurrency.
- [ ] **Step 2: Triage failures.** `NoSuchTableError: <table>` = the table
      doesn't exist in Paterson's PS instance (expected candidates:
      `u_clg_et_stu`, `u_clg_et_stu_alt`, `u_expectations`,
      `u_storedgrades_de`). Remove those entries from `assets.yaml`, update the
      test's expected count, commit
      (`fix(kipppaterson): prune tables absent from Paterson Oracle`), push
      (this respins the branch deployment — re-resolve the hash). Any OTHER
      failure class (tunnel, types, timeouts): stop and diagnose before
      proceeding.
- [ ] **Step 3: Type audit.** Query
      `dagster_kipppaterson_dlt_powerschool.INFORMATION_SCHEMA.COLUMNS` for any
      `FLOAT64` or `BIGNUMERIC` columns. Expected: none (the
      `oracle_number_adapter` pins them to NUMERIC). If any appear, fix the
      adapter, drop the affected tables in BQ (hand `DROP` statements to the
      user — `replace` disposition cannot change existing column types), and
      re-run.
- [ ] **Step 4: (removed)** `student_email` is retired — no discovery needed.
      See the Task 5 decision note above and Task 8.

---

### Task 6: dbt `staging/dlt` variant + Paterson swap

**Files:**

- Create: `scripts/gen_powerschool_dlt_staging.py`
- Create: `src/dbt/powerschool/models/sis/staging/dlt/sources-bigquery.yml`
- Create:
  `src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__<table>.sql` (one
  per synced table, generated)
- Modify: `src/dbt/kipppaterson/dbt_project.yml` (variant swap)
- Possibly modify:
  `src/dbt/kipppaterson/models/powerschool/sis/staging/stg_powerschool__u_studentsuserfields.sql`
  (district-local override — read it; if it reads the sftp source, port it to
  the dlt source)

**Interfaces:**

- Consumes: populated `dagster_kipppaterson_dlt_powerschool` tables (Task 5);
  shared contract properties
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__<t>.yml`
  (column names + `data_type` — the target shape).
- Produces: enabled `stg_powerschool__*` models under `staging/dlt/` whose
  output contract matches the properties files, reading
  `source("powerschool_dlt", "<table>")`.

- [ ] **Step 1: Write `sources-bigquery.yml`** (shared package, follows the
      focus dlt convention — native BQ tables, no `external:` block):

```yaml
sources:
  - name: powerschool_dlt
    schema:
      "{{ var('powerschool_dlt_schema', 'dagster_' ~ project_name ~
      '_dlt_powerschool') }}"
    tables:
      - name: students
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - powerschool
                - students
      # ... one entry per synced table, same shape (generate in Step 2's
      # script run — do not hand-write 60+ stanzas)
```

- [ ] **Step 2: Write the generator script**
      `scripts/gen_powerschool_dlt_staging.py`. Inputs: the code-location
      `assets.yaml` (table list), the properties dir (contract per model), and
      live `dagster_kipppaterson_dlt_powerschool.INFORMATION_SCHEMA.COLUMNS`
      (raw dlt types, via `google.cloud.bigquery` ADC). For each table, emit
      `staging/dlt/stg_powerschool__<t>.sql`:
  - contract column whose raw type already matches → bare `<col>,`
  - raw `TIMESTAMP` where contract says `date` → `cast(<col> as date) as <col>,`
  - raw `TIMESTAMP` where contract says `datetime` →
    `cast(<col> as datetime) as <col>,`
  - raw `BIGNUMERIC`/`NUMERIC` where contract says `int64` →
    `cast(<col> as int64) as <col>,`
  - raw `BIGNUMERIC` where contract says `numeric` →
    `cast(<col> as numeric) as <col>,`
  - contract column missing from the raw table → **fail loudly** (print and exit
    non-zero; a missing column means the contract or the sync is wrong — decide
    per case, don't null-fill silently)
  - trailing `from {{ source("powerschool_dlt", "<t>") }}` (explicit column
    list, no `select *` — the contract is the interface) Also emit the full
    `sources-bigquery.yml` table stanzas (Step 1's file). Run it:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson run python /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/scripts/gen_powerschool_dlt_staging.py
```

- [ ] **Step 3: Handle special-case models.** `stg_powerschool__student_email`
      is **retired** — do NOT create a dlt variant of it (Task 8 removes the
      model and its consumer). For the kipppaterson-local
      `stg_powerschool__u_studentsuserfields` override, port it to the dlt
      source if it reads sftp.
- [ ] **Step 4: Swap the Paterson project config** in
      `src/dbt/kipppaterson/dbt_project.yml`: under `powerschool.sis.staging`,
      set `sftp: +enabled: false` (drop its per-model sub-entries) and
      `dlt: +enabled: true`; mirror for the sources block
      (`sftp.powerschool_sftp` disabled entries → remove; sources under `dlt`
      need no external-table config). Keep the previously-disabled downstream
      models (gradebook `int_` models etc.) disabled — enabling new consumers is
      out of scope.
- [ ] **Step 5: Build locally against dev target**:

```bash
uv run dbt build --select staging.dlt --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/src/dbt/kipppaterson
```

(dev target reads the real `dagster_kipppaterson_dlt_powerschool` dataset —
`powerschool_dlt_schema` var needs no override since the dataset name is not
project-prefixed per district... verify: for kipppaterson,
`'dagster_' ~ project_name ~ '_dlt_powerschool'` =
`dagster_kipppaterson_dlt_powerschool` — correct as-is.) Expected: all staging
models build green with contracts enforced. Iterate on the generator for any
contract mismatch.

- [ ] **Step 6: Run the full downstream build** to prove nothing broke:

```bash
uv run dbt build --select staging.dlt+ --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-paterson/src/dbt/kipppaterson
```

- [ ] **Step 7: Commit** (script, generated models, sources yml, project config)
      — `feat(dbt): add powerschool staging dlt variant; swap kipppaterson`.

---

### Task 7: parity validation (26 overlapping tables)

**Files:** none (queries + a results comment). Local scratch under
`.claude/scratch/` for any row-level output.

- [ ] **Step 1: Row counts.** For each of Paterson's 26 previously-SFTP tables,
      compare `dagster_kipppaterson_dlt_powerschool.<t>` vs the still-live
      SFTP-fed staging table `kipppaterson_powerschool.stg_powerschool__<t>`
      count. Small deltas are expected where the CSV drop lags Oracle — re-check
      any delta against drop freshness before calling it a failure.
- [ ] **Step 2: Key-set equality** on keyed tables (e.g. `dcid` for `students`,
      `storedgrades`, `cc`, `sections`, ...):
      `select count(*) from A full outer join B using (dcid) where A.dcid is null or B.dcid is null`
      = 0 (modulo the freshness caveat).
- [ ] **Step 3: Spot value checks** on divergence-prone classes (per the spike):
      a timestamp column (`transaction_date` wall-clock equality), a numeric
      column (GPA/balance), a free-text column with embedded newlines
      (`storedgrades` comments). Join on key, count mismatches.
- [ ] **Step 4: Record results** as a PR comment: per-table counts + mismatch
      tallies only (no PII values). Any true mismatch: stop, diagnose, fix
      before Task 8.

---

### Task 8: retire the SFTP path (and `student_email`)

> **`student_email` retirement (decision 2026-07-16).** The Paterson-only
> `stg_powerschool__student_email` model has a real downstream consumer:
> `kipptaf` `base_powerschool__student_enrollments.sql:113`
> `if(ar.region = 'Paterson', se.email, sl.google_email) as student_email_google`
> (join at `:219`). Retiring the source requires a replacement for the Paterson
> branch of that column — **resolution pending user answer** (see the
> controller's question). Steps 6-7 below implement whichever the user chooses;
> do not code them until the resolution is recorded here.

**Files:**

- Delete: `src/teamster/code_locations/kipppaterson/powerschool/sis/sftp/`
  (assets.py, schema.py, config/, `__init__.py`)
- Modify: `src/teamster/code_locations/kipppaterson/powerschool/sis/__init__.py`
  (drop sftp)
- Modify: couchdrop sensor config/code — read
  `src/teamster/code_locations/kipppaterson/couchdrop/` first; remove only the
  powerschool watch (the sensor also serves finalsite `status_report` — keep
  that)
- Modify: `src/teamster/code_locations/kipppaterson/CLAUDE.md` (PowerSchool row:
  SFTP → dlt; remove the "Critical Difference" section; add the dlt schedules to
  the Schedules section)
- Modify: `tests/` — remove/adjust any tests referencing the Paterson
  powerschool sftp assets (`grep -rn "powerschool.sis.sftp" tests src`)

**Steps:**

- [ ] **Step 1: Delete the sftp module** and fix all references
      (`grep -rn "sis.sftp\|sis/sftp" src tests` — scope to kipppaterson; the
      shared `powerschool/sis/sftp` dbt models stay for other uses of the
      package until all districts migrate... verify: only Paterson enables them;
      leave the shared models in place, disabled).
- [ ] **Step 2: Update couchdrop sensor + CLAUDE.md** as above.
- [ ] **Step 3: Re-run definition tests + import check** (same commands as Task
      3 Step 7). Run the full local pytest suite for touched areas:
      `... run pytest tests/assets tests/libraries -v`.
- [ ] **Step 4: Note in the PR body**: `reference/automations.md` must be
      regenerated in a full environment (codespace silently drops locations);
      flag for post-merge or a maintainer run. Also note: Ops should stop the
      Couchdrop PowerSchool export only after the PR has soaked in prod
      (rollback insurance).
- [ ] **Step 5: Commit** —
      `feat(kipppaterson)!: retire powerschool couchdrop sftp path` (the `!`
      marks the asset-key removal).
- [ ] **Step 6: Retire `student_email` (per resolution above).** Remove the
      Paterson `stg_powerschool__student_email` (do not create a dlt variant;
      remove/disable the sftp one and its source entry) AND the `kipptaf`
      `stg_powerschool__student_email.sql` + its properties + the
      `sources-kipppaterson.yml` entry.
- [ ] **Step 7: Update the `kipptaf` consumer.** Edit
      `base_powerschool__student_enrollments.sql` (drop the `se` join at `:219`
      and rewrite `student_email_google` at `:113` per the recorded resolution).
      Build `base_powerschool__student_enrollments+` on the kipptaf project to
      confirm downstream marts still build green. Commit separately:
      `refactor(kipptaf): retire powerschool student_email source`.

---

### Task 9: CI green + handoff

- [ ] **Step 1: Push; confirm dbt Cloud CI state first** (never push over an
      in-progress run — check `pull_request_read get_status`). dbt CI builds
      `state:modified+` against the PR schema; it may need one re-trigger if it
      raced the branch-deployment materializations.
- [ ] **Step 2: After CI passes**, fetch warnings:
      `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`.
      Pre-existing warnings unchanged from main: search for a tracker before
      filing.
- [ ] **Step 3: Check both CI surfaces** (commit status for dbt Cloud; check
      runs for Trunk/CodeQL/claude) before declaring green.
- [ ] **Step 4: Mark the PR ready for review** (triggers `claude-review`).
      Verify its convention claims before complying. CODEOWNERS review on
      `src/dbt/` (analytics-engineers) gates the merge — hand off to the user.
      Squash merge; post-merge, watch the first prod schedule ticks
      (`mcp__dagster__list_runs`) and the location deploy
      (`get_location_load_history`).

---

## Self-review notes

- Spec coverage: library+translator (T1), paramiko tunnel (T2), code
  location/config/schedules/resources (T3), branch-deployment validation (T4-5),
  type caveats (T1 adapter + T5 audit + T6 casts), staging variant + swap (T6),
  parity (T7), sftp retirement + docs (T8), CI/cutover (T9).
- `student_email` resolved via T5 Step 4 discovery + T6 Step 3.
- Deliberately not implemented (spec: out of scope): windowed replace,
  incremental cursors, other districts, sshpass retirement for ODBC districts.
