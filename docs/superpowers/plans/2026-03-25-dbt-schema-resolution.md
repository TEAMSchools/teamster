# dbt Schema Resolution Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered inline Jinja schema conditionals in all 61 dbt
source files with centralized `resolve_source_schema` and
`resolve_region_source_schema` macros, backed by proper `dev`/`staging`/`prod`
profiles, so developers get safe defaults and consistent schema resolution.

**Architecture:** Target-driven: `--target dev` (default) writes to
`zz_<GITHUB_USER>_*`, `--target staging` writes to `zz_stg_*`, `--target prod`
writes to bare schema names. A single `resolve_source_schema(base_schema)` macro
(in each of the 5 school/network projects) centralizes source schema logic.
Source-system projects resolve the macro from the consuming project's namespace
at compile time. kipptaf additionally gets a
`resolve_region_source_schema(base_schema)` macro and a `dev-region` target for
its four cross-regional source files — these default to production and opt into
personal namespace only via `--target dev-region`. Migration is phased: macros +
profiles first (backward-compatible), then source file rewrites, then cleanup.

**Tech Stack:** dbt (BigQuery), Jinja2 macros, YAML, Python (Dagster
`DbtCliResource`), bash (git hook), VS Code tasks

**Spec:** `docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md`

|                 | Status      |
| --------------- | ----------- |
| **Plan**        | IN PROGRESS |
| **Development** | NOT STARTED |

---

## File Map

### Phase 1 — Macros, profiles, Dagster, dbt Cloud

| Action | File                                                      | What changes                                                                                                                                                 |
| ------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Create | `src/dbt/kipptaf/macros/resolve_source_schema.sql`        | New macro                                                                                                                                                    |
| Create | `src/dbt/kipptaf/macros/resolve_region_source_schema.sql` | New macro (kipptaf only)                                                                                                                                     |
| Create | `src/dbt/kippnewark/macros/resolve_source_schema.sql`     | New macro                                                                                                                                                    |
| Create | `src/dbt/kippcamden/macros/resolve_source_schema.sql`     | New macro                                                                                                                                                    |
| Create | `src/dbt/kippmiami/macros/resolve_source_schema.sql`      | New macro                                                                                                                                                    |
| Create | `src/dbt/kipppaterson/macros/resolve_source_schema.sql`   | New macro                                                                                                                                                    |
| Modify | `.dbt/profiles.yml`                                       | Rename `<project>` target → `dev`; update `staging` schema; add `dev-region` for kipptaf; add source-system `dev` target; keep old targets during transition |
| Modify | `src/dbt/kipptaf/profiles.yml`                            | Add `dev` + `prod` targets, default `dev`                                                                                                                    |
| Modify | `src/dbt/kippnewark/profiles.yml`                         | Add `dev` + `prod` targets, default `dev`                                                                                                                    |
| Modify | `src/dbt/kippcamden/profiles.yml`                         | Add `dev` + `prod` targets, default `dev`                                                                                                                    |
| Modify | `src/dbt/kippmiami/profiles.yml`                          | Add `dev` + `prod` targets, default `dev`                                                                                                                    |
| Modify | `src/dbt/kipppaterson/profiles.yml`                       | Add `dev` + `prod` targets, default `dev`                                                                                                                    |
| Modify | `src/teamster/core/resources.py`                          | Update `get_dbt_cli_resource` — detect prod via env var, remove dead `test` param                                                                            |
| Modify | `src/teamster/core/CLAUDE.md`                             | Update `get_dbt_cli_resource` docs                                                                                                                           |
| Manual | dbt Cloud UI                                              | Job target names: `default` → `staging`/`prod`                                                                                                               |
| Manual | dbt Cloud UI                                              | Staging environment dataset: `z_dev_kipptaf` → `zz_stg_kipptaf`                                                                                              |

### Phase 2 — Source file rewrites (~61 files)

All `sources*.yml` files containing inline Jinja conditionals (`target.name`,
`DBT_CLOUD_ENVIRONMENT_TYPE`, `GITHUB_USER`). Grouped by project:

