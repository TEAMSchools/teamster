# Finalsite NJ Contacts — Phase 1 (Newark Ingestion + Discovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Finalsite Contacts API `contacts` asset into the `kippnewark`
Dagster code location (mirroring the existing `kippmiami` integration), deploy
it, and run the discovery queries that unblock the dbt modeling phase.

**Architecture:** `kippnewark` gains a location-local `resources.py` holding a
`FinalsiteResource` instance, a `contacts` Avro asset built from the shared
`build_finalsite_asset()` factory, a daily schedule, and the k8s secret env-var
wiring in `dagster-cloud.yaml`. No library changes in this phase — the
`Relationship` schema extension for the rank field is deferred to Phase 3, after
discovery reveals the field name.

**Tech Stack:** Dagster (Python 3.13), `dagster-k8s`, `py_avro_schema`, GCS Avro
IO manager, BigQuery external tables.

## Global Constraints

- **Python**: always `uv run` — never bare `python`/`python3`.
  `requires-python = ">=3.13"`.
- **Worktree**: all work happens in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj`.
  Every `git` call uses `git -C <worktree>`; every Python call uses
  `VIRTUAL_ENV= uv --directory <worktree> run python ...` with an absolute
  script path (or run from the worktree cwd).
- **Asset key convention**: `[code_location, integration, asset_name]` →
  `["kippnewark", "finalsite", "contacts"]`.
- **Library/code-location split**: no edits to `libraries/finalsite/` in this
  phase. Reuse `build_finalsite_asset()` and `FinalsiteResource` unchanged.
- **Do not commit secret VALUES.** `dagster-cloud.yaml` references k8s secret
  NAMES and keys only (`op-finalsite-api-kippnewark`), never the credential
  itself.
- **Conventional commits**; branch `cbini/feat/claude-finalsite-contacts-nj`
  (already created, linked to #4346).

## Confirmed config values

- **Finalsite server subdomain for Newark:** `kippnewark.fsenrollment.com`
  (confirmed) — matches the `server=CODE_LOCATION` default, so Task 1 needs no
  change.
- **Newark 1Password item:** `vaults/Data Team/items/Finalsite API - Newark`
  (confirmed). The `op-finalsite-api-kippnewark` k8s secret does NOT exist yet —
  Task 4 declares the `OnePasswordItem` that syncs it. The field internal names
  are ASSUMED to be `username` (credential id) / `password` (secret), mirroring
  the Miami item; Task 4 Step 4 verifies this against the synced secret before
  Task 5 wires `secretKeyRef.key`.

---

## Task 1: Newark `FinalsiteResource`

`kippnewark` currently has no `resources.py` — every resource comes from
`core.resources`. Finalsite is location-specific (per-instance credentials), so
it needs a location-local resource file, exactly as `kippmiami` has.

**Files:**

- Create: `src/teamster/code_locations/kippnewark/resources.py`

**Interfaces:**

- Produces: `FINALSITE_RESOURCE: FinalsiteResource` — imported by
  `definitions.py` (Task 3) as the `"finalsite"` resource.

- [ ] **Step 1: Create the resource file**

Create `src/teamster/code_locations/kippnewark/resources.py`:

```python
from dagster import EnvVar

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.finalsite.api.resources import FinalsiteResource

# NOTE: server defaults to CODE_LOCATION ("kippnewark") →
# kippnewark.fsenrollment.com. Confirm Newark's actual Finalsite subdomain
# before deploy (see plan "Open config value"); pass an explicit string here if
# it differs.
FINALSITE_RESOURCE = FinalsiteResource(
    server=CODE_LOCATION,
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID"),
    secret=EnvVar("FINALSITE_SECRET"),
)
```

- [ ] **Step 2: Validate it imports**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  run python -c "from teamster.code_locations.kippnewark.resources import FINALSITE_RESOURCE; print(type(FINALSITE_RESOURCE).__name__)"
```

