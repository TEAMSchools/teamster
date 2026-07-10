# DeansList: add Paterson and restructure per-school API keys

- **Issue:** [#4367](https://github.com/TEAMSchools/teamster/issues/4367)
- **Status:** Design
- **Date:** 2026-07-10

## Summary

Two related changes to the DeansList integration:

1. **Restructure per-school API key storage** so that adding or rotating a
   school key is a single field edit in the 1Password UI, instead of
   hand-editing a fragile multi-line YAML blob. This touches the shared
   `DeansListResource`, so it migrates all four API districts at once.
2. **Extend the DeansList integration to Paterson** end-to-end: Dagster
   ingestion, the district dbt project, and the kipptaf cross-district models.

## Background: current architecture

### Key delivery

- One 1Password item, `DeansList API` (vault `Data Team`), is synced by the
  1Password Kubernetes Operator into the `op-deanslist-api` secret in the
  `dagster-cloud` namespace. Each field of the item becomes one key of the
  secret. The `OnePasswordItem` custom resource lives in
  [`.k8s/1password/items.yaml`](../../../.k8s/1password/items.yaml).
- Today the item has two fields: `subdomain` and a single field holding an
  entire YAML blob (`api_key_map: {school_id: key, ...}`) covering every school
  across the network.
- Each district's `dagster-cloud.yaml` projects the blob field into the code and
  run pods as a file under `/etc/secret-volume/`, and sets `DEANSLIST_SUBDOMAIN`
  from the `subdomain` key.
- `DeansListResource`
  ([`src/teamster/libraries/deanslist/resources.py`](../../../src/teamster/libraries/deanslist/resources.py))
  is a single shared instance
  ([`src/teamster/core/resources.py`](../../../src/teamster/core/resources.py)),
  configured with `subdomain` and `api_key_map` (the file path). At startup it
  parses the YAML into `self._api_key_map`, then looks up
  `self._api_key_map[school_id]` per request. All API districts share this one
  resource and one subdomain.

### Pain points

- The YAML blob is a single 1Password field: no per-school history, easy to
  break indentation, awkward to diff or edit.
- Adding a school is at least two edits (the key blob, plus the district's
  partition list) followed by a redeploy. This spec targets the **key** half.

### District ingestion

- API districts (`kippnewark`, `kippcamden`, `kippmiami`) each have a
  `<district>/deanslist/` module: `assets.py` (a `StaticPartitionsDefinition` of
  the district's DeansList `school_id`s, plus factory calls from
  [`libraries/deanslist/assets.py`](../../../src/teamster/libraries/deanslist/assets.py)),
  `schema.py`, `schedules.py`, `__init__.py`, and `config/*.yaml`.
- `kipppaterson` has **no** DeansList module today, and its CLAUDE.md lists
  DeansList as absent. Paterson also has no ODBC PowerSchool and no BigQuery
  writes from its location (its PowerSchool arrives via Couchdrop SFTP), but
  that does not affect DeansList, which is a direct REST pull.

### dbt

- The `deanslist` source-system package produces `stg_deanslist__*` and
  `int_deanslist__*` models. It builds inside each **consuming district**
  project (`kippnewark`, `kippcamden`, `kippmiami`), reading that district's own
  `src_deanslist__*` external tables. `kipppaterson` does not import the
  package.
- `kipptaf` does not import the package. It has its own `models/deanslist/api/`
  union layer: one `sources-kipp<district>.yml` per district plus `stg_`/`int_`
  models that
  `dbt_utils.union_relations([source("kippnewark_deanslist", ...), ...])` across
  the three API districts. Downstream kipptaf models (for example
  `int_students__attendance_interventions`) consume those union models.

## Goals

- Editing or rotating a school key is a single 1Password field edit; no YAML, no
  `dagster-cloud.yaml` change, no code change.
- The four API districts share one consistent key mechanism after migration.
- Paterson DeansList data is ingested and queryable network-wide (district
  project plus kipptaf unions).

## Non-goals

- Deriving the Dagster school-partition list dynamically. The per-district
  `StaticPartitionsDefinition` stays explicit (an intentional scope decision).
  Adding a school still requires a small code edit plus redeploy; only the key
  edit is being simplified.
- Changing the secret store (staying on 1Password) or moving to a runtime
  secrets API.
- Per-district subdomains. Paterson joins the existing shared subdomain.

## Design

### Part 1 — Per-school key fields to a mounted directory

The operator maps each 1Password field to one secret key. We exploit that: store
one field per school, then mount the whole secret as a directory of files and
let the resource assemble the map.

#### 1Password item

`DeansList API` keeps its `subdomain` field and gains one text field per school:
field label = the DeansList `school_id` (for example `121`), value = that
school's API key. `op-deanslist-api` then synchronizes to a secret with keys
`subdomain`, `121`, `122`, and so on.

#### Deploy config (`dagster-cloud.yaml`, all four districts)

Mount the whole `op-deanslist-api` secret as a **directory** in its own
`mountPath` (for example `/etc/secret-volume/deanslist`), with no `items:`
filter, so every field lands as a file whose name is the school id and whose
content is the key. The `subdomain` field lands as a file in the same directory,
so the resource reads it from there too — the separate `DEANSLIST_SUBDOMAIN`
environment-variable mapping is **removed** from all four `dagster-cloud.yaml`
files. One directory is now the sole loading mechanism. Both `server_k8s_config`
and `run_k8s_config` consumers apply.

The field-to-directory chain is two hops, and only the first is
1Password-specific:

1. **Operator maps field to secret key** (already how `subdomain` works today):
   the 1Password Operator writes each field of the `DeansList API` item as one
   key of the `op-deanslist-api` Secret.
2. **kubelet maps secret key to file** (standard Kubernetes): a Secret mounted
   as a volume is written as one file per key, filename = key, contents = value.
   Today's `items:` filter cherry-picks the single blob key as one file;
   dropping it materializes every key as its own file.

So the change adds fields and removes one filter — no new infrastructure.

Example projected-volume source:

```yaml
volumes:
  - name: deanslist-keys
    projected:
      sources:
        - secret:
            name: op-deanslist-api
volumeMounts:
  - name: deanslist-keys
    readOnly: true
    mountPath: /etc/secret-volume/deanslist
```

#### Resource change

The resource loads everything from the one mounted directory. Both config fields
(`subdomain` and `api_key_map`) collapse into a single `api_key_dir`: the
subdomain comes from the `subdomain` file, and the key map from the
numeric-named files.

```python
def setup_for_execution(self, context: InitResourceContext) -> None:
    self._log = check.not_none(value=context.log)

    key_dir = pathlib.Path(self.api_key_dir)

    subdomain = (key_dir / "subdomain").read_text().strip()
    self._base_url = f"https://{subdomain}.deanslistsoftware.com/api"

    self._api_key_map = {
        int(f.name): f.read_text().strip()
        for f in key_dir.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name.isdigit()
    }
```

The `subdomain` file is read explicitly; the `f.name.isdigit()` filter keeps it
(and the projected-volume symlink entries `..data` / timestamped dirs) out of
the key map. `get()` and `list()` are unchanged; they already look up
`self._api_key_map[school_id]` with an `int` key. The single instantiation in
`core/resources.py` passes only `api_key_dir="/etc/secret-volume/deanslist"` —
the `subdomain=EnvVar("DEANSLIST_SUBDOMAIN")` argument is dropped.

#### Blast radius

Because the resource is shared, this converts all four districts at once. A
one-time manual step (owner: whoever administers the 1Password item): re-enter
the existing keys as individual fields, then delete the YAML blob field — done
in the additive-first order below so nothing breaks mid-migration.

#### Risk: field label vs secret key name

`.k8s/CLAUDE.md` warns that a secret key can come from a field's internal name,
not its UI label (known remaps on login-template fields, for example `password`
to `newPassword`). We rely on custom numeric fields syncing as `121`, `122`, and
so on. The `subdomain` field is already proven safe — it syncs to secret key
`subdomain` today (the existing `secretKeyRef`), so reading the `subdomain` file
carries no new risk and gives a working reference point for the numeric fields.

- **Verify early** (owner-side; `kubectl` is blocked from this tool): add one
  test field, then
  `kubectl -n dagster-cloud get secret op-deanslist-api -o jsonpath='{.data}' | jq keys`.
- **Fallback if labels do not survive:** store `school_id|key` in the field
  _value_ and parse each file's contents instead of trusting the filename. The
  resource logic changes from "filename is the id" to "split the value on `|`".

### Part 2 — Paterson Dagster ingestion

Add `src/teamster/code_locations/kipppaterson/deanslist/`, mirroring
`kippnewark`:

- `assets.py` — a `StaticPartitionsDefinition` of Paterson's DeansList
  `school_id`s (**supplied separately**, see Prerequisites), plus the same
  factory calls (`build_deanslist_static_partition_asset`,
  `build_deanslist_multi_partition_asset`,
  `build_deanslist_paginated_multi_partition_asset`) driven by `config/*.yaml`.
- `schema.py` — the Pydantic and Avro schemas Paterson needs (start from
  Newark's; trim to the endpoints Paterson uses).
- `schedules.py`, `__init__.py`, and `config/` (`static-partition-assets.yaml`,
  `multi-partition-monthly-assets.yaml`, `multi-partition-fiscal-assets.yaml`) —
  copied from Newark and adjusted to Paterson's endpoint set.

Wire-up:

- `kipppaterson/definitions.py`: import `DEANSLIST_RESOURCE`, add
  `"deanslist": DEANSLIST_RESOURCE` to resources, and add the module's assets
  and schedules.
- `kipppaterson/dagster-cloud.yaml`: add the directory mount from Part 1 (no
  `DEANSLIST_SUBDOMAIN` variable — the subdomain is read from the mounted
  `subdomain` file, same shared subdomain).
- `kipppaterson/CLAUDE.md`: remove DeansList from the "does not use" list and
  add it to Active Integrations (schedule-driven).

### Part 3 — Paterson district dbt project

- `src/dbt/kipppaterson/packages.yml`: add `- local: ../deanslist`.
- `src/dbt/kipppaterson/dbt_project.yml`: add a `deanslist:` models block
  (`+materialized: table`, and disable any models Paterson does not use,
  matching the Newark pattern that disables `stg_deanslist__followups`). Confirm
  the external-source variables the package needs (`cloud_storage_uri_base` is
  already set at the project level; the package sources resolve schema via
  `{{ project_name }}`).
- Stage the new external sources with `--target staging` before the dbt Cloud CI
  job will pass (per the External Table Pattern in `src/dbt/CLAUDE.md`). This
  requires Paterson DeansList Avro to have landed in GCS first.

### Part 4 — kipptaf cross-district inclusion

- Add `src/dbt/kipptaf/models/deanslist/api/sources-kipppaterson.yml`, mirroring
  the existing three per-district source files.
- Add `source("kipppaterson_deanslist", "<model>")` to the `relations=[...]`
  list of every kipptaf `deanslist/api` union model (staging and intermediate).
- No downstream kipptaf model logic changes — they read the union outputs, which
  now include Paterson.

## Rollout and sequencing

There is one hard ordering constraint, and it is data-dependent: Paterson
DeansList Avro must exist in GCS before the dbt external sources can be staged,
and staging is what lets dbt Cloud CI pass. That single seam — everything that
_produces_ the data, then everything that _reads_ it — splits the work into
**two PRs**.

Bracketing both PRs are two manual 1Password steps (owner: whoever administers
the `DeansList API` item), done additive-first so nothing breaks mid-migration:

- **Before PR 1 merges:** add every school as its own field — existing
  districts' keys re-entered from the blob, plus Paterson's — while leaving the
  YAML blob field in place.
- **After PR 1 deploys and is verified:** delete the old YAML blob field.

### PR 1 — Keys plus Paterson ingestion (Python and K8s only)

- The `DeansListResource` directory change and its `core/resources.py`
  instantiation.
- The directory-mount change to all four `dagster-cloud.yaml` files.
- The new `kipppaterson/deanslist` module and its `definitions.py`,
  `dagster-cloud.yaml`, and CLAUDE.md wiring.

No dbt changes, so dbt Cloud CI is a no-op on this PR. After the post-merge
deploy: verify Newark/Camden/Miami still pull DeansList (a sample school
partition materializes), materialize Paterson's assets so its Avro lands in prod
GCS, then remove the blob field.

### PR 2 — All dbt (Paterson district plus kipptaf unions)

- Paterson district project: `packages.yml`, `dbt_project.yml`, and staging the
  new external sources.
- kipptaf: `sources-kipppaterson.yml` and Paterson added to each
  `union_relations` list.

Land these together via the single-PR cross-project workflow in
`src/dbt/kipptaf/CLAUDE.md` (stage/clone the Paterson district models into
`zz_stg_*` so kipptaf CI reads them). This depends on PR 1 being deployed and
Paterson's DeansList assets materialized in prod, so the external sources stage
against real data.

**Optional third PR:** if you would rather verify the network-wide key migration
in isolation before adding a new district, lift the `DeansListResource` plus
four-`dagster-cloud.yaml` change out of PR 1 into its own PR ahead of Paterson.
Two PRs is the floor; this makes it three.

## Testing and validation

- **Resource unit behavior:** a focused test that points the resource at a temp
  directory of numeric-named files plus a `subdomain` file and a `..data`-style
  entry, asserting the base URL uses the subdomain and the key map contains only
  the numeric files with `int` keys.
- **Existing districts unaffected:** after PR 1 deploys, materialize one static
  and one multi-partition DeansList asset per existing district for a known
  school and confirm row counts are non-zero and the Avro schema check passes.
- **Paterson ingestion:** materialize Paterson DeansList assets; confirm Avro in
  the Paterson GCS path and passing schema checks.
- **dbt:** `uv run dbt build --select <paterson deanslist models>` against the
  district project; then the kipptaf union models after Paterson prod exists.
  kipptaf CI only builds kipptaf, so district-side correctness is verified with
  a local district build.

## Alternatives considered

- **Per-school fields exposed as individual environment variables** rather than
  a mounted directory. Rejected: adding a school would require editing
  `dagster-cloud.yaml` (two blocks) every time — it re-creates the toil this
  change removes.
- **Runtime fetch from the in-cluster 1Password Connect API**, skipping the
  synced secret entirely. Rejected: adds a network dependency and token handling
  at run time — disproportionate to an "easier to edit" goal.
- **Dynamically derived partitions** (single source of truth). Explicitly out of
  scope per the scope decision; the partition list stays explicit.

## Prerequisites and open items

- **Paterson DeansList `school_id`s and API keys** must be provided (the ids for
  the partition definition, the keys for the 1Password fields).
- **Field-label sync verification** (Part 1 risk) should be confirmed before
  committing to filename-as-id, with the value-encoded fallback ready.
- **Endpoint set for Paterson:** confirm which DeansList endpoints Paterson uses
  (to trim `schema.py` and `config/*.yaml` from the Newark copy).
