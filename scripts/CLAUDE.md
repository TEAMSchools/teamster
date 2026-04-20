# CLAUDE.md — `scripts/`

Project utilities. Python scripts: `uv run scripts/<name>.py [args]`. Shell
scripts: `bash scripts/<name>.sh`.

## Script Catalog

| Script                                        | Purpose                                             |
| --------------------------------------------- | --------------------------------------------------- |
| `dagster-dev.py`                              | Start Dagster webserver for selected code locations |
| `avro-schema-update.py`                       | Rewrite Avro data in GCS with updated schema        |
| `dbt-bq-audit.py`                             | Audit BigQuery objects against dbt manifest         |
| `dbt-build-init.sh`                           | Initialize dbt build environment                    |
| `dbt-manifest.py`                             | Extract dbt manifest model list to CSV              |
| VS Code task: **dbt: Stage External Sources** | (see below)                                         |
| `dbt-yaml.py`                                 | Parse and transform dbt YAML files                  |
| `enrich_staging_descriptions.py`              | Write descriptions + PII flags to staging YAMLs     |
| `extract_ceds_schema.py`                      | Extract CEDS attribute names from GitHub XLSX       |
| `extract_edfi_schema.py`                      | Extract Ed-Fi attribute names from OpenAPI spec     |
| `extract_pdf_dictionary.py`                   | Extract column descriptions from source-system PDFs |
| `gen-automations-doc.py`                      | Regenerate `docs/reference/automations.md`          |
| `gen_column_naming_audit_inventory.py`        | Generate mart column naming audit inventory CSV     |
| `propagate_mart_descriptions.py`              | Propagate staging descriptions into downstream YAML |
| `init_sftp_integration.py`                    | Inspect SFTP servers and scaffold new integrations  |
| `json2py.py`                                  | Generate Pydantic models from JSON schemas          |
| `migrate-asset-key.py`                        | Migrate asset materialization history to new key    |
| `update.py`                                   | Update all project dependencies (uv, Trunk, dbt)    |

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