Expected: prints `FinalsiteResource` with no import error.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  add src/teamster/code_locations/kippnewark/resources.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  commit -m "feat(kippnewark): add FinalsiteResource. Refs #4346"
```

---

## Task 2: Newark `contacts` asset, schema, and schedule

Add the Avro schema, the asset, and a daily schedule to the existing
`kippnewark/finalsite/` module, and export the schedule from its `__init__.py`.
`kippnewark/finalsite/schema.py` currently defines only `STATUS_REPORT_SCHEMA`;
`assets.py` currently defines only the `status_report` SFTP asset; there is no
`schedules.py` yet.

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/finalsite/schema.py`
- Modify: `src/teamster/code_locations/kippnewark/finalsite/assets.py`
- Create: `src/teamster/code_locations/kippnewark/finalsite/schedules.py`
- Modify: `src/teamster/code_locations/kippnewark/finalsite/__init__.py`

**Interfaces:**

- Consumes: `build_finalsite_asset()` (library), `Contact` Pydantic model
  (library), `CODE_LOCATION` / `LOCAL_TIMEZONE` (unchanged; `LOCAL_TIMEZONE`
  must be added to the `kippnewark` `__init__.py` import in Step 3).
- Produces: `assets` list (now includes `contacts`), `schedules` list — both
  consumed by `definitions.py` (Task 3).

- [ ] **Step 1: Add `CONTACTS_SCHEMA` to `schema.py`**

Edit `src/teamster/code_locations/kippnewark/finalsite/schema.py` to import the
`Contact` model and generate its Avro schema. Final file contents:

```python
import json

import py_avro_schema

from teamster.libraries.finalsite.api.schema import Contact
from teamster.libraries.finalsite.sftp.schema import StatusReport

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STATUS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StatusReport, options=pas_options)
)

CONTACTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Contact, options=pas_options)
)
```

- [ ] **Step 2: Add the `contacts` asset to `assets.py`**

Edit `src/teamster/code_locations/kippnewark/finalsite/assets.py`. Add the
`build_finalsite_asset` and `CONTACTS_SCHEMA` imports, define the `contacts`
asset, and add it to the `assets` list. The `status_report` asset stays
unchanged. Resulting imports + additions:

```python
from teamster.code_locations.kippnewark import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippnewark.finalsite.schema import (
    CONTACTS_SCHEMA,
    STATUS_REPORT_SCHEMA,
)
from teamster.libraries.finalsite.api.assets import build_finalsite_asset
from teamster.libraries.finalsite.sftp.assets import (
    get_finalsite_school_year_partition_keys,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

# ... existing status_report asset unchanged ...

contacts = build_finalsite_asset(
    code_location=CODE_LOCATION,
    asset_name="contacts",
    schema=CONTACTS_SCHEMA,
    params={"includes": "contacts.relationships"},
)

assets = [
    status_report,
    contacts,
]
```

- [ ] **Step 3: Create `schedules.py`**

`kippnewark/__init__.py` currently exports `CODE_LOCATION` and
`CURRENT_FISCAL_YEAR` but not `LOCAL_TIMEZONE` — it IS defined there, so the
import works. Create
`src/teamster/code_locations/kippnewark/finalsite/schedules.py` mirroring
Miami's (daily 04:00 ET):

```python
from dagster import ScheduleDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE

finalsite_contacts_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__finalsite__contacts__daily_asset_job_schedule",
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{CODE_LOCATION}/finalsite/contacts"],
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
```

- [ ] **Step 4: Export `schedules` from `__init__.py`**

Edit `src/teamster/code_locations/kippnewark/finalsite/__init__.py` to match
Miami's export shape:

```python
from teamster.code_locations.kippnewark.finalsite.assets import assets
from teamster.code_locations.kippnewark.finalsite.schedules import schedules

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 5: Validate imports (schema generation + module load)**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  run python -c "from teamster.code_locations.kippnewark import finalsite; print(len(finalsite.assets), 'assets', len(finalsite.schedules), 'schedules')"
```

Expected: prints `2 assets 1 schedules` (Avro schema generation for `Contact`
succeeds, no import error).

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  add src/teamster/code_locations/kippnewark/finalsite/
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  commit -m "feat(kippnewark): add Finalsite contacts asset and daily schedule. Refs #4346"
```

---

## Task 3: Wire Finalsite into `kippnewark/definitions.py`

The asset auto-loads via `load_assets_from_modules([... finalsite ...])`
(already present). What is missing: the `"finalsite"` resource and the
`finalsite.schedules` registration.

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/definitions.py`

