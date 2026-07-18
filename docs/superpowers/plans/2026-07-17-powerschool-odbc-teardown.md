# PowerSchool ODBC SIS Teardown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the legacy PowerSchool ODBC SIS stack (#4441 + #4442, one PR):
delete Miami's dead wiring, archive the shared Python/dbt libraries in place,
repoint downstream consumers at the frozen `kippmiami_powerschool` BigQuery
dataset, and rename the paramiko tunnel to `open_ssh_tunnel`.

**Architecture:** Nothing in `src/teamster/libraries/powerschool/sis/odbc/` or
`src/dbt/powerschool/models/sis/staging/odbc/` changes — they are archived by
removing every reference to them (unreferenced Python modules never import;
disabled dbt models never build). Deletion is limited to Miami-specific dead
code. Downstream kipptaf/Miami-fldoe reads switch to hardcoded-schema BQ-native
sources over the frozen dataset.

**Tech Stack:** Dagster code locations, dbt (BigQuery), dagster-cloud.yaml K8s
config, GitHub Actions deploy workflows.

**Spec:**
`docs/superpowers/specs/2026-07-17-powerschool-odbc-teardown-design.md`

## Global Constraints

- ALL file edits target the worktree:
  `/workspaces/teamster/.worktrees/cbini/chore/claude-powerschool-odbc-teardown`
  (below: `{wt}`). Editing `/workspaces/teamster/<path>` silently dirties main.
- Git: `git -C {wt} ...` on every call. Commit messages use conventional commits
  and end with the Claude co-author line.
- dbt: `uv run dbt <cmd> --project-dir {wt}/src/dbt/<project>` from the main
  repo. Each project needs `uv run dbt deps --project-dir ...` once in a fresh
  worktree.
- Python: `VIRTUAL_ENV= uv --directory {wt} run python ...` /
  `VIRTUAL_ENV= uv --directory {wt} run pytest ...`.
- Trunk: binary `/workspaces/teamster/.trunk/tools/trunk`, run with cwd inside
  the worktree; `check --force --no-fix </dev/null` for verification.
- Do NOT modify anything under `src/teamster/libraries/powerschool/sis/odbc/`,
  `src/dbt/powerschool/models/` (models are archives), or
  `tests/libraries/powerschool/sis/odbc/` — archive is byte-for-byte.
- Do NOT touch `open_ssh_tunnel_paramiko`'s implementation body — rename only.
- The frozen `kippmiami_powerschool` BigQuery dataset must never be dropped.

---

### Task 1: dbt powerschool package — default the odbc variant off

**Files:**

- Modify: `{wt}/src/dbt/powerschool/dbt_project.yml`
- Modify: `{wt}/src/dbt/kippnewark/dbt_project.yml`
- Modify: `{wt}/src/dbt/kippcamden/dbt_project.yml`
- Modify: `{wt}/src/dbt/kipppaterson/dbt_project.yml`

**Interfaces:**

- Produces: package-level defaults `models...odbc.+enabled: false` and
  `sources...odbc.+enabled: false` that Task 2 relies on when Miami stops
  overriding them.

- [ ] **Step 1: Flip the package defaults**

In `{wt}/src/dbt/powerschool/dbt_project.yml`, change the `odbc` models block
(currently `+enabled: true`) and add a `sources:` section. Final file tail:

```yaml
models:
  +schema: powerschool
  powerschool:
    sis:
      staging:
        +contract:
          enforced: true
        # ARCHIVED (#4442): the ODBC ingestion path is retired; models are
        # kept in-tree for reference. No district enables this variant.
        odbc:
          +enabled: false
        sftp:
          +enabled: false
        dlt:
          +enabled: false

sources:
  powerschool:
    sis:
      staging:
        # ARCHIVED (#4442): see models note above.
        odbc:
          +enabled: false
```

- [ ] **Step 2: Remove the now-redundant NJ district odbc overrides**

Each district previously had to disable odbc itself; the package default now
does it. Remove ONLY the `odbc:` keys (and their `+enabled: false` child) —
leave `sftp:` / `dlt:` keys untouched:

- `{wt}/src/dbt/kippnewark/dbt_project.yml` — models block (~line 90) and
  sources block (~line 129)