- **kipptaf** (42 files): all `src/dbt/kipptaf/models/**/sources*.yml` files
  with inline Jinja, **except** the four cross-regional source files below
- **kipptaf cross-regional** (4 files): `sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kippmiami.yml`, `sources-kipppaterson.yml`
  — use `resolve_region_source_schema` instead of `resolve_source_schema`
- **kippnewark** (1 file): `src/dbt/kippnewark/models/edplan/sources-drive.yml`
- **kippcamden** (1 file): `src/dbt/kippcamden/models/edplan/sources-drive.yml`
- **kippmiami** (1 file): `src/dbt/kippmiami/models/fldoe/sources.yml`
- **amplify** (1 file): `src/dbt/amplify/models/sources.yml`
- **deanslist** (1 file): `src/dbt/deanslist/models/sources.yml`
- **edplan** (2 files): `src/dbt/edplan/models/sources.yml`,
  `src/dbt/edplan/models/sources-archive.yml`
- **finalsite** (1 file): `src/dbt/finalsite/models/sources.yml`
- **iready** (1 file): `src/dbt/iready/models/sources.yml`
- **overgrad** (1 file): `src/dbt/overgrad/models/sources.yml`
- **pearson** (1 file): `src/dbt/pearson/models/sources.yml`
- **powerschool** (2 files):
  `src/dbt/powerschool/models/sis/staging/odbc/sources.yml`,
  `src/dbt/powerschool/models/sis/staging/sftp/sources.yml`
- **renlearn** (1 file): `src/dbt/renlearn/models/sources.yml`
- **titan** (1 file): `src/dbt/titan/models/sources.yml`

### Phase 3 — Cleanup

| Action | File                                 | What changes                                                                                                                                                                |
| ------ | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Modify | `.dbt/profiles.yml`                  | Remove old targets (keep only `dev`/`dev-region`/`staging`/`prod` for kipptaf; `dev`/`staging`/`prod` for other school/network; `dev` only for source-system)               |
| Modify | `.devcontainer/devcontainer.json`    | Remove `DBT_CLOUD_ENVIRONMENT_TYPE` env var                                                                                                                                 |
| Modify | `.vscode/settings.json`              | Remove `DBT_CLOUD_ENVIRONMENT_TYPE` if present; add Power User defer config                                                                                                 |
| Modify | `.vscode/tasks.json`                 | Add "dbt: Stage External Sources" task + inputs                                                                                                                             |
| Delete | `scripts/dbt-sxs.py`                 | Replaced by VS Code task                                                                                                                                                    |
| Modify | `scripts/CLAUDE.md`                  | Replace `dbt-sxs.py` entry with VS Code task documentation: project selection, source filtering (equivalent of `--select`), and test-bucket option (equivalent of `--test`) |
| Manual | `.git/hooks/post-merge`              | New bash script for prod manifest generation                                                                                                                                |
| Manual | `.devcontainer/scripts/postStart.sh` | Wire manifest generation (protected file — present as manual block)                                                                                                         |

---

## Phase 1 — Macros, Profiles, Dagster, dbt Cloud

### Task 1: Add macros to school/network projects

- [ ] Create `resolve_source_schema` in all 5 school/network projects. Content
      (identical for all 5):

```sql
{% macro resolve_source_schema(base_schema) %}
  {%- if target.name == 'dev' -%}
    zz_{{ env_var('GITHUB_USER', 'dev') }}_{{ base_schema }}
  {%- elif target.name == 'staging' -%}
    zz_stg_{{ base_schema }}
  {%- else -%}
    {{ base_schema }}
  {%- endif -%}
{% endmacro %}
```

- [ ] Create `resolve_region_source_schema` in kipptaf only. This macro governs
      the four cross-regional source files (`sources-kipp*.yml`) and defaults to
      production — developers opt in to personal namespace via
      `--target dev-region`:

```sql
{% macro resolve_region_source_schema(base_schema) %}
  {%- if target.name == 'dev-region' -%}
    zz_{{ env_var('GITHUB_USER', 'dev') }}_{{ base_schema }}
  {%- elif target.name == 'staging' -%}
    zz_stg_{{ base_schema }}
  {%- else -%}
    {{ base_schema }}
  {%- endif -%}
{% endmacro %}
```