**Interfaces:**

- Consumes: `FINALSITE_RESOURCE` (Task 1), `finalsite.schedules` (Task 2).

- [ ] **Step 1: Import `FINALSITE_RESOURCE`**

Edit `src/teamster/code_locations/kippnewark/definitions.py`. After the
`from teamster.code_locations.kippnewark import (...)` block, add:

```python
from teamster.code_locations.kippnewark.resources import FINALSITE_RESOURCE
```

- [ ] **Step 2: Register the schedule**

In the `schedules=[...]` list, add `*finalsite.schedules,` (keep existing
entries):

```python
    schedules=[
        *extracts.schedules,
        *deanslist.schedules,
        *finalsite.schedules,
        *overgrad.schedules,
        *powerschool.schedules,
    ],
```

- [ ] **Step 3: Register the resource**

In the `resources={...}` dict, add the `"finalsite"` key (alphabetical slot,
after `"dbt_cli"`/`"deanslist"` and before `"gcs"`):

```python
        "finalsite": FINALSITE_RESOURCE,
```

- [ ] **Step 4: Validate the full code location**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  run dagster definitions validate -m teamster.code_locations.kippnewark.definitions
```

Expected: `Validation successful`. If it fails ONLY on missing env vars /
manifest (codespace has no prod secrets), fall back to the import check:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  run python -c "from teamster.code_locations.kippnewark.definitions import defs; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  add src/teamster/code_locations/kippnewark/definitions.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  commit -m "feat(kippnewark): register Finalsite resource and contacts schedule. Refs #4346"
```

---

## Task 4: Declare the Newark Finalsite 1Password item

The `op-finalsite-api-kippnewark` k8s secret does not exist. The
1Password-Connect operator creates each k8s secret from an `OnePasswordItem`
manifest declared in `.k8s/1password/items.yaml`. Add Newark's, mirroring the
Miami entry (lines 385-392). Applying the manifest to the cluster is a manual
`kubectl` step (Step 3) that needs cluster access — hand it to the user if
Claude lacks `kubectl` context.

**Files:**

- Modify: `.k8s/1password/items.yaml`

- [ ] **Step 1: Append the Newark `OnePasswordItem`**

Append to the end of `.k8s/1password/items.yaml` (each item is a `---`-separated
document; match the Miami finalsite entry shape exactly):

```yaml
---
apiVersion: onepassword.com/v1
kind: OnePasswordItem
metadata:
  name: op-finalsite-api-kippnewark
  namespace: dagster-cloud
spec:
  itemPath: vaults/Data Team/items/Finalsite API - Newark
```

- [ ] **Step 2: Validate YAML + trunk-check**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj && \
  VIRTUAL_ENV= uv run python -c "import yaml; docs=list(yaml.safe_load_all(open('.k8s/1password/items.yaml'))); print(sum(1 for d in docs if d and d['metadata']['name']=='op-finalsite-api-kippnewark'), 'newark item')" && \
  /workspaces/teamster/.trunk/tools/trunk check --force .k8s/1password/items.yaml
```

Expected: prints `1 newark item`, then `✔ No issues`.

- [ ] **Step 3: Apply to the cluster (manual / user)**

Requires `dagster-cloud` cluster credentials (see `.k8s/setup.sh`). Hand to the
user if Claude has no `kubectl` context:

```bash
kubectl apply -f .k8s/1password/items.yaml
```

The operator then creates the `op-finalsite-api-kippnewark` secret from the
1Password item (may take a few seconds to sync).

- [ ] **Step 4: Verify the synced secret's key names**

k8s secret keys come from the 1Password field's INTERNAL name, not the UI label
(`.k8s/CLAUDE.md` — SFTP items remap `password` → `newPassword`, etc.). Confirm
Task 5's `secretKeyRef.key` values before wiring:

```bash
kubectl -n dagster-cloud get secret op-finalsite-api-kippnewark -o jsonpath='{.data}' | jq keys
```

Expected: includes `"username"` and `"password"`. If the Newark item uses
different field names, use those exact names as the `key:` values in Task 5
instead of `username`/`password`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  add .k8s/1password/items.yaml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  commit -m "feat(k8s): declare Newark Finalsite API 1Password item. Refs #4346"
```