- `{wt}/src/dbt/kippcamden/dbt_project.yml` — models block (~line 72) and
  sources block (~line 97)
- `{wt}/src/dbt/kipppaterson/dbt_project.yml` — models block (~line 94) and
  sources block (~line 157; keep the `sftp: powerschool_sftp:` table entries
  below it)

- [ ] **Step 3: Verify the three NJ districts still parse**

```bash
wt=/workspaces/teamster/.worktrees/cbini/chore/claude-powerschool-odbc-teardown
for p in kippnewark kippcamden kipppaterson; do
  uv run dbt deps --project-dir "$wt/src/dbt/$p"
  uv run dbt parse --project-dir "$wt/src/dbt/$p"
done
```

Expected: each parse completes with no errors (warnings about tests are fine).

- [ ] **Step 4: Commit**

```bash
git -C "$wt" add src/dbt/powerschool/dbt_project.yml src/dbt/kippnewark/dbt_project.yml src/dbt/kippcamden/dbt_project.yml src/dbt/kipppaterson/dbt_project.yml
git -C "$wt" commit -m "refactor(powerschool): archive dbt odbc variant, disabled by default

Refs #4442

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: kippmiami dbt teardown + frozen FLEID source

**Files:**

- Modify: `{wt}/src/dbt/kippmiami/packages.yml`
- Modify: `{wt}/src/dbt/kippmiami/dbt_project.yml`
- Delete: `{wt}/src/dbt/kippmiami/models/powerschool/` (whole dir)
- Delete: `{wt}/src/dbt/kippmiami/models/extracts/powerschool/` (whole dir)
- Modify: `{wt}/src/dbt/kippmiami/models/extracts/sources.yml`
- Modify: `{wt}/src/dbt/kippmiami/models/fldoe/sources-bigquery.yml`
- Modify:
  `{wt}/src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql`

**Interfaces:**

- Consumes: Task 1's package defaults (Miami stops overriding them).
- Produces: source `kippmiami_powerschool` with tables
  `stg_powerschool__students`, `stg_powerschool__u_studentsuserfields` —
  referenced as `source("kippmiami_powerschool", "<table>")`.

- [ ] **Step 1: Remove the powerschool package import**

In `{wt}/src/dbt/kippmiami/packages.yml`, delete the line
`  - local: ../powerschool`. (`dbt_utils` still resolves via the focus /
deanslist / finalsite / iready packages.)

- [ ] **Step 2: Remove Miami's powerschool config blocks**

In `{wt}/src/dbt/kippmiami/dbt_project.yml`:

1. Delete the `powerschool:` block under `models: kippmiami:` (lines 44–50:
   `+materialized`, `+schema: powerschool`, `sis: staging: contract`).
1. Delete the entire `powerschool:` block under top-level `models:` (lines
   66–125: `+materialized: table` through the last
   `stg_powerschool__u_storedgrades_de: +enabled: false`).
1. Delete the entire top-level `sources:` block (lines 134–193) — its only child
   is `powerschool:`.

- [ ] **Step 3: Delete Miami's powerschool model dirs**

```bash
git -C "$wt" rm -r src/dbt/kippmiami/models/powerschool src/dbt/kippmiami/models/extracts/powerschool
```

(Removes the `stg_powerschool__u_studentsuserfields` override and both
`rpt_powerschool__autocomm_*` wrappers + their properties yml.)

- [ ] **Step 4: Remove the autocomm entries from the extracts source**

In `{wt}/src/dbt/kippmiami/models/extracts/sources.yml`, delete the three
`kipptaf_extracts` table entries `rpt_powerschool__autocomm_teachers`,
`rpt_powerschool__autocomm_students`, and
`rpt_powerschool__autocomm_students_iep` (each: `- name:` line + its
`config: meta: dagster:` block). The five `rpt_focus__*` entries stay.

- [ ] **Step 5: Add the frozen source for the FLEID lookup**

Append to `{wt}/src/dbt/kippmiami/models/fldoe/sources-bigquery.yml` (same
`sources:` list as the existing `fldoe` entry):

```yaml
- name: kippmiami_powerschool
  description: >-
    Frozen pre-Focus PowerSchool archive (final ODBC pull 2026-07-01; SIS moved
    to Focus). Never rebuilt — the kippmiami_powerschool dataset must not be
    dropped. Read only for the student_number-fleid lookup until a Focus-based
    FLEID lookup replaces it.
  schema: kippmiami_powerschool
  tables:
    - name: stg_powerschool__students
      config:
        meta:
          dagster:
            group: powerschool
            asset_key:
              - kippmiami
              - powerschool
              - stg_powerschool__students
    - name: stg_powerschool__u_studentsuserfields
      config:
        meta:
          dagster:
            group: powerschool
            asset_key:
              - kippmiami
              - powerschool
              - stg_powerschool__u_studentsuserfields
