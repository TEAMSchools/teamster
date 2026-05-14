# CLAUDE.md — `scripts/`

Project utilities. Python scripts: `uv run scripts/<name>.py [args]`. Shell
scripts: `bash scripts/<name>.sh`.

## Script Catalog

| Script                                        | Purpose                                                                                                                                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dagster-dev.py`                              | Start Dagster webserver for selected code locations                                                                                                                                                 |
| `dagster-mcp-launch.sh`                       | MCP launcher: exchange OP token for scoped Dagster Cloud API token, exec `dagster_plus_mcp`                                                                                                         |
| `dbt-mcp-launch.sh`                           | MCP launcher: exchange OP token for dbt Cloud service token, exec `dbt-mcp`                                                                                                                         |
| `cube-rest-mcp-launch.sh`                     | MCP launcher (dev mode only): fetch `CUBEJS_API_SECRET`, exec `src/cube/mcp/server.py` in stdio. Default cube MCP path is the Cloud Run deploy — use this only when iterating on the server itself. |
| `audit_marts_yaml.py`                         | Audit mart YAMLs against BigQuery + Dagster (#3678)                                                                                                                                                 |
| `avro-schema-update.py`                       | Rewrite Avro data in GCS with updated schema                                                                                                                                                        |
| `dbt-bq-audit.py`                             | Audit BigQuery objects against dbt manifest                                                                                                                                                         |
| `dbt-build-init.sh`                           | Initialize dbt build environment                                                                                                                                                                    |
| `dbt-manifest.py`                             | Extract dbt manifest model list to CSV                                                                                                                                                              |
| VS Code task: **dbt: Stage External Sources** | (see below)                                                                                                                                                                                         |
| `dbt-yaml.py`                                 | Parse and transform dbt YAML files                                                                                                                                                                  |
| `enrich_staging_descriptions.py`              | Write descriptions + PII flags to staging YAMLs                                                                                                                                                     |
| `extract_ceds_schema.py`                      | Extract CEDS attribute names from GitHub XLSX                                                                                                                                                       |
| `extract_edfi_schema.py`                      | Extract Ed-Fi attribute names from OpenAPI spec                                                                                                                                                     |
| `extract_pdf_dictionary.py`                   | Extract column descriptions from source-system PDFs                                                                                                                                                 |
| `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`                                                                                                                                                          |
| `gen_column_naming_audit_inventory.py`        | Generate mart column naming audit inventory CSV                                                                                                                                                     |
| `propagate_mart_descriptions.py`              | Propagate staging descriptions into downstream YAML                                                                                                                                                 |
| `init_sftp_integration.py`                    | Inspect SFTP servers and scaffold new integrations                                                                                                                                                  |
| `json2py.py`                                  | Generate Pydantic models from JSON schemas                                                                                                                                                          |
| `migrate-asset-key.py`                        | Migrate asset materialization history to new key                                                                                                                                                    |
| `update.py`                                   | Update all project dependencies (uv, Trunk, dbt)                                                                                                                                                    |

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
- `gen-automations-doc.py` — requires dbt manifests to be parsed
- `dbt-bq-audit.py` — writes to `scripts/script_output/`; directory must exist

## Caveats

- `migrate-asset-key.py` creates runless materialization events — automation
  cursors will not recognize migrated events.
- `update.py` upgrades all 15 dbt projects sequentially — slow operation.

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

## Testing standalone PEP 723 scripts

Load the script in tests via `importlib.util.spec_from_file_location` and
register `sys.modules[name] = module` _before_ `exec_module` (the registration
is required for `@dataclass` to resolve). Don't add `scripts/__init__.py` —
scripts/ stays a directory of standalone executables.