---

## Task 5: k8s secret env-var wiring in `dagster-cloud.yaml`

`FinalsiteResource` reads `FINALSITE_CREDENTIAL_ID` and `FINALSITE_SECRET` from
the environment. These must be projected from the k8s secret into BOTH the
`server_k8s_config` (code-server pod) and `run_k8s_config` (run pod) env blocks,
mirroring `kippmiami/dagster-cloud.yaml` lines 190-199 (server) and 218-227
(run). Miami sources them from secret `op-finalsite-api-kippmiami`; Newark uses
`op-finalsite-api-kippnewark` (declared in Task 4). Use the key names verified
in Task 4 Step 4 (defaults `username`/`password` below).

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/dagster-cloud.yaml`

- [ ] **Step 1: Inspect Newark's current env blocks**

Read `src/teamster/code_locations/kippnewark/dagster-cloud.yaml` and locate the
`server_k8s_config.container_config.env` list and the
`run_k8s_config.container_config.env` list.

- [ ] **Step 2: Add the two env vars to the `server_k8s_config` env list**

Append to the `server_k8s_config.container_config.env` list (2-space list-item
indentation matching siblings):

```yaml
- name: FINALSITE_CREDENTIAL_ID
  valueFrom:
    secretKeyRef:
      name: op-finalsite-api-kippnewark
      key: username
- name: FINALSITE_SECRET
  valueFrom:
    secretKeyRef:
      name: op-finalsite-api-kippnewark
      key: password
```

- [ ] **Step 3: Add the same two env vars to the `run_k8s_config` env list**

Append the identical block to the `run_k8s_config.container_config.env` list.

- [ ] **Step 4: Validate YAML parses**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  run python -c "import yaml,sys; d=yaml.safe_load(open('src/teamster/code_locations/kippnewark/dagster-cloud.yaml')); print('parsed', d['locations'][0]['location_name'])"
```

Expected: prints `parsed kippnewark`.

- [ ] **Step 5: Trunk-check the edited YAML**

Run from inside the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj && \
  /workspaces/teamster/.trunk/tools/trunk check --force \
  src/teamster/code_locations/kippnewark/dagster-cloud.yaml
```

Expected: `✔ No issues` (or auto-fixed formatting applied).

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  add src/teamster/code_locations/kippnewark/dagster-cloud.yaml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  commit -m "feat(kippnewark): project Finalsite API credentials into k8s env. Refs #4346"
```

> **Deploy note:** merging a change to a code location's `dagster-cloud.yaml`
> triggers that location's prod deploy. Confirm the
> `op-finalsite-api-kippnewark` k8s secret exists (Task 4 applied + synced)
> BEFORE merge, or the code server boots without the credential and the first
> `contacts` run fails auth.

---

## Task 6: Open the PR

**Files:** none (PR only).

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-nj \
  push -u origin cbini/feat/claude-finalsite-contacts-nj
```

- [ ] **Step 2: Create the PR**

Use `mcp__github__create_pull_request` with base `main`, head
`cbini/feat/claude-finalsite-contacts-nj`, body from
`.github/pull_request_template.md`, and `Refs #4346` in the body. Title:
`feat(kippnewark): add Finalsite contacts ingestion`.

- [ ] **Step 3: Verify CI**

Wait for Trunk / CodeQL check-runs to go green
(`mcp__github__pull_request_read get_check_runs`). dbt Cloud CI is a no-op here
(no dbt models changed). Address any Trunk failures and re-push.

---

## Post-deploy: discovery (unblocks Phase 3 dbt modeling)

These steps are OPERATIONAL, not code — they run AFTER the PR merges, the
`kippnewark` location redeploys, and the `contacts` asset materializes at least
once in prod. They produce the spec addendum that pins the dbt SQL shape. Do NOT
mark Phase 1 "done" until the discovery findings are recorded.

- [ ] **Step 1: Materialize the Newark contacts asset in prod**

