# Newark PowerSchool dlt Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate kippnewark's PowerSchool SIS ingestion from ODBC/Avro/GCS to
the shared dlt factory, retire Newark's ODBC path, and centralize the Oracle and
SSH resource construction (#4423, #4424 part 1).

**Architecture:** Per
`docs/superpowers/specs/2026-07-17-powerschool-dlt-newark-migration-design.md`.
One probe-gated `@dlt_assets` multi-asset over ~57 tables, naive full replace
(spike-proven at ~50k rows/s with `arraysize=10_000`), intraday/nightly schedule
tiers mirroring today's ODBC freshness. Oracle credentials become an injected
`ConfigurableResource`; the paramiko SSH resource construction moves fully into
`core/resources.py`.

**Tech Stack:** Dagster (`dagster-dlt`), dlt `sql_database` (`table_rows`),
SQLAlchemy + python-oracledb, BigQuery, dbt.

**Task ordering constraint:** the dlt op's `db_powerschool: OracleResource`
annotation and the ODBC ops' `db_powerschool: PowerSchoolODBCResource`
annotation cannot both validate against one binding — Newark's definitions are
transiently inconsistent from Task 1 until Task 3 (ODBC retirement) rebinds the
key. Do not reorder Tasks 1-3, and do not validate Newark's `definitions.py`
between them (module-level asset imports are fine).

## Global Constraints

- All file paths are relative to the worktree:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike`
  (branch `cbini/feat/claude-powerschool-dlt-newark-spike`, PR #4429, issue
  #4427). Read/Edit/Write MUST use the worktree absolute path, never
  `/workspaces/teamster/src/...`.
- Git: `git -C <worktree> ...` on every git call. Commit messages use
  conventional commits and end the body with `Refs #4427`.
- Python: `VIRTUAL_ENV= uv --directory <worktree> run python ...` — never bare
  `python` or main-repo `uv run` for worktree code.
- dbt: `uv run dbt <cmd> --project-dir <worktree>/src/dbt/kippnewark` (never
  `uv --directory <worktree> run dbt`).
- Trunk: pre-commit hook formats automatically; for `.md`/`.sql`/`.yml` files
  verify with
  `cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix <file> </dev/null`.
- IDE Pyright diagnostics on worktree files are false-positive-prone; trust
  `uv run` executed against the worktree.
- The branch deployment name is `0f8afb80d9019af3f503ee29a79448ac20481636`
  (dagster MCP `deployment` arg). Pushing to the branch rebuilds it (~8 min); a
  fresh code server needs ~90s warmup before MCP calls succeed.
- `dagster_kippnewark_dlt_powerschool` is shared between the branch deployment
  and prod (dlt datasets are not branch-isolated).
- Do not push while dbt Cloud CI is mid-run on the PR; bundle fix commits.
- If a district's definitions import fails on a missing dbt manifest, first run
  `VIRTUAL_ENV= uv --directory <worktree> run dagster-dbt project prepare-and-package --file <worktree>/src/teamster/code_locations/<district>/__init__.py`.

---

### Task 1: OracleResource and factory injection (#4423)

**Files:**

- Create: `src/teamster/libraries/dlt/powerschool/resources.py`
- Create: `tests/resources/test_powerschool_oracle_resource.py`
- Modify: `src/teamster/libraries/dlt/powerschool/assets.py`
- Modify: `src/teamster/core/resources.py` (add factory function)
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`

**Interfaces:**

- Produces: `OracleResource` (ConfigurableResource: `user`, `password`, `host`,
  `port`, `service_name`, all `str`; method `connection_url(self) -> str`);
  `get_powerschool_oracle_resource() -> OracleResource` in
  `teamster.core.resources`; the `@dlt_assets` op now requires a resource bound
  to the key `db_powerschool` of type `OracleResource`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/resources/test_powerschool_oracle_resource.py`:

```python
from teamster.libraries.dlt.powerschool.resources import OracleResource


def test_connection_url_quotes_password():
    resource = OracleResource(
        user="psnavigator",
        password="p@ss/wo:rd",
        host="localhost",
        port="1521",
        service_name="PSPRODDB",
    )

    assert resource.connection_url() == (
        "oracle+oracledb://psnavigator:p%40ss%2Fwo%3Ard@localhost:1521"
        "/?service_name=PSPRODDB"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike run pytest /workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike/tests/resources/test_powerschool_oracle_resource.py -v`

Expected: FAIL — `ModuleNotFoundError` /
`No module named 'teamster.libraries.dlt.powerschool.resources'`.

- [ ] **Step 3: Create the resource**

Create `src/teamster/libraries/dlt/powerschool/resources.py`:

```python
from urllib.parse import quote

from dagster import ConfigurableResource


class OracleResource(ConfigurableResource):
    """Connection config for the PowerSchool Oracle database (dlt path).

    The DB host is the tunnel-local endpoint (normally localhost) because the
    SSH tunnel forwards localhost:1521 to the PowerSchool server.
    """

    user: str
    password: str
    host: str
    port: str
    service_name: str

    def connection_url(self) -> str:
        password = quote(self.password, safe="")

        return (
            f"oracle+oracledb://{self.user}:{password}@{self.host}:{self.port}"
            f"/?service_name={self.service_name}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Inject into the factory**

In `src/teamster/libraries/dlt/powerschool/assets.py`:

1. Delete the `_oracle_connection_url()` function and the now-unused `import os`
   and `from urllib.parse import quote` imports.
1. Add
   `from teamster.libraries.dlt.powerschool.resources import OracleResource`.
1. Thread a `connection_url: str` parameter through `_build_resource` and
   `_powerschool_source`:

```python
def _build_resource(
    table: PowerSchoolTable, signature: dict | None, connection_url: str
):
```

with the engine line inside `_table_rows` becoming (keep the arraysize comment
already on it):

```python
        engine = sa.create_engine(connection_url, arraysize=10_000)
```

and:

```python
@dlt.source(name=_SOURCE_NAME)
def _powerschool_source(
    selected: list[PowerSchoolTable],
    signatures: dict[str, dict],
    connection_url: str,
):
    """dlt source narrowed to `selected`, wiring each table's probed signature."""
    for table in selected:
        yield _build_resource(table, signatures.get(table.name), connection_url)
```

1. In `build_powerschool_dlt_assets`, the spec-only source call becomes
   `_powerschool_source(tables, {}, "")` (never executed; asset specs only).
1. The op gains the resource parameter and uses it for both probe and run:

```python
    def _assets(
        context: AssetExecutionContext,
        dlt: DagsterDltResource,
        ssh_powerschool: SSHResource,
        db_powerschool: OracleResource,
    ) -> Iterator:
```

with `connection_url = db_powerschool.connection_url()` as the first line of the
`with ssh_powerschool.open_ssh_tunnel_paramiko():` block, the probe engine
becoming `engine = sa.create_engine(connection_url)`, and the run call using
`_powerschool_source(changed, current, connection_url)`.

- [ ] **Step 6: Add the core factory and wire Paterson**

In `src/teamster/core/resources.py`, next to `get_powerschool_ssh_resource`
(import `OracleResource` from `teamster.libraries.dlt.powerschool.resources`):

```python
def get_powerschool_oracle_resource() -> OracleResource:
    return OracleResource(
        user=EnvVar("PS_DB_USERNAME"),
        password=EnvVar("PS_DB_PASSWORD"),
        host=EnvVar("PS_DB_HOST"),
        port=EnvVar("PS_DB_PORT"),
        service_name=EnvVar("PS_DB_DATABASE"),
    )
```

In `src/teamster/code_locations/kipppaterson/definitions.py`, add
`get_powerschool_oracle_resource` to the `teamster.core.resources` import list
and add to the `resources` dict:

```python
        "db_powerschool": get_powerschool_oracle_resource(),
```

Do NOT touch kippnewark's `definitions.py` in this task — its ODBC assets still
require the old `PowerSchoolODBCResource` under the same key; Task 3 rebinds it.

- [ ] **Step 7: Validate Paterson only**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
VIRTUAL_ENV= uv --directory "$wt" run python -c "
import teamster.code_locations.kipppaterson.definitions
print('ok')
"
```

Expected: `ok` (BetaWarnings are fine). Newark's definitions are expected to be
inconsistent until Task 3 — do not validate them here.

- [ ] **Step 8: Commit**

```bash
git -C "$wt" add src/teamster/libraries/dlt/powerschool/ src/teamster/core/resources.py src/teamster/code_locations/kipppaterson/definitions.py tests/resources/test_powerschool_oracle_resource.py
git -C "$wt" commit -m "refactor(powerschool): inject oracle credentials as a resource

Closes #4423. Refs #4427"
```

---

### Task 2: Newark full table config and schedules

**Files:**

- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`
  (replace spike config with the full 57-table set)
- Create:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/schedules.py`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/__init__.py`
- Modify: `src/teamster/code_locations/kippnewark/powerschool/sis/__init__.py`

**Interfaces:**

- Consumes: the factory from Task 1 (public signature unchanged:
  `build_powerschool_dlt_assets(code_location, tables, op_tags=None)`).
- Produces: `sis.assets` (list with one dlt multi-asset over 57 tables) and
  `sis.schedules` (two `ScheduleDefinition`s named
  `kippnewark__powerschool__dlt__intraday_asset_job_schedule` and
  `kippnewark__powerschool__dlt__nightly_asset_job_schedule`).

- [ ] **Step 1: Write the full assets.yaml**

Replace the spike `config/assets.yaml` entirely. The table set is the union of
the five ODBC config files (commented-out tables excluded); cursors come from
the incumbent `partition_column`. Cross-check while writing: 27 intraday + 30
nightly = 57.

```yaml
assets:
  # intraday, cursor transaction_date
  - table_name: attendance
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: cc
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: courses
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: pgfinalgrades
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: schools
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: sections
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: storedgrades
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: students
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: termbins
    cursor_column: transaction_date
    schedule_tier: intraday
  - table_name: terms
    cursor_column: transaction_date
    schedule_tier: intraday
  # intraday, cursor whenmodified
  - table_name: gradescaleitem
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: roledef
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_crs_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_ren_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_nj_stu_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: s_stu_x
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: schoolstaff
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: sectionteacher
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: studentcorefields
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: studentrace
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_clg_et_stu
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_clg_et_stu_alt
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_expectations
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_storedgrades_de
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: u_studentsuserfields
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: users
    cursor_column: whenmodified
    schedule_tier: intraday
  - table_name: userscorefields
    cursor_column: whenmodified
    schedule_tier: intraday
  # nightly, cursor whenmodified (gradebook)
  - table_name: assignmentcategoryassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: assignmentscore
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: assignmentsection
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: districtteachercategory
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalcformulaweight
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalcschoolassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradecalculationtype
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeformulaset
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeschoolconfig
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradeschoolformulaassoc
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: gradesectionconfig
    cursor_column: whenmodified
    schedule_tier: nightly
  - table_name: teachercategory
    cursor_column: whenmodified
    schedule_tier: nightly
  # nightly, no cursor (always fully replaced when selected)
  - table_name: attendance_code
    cursor_column: null
    schedule_tier: nightly
  - table_name: attendance_conversion_items
    cursor_column: null
    schedule_tier: nightly
  - table_name: bell_schedule
    cursor_column: null
    schedule_tier: nightly
  - table_name: calendar_day
    cursor_column: null
    schedule_tier: nightly
  - table_name: cycle_day
    cursor_column: null
    schedule_tier: nightly
  - table_name: fte
    cursor_column: null
    schedule_tier: nightly
  - table_name: gen
    cursor_column: null
    schedule_tier: nightly
  - table_name: gpnode
    cursor_column: null
    schedule_tier: nightly
  - table_name: gpprogresssubject
    cursor_column: null
    schedule_tier: nightly
  - table_name: gpprogresssubjectearned
    cursor_column: null
    schedule_tier: nightly
  - table_name: gpprogresssubjectenrolled
    cursor_column: null
    schedule_tier: nightly
  - table_name: log
    cursor_column: null
    schedule_tier: nightly
  - table_name: reenrollments
    cursor_column: null
    schedule_tier: nightly
  - table_name: spenrollments
    cursor_column: null
    schedule_tier: nightly
  - table_name: studenttest
    cursor_column: null
    schedule_tier: nightly
  - table_name: studenttestscore
    cursor_column: null
    schedule_tier: nightly
  - table_name: test
    cursor_column: null
    schedule_tier: nightly
  - table_name: testscore
    cursor_column: null
    schedule_tier: nightly
```

- [ ] **Step 2: Create schedules.py**

Copy `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/schedules.py`
verbatim, changing only the import line to
`from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE`.
The file defines `_tier_targets(tier)` (validates `schedule_tier` values and
that intraday tables have a `cursor_column`) and the two `ScheduleDefinition`s
(`*/15 * * * *` intraday, `0 2 * * *` nightly, both
`dagster/max_runtime: 3600`), exported as `schedules`.

- [ ] **Step 3: Export schedules through the package inits**

`src/teamster/code_locations/kippnewark/powerschool/sis/dlt/__init__.py`:

```python
from teamster.code_locations.kippnewark.powerschool.sis.dlt import (
    assets,
    schedules,
)

__all__ = [
    "assets",
    "schedules",
]
```

`src/teamster/code_locations/kippnewark/powerschool/sis/__init__.py`:

```python
from teamster.code_locations.kippnewark.powerschool.sis import dlt

assets = [*dlt.assets.assets]

schedules = [*dlt.schedules.schedules]

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 4: Validate asset count and schedule targets**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
VIRTUAL_ENV= uv --directory "$wt" run python -c "
from teamster.code_locations.kippnewark.powerschool import sis
keys = {k.to_user_string() for a in sis.assets for k in a.keys}
assert len(keys) == 57, len(keys)
from teamster.code_locations.kippnewark.powerschool.sis.dlt.schedules import _tier_targets
assert len(_tier_targets('intraday')) == 27, _tier_targets('intraday')
assert len(_tier_targets('nightly')) == 30
print('ok')
"
```

Expected: `ok`. (This imports asset modules only — Newark's `definitions.py`
stays unvalidated until Task 3.)

- [ ] **Step 5: Commit**

```bash
git -C "$wt" add src/teamster/code_locations/kippnewark/powerschool/sis/
git -C "$wt" commit -m "feat(kippnewark): full powerschool dlt table config and schedules

Refs #4427"
```

---

### Task 3: Retire Newark's ODBC path

**Files:**

- Delete: `src/teamster/code_locations/kippnewark/powerschool/assets.py`,
  `.../powerschool/schedules.py`, `.../powerschool/sensors.py`,
  `.../powerschool/config/` (all five YAMLs)
- Modify: `src/teamster/code_locations/kippnewark/powerschool/__init__.py`
- Modify: `src/teamster/code_locations/kippnewark/definitions.py`

**Interfaces:**

- Consumes: `sis.assets` / `sis.schedules` from Task 2;
  `get_powerschool_oracle_resource` from Task 1.
- Produces: `powerschool.assets` and `powerschool.schedules` (dlt only, no
  `sensors`); `definitions.py` binds `db_powerschool` to `OracleResource`.

- [ ] **Step 1: Delete the ODBC files**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
git -C "$wt" rm -r src/teamster/code_locations/kippnewark/powerschool/assets.py src/teamster/code_locations/kippnewark/powerschool/schedules.py src/teamster/code_locations/kippnewark/powerschool/sensors.py src/teamster/code_locations/kippnewark/powerschool/config
```

- [ ] **Step 2: Rewrite powerschool/**init**.py (Paterson shape)**

```python
from teamster.code_locations.kippnewark.powerschool.sis import assets, schedules

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 3: Update definitions.py**

- Remove `DB_POWERSCHOOL` from the `teamster.core.resources` import list; add
  `get_powerschool_oracle_resource`.
- Replace the binding `"db_powerschool": DB_POWERSCHOOL,` with
  `"db_powerschool": get_powerschool_oracle_resource(),`.
- Remove `*powerschool.sensors,` from the `sensors` list (the module no longer
  exports sensors).
- `*powerschool.schedules,` in `schedules` now resolves to the dlt schedules —
  no edit needed.

- [ ] **Step 4: Sweep for dangling references**

```bash
grep -rn "build_powerschool_table_asset\|powerschool_table_assets\|DB_POWERSCHOOL" "$wt/src/teamster/code_locations/kippnewark/"
```

Expected: NO hits under kippnewark. Investigate and fix any hit (candidates:
`freshness.py`, `extracts/`, `dbt/assets.py` — none expected; `freshness.py` has
no powerschool entries as of planning).

- [ ] **Step 5: Validate + tests**

```bash
VIRTUAL_ENV= uv --directory "$wt" run python -c "
import teamster.code_locations.kippnewark.definitions as d
keys = {k.to_user_string() for a in (d.defs.assets or []) for k in getattr(a, 'keys', [])}
odbc = {k for k in keys if k.startswith('kippnewark/powerschool/') and '/sis/' not in k}
assert not odbc, odbc
print('ok')
"
VIRTUAL_ENV= uv --directory "$wt" run pytest "$wt/tests/test_dagster_definitions.py" -v -k "kippnewark or kipppaterson"
```

Expected: `ok`, tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C "$wt" add -A -- src/teamster/code_locations/kippnewark/
git -C "$wt" commit -m "feat(kippnewark)!: retire powerschool odbc ingestion

Replaced by the dlt path. Refs #4427"
```

---

### Task 4: Centralize the paramiko SSH resource (#4424 part 1)

**Files:**

- Modify: `src/teamster/core/resources.py` (`get_powerschool_ssh_resource`)
- Modify: `src/teamster/code_locations/kipppaterson/resources.py` (delete
  `SSH_POWERSCHOOL`)
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`
- Modify: `src/teamster/code_locations/kippnewark/resources.py` (delete the
  spike-added `SSH_POWERSCHOOL`)
- Modify: `src/teamster/code_locations/kippnewark/definitions.py`
- Maybe modify: `src/teamster/code_locations/kippcamden/dagster-cloud.yaml`,
  `src/teamster/code_locations/kippmiami/dagster-cloud.yaml`

**Interfaces:**

- Produces: `get_powerschool_ssh_resource()` now returns an `SSHResource` with
  `password=EnvVar("PS_SSH_PASSWORD")` and `enable_legacy_rsa=True`.
- Consumes: nothing from Tasks 1-3 (independent, but sequenced after them so
  every district's definitions validate here).

- [ ] **Step 1: Update the core factory**

In `src/teamster/core/resources.py`:

```python
def get_powerschool_ssh_resource() -> SSHResource:
    return SSHResource(
        remote_host=EnvVar("PS_SSH_HOST"),
        remote_port=EnvVar.int("PS_SSH_PORT"),
        username=EnvVar("PS_SSH_USERNAME"),
        password=EnvVar("PS_SSH_PASSWORD"),
        tunnel_remote_host=EnvVar("PS_SSH_REMOTE_BIND_HOST"),
        # paramiko 5.0 dropped ssh-rsa; PowerSchool-hosted servers still
        # require it (the ODBC sshpass path forces +ssh-rsa the same way)
        enable_legacy_rsa=True,
    )
```

- [ ] **Step 2: Remove the two local copies**

- `src/teamster/code_locations/kipppaterson/resources.py`: delete the
  `SSH_POWERSCHOOL = SSHResource(...)` block and the now-unused
  `from teamster.libraries.ssh.resources import SSHResource` import (keep
  `FINALSITE_RESOURCE`).
- `src/teamster/code_locations/kipppaterson/definitions.py`: import
  `get_powerschool_ssh_resource` from `teamster.core.resources`, change the
  binding to `"ssh_powerschool": get_powerschool_ssh_resource(),`, and remove
  `SSH_POWERSCHOOL` from the `...kipppaterson.resources` import.
- `src/teamster/code_locations/kippnewark/resources.py`: delete the spike-added
  `SSH_POWERSCHOOL` block and `SSHResource` import (restore the file to
  `FINALSITE_RESOURCE` only).
- `src/teamster/code_locations/kippnewark/definitions.py`: change the binding
  back to `"ssh_powerschool": get_powerschool_ssh_resource(),` (import from
  core; remove the `SSH_POWERSCHOOL` import from `...kippnewark.resources`).

- [ ] **Step 3: Verify PS_SSH_PASSWORD reaches every code server**

Camden and Miami still run ODBC assets whose execution-plan resource config now
includes the `password` field — their CODE SERVER env must define
`PS_SSH_PASSWORD` (this exact gap broke the first Newark spike launch).

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
for d in kippcamden kippmiami; do
  echo "== $d"
  awk '/run_k8s_config/{run=1} /PS_SSH_PASSWORD/{print (run ? "run-pods" : "code-server")}' \
    "$wt/src/teamster/code_locations/$d/dagster-cloud.yaml"
done
```

Expected: each district prints BOTH `code-server` and `run-pods`. For any
district missing the `code-server` occurrence, add this block to the FIRST
(`container_context` server) `env:` list, next to the other `PS_SSH_*` entries,
mirroring Newark commit `77ddf0bbf` (secret name is per-district):

```yaml
- name: PS_SSH_PASSWORD
  valueFrom:
    secretKeyRef:
      name: op-ps-ssh-<district>
      key: password
```

- [ ] **Step 4: Validate all four powerschool districts**

```bash
VIRTUAL_ENV= uv --directory "$wt" run python -c "
import teamster.code_locations.kipppaterson.definitions
import teamster.code_locations.kippnewark.definitions
import teamster.code_locations.kippcamden.definitions
import teamster.code_locations.kippmiami.definitions
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git -C "$wt" add src/teamster/core/resources.py src/teamster/code_locations/kipppaterson/ src/teamster/code_locations/kippnewark/ src/teamster/code_locations/kippcamden/dagster-cloud.yaml src/teamster/code_locations/kippmiami/dagster-cloud.yaml
git -C "$wt" commit -m "refactor(powerschool): centralize paramiko ssh resource construction

Refs #4424. Refs #4427"
```

---

### Task 5: dbt — missing dlt staging models and the variant flip

**Controller note (corrected after verification):** The gap is **10** tables,
not 9. Nine are SHARED-package tables that need new `staging/dlt` models
translated from their odbc counterparts; the tenth, `u_studentsuserfields`, is
**district-specific** (each district has its own model because the user-defined
columns differ) and needs its Newark model repointed, not a shared model. AND:
because enabling the `staging/dlt` directory builds every model in it,
kipppaterson (the only other dlt district) will start building the 9 new shared
models against source tables it does NOT extract — so they MUST be disabled for
Paterson or Paterson's CI breaks. The reverse check is clean: every EXISTING
shared dlt model's table is in Newark's 57, so Newark needs no dlt per-model
disables.

**Files:**

- Create (9 shared models, translated from their odbc counterparts):
  `src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__<t>.sql` for `t`
  in: `gpnode`, `gpprogresssubject`, `gpprogresssubjectearned`,
  `gpprogresssubjectenrolled`, `gradesectionconfig`, `u_clg_et_stu`,
  `u_clg_et_stu_alt`, `u_expectations`, `u_storedgrades_de`
- Modify: `src/dbt/powerschool/models/sis/staging/dlt/sources-bigquery.yml` (add
  the 9; `u_studentsuserfields` is already present)
- Modify: `src/dbt/kipppaterson/dbt_project.yml` (disable the 9 new shared
  models for Paterson)
- Rewrite:
  `src/dbt/kippnewark/models/powerschool/sis/staging/stg_powerschool__u_studentsuserfields.sql`
  (repoint from the odbc source to the dlt source, dlt idiom, Newark's own
  column set)
- Modify: `src/dbt/kippnewark/dbt_project.yml` (variant flip)

**Interfaces:**

- Consumes: table names from Task 2's `assets.yaml`.
- Produces: a `stg_powerschool__<t>` dlt model for every Newark-extracted shared
  table; kippnewark builds the `dlt` staging variant; kipppaterson's build is
  preserved.

- [ ] **Step 1: Confirm the gap set (already computed by the controller)**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
grep 'table_name:' "$wt/src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml" | awk '{print $3}' | sort > /tmp/claude-1000/newark_tables.txt
ls "$wt/src/dbt/powerschool/models/sis/staging/dlt/" | grep '\.sql$' | sed 's/stg_powerschool__//;s/\.sql$//' | sort > /tmp/claude-1000/dlt_models.txt
comm -23 /tmp/claude-1000/newark_tables.txt /tmp/claude-1000/dlt_models.txt   # expect the 10
```

The 10: the 9 shared listed above + `u_studentsuserfields` (district-specific,
handled in Step 5). Confirm the output is exactly these 10 before proceeding.

- [ ] **Step 2: Author the 9 shared dlt staging models**

For each of the 9 shared tables, open the ODBC counterpart
`src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__<t>.sql` and
translate to a new
`src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__<t>.sql` using
these mechanical rules (study an existing dlt model such as
`stg_powerschool__gradescaleitem.sql` for the exact idiom):

1. `from {{ source("powerschool_odbc", "src_powerschool__<t>") }}` (or whatever
   the odbc source ref is) → `from {{ source("powerschool_dlt", "<t>") }}`.
1. Avro union unwraps become casts, keeping the identical output column name:
   - `x.int_value as x` → `cast(x as int) as x`
   - `x.long_value as x` → `cast(x as int) as x`
   - `x.double_value as x` → `cast(x as float64) as x`
   - date/timestamp unwraps: match what an existing dlt model does for the same
     column name (`whenmodified` passthrough in
     `stg_powerschool__gradescaleitem.sql`; `transaction_date` handling in
     `stg_powerschool__storedgrades.sql`) — the dlt source lands Oracle DATE as
     `datetime`.
1. Plain passthrough columns stay as-is (keep backtick-quoting of reserved words
   like `` `type` ``). Preserve the ODBC model's exact output column set and
   order.
1. Do NOT include avro metadata columns (`_dagster_*`) or dlt metadata columns
   (`_dlt_id`, `_dlt_load_id`).

Example — `stg_powerschool__gradesectionconfig.sql` (translate the odbc file's
FULL column list; snippet shows the idiom, the real file must cover EVERY column
the odbc model outputs):

```sql
select
    calcmetricsectionfromstnd,
    defaultroundingrule,
    higherlevelstndmetric,
    recentscoreweightlist,
    stndcalculationmetric,
    `type`,
    whencreated,
    whenmodified,
    whocreated,
    whomodified,

    cast(defaultdecimalcount as int) as defaultdecimalcount,
    cast(gradeformulasetid as int) as gradeformulasetid,
    cast(gradesectionconfigid as int) as gradesectionconfigid,
    cast(sectionsdcid as int) as sectionsdcid,
    -- ...every remaining unwrapped column from the odbc model, same names
from {{ source("powerschool_dlt", "gradesectionconfig") }}
```

- [ ] **Step 3: Add the 9 to sources-bigquery.yml**

In `src/dbt/powerschool/models/sis/staging/dlt/sources-bigquery.yml`, add one
entry per new table, alphabetically within the `tables:` list, exactly matching
the existing pattern (do NOT re-add `u_studentsuserfields` — verify it is
already there):

```yaml
- name: gradesectionconfig
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - powerschool
          - sis
          - gradesectionconfig
```

- [ ] **Step 4: Disable the 9 new shared models for kipppaterson**

Paterson does NOT extract these 9 tables; without disabling, Paterson's dlt
build reads non-existent source tables. In
`src/dbt/kipppaterson/dbt_project.yml`, under
`models: powerschool: sis: staging: dlt:`, add a per-model `+enabled: false` for
each of the 9 (leave the existing `+enabled: true` for the directory and the
existing `int_powerschool__section_grade_config: +enabled: false` under
`intermediate:` untouched):

```yaml
dlt:
  +enabled: true
  stg_powerschool__gpnode:
    +enabled: false
  stg_powerschool__gpprogresssubject:
    +enabled: false
  stg_powerschool__gpprogresssubjectearned:
    +enabled: false
  stg_powerschool__gpprogresssubjectenrolled:
    +enabled: false
  stg_powerschool__gradesectionconfig:
    +enabled: false
  stg_powerschool__u_clg_et_stu:
    +enabled: false
  stg_powerschool__u_clg_et_stu_alt:
    +enabled: false
  stg_powerschool__u_expectations:
    +enabled: false
  stg_powerschool__u_storedgrades_de:
    +enabled: false
```

- [ ] **Step 5: Repoint Newark's district-specific u_studentsuserfields**

`src/dbt/kippnewark/models/powerschool/sis/staging/stg_powerschool__u_studentsuserfields.sql`
currently reads
`from {{ source("powerschool_odbc", "src_powerschool__u_studentsuserfields") }}`
with the odbc avro-unwrap idiom. Rewrite it to read
`from {{ source("powerschool_dlt", "u_studentsuserfields") }}` with the dlt cast
idiom (same rules as Step 2), PRESERVING Newark's existing output column set (do
not adopt Paterson's column list — Newark's UDF columns differ). Use
`src/dbt/kipppaterson/models/powerschool/sis/staging/stg_powerschool__u_studentsuserfields.sql`
ONLY as the idiom reference. Do not change its properties file
(`properties/stg_powerschool__u_studentsuserfields.yml`) unless a column name
actually changes — column names must stay identical so the contract and
downstream `rpt_powerschool__autocomm_students` keep resolving.

- [ ] **Step 6: Flip the kippnewark variants**

In `src/dbt/kippnewark/dbt_project.yml`:

1. In `models: ... powerschool: sis: staging:`, replace the entire `odbc:` block
   (including all its per-model `+enabled: false` overrides) with:

```yaml
odbc:
  +enabled: false
dlt:
  +enabled: true
```

(keep the existing `sftp: +enabled: false` sibling. The reverse check confirmed
every existing shared dlt model's table is in Newark's 57, and Newark extracts
all 9 new tables, so Newark needs NO dlt per-model disables. Newark keeps
`int_powerschool__section_grade_config` ENABLED — it has `gradesectionconfig`,
unlike Paterson.)

1. In the `sources:` section, mirror Paterson's powerschool shape
   (`src/dbt/kipppaterson/dbt_project.yml`,
   `sources: powerschool: sis: staging:`): disable the `odbc` source tree, keep
   the sftp source disables Newark already has, and leave the `powerschool_dlt`
   source enabled. Preserve Newark's other source configs untouched.

- [ ] **Step 7: Parse both projects and lint**

```bash
uv run dbt parse --project-dir "$wt/src/dbt/kippnewark"
uv run dbt parse --project-dir "$wt/src/dbt/kipppaterson"
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git -C "$wt" diff --name-only HEAD -- 'src/dbt/*' | sed "s|^|$wt/|") </dev/null
```

Expected: BOTH parses succeed (Newark: no missing-source/disabled-ref errors;
Paterson: the 9 disables resolve, no dangling refs); trunk clean (sqlfluff runs
here, not at commit). A Paterson parse failure usually means a Paterson int/mart
model refs one of the 9 disabled staging models — if so, STOP and report it (it
means Paterson silently needs that table, which contradicts the analysis).

- [ ] **Step 8: Commit**

```bash
git -C "$wt" add src/dbt/powerschool/ src/dbt/kippnewark/ src/dbt/kipppaterson/dbt_project.yml
git -C "$wt" commit -m "feat(dbt): enable powerschool dlt staging variant for kippnewark

Adds the 9 shared dlt staging models Newark needs beyond the Paterson set
(disabled for Paterson, which does not extract them), repoints Newark's
district-specific u_studentsuserfields to the dlt source, and flips Newark's
staging variant to dlt. Refs #4427"
```

---

### Task 6: Branch-deployment validation

**Files:** none (operational task; runs against the branch deployment and
BigQuery).

**Interfaces:**

- Consumes: everything from Tasks 1-5, pushed to the PR branch.

- [ ] **Step 1: Push and wait for the branch deployment**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-dlt-newark-spike
git -C "$wt" push
gh run list --branch cbini/feat/claude-powerschool-dlt-newark-spike --limit 5 --json databaseId,name,status --jq '.[] | select(.name=="kippnewark") | "\(.databaseId) \(.status)"'
gh run watch <kippnewark-run-id> --exit-status --interval 30   # run_in_background
```

Then wait ~90s for the code server to warm.

- [ ] **Step 2: Drop the polluted dataset (user's terminal)**

Hand this statement to the user to run in THEIR terminal (BQ MCP is SELECT-only;
`bq` CLI auth is user-scoped; the classifier requires user-named DDL):

```sql
DROP SCHEMA `teamster-332318.dagster_kippnewark_dlt_powerschool` CASCADE;
```

- [ ] **Step 3: Launch the initial full load**

Via the dagster MCP (`deployment=0f8afb80d9019af3f503ee29a79448ac20481636`,
`repository_location_name=kippnewark`): `launch_run` with ALL 57 asset keys
(`kippnewark/powerschool/sis/<table>` for every `table_name` in `assets.yaml`).
Preview with `confirm=False`, then `confirm=True`. Expect ~15-25 min (36.4M
rows; parallel extract over one tunnel). Monitor with `get_run` +
`get_run_logs(filter_types=["LogMessageEvent"])`.

Expected: run SUCCESS, 57 materializations.

- [ ] **Step 4: Verify row counts and idle-tick behavior**

Row counts (BigQuery MCP) — spot-check against the ODBC-era staging tables
(small drift is expected for tables that changed since the ODBC path last ran):

```sql
SELECT 'attendance' AS t,
  (SELECT COUNT(*) FROM `teamster-332318.dagster_kippnewark_dlt_powerschool.attendance`) AS dlt_n,
  (SELECT COUNT(*) FROM `teamster-332318.kippnewark_powerschool.stg_powerschool__attendance`) AS odbc_n
UNION ALL
SELECT 'assignmentscore',
  (SELECT COUNT(*) FROM `teamster-332318.dagster_kippnewark_dlt_powerschool.assignmentscore`),
  (SELECT COUNT(*) FROM `teamster-332318.kippnewark_powerschool.stg_powerschool__assignmentscore`)
UNION ALL
SELECT 'students',
  (SELECT COUNT(*) FROM `teamster-332318.dagster_kippnewark_dlt_powerschool.students`),
  (SELECT COUNT(*) FROM `teamster-332318.kippnewark_powerschool.stg_powerschool__students`)
```

Idle tick: immediately relaunch the same 57-asset run; the probe should report
few-to-zero changed tables and the no-cursor nightly tables reloading (they are
always loaded when selected) — total step time minutes, not tens of minutes.

- [ ] **Step 5: dbt Cloud CI**

The push in Step 1 triggered dbt Cloud CI (it builds `state:modified+` — all dlt
staging models + downstream). If CI ran BEFORE the initial load and failed on
missing source tables, re-trigger AFTER Step 3 with
`git -C "$wt" commit --allow-empty -m "chore: rerun ci" && git -C "$wt" push`
(only once dbt Cloud is in a terminal state). When green, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`.

Expected: CI green; no NEW warnings versus main.

---

### Task 7: PR finalization and docs

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/CLAUDE.md`
- Modify: PR #4429 title/body (GitHub, not repo files)

**Interfaces:**

- Consumes: green validation from Task 6.

- [ ] **Step 1: Update kippnewark CLAUDE.md**

In the Active Integrations table, change the `powerschool` row to `dlt assets` /
`schedules (intraday 15-min + nightly 2am)`, and replace the "PowerSchool
Configuration" section body: config at `powerschool/sis/dlt/config/assets.yaml`,
probe-gated full replace, resources `ssh_powerschool` + `db_powerschool` built
by `core/resources.py` factories.

- [ ] **Step 2: Retitle PR #4429 and rewrite the body**

Title: `feat(kippnewark): migrate powerschool sis ingestion to dlt`. Body:
follow `.github/pull_request_template.md`; summary covers the migration, the two
refactors (`Closes #4423`, `Refs #4424`), spike results (link the spec), and the
go-live steps; ends with `Refs #4427`. Use
`gh api -X PATCH repos/TEAMSchools/teamster/pulls/4429 -F body=@<file>` for the
body (avoids MCP entity-encoding) and verify the stored body with
`gh api repos/TEAMSchools/teamster/pulls/4429 --jq .body`.

- [ ] **Step 3: Commit docs and push**

```bash
git -C "$wt" add src/teamster/code_locations/kippnewark/CLAUDE.md
git -C "$wt" commit -m "docs(kippnewark): powerschool dlt migration notes

Refs #4427"
git -C "$wt" push
```

(Respect the dbt Cloud CI state before pushing.)

- [ ] **Step 4: Review gate**

Wait for `claude-review` + Trunk + dbt Cloud + Dagster Cloud checks (check BOTH
commit statuses and check runs). Address findings; CODEOWNERS approval
(`src/dbt/` → analytics-engineers) is required before merge. Squash merge —
performed by the user or on their explicit instruction.

---

## Go-live (post-merge, mostly user-driven)

1. Confirm the kippnewark location deploy loaded the merge commit
   (`get_location_load_history`).
1. The dataset already holds the branch-deployment full load and dlt state —
   prod schedules continue from it (same dataset; no re-drop, no re-load). The
   first intraday tick validates probe-gating in prod.
1. Set the `dlt_powerschool_kippnewark` pool to limit 1 (Dagster UI — user).
1. Regenerate `docs/automations.md` in a full environment
   (`uv run scripts/gen-automations-doc.py`; the codespace drops locations whose
   imports fail — do NOT regenerate here if any location fails to import).
1. Watch the first nightly (2am) run; confirm gradebook tables reload in under
   ~15 min and the run stays within `max_runtime: 3600`.