```

(The `asset_key` meta keeps the historical Dagster lineage keys — matches the
`kippmiami_fldoe_archive` precedent in kipptaf. The keys become external assets
once Task 4 deletes their definitions; Dagster tolerates this.)

- [ ] **Step 6: Repoint the FLEID lookup refs**

In `int_fldoe__all_assessments.sql`, inside the `fleid_lookup_raw` CTE, change
exactly two lines:

```sql
        from {{ source("kippmiami_powerschool", "stg_powerschool__students") }} as s
        inner join
            {{ source("kippmiami_powerschool", "stg_powerschool__u_studentsuserfields") }} as suf
```

(Previously `ref("stg_powerschool__students")` /
`ref("stg_powerschool__u_studentsuserfields")`. Everything else in the file is
unchanged.)

- [ ] **Step 7: Verify Miami parses and the model compiles against the frozen
      schema**

```bash
uv run dbt deps --project-dir "$wt/src/dbt/kippmiami"
uv run dbt parse --project-dir "$wt/src/dbt/kippmiami"
uv run dbt compile --select int_fldoe__all_assessments --project-dir "$wt/src/dbt/kippmiami"
grep -o '`teamster-332318`.`kippmiami_powerschool`.`stg_powerschool__[a-z_]*`' \
  "$wt/src/dbt/kippmiami/target/compiled/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql" | sort -u
```

Expected: parse/compile succeed; grep prints both frozen table paths.

- [ ] **Step 8: Commit**

```bash
git -C "$wt" add -A src/dbt/kippmiami
git -C "$wt" commit -m "chore(kippmiami): drop powerschool dbt package, read frozen archive for fleid lookup

Refs #4441

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: kipptaf — convert Miami powerschool source to frozen BQ-native

**Files:**

- Modify: `{wt}/src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`

**Interfaces:**

- Consumes: nothing from other tasks (independent).
- Produces: source `kippmiami_powerschool` resolving to the literal
  `kippmiami_powerschool` schema in EVERY target (dev/staging/prod), so dbt
  Cloud CI stops expecting `zz_stg_kippmiami_powerschool` clones.

- [ ] **Step 1: Hardcode the schema and describe the freeze**

Replace the source header (name + 4-line conditional `schema:` block) with:

```yaml
sources:
  - name: kippmiami_powerschool
    description: >-
      Frozen pre-Focus PowerSchool archive (final ODBC pull 2026-07-01; Miami's
      SIS moved to Focus). Never rebuilt — the kippmiami_powerschool dataset
      must not be dropped. Declared BQ-native (plain schema, no target branch)
      so every target reads the frozen prod tables directly.
    schema: kippmiami_powerschool
    tables:
```

ALL ~95 `tables:` entries below stay exactly as-is, including their
`meta.dagster.asset_key` blocks (historical lineage keys — same rationale as
Task 2 Step 5).

- [ ] **Step 2: Verify kipptaf parses and resolves the frozen schema in
      staging**

```bash
uv run dbt deps --project-dir "$wt/src/dbt/kipptaf"
uv run dbt parse --project-dir "$wt/src/dbt/kipptaf"
uv run dbt compile --select stg_powerschool__schools --target staging --project-dir "$wt/src/dbt/kipptaf"
grep -c 'zz_stg_kippmiami_powerschool' \
  "$wt/src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql" || true
grep -c '`kippmiami_powerschool`' \
  "$wt/src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql"
```

Expected: first grep prints `0` (no staging-prefixed Miami schema); second
prints `1` or more.

- [ ] **Step 3: Commit**