- [ ] Confirm current default target in `.dbt/profiles.yml`
- [ ] Verify both macros compile (`dbt parse --project-dir src/dbt/kipptaf`)
- [ ] Commit

### Task 2: Update `.dbt/profiles.yml`

- [ ] Add `dev`/`staging`/`prod` targets to the 5 school/network projects
      alongside existing targets (legacy targets kept for Phase 3 cleanup)
- [ ] Add `dev-region` target to kipptaf only — identical output schema to
      `dev`; target name is what `resolve_region_source_schema` keys off:

```yaml
dev-region:
  type: bigquery
  schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
  method: oauth
  project: teamster-332318
  threads: 40
```

- [ ] Add a single `dev` target to each source-system project
- [ ] Leave `integration_tests` unchanged
- [ ] Verify `dbt debug` resolves correctly for at least one school project
- [ ] Commit

### Task 3: Update shipped `src/dbt/*/profiles.yml`

- [ ] Replace each of the 5 school/network project profile files with a
      two-target (`dev`/`prod`) pattern, `dev` as default
- [ ] Validate Dagster definitions for kipptaf
      (`uv run dagster definitions validate -m teamster.kipptaf`)
- [ ] Parse all 5 school projects with `--target dev` and `--target prod`
- [ ] Commit

### Task 4: Update `get_dbt_cli_resource` in Dagster

- [ ] Replace the function body — remove `test` param, detect prod via
      `DAGSTER_CLOUD_DEPLOYMENT_NAME`:

```python
def get_dbt_cli_resource(dbt_project: DbtProject) -> DbtCliResource:
    if os.getenv("DAGSTER_CLOUD_DEPLOYMENT_NAME") and not os.getenv(
        "DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT"
    ):
        return DbtCliResource(project_dir=dbt_project, target="prod")
    return DbtCliResource(project_dir=dbt_project)
```

- [ ] Update `src/teamster/core/CLAUDE.md` to document the new behavior
- [ ] Verify no callers pass `test=True`
- [ ] Validate Dagster definitions
- [ ] Commit

### Task 5: Update dbt Cloud (manual)

Must be done before Phase 2 — after source files are rewritten,
`resolve_source_schema` keys only on `target.name`. If dbt Cloud still sends
`target: default`, the `else` branch fires and CI reads from prod schemas.

- [ ] Update job target names in dbt Cloud UI:
  - Build Modified - CI: `default` → `staging`
  - Build Modified - Staging: `default` → `staging`
  - Parse - Staging: `default` → `staging`
  - Parse - Production: `default` → `prod`
- [ ] Update Staging environment dataset: `z_dev_kipptaf` → `zz_stg_kipptaf`
- [ ] Confirm a staging CI run completes successfully before proceeding to Phase
      2

---

## Phase 2 — Source File Rewrites

**Substitution rule:**

- Standard source files: `schema: "{{ resolve_source_schema('base_schema') }}"`
- kipptaf cross-regional source files (`sources-kipp*.yml`) only:
  `schema: "{{ resolve_region_source_schema('base_schema') }}"`

### Task 6: Rewrite kipptaf source files (~46 files)

- [ ] Replace all inline Jinja `schema:` blocks in
      `src/dbt/kipptaf/models/**/sources*.yml` with `resolve_source_schema()`
      calls
- [ ] **Exception**: the four cross-regional files (`sources-kippnewark.yml`,
      `sources-kippcamden.yml`, `sources-kippmiami.yml`,
      `sources-kipppaterson.yml`) use `resolve_region_source_schema()` instead —
      these point to regional staging model outputs (authoritative production
      tables) and default to production; use `--target dev-region` to read from
      personal namespace during cross-project development
- [ ] Parse with `--target dev` and `--target prod`
- [ ] Commit

### Task 7: Rewrite school project source files (kippnewark, kippcamden, kippmiami — 3 files)

- [ ] Replace inline Jinja in the 3 school-resident source files
- [ ] Parse each project
- [ ] Commit

### Task 8: Rewrite source-system package source files (12 files across amplify, deanslist, edplan, finalsite, iready, overgrad, pearson, powerschool, renlearn, titan)

