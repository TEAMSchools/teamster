# CLAUDE.md — `scripts/`

## Script Catalog

| Script                         | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dagster-mcp-launch.sh`        | MCP launcher: exchange OP token for scoped Dagster Cloud API token, exec `dagster_plus_mcp`. Pass `--no-exec` when sourcing it to get the credentials without starting the server                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `dagster-plus-mcp-headers.sh`  | MCP `headersHelper` for Dagster's official hosted server: sources `dagster-mcp-launch.sh --no-exec`, prints the bearer and organization headers as JSON                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `cube-rest-mcp-launch.sh`      | MCP launcher (dev mode only): fetch `CUBE_API_SECRET`, exec `src/cube/mcp/server.py` in stdio. Default cube MCP path is the Cloud Run deploy — use this only when iterating on the server itself.                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `tableau-mcp-launch.sh`        | MCP launcher: fetch Tableau connection config (server/site/PAT) from 1Password item `Tableau Server PAT - Dagster` (Data Team vault), exec `@tableau/mcp-server`. Reuses the same PAT as the Dagster Tableau refresh assets.                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `avro-schema-update.py`        | Rewrite Avro data in GCS with updated schema (flat records only — stringifies values and drops nulls; for nested schemas use `reencode_avro_partitions.py`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `bq-cleanup.sh`                | Drop orphaned BigQuery datasets / tables / views (dry-run by default; `--execute` to drop)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `cube_catalog_export.py`       | Regenerate the published Cube semantic-layer catalog from the deployed model's `/meta`: writes `docs/reference/cube-catalog-meta.json` and splices the `## Views` section of `docs/reference/cube-semantic-catalog.md`, leaving that page's hand-written front matter intact. Needs `CUBE_API_SECRET` + `CUBE_REST_URL`. Run as a network-scoped identity — it exits non-zero on an empty catalog, because an access denial and an undeployed model are indistinguishable from the caller's side.                                                                                                                                                         |
| `cube_rls_matrix.py`           | Validate Cube row-level security per viewer over the local SQL API — one connection per viewer email running the same query, so any scope difference is attributable to access policy. Viewer emails are PII: pass via `--viewers` or `--viewers-file`, never hardcoded. Needs the Cube dev server with the SQL API enabled (#4526).                                                                                                                                                                                                                                                                                                                      |
| `cube_types_export.py`         | Generate `docs/reference/cube-catalog.d.ts` from the committed `cube-catalog-meta.json` — member-name unions and a row interface per view, plus a view-keyed `CubeQuery` generic. Offline: needs no Cube credentials and no network, so anyone who can clone the repo can regenerate it. Every member description becomes JSDoc, and measures are typed `string` because the REST API stringifies numeric measures. Run `cube_catalog_export.py` first when the model has moved; commit the output.                                                                                                                                                       |
| `dbt-yaml.py`                  | **Non-functional** — shells out to `generate_model_yaml`, a `dbt-codegen` macro; that package is not in any `packages.yml`, so the run errors with "could not find a macro". Write properties YAML by hand.                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `reencode_avro_partitions.py`  | Re-encode an asset's partitioned GCS Avro files to its current schema — homogenize writer schemas across partitions after a partial backfill so heterogeneous-schema reads don't drop new fields (nested-safe; idempotent; dry-run by default, `--execute` to write). See #4151.                                                                                                                                                                                                                                                                                                                                                                          |
| `sandbox_coverage_manifest.py` | Generate `src/cube/sandbox/coverage_manifest.yml` — every cell the Cube sandbox's synthetic dataset must contain, from production introspection plus the cube model, `cube.js` and `access.js`. Reads schema and codesets only, never rows. Derives the table set from the union of `sql_table:` and `cube.js` (19 vs 20 — `dim_staff_reporting_chain` is in no YAML) and asserts the count. Scope cells come from `access.js`, NOT `SELECT DISTINCT`: production data is a subset of the enum domain the code handles. `--introspection` replays a saved payload so the build runs without credentials; a payload missing a declared codeset is refused. |

## VS Code Task: dbt: Stage External Sources

Replaced `dbt-sxs.py`. Run via **Terminal > Run Task > dbt: Stage External
Sources** in VS Code.

**Inputs** (prompted at run time):

- **Project** (pickString): `kipptaf`, `kippnewark`, `kippcamden`, `kippmiami`,
  `kipppaterson`
- **Target** (pickString): `defer` (default), `dev`, `staging`
- **Source** (promptString): dbt source selector, default `*`

**Terminal equivalent:**

```bash
uv run dbt run-operation stage_external_sources \
  --project-dir src/dbt/<project> \
  --target <target> \
  --vars '{"ext_full_refresh": "true", "cloud_storage_uri_base": "gs://teamster-<project>/dagster/<project>"}' \
  --args 'select: <source>'
```

## Prerequisites

- `dbt-manifest.py` — requires `dbt parse` to have run first (reads
  `target/manifest.json`)
- `gen-automations-doc.py` — requires dbt manifests to be parsed. **Do NOT run
  in the codespace**: it imports every code location incl. `kipptaf`, which
  fails at module load (eager `EnvVar`), and the script `continue`s past the
  failed import → writes a catalog with `kipptaf` silently DROPPED. Run only in
  a bootstrapped terminal where all locations import.
- `generate_marts_reference.py` — no prerequisites; run after adding/removing a
  fact table or changing FK constraints:
  `uv run scripts/generate_marts_reference.py`. Like `automations.md`, commit
  the output in its prettier-formatted form — the generator emits compact tables
  that the pre-commit formatter pads, so the working tree shows table-padding
  churn between run and commit; that is expected.

## Caveats

- `migrate-asset-key.py` creates runless materialization events — automation
  cursors will not recognize migrated events.

## Authoring an MCP server

Reference implementation: [`src/cube/mcp/server.py`](../src/cube/mcp/server.py).
Pattern:

- PEP 723 inline `dependencies` (mcp, httpx, pyjwt, pydantic) — `uv run`
  installs them at launch; don't add to `pyproject.toml` for MCP-only deps.
- FastMCP with `instructions=` for server-level guidance shown to the LLM
  (member naming, filter operators, PII defaults, etc.).
- Per-user config that can't be derived from env: `Context.elicit()` with a
  `BaseModel` schema, cache the answer at `~/.config/teamster/<name>` so the
  prompt fires once per user. Allow `<UPPER>_OVERRIDE` env var to bypass.
- Launcher (`<name>-mcp-launch.sh`) handles only the secret fetch via `op read`;
  non-secret config lives in `.mcp.json` `env:`.
- A **hosted** (`"type": "http"`) server has no launcher, and `${VAR}` in its
  `headers` resolves against the shell, where this container keeps no secrets.
  Point `headersHelper` at a script instead: Claude Code runs it at connection
  time, parses stdout as a JSON object of headers, and kills it after 10s. The
  token then lives only in that helper process, and never in `.mcp.json`, which
  is checked in. Claude Code logs the header back as
  `"Authorization":"[REDACTED]"`, so it does not reach the subprocess debug log
  either. `dagster-plus-mcp-headers.sh` is the reference.
- Adding an MCP for a system Dagster already integrates? Reuse its 1Password
  item rather than minting new credentials — `dagster-cloud.yaml`'s
  `op-<system>` `secretKeyRef` confirms the item exists (item name ≈ secret
  name, minus the `op-` prefix).
- A launcher's `op read` references must match 1Password field **labels**.
  Source them from `.devcontainer/tpl/.env.tpl` (hook-blocked — ask the user to
  paste the relevant lines). Do NOT derive them from `dagster-cloud.yaml`
  `secretKeyRef.key`: those are 1Password-operator-normalized internal names
  (label `site id` → k8s key `site-id`) and won't resolve via `op read`.
- **Containerizing a PEP 723 script**: install deps at Dockerfile build time via
  `uv export --script foo.py --no-hashes > /tmp/requirements.txt && uv pip install --system --no-cache -r /tmp/requirements.txt`,
  then `CMD ["python", "foo.py"]`. `CMD ["uv", "run", "foo.py"]` reinstalls on
  every Cloud Run cold start. See `src/cube/mcp/Dockerfile`.

## Testing standalone PEP 723 scripts

Load the script in tests via `importlib.util.spec_from_file_location` and
register `sys.modules[name] = module` _before_ `exec_module` (the registration
is required for `@dataclass` to resolve). Don't add `scripts/__init__.py` —
scripts/ stays a directory of standalone executables.

Don't annotate test helpers with a type from the loaded module (e.g.
`-> list[mod.Class]`) — `mod` is a runtime variable, not a static module, so
pyright flags `reportInvalidTypeForm`. Use a builtin/bare annotation
(`-> list`).