```bash
git -C "$wt" add src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
git -C "$wt" commit -m "refactor(kipptaf): read Miami powerschool as frozen BQ-native source

Refs #4441 #4442

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: kippmiami Dagster teardown + shared resource unwiring

**Files:**

- Delete: `{wt}/src/teamster/code_locations/kippmiami/powerschool/` (whole dir)
- Delete:
  `{wt}/src/teamster/code_locations/kippmiami/extracts/config/powerschool.yaml`
- Modify: `{wt}/src/teamster/code_locations/kippmiami/definitions.py`
- Modify: `{wt}/src/teamster/code_locations/kippmiami/extracts/assets.py`
- Modify: `{wt}/src/teamster/code_locations/kippmiami/extracts/jobs.py`
- Modify: `{wt}/src/teamster/code_locations/kippmiami/extracts/schedules.py`
- Modify: `{wt}/src/teamster/core/resources.py`
- Delete: `{wt}/tests/assets/test_assets_powerschool_sis.py`
- Delete: `{wt}/tests/schedules/test_schedules_powerschool_sis.py`
- Delete: `{wt}/tests/sensors/test_sensors_powerschool_sis.py`
- Modify: `{wt}/tests/utils.py`

**Interfaces:**

- Consumes: nothing (kippmiami-scoped + core unwiring).
- Produces: `core/resources.py` without `DB_POWERSCHOOL` /
  `PowerSchoolODBCResource` — the odbc library loses its last importer.
  `get_powerschool_ssh_resource()` and `get_powerschool_oracle_resource()`
  remain exported (dlt districts).

- [ ] **Step 1: Delete Miami's powerschool module and extract config**

```bash
git -C "$wt" rm -r src/teamster/code_locations/kippmiami/powerschool
git -C "$wt" rm src/teamster/code_locations/kippmiami/extracts/config/powerschool.yaml
```

- [ ] **Step 2: Rewrite definitions.py**

Full new content of `{wt}/src/teamster/code_locations/kippmiami/definitions.py`:

```python
from dagster import (
    AssetSelection,
    AutomationConditionSensorDefinition,
    Definitions,
    load_assets_from_modules,
)
from dagster_k8s import k8s_job_executor

from teamster.code_locations.kippmiami import (
    CODE_LOCATION,
    DBT_PROJECT,
    couchdrop,
    dbt,
    deanslist,
    dlt,
    extracts,
    finalsite,
    fldoe,
    iready,
    renlearn,
)
from teamster.code_locations.kippmiami.resources import FINALSITE_RESOURCE, SSH_FOCUS
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DEANSLIST_RESOURCE,
    DLT_RESOURCE,
    GCS_RESOURCE,
    GOOGLE_DRIVE_RESOURCE,
    SSH_COUCHDROP,
    SSH_IREADY,
    SSH_RENLEARN,
    get_dbt_cli_resource,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
    get_io_manager_gcs_pickle,
)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            dbt,
            dlt,
            extracts,
            deanslist,
            finalsite,
            fldoe,
            iready,
            renlearn,
        ]
    ),
    schedules=[
        *dlt.schedules,
        *extracts.schedules,
        *deanslist.schedules,
        *finalsite.schedules,
    ],
    sensors=[
        *couchdrop.sensors,
        *iready.sensors,
        *renlearn.sensors,
        AutomationConditionSensorDefinition(
            name=f"{CODE_LOCATION}__automation_condition_sensor",
            target=AssetSelection.all(),
        ),
    ],
    resources={
        "db_bigquery": BIGQUERY_RESOURCE,
        "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
        "deanslist": DEANSLIST_RESOURCE,
        "dlt": DLT_RESOURCE,
        "finalsite": FINALSITE_RESOURCE,
        "gcs": GCS_RESOURCE,
        "google_drive": GOOGLE_DRIVE_RESOURCE,
        "io_manager_gcs_avro": get_io_manager_gcs_avro(CODE_LOCATION),
        "io_manager_gcs_file": get_io_manager_gcs_file(CODE_LOCATION),
        "io_manager": get_io_manager_gcs_pickle(CODE_LOCATION),
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_focus": SSH_FOCUS,
        "ssh_iready": SSH_IREADY,
        "ssh_renlearn": SSH_RENLEARN,
    },
)
```

- [ ] **Step 3: Trim the extracts module to focus-only**

`{wt}/src/teamster/code_locations/kippmiami/extracts/assets.py` — full new
content:

```python
import pathlib