- [ ] Replace inline Jinja in all 12 source-system package source files
- [ ] Note: `dbt parse` directly against a standalone source-system project will
      fail after this change — this is expected (macro lives in consuming
      project namespace)
- [ ] Parse each via its consuming school project to verify
- [ ] Commit

---

## Phase 3 — Cleanup

### Task 9: Remove old targets from `.dbt/profiles.yml`

- [ ] Keep only `dev`/`dev-region`/`staging`/`prod` for kipptaf;
      `dev`/`staging`/`prod` for other school/network projects; `dev` only for
      source-system projects
- [ ] Verify `dbt debug` still resolves for each project type
- [ ] Commit

### Task 10: Remove `DBT_CLOUD_ENVIRONMENT_TYPE` from devcontainer and VS Code settings

- [ ] Present as manual block for `.devcontainer/devcontainer.json` (protected
      file)
- [ ] Remove from `.vscode/settings.json` if present
- [ ] Commit `.vscode/settings.json` change

### Task 11: Delete `scripts/dbt-sxs.py` and document replacement in `scripts/CLAUDE.md`

- [ ] Delete `scripts/dbt-sxs.py`
- [ ] Update `scripts/CLAUDE.md`: replace the `dbt-sxs.py` table entry with an
      entry for the new VS Code task, documenting:
  - How to select a project
  - How to filter to specific sources (equivalent of `--select`)
  - How to target the test GCS bucket (equivalent of `--test`)
- [ ] Commit

### Task 12: Set up `post-merge` git hook and devcontainer wiring (both manual blocks)

Present as manual blocks (both files are protected):

**`.git/hooks/post-merge`**:

```bash
#!/usr/bin/env bash
set -e
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --target-path target/prod
done
```

**`.devcontainer/scripts/postStart.sh`** addition — wire the same `dbt parse`
loop so the prod manifest is available on first Codespace session.

### Task 13: Configure Power User `--defer` in VS Code settings

- [ ] Add to `.vscode/settings.json`:

```json
{
  "dbt.deferConfigPerProject": {
    "kipptaf": {
      "deferToProduction": true,
      "manifestPathForDeferral": "src/dbt/kipptaf/target/prod/manifest.json",
      "favorState": false
    }
  }
}
```

- [ ] Add similar entries for regional projects as needed
- [ ] Verify Power User picks up the config (check "Apply defer configuration"
      in command palette)
- [ ] Commit

### Task 14: Add VS Code task for staging external sources

- [ ] Add to `.vscode/tasks.json`:

```json
{
  "label": "dbt: Stage External Sources",
  "type": "shell",
  "command": "uv run dbt run-operation stage_external_sources --project-dir src/dbt/${input:dbtProject} --target ${input:dbtSxsTarget} --vars '{\"ext_full_refresh\": \"true\", \"cloud_storage_uri_base\": \"gs://teamster-${input:dbtProject}/dagster/${input:dbtProject}\"}' --args 'select: ${input:dbtSourceSelect}'",
  "problemMatcher": []
}
```

With inputs:

```json
{
  "id": "dbtProject",
  "type": "pickString",
  "description": "dbt project",
  "options": ["kipptaf", "kippnewark", "kippcamden", "kippmiami", "kipppaterson"]
},
{
  "id": "dbtSxsTarget",
  "type": "pickString",
  "description": "Target environment",
  "options": ["dev", "staging"],
  "default": "dev"
},
{
  "id": "dbtSourceSelect",
  "type": "promptString",
  "description": "Source selection (e.g. google_sheets.my_source). Use * to stage all sources.",
  "default": "*"
}
```

- [ ] Commit

---

## Post-Migration Verification

### Task 15: Full staging build and cleanup

- [ ] Stage all external sources to `zz_stg_*` using VS Code task
- [ ] Trigger a full staging build in dbt Cloud
- [ ] Confirm CI is healthy on a test PR
- [ ] Update spec and plan statuses to COMPLETE
- [ ] Audit and drop old `z_dev_*` BigQuery datasets
- [ ] Open PR referencing issue #3511
