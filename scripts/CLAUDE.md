# CLAUDE.md — `scripts/`

Project utilities. Python scripts: `uv run scripts/<name>.py [args]`. Shell
scripts: `bash scripts/<name>.sh`.

## Script Catalog

| Script                                              | Purpose                                                                                                                                                                                                                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dagster-dev.py`                                    | Start Dagster webserver for selected code locations                                                                                                                                                                                                                              |
| `dagster-mcp-launch.sh`                             | MCP launcher: exchange OP token for scoped Dagster Cloud API token, exec `dagster_plus_mcp`                                                                                                                                                                                      |
| `dbt-mcp-launch.sh`                                 | MCP launcher: exchange OP token for dbt Cloud service token, exec `dbt-mcp`                                                                                                                                                                                                      |
| `cube-rest-mcp-launch.sh`                           | MCP launcher (dev mode only): fetch `CUBE_API_SECRET`, exec `src/cube/mcp/server.py` in stdio. Default cube MCP path is the Cloud Run deploy — use this only when iterating on the server itself.                                                                                |
| `tableau-mcp-launch.sh`                             | MCP launcher: fetch Tableau connection config (server/site/PAT) from 1Password item `Tableau Server PAT - Dagster` (Data Team vault), exec `@tableau/mcp-server`. Reuses the same PAT as the Dagster Tableau refresh assets.                                                     |
| `audit_marts_yaml.py`                               | Audit mart YAMLs against BigQuery + Dagster (#3678)                                                                                                                                                                                                                              |
| `avro-schema-update.py`                             | Rewrite Avro data in GCS with updated schema (flat records only — stringifies values and drops nulls; for nested schemas use `reencode_avro_partitions.py`)                                                                                                                      |
| `backfill_google_directory_student_external_ids.py` | One-shot: backfill Workspace `externalIds[type='organization']` for existing student accounts (#3950)                                                                                                                                                                            |
| `bq-cleanup.sh`                                     | Drop orphaned BigQuery datasets / tables / views (dry-run by default; `--execute` to drop)                                                                                                                                                                                       |
| `dbt-manifest.py`                                   | Extract dbt manifest model list to CSV                                                                                                                                                                                                                                           |
| VS Code task: **dbt: Stage External Sources**       | (see below)                                                                                                                                                                                                                                                                      |
| `dbt-yaml.py`                                       | Parse and transform dbt YAML files                                                                                                                                                                                                                                               |
| `enrich_staging_descriptions.py`                    | Write descriptions + PII flags to staging YAMLs                                                                                                                                                                                                                                  |
| `extract_ceds_schema.py`                            | Extract CEDS attribute names from GitHub XLSX                                                                                                                                                                                                                                    |
| `extract_edfi_schema.py`                            | Extract Ed-Fi attribute names from OpenAPI spec                                                                                                                                                                                                                                  |
| `extract_pdf_dictionary.py`                         | Extract column descriptions from source-system PDFs                                                                                                                                                                                                                              |
| `gen-automations-doc.py`                            | Regenerate `docs/reference/automations.md`                                                                                                                                                                                                                                       |
| `generate_marts_reference.py`                       | Regenerate `docs/reference/marts-data-models.md` from marts FK constraints (parses marts properties YAML; no dbt build or warehouse access needed)                                                                                                                               |
| `gen_column_naming_audit_inventory.py`              | Generate mart column naming audit inventory CSV                                                                                                                                                                                                                                  |
| `propagate_mart_descriptions.py`                    | Propagate staging descriptions into downstream YAML                                                                                                                                                                                                                              |
| `init_sftp_integration.py`                          | Inspect SFTP servers and scaffold new integrations                                                                                                                                                                                                                               |
| `json2py.py`                                        | Generate Pydantic models from JSON schemas                                                                                                                                                                                                                                       |
| `migrate-asset-key.py`                              | Migrate asset materialization history to new key                                                                                                                                                                                                                                 |
| `reencode_avro_partitions.py`                       | Re-encode an asset's partitioned GCS Avro files to its current schema — homogenize writer schemas across partitions after a partial backfill so heterogeneous-schema reads don't drop new fields (nested-safe; idempotent; dry-run by default, `--execute` to write). See #4151. |
| `sync_cube_descriptions.py`                         | Sync dbt mart column descriptions into Cube cube YAML dimensions                                                                                                                                                                                                                 |

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