from dagster import config_from_files

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.extracts.assets import build_bigquery_query_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

focus_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/focus.yaml"])["assets"]
]

assets = [
    *focus_extract_assets,
]
```

`{wt}/src/teamster/code_locations/kippmiami/extracts/jobs.py` — full new
content:

```python
from dagster import define_asset_job

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.extracts.assets import focus_extract_assets

focus_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__focus__asset_job",
    selection=focus_extract_assets,
)
```

`{wt}/src/teamster/code_locations/kippmiami/extracts/schedules.py` — full new
content:

```python
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    cron_schedule="0 5 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
```

(`extracts/__init__.py` is unchanged — it re-exports `assets` and `schedules`.)

- [ ] **Step 4: Unwire the odbc library from core/resources.py**

In `{wt}/src/teamster/core/resources.py`:

1. Delete the import line
   `from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource`
   (line 15).
1. Delete the `DB_POWERSCHOOL = PowerSchoolODBCResource(...)` block (lines
   92–98). Keep `get_powerschool_ssh_resource()` and
   `get_powerschool_oracle_resource()`.

- [ ] **Step 5: Delete the dead ODBC-era integration tests**

These three files import `code_locations/<loc>/powerschool` module shapes that
no longer exist (NJ districts now expose `powerschool/sis/dlt`; Miami's module
is deleted in Step 1) — they are pre-migration leftovers:

```bash
git -C "$wt" rm tests/assets/test_assets_powerschool_sis.py tests/schedules/test_schedules_powerschool_sis.py tests/sensors/test_sensors_powerschool_sis.py
```

Then in `{wt}/tests/utils.py`, delete the two helpers those files consumed —
`get_ssh_powerschool_resource()` and `get_db_powerschool_resource()` — plus the
now-unused imports (`PowerSchoolODBCResource`; also `SSHResource` / `EnvVar` /
`check` IF nothing else in the file uses them — check remaining content before
removing each import). The archived unit suite
`tests/libraries/powerschool/sis/odbc/` has its own fixtures and stays.

- [ ] **Step 6: Verify all four locations import**

```bash
wt=/workspaces/teamster/.worktrees/cbini/chore/claude-powerschool-odbc-teardown
for loc in kippmiami kippnewark kippcamden kipppaterson; do
  VIRTUAL_ENV= uv --directory "$wt" run dagster-dbt project prepare-and-package \
    --file "src/teamster/code_locations/$loc/__init__.py"
  VIRTUAL_ENV= uv --directory "$wt" run python -c \
    "import teamster.code_locations.$loc.definitions; print('$loc OK')"
done
```

Expected: `<loc> OK` for all four. (kipptaf is not importable in the codespace
for unrelated reasons — dlt credential specs — and is not touched by this task.)

- [ ] **Step 7: Commit**

```bash
git -C "$wt" add -A src/teamster tests
git -C "$wt" commit -m "chore(kippmiami): remove PowerSchool ODBC Dagster stack

Deletes Miami's powerschool module, autocomm extract wiring, and the
DB_POWERSCHOOL core resource; drops the dead ODBC-era integration tests.
The odbc library itself is archived in place with zero importers.

Refs #4441 #4442

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: SSH — remove sshpass tunnel, rename paramiko tunnel

**Files:**

- Modify: `{wt}/src/teamster/libraries/ssh/resources.py`
- Modify: `{wt}/src/teamster/libraries/dlt/powerschool/assets.py:277`
- Modify: `{wt}/tests/libraries/test_ssh_paramiko_tunnel.py`
- Modify: `{wt}/src/teamster/libraries/ssh/CLAUDE.md`

**Interfaces:**

- Produces:
  `SSHResource.open_ssh_tunnel(local_port: int = 1521, remote_port: int = 1521)`
  — a context manager yielding the bound local port (the former
  `open_ssh_tunnel_paramiko`, body unchanged).

- [ ] **Step 1: Edit libraries/ssh/resources.py**

1. Delete the `SSHTunnelError` class (lines 74–75; no other module references
   it).