Hand off to the user (prod materialization is classifier-blocked for Claude), or
via Dagster UI: materialize `kippnewark/finalsite/contacts`. Confirm success and
a non-zero `record_count` via
`mcp__dagster__get_asset_materializations(asset_key="kippnewark/finalsite/contacts")`.

- [ ] **Step 2: Stage the external source for the new region**

The `finalsite` package's `api/` models are `+enabled: false` for `kippnewark`
today (Phase 3 flips this). The raw external table lands under the Newark
Finalsite dataset regardless. Confirm the external exists via BigQuery MCP
(`<dataset>.__TABLES__`, look for the `contacts` external).

- [ ] **Step 3: Run the discovery queries**

Against the Newark `contacts` external / `stg`-equivalent, answer each spec
discovery-checklist item. Keep all PII in the Codespace / scratch — write only
aggregates and field NAMES to the addendum. Queries (BigQuery MCP):

- **Rank field on relationships** — inspect the `relationships` repeated field's
  subfields and whether any encodes rank/order distinct from `primary`:

  ```sql
  select r.rel_type, r.primary, count(*) n
  from `<newark_finalsite_dataset>.src_finalsite__contacts`,
    unnest(relationships) as r
  group by 1, 2
  order by 3 desc
  ```

  Also list the raw JSON keys present on a relationship element (the Avro/struct
  field list) to see if a rank/order/sequence field exists that the current
  `Relationship` Pydantic model omits.

- **Non-student contact records reachable via `rel_id`** — check whether the
  contacts payload includes parent/guardian records that `rel_id` joins to, and
  which detail fields (phone/email/address) they carry:

  ```sql
  select count(*) n_total,
    countif(array_length(relationships) > 0) n_with_rel,
    countif(email is not null) n_with_email,
    countif(array_length(households) > 0) n_with_household
  from `<newark_finalsite_dataset>.src_finalsite__contacts`
  ```

- **Emergency-contact custom field sets** — list every `custom_attributes`
  `field_name` and its populated value subtype, to identify the 4 emergency
  sets:

  ```sql
  select ca.field_name,
    countif(ca.value.string_value is not null) n_str,
    countif(ca.value.boolean_value is not null) n_bool,
    countif(ca.value.array_string_value is not null) n_arr,
    count(*) n
  from `<newark_finalsite_dataset>.src_finalsite__contacts`,
    unnest(custom_attributes) as ca
  group by 1
  order by 1
  ```

- **Track-siloed vs global** — repeat the field_name listing over
  `track_attributes` to determine whether the emergency sets are global
  (`custom_attributes`) or per-track (`track_attributes`).

- [ ] **Step 4: Record findings as a spec addendum**

Append an `## Addendum: Discovery findings (YYYY-MM-DD)` section to
`docs/superpowers/specs/2026-07-08-finalsite-contacts-nj-design.md` on this
branch (or a Phase-3 branch): the rank field name + semantics, the 4 emergency
field-set names and their attributes, whether `rel_id` resolves to a
detail-bearing record, and the custom-vs-track placement. Commit. This addendum
is the input to the Phase 3 dbt plan.

---

## Self-review notes

- **Spec coverage (Phase 1 scope only):** Tasks 1-5 cover the spec's "Dagster
  ingestion (per NJ region)" bullets for Newark (resource, asset, schedule,
  1Password secret sync, k8s env wiring); Task 6 opens the PR; the discovery
  section covers the spec's "Discovery checklist (Phase 2)". The `Relationship`
  schema extension, finalsite package models, kipptaf union/pivot/dim/bridge,
  consumer updates, and the `+enabled` flip are Phase 3+ and intentionally OUT
  of this plan.
- **No library edits** this phase — the rank field can't be added to the
  `Relationship` model until discovery names it. The `contacts` asset ingests
  the full raw payload regardless, so discovery has everything it needs without
  the schema change.
- **Confirmed config:** Newark subdomain `kippnewark.fsenrollment.com`; secret
  item `vaults/Data Team/items/Finalsite API - Newark` (secret not yet synced —
  Task 4 declares + applies it; Task 4 Step 4 verifies key names before Task 5
  wires them).
