# CLAUDE.md — `scripts/`

Project utilities. Python scripts: `uv run scripts/<name>.py [args]`. Shell
scripts: `bash scripts/<name>.sh`.

## Script Catalog

| Script                        | Purpose                                                        |
| ----------------------------- | -------------------------------------------------------------- |
| `dagster-dev.py`              | Start Dagster webserver for selected code locations            |
| `avro-schema-update.py`       | Rewrite Avro data in GCS with updated schema                   |
| `dbt-bq-audit.py`             | Audit BigQuery objects against dbt manifest                    |
| `dbt-build-init.sh`           | Initialize dbt build environment                               |
| `dbt-manifest.py`             | Extract dbt manifest model list to CSV                         |
| `dbt-sxs.py`                  | Run dbt side-by-side source comparison                         |
| `dbt-yaml.py`                 | Parse and transform dbt YAML files                             |
| `gen-automations-doc.py`      | Regenerate `docs/reference/automations.md`                     |
| `json2py.py`                  | Generate Pydantic models from JSON schemas                     |
| `migrate-asset-key.py`        | Migrate asset materialization history to new key               |
| `tableau-analyze-workbook.py` | Parse Tableau `.twb`/`.twbx` → JSON for `/star-schema-advisor` |
| `update.py`                   | Update all project dependencies (uv, Trunk, dbt)               |

## Prerequisites

- `dbt-manifest.py` — requires `dbt parse` to have run first (reads
  `target/manifest.json`)
- `gen-automations-doc.py` — requires dbt manifests to be parsed
- `dbt-bq-audit.py` — writes to `scripts/script_output/`; directory must exist

## Caveats

- `migrate-asset-key.py` creates runless materialization events — automation
  cursors will not recognize migrated events.
- `update.py` upgrades all 15 dbt projects sequentially — slow operation.