1. Delete the entire sshpass `open_ssh_tunnel()` method (lines 197–247).
1. Rename `open_ssh_tunnel_paramiko` → `open_ssh_tunnel` (line 250). Update its
   docstring first paragraph to:

   ```text
   In-process SSH local port forward.

   Replaced the retired sshpass-subprocess tunnel (#4442): no password file
   mount, no readiness race, host-key verification kept (get_connection
   handles legacy ssh-rsa and transient-failure retry). Yields the bound
   local port; pass local_port=0 for an ephemeral port.
   ```

1. Remove now-unused imports: `subprocess`, `time` (verify with a grep that no
   other use remains in the file before removing each).
1. Keep the `test: bool` field on `SSHResource` (other resource construction
   paths set it).

- [ ] **Step 2: Update the one live caller**

`{wt}/src/teamster/libraries/dlt/powerschool/assets.py` line 277:

```python
        with ssh_powerschool.open_ssh_tunnel():
```

(was `ssh_powerschool.open_ssh_tunnel_paramiko()`).

- [ ] **Step 3: Update the tunnel test file**

In `{wt}/tests/libraries/test_ssh_paramiko_tunnel.py`, replace all four
`open_ssh_tunnel_paramiko` occurrences (three call sites at lines 64/114/168,
one comment at line 19) and the assertion message at line 186 with
`open_ssh_tunnel`.

- [ ] **Step 4: Update libraries/ssh/CLAUDE.md**

Rewrite the stale statements: the capability bullet for the sshpass
`open_ssh_tunnel()` subprocess, the `test` field's purpose row, the "only called
by the PowerSchool ODBC library" note, and the "remains for the incumbent ODBC
districts" note. State instead: `open_ssh_tunnel()` is the in-process paramiko
forward used by the dlt PowerSchool path (renamed from
`open_ssh_tunnel_paramiko` in #4442; the sshpass subprocess tunnel is retired —
the archived odbc library's `open_ssh_tunnel()` calls predate the rename and
refer to the removed sshpass semantics). Keep the legacy-rsa and rekey
documentation unchanged.

- [ ] **Step 5: Run the affected test suites**

```bash
VIRTUAL_ENV= uv --directory "$wt" run pytest \
  tests/libraries/test_ssh_paramiko_tunnel.py \
  tests/resources/test_resource_ssh_rekey.py \
  tests/libraries/powerschool \
  tests/libraries/test_dlt_powerschool_assets.py \
  tests/libraries/test_powerschool_dlt_extract_workers.py -v
```

Expected: all pass. The archived odbc unit tests mock the SSH resource (`Mock`
auto-creates `open_ssh_tunnel`), so the rename does not break them.

- [ ] **Step 6: Commit**

```bash
git -C "$wt" add src/teamster/libraries/ssh src/teamster/libraries/dlt/powerschool/assets.py tests/libraries/test_ssh_paramiko_tunnel.py
git -C "$wt" commit -m "refactor(ssh): retire sshpass tunnel, rename paramiko forward to open_ssh_tunnel

Refs #4442 #4424

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Infra — secrets, Dockerfile, deploy workflow

**Files:**

- Modify: `{wt}/src/teamster/code_locations/kippmiami/dagster-cloud.yaml`
- Modify: `{wt}/src/teamster/code_locations/kippnewark/dagster-cloud.yaml`
- Modify: `{wt}/src/teamster/code_locations/kippcamden/dagster-cloud.yaml`
- Modify: `{wt}/.k8s/1password/items.yaml`
- Modify: `{wt}/Dockerfile`
- Modify: `{wt}/.github/workflows/deploy-prod-kippmiami.yaml`

**Interfaces:** none (config only).

- [ ] **Step 1: kippmiami dagster-cloud.yaml — drop all PowerSchool config**

1. In `volume_mounts`, delete the `secret-volume` entry (name/readOnly/
   mountPath, lines 12–14). Keep `deanslist-keys`.
1. In `volumes`, delete the `secret-volume` projected block (lines 19–26 — the
   `op-ps-ssh-kippmiami` password-file projection). Keep `deanslist-keys`.
1. In `container_context.k8s.server_k8s_config.container_config.env`, delete
   every `PS_DB_*` and `PS_SSH_*` entry (nine entries: `PS_DB_PASSWORD`,
   `PS_SSH_PASSWORD`, `PS_SSH_PORT`, `PS_SSH_REMOTE_BIND_HOST`,
   `PS_SSH_USERNAME`, `PS_DB_HOST`, `PS_DB_DATABASE`, `PS_DB_PORT`,
   `PS_DB_USERNAME`, `PS_SSH_HOST` — ten names total).
1. Same deletion in `run_k8s_config.container_config.env` (same ten names).
1. All `FOCUS_*`, `FINALSITE_*`, `COUCHDROP_*`, `IREADY_*`, `RENLEARN_*` entries
   stay.

- [ ] **Step 2: kippnewark + kippcamden dagster-cloud.yaml — drop the dead
      password-file mount**

In each file: delete the `secret-volume` entry from `volume_mounts` (lines
11–13) and the `secret-volume` projected block from `volumes` (lines 18–26 — the
`op-ps-ssh-<district>` `powerschool_ssh_password.txt` projection). Keep
`deanslist-keys` in both lists, and keep ALL `PS_DB_*` / `PS_SSH_*` environment
entries — the dlt tunnel reads them.

- [ ] **Step 3: Remove Miami's PowerSchool 1Password items**

In `{wt}/.k8s/1password/items.yaml`, delete the two `OnePasswordItem` documents
named `op-ps-db-kippmiami` (itemPath
`vaults/Data Team/items/PowerSchool DB - Miami`) and `op-ps-ssh-kippmiami`
(itemPath `vaults/Data Team/items/PowerSchool SSH - Miami`) — each is a 7-line
`---`-separated document. All other districts' `op-ps-*` items stay (dlt env
vars read them). Note for the PR body: cluster-side deletion
(`kubectl delete onepassworditem ...`) is handed to the user per `.k8s/`
conventions.

- [ ] **Step 4: Dockerfile — drop the tunnel binaries**

Line 16: change

```dockerfile
        openssh-client sshpass build-essential git \
```

to

```dockerfile
        build-essential git \
```

(Verified: the sshpass subprocess was the only consumer of both packages; the
paramiko tunnel is pure Python; git/dbt fetches are https.)

- [ ] **Step 5: deploy-prod-kippmiami.yaml — drop stale paths**

Delete three lines: `- src/dbt/powerschool/**` (line 23, push paths — Miami no
longer imports the package) and
`- src/teamster/libraries/powerschool/sis/odbc/**` from BOTH the push paths
(line 36) and the pull_request paths (line 57). Other locations' workflows are
untouched.

- [ ] **Step 6: Verify + grep sweep**

```bash
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/code_locations/kippmiami/dagster-cloud.yaml \
  src/teamster/code_locations/kippnewark/dagster-cloud.yaml \
  src/teamster/code_locations/kippcamden/dagster-cloud.yaml \
  .k8s/1password/items.yaml Dockerfile \
  .github/workflows/deploy-prod-kippmiami.yaml </dev/null
grep -rn "ps-db-kippmiami\|ps-ssh-kippmiami" "$wt/src" "$wt/.k8s" || echo CLEAN
grep -rn "sshpass" "$wt/Dockerfile" || echo CLEAN
```

Expected: trunk "No issues"; both greps print `CLEAN`.

- [ ] **Step 7: Commit**

```bash
git -C "$wt" add -u
git -C "$wt" commit -m "chore(infra): remove PowerSchool ODBC secrets, tunnel binaries, stale deploy paths

Refs #4441 #4442

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Docs/CLAUDE.md sweep + full verification battery

**Files:**

- Modify: `{wt}/src/teamster/CLAUDE.md`
- Modify: `{wt}/src/teamster/code_locations/kippmiami/CLAUDE.md`
- Modify: `{wt}/src/dbt/kippmiami/CLAUDE.md`
- Modify: `{wt}/src/dbt/powerschool/CLAUDE.md`
- Possibly modify: `{wt}/docs/reference/architecture.md`,
  `{wt}/docs/guides/dbt-development.md` (grep-dependent)

**Interfaces:** none.

- [ ] **Step 1: Update stale CLAUDE.md claims**

1. `src/teamster/CLAUDE.md` — Multi-access library row: change
   `powerschool (ODBC + SFTP + API)` to
   `powerschool (dlt + SFTP + API; ODBC archived)`.
1. `code_locations/kippmiami/CLAUDE.md` — delete the `powerschool` row from the
   Active Integrations table and the whole "PowerSchool Configuration" section;
   add one line under Florida-Specific or Identity: "PowerSchool (pre-Focus SIS)
   is retired — frozen archive in BigQuery dataset `kippmiami_powerschool`; do
   not drop."
1. `src/dbt/kippmiami/CLAUDE.md` — remove `powerschool/` and
   `extracts/powerschool/` from the Model Structure tree and the "PowerSchool
   data source: ODBC" line; note the `kippmiami_powerschool` frozen source used
   by `int_fldoe__all_assessments`, and that `powerschool` is no longer in
   `packages.yml`.
1. `src/dbt/powerschool/CLAUDE.md` — Model Structure: change the `odbc/` comment
   from "(enabled by default)" to "(ARCHIVED — disabled by default; no district
   builds it)". Update the sentence "Each district project overrides
   `odbc.+enabled` and `sftp.+enabled`" to reflect that only `sftp`/`dlt` are
   toggled now.

- [ ] **Step 2: Sweep docs/ for stale claims**

```bash
grep -rn "odbc\|ODBC" "$wt/docs/reference/architecture.md" "$wt/docs/guides/dbt-development.md"
```

Update any sentence that claims Miami ingests PowerSchool via ODBC or that the
ODBC path is live (describe it as archived). Do NOT regenerate
`docs/reference/automations.md` (generated; codespace drops locations) — note in
the PR body that it should be regenerated in a full environment.

- [ ] **Step 3: Final repo-wide grep sweeps**

```bash
grep -rn "DB_POWERSCHOOL" "$wt/src" "$wt/tests" || echo CLEAN
grep -rn "open_ssh_tunnel_paramiko" "$wt/src" "$wt/tests" "$wt/docs" || echo CLEAN
grep -rn "powerschool_odbc\|sis/odbc\|sis\.odbc" "$wt/src" "$wt/tests" "$wt/docs" "$wt/.github" \
  | grep -v "src/teamster/libraries/powerschool/sis/odbc/" \
  | grep -v "src/dbt/powerschool/" \
  | grep -v "tests/libraries/powerschool/sis/odbc/" \
  | grep -v "docs/superpowers/" || echo CLEAN
```

Expected: `CLEAN` for the first two; the third may surface CLAUDE.md / docs
lines that intentionally describe the archive — verify each is a true archive
description, not live wiring.

- [ ] **Step 4: Full verification battery**

```bash
# dbt: all five projects parse
for p in powerschool kippnewark kippcamden kipppaterson kippmiami kipptaf; do
  uv run dbt parse --project-dir "$wt/src/dbt/$p" || echo "PARSE FAIL: $p"
done
# Dagster: four locations import (see Task 4 Step 6 for the loop)
# Tests: affected suites green (see Task 5 Step 5)
# Trunk: check every modified/created md + yaml file
cd "$wt" && git diff --name-only origin/main...HEAD | \
  xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Note: `dbt parse --project-dir .../powerschool` standalone may fail on
unresolvable vars (expected for source-system packages, per `src/dbt/CLAUDE.md`)
— district parses are the real gate; do not chase a standalone-package parse
failure.

- [ ] **Step 5: Commit**

```bash
git -C "$wt" add -u
git -C "$wt" commit -m "docs: update CLAUDE.md and docs for PowerSchool ODBC archive

Refs #4441 #4442

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-plan (not tasks — handled at PR time)

1. PR closes BOTH issues (`Closes #4441`, `Closes #4442`) and notes the two
   approved deviations from the issue text: the Python/dbt odbc code is archived
   in place rather than deleted, and `openssh-client` is removed alongside
   `sshpass`.
1. PR body notes: the archived odbc lib's `open_ssh_tunnel()` calls refer to the
   removed sshpass semantics; `docs/reference/automations.md` needs regeneration
   in a full environment; cluster-side deletion of the two Miami
   OnePasswordItems is a manual user step.
1. File the follow-up issue: Focus-based FLEID lookup for
   `int_fldoe__all_assessments` (new Miami students have no FLEID mapping in the
   frozen archive).
1. Comment on #4424 after merge: part 1 (centralized SSH construction) already
   landed with the dlt migrations; part 2's subject is now named
   `open_ssh_tunnel` (paramiko), sshpass path removed.
