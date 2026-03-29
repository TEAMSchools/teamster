# dbt Schema Resolution Rework

|                 | Status      |
| --------------- | ----------- |
| **Spec**        | APPROVED    |
| **Plan**        | NOT STARTED |
| **Development** | NOT STARTED |

## Problem

Schema logic is scattered across individual `sources*.yml` files with
inconsistent Jinja conditionals. Some check three conditions (`target.name`,
`DBT_CLOUD_ENVIRONMENT_TYPE`, `GITHUB_USER`), some check one, some check none.
There is no `generate_schema_name` or `generate_database_name` macro — output
schema logic lives entirely in `profiles.yml` targets. This inconsistency makes
developer workflows unreliable and error-prone.

## Goals

1. Consistent schema resolution across all 15 dbt projects
2. Safe defaults — developers cannot accidentally write to production
3. Support `--defer` via dbt Power User for everyday development — unchanged
   `ref()` models resolve to prod. Regional source data (kipptaf
   `sources-kipp*.yml`) also resolves to prod by default via a dedicated macro;
   opt-in to personal namespace via `--target dev-region`
4. dbt Cloud CI validates PRs against staging datasets
5. New integration development (including external sources) works in isolation

## Design

### Target-Driven Architecture

All schema resolution is controlled by `--target`. School/network projects get
three targets (`dev`, `staging`, `prod`); source-system projects get a single
`dev` target. One shared macro centralizes source schema logic. Model output
schemas are handled by dbt's built-in `generate_schema_name` default, which
already produces the correct behavior when profiles carry the right `schema`
prefix per target.

### Macros

#### Placement strategy

The `resolve_source_schema` macro lives in the **5 school/network projects
only** (kipptaf, kippnewark, kippcamden, kippmiami, kipppaterson). Source-system
projects (amplify, deanslist, edplan, finalsite, iready, overgrad, pearson,
powerschool, renlearn, titan) are consumed as dbt packages — their source files
call `resolve_source_schema` at compile time, but the macro is resolved from the
consuming project's namespace.

Source-system projects do NOT get their own copy of the macro.

#### `resolve_source_schema(base_schema)`

Controls where `source()` calls read from. Used in all projects **except** for
kipptaf's cross-regional source files (see `resolve_region_source_schema`).

| Target    | Result                           |
| --------- | -------------------------------- |
| `dev`     | `zz_<GITHUB_USER>_<base_schema>` |
| `staging` | `zz_stg_<base_schema>`           |
| `prod`    | `<base_schema>`                  |

Implementation:

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

All inline Jinja conditionals in source files are replaced with a single macro
call, with the exception noted below for kipptaf cross-regional sources. This
applies to source files in **all** projects — including source-system packages,
which resolve the macro from the consuming project's namespace at compile time.

```yaml
# before (inconsistent, per-file logic)
schema: |
  {%- if target.name == 'staging' -%}z_dev_
  {%- elif env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'staging' -%}z_dev_
  {%- elif env_var('GITHUB_USER', '') != '' -%}zz_{{ env_var('GITHUB_USER') }}_
  {%- endif -%}kippnewark_powerschool

# after
schema: "{{ resolve_source_schema('kippnewark_powerschool') }}"
```

#### `resolve_region_source_schema(base_schema)` (kipptaf only)

Controls where kipptaf's cross-regional `source()` calls read from. Used
exclusively in `sources-kippnewark.yml`, `sources-kippcamden.yml`,
`sources-kippmiami.yml`, and `sources-kipppaterson.yml`. These files point to
regional staging model outputs — authoritative BigQuery tables that live in
production and do not belong in any developer's personal namespace.

Default behavior is production (no prefix). Developers working on regional model
changes and needing to test end-to-end through kipptaf opt in via
`--target dev-region`.

| Target       | Result                           |
| ------------ | -------------------------------- |
| `dev`        | `<base_schema>` (production)     |
| `dev-region` | `zz_<GITHUB_USER>_<base_schema>` |
| `staging`    | `zz_stg_<base_schema>`           |
| `prod`       | `<base_schema>`                  |

Implementation:

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

This macro lives in **kipptaf only** — no other project has cross-regional
source files.

#### Model output schemas (no custom macro needed)

dbt's built-in `generate_schema_name` default produces
`<target.schema>_<custom_schema>` (or just `<target.schema>` when no custom
schema is set). Since the profile's `schema` field already carries the correct
prefix per target, this produces the right output without any override:

| Target    | custom_schema | Result                                 |
| --------- | ------------- | -------------------------------------- |
| `dev`     | `powerschool` | `zz_<GITHUB_USER>_kipptaf_powerschool` |
| `dev`     | (none)        | `zz_<GITHUB_USER>_kipptaf`             |
| `staging` | `powerschool` | `zz_stg_kipptaf_powerschool`           |
| `staging` | (none)        | `zz_stg_kipptaf`                       |
| `prod`    | `powerschool` | `kipptaf_powerschool`                  |
| `prod`    | (none)        | `kipptaf`                              |

No `generate_schema_name` override is defined in any project. dbt ignores custom
`generate_schema_name` macros in installed packages, so this also avoids
namespace collision issues with source-system packages.

### Profiles

#### `.dbt/profiles.yml` (local dev + dbt Cloud)

School/network projects get three targets (`dev`, `staging`, `prod`). Default
target is `dev` (safe). Source-system projects get a single `dev` target —
matching the `integration_tests` pattern.

```yaml
kipptaf:
  target: dev
  outputs:
    dev:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    dev-region:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    staging:
      type: bigquery
      schema: zz_stg_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    prod:
      type: bigquery
      schema: kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
```

`dev-region` is identical to `dev` in output schema — the only difference is the
target name, which `resolve_region_source_schema` keys off to resolve kipptaf's
cross-regional sources to personal namespace instead of production.

The 5 school/network projects (`kipptaf`, `kippnewark`, `kippcamden`,
`kippmiami`, `kipppaterson`) get all three standard targets. kipptaf
additionally gets `dev-region`.

Source-system projects (`amplify`, `deanslist`, `edplan`, `finalsite`, `iready`,
`overgrad`, `pearson`, `powerschool`, `renlearn`, `titan`) get a single `dev`
target — the same pattern as `integration_tests`. They are consumed as packages
in prod and never deployed standalone, so `staging` and `prod` targets are not
needed.

#### `src/dbt/<project>/profiles.yml` (shipped to Dagster)

Two targets: `dev` (default, safe for local `dagster dev`) and `prod`.

```yaml
kipptaf:
  target: dev
  outputs:
    dev:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    prod:
      type: bigquery
      schema: kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
```

### Dagster

One change to `get_dbt_cli_resource` in `src/teamster/core/resources.py`. The
`test` parameter and hardcoded executable path are dead code (no caller passes
`test=True`) and are removed. The factory detects Dagster Cloud prod via
`DAGSTER_CLOUD_DEPLOYMENT_NAME`:

```python
def get_dbt_cli_resource(dbt_project: DbtProject) -> DbtCliResource:
    if os.getenv("DAGSTER_CLOUD_DEPLOYMENT_NAME") and not os.getenv(
        "DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT"
    ):
        return DbtCliResource(project_dir=dbt_project, target="prod")
    return DbtCliResource(project_dir=dbt_project)
```

| Context             | Behavior                   |
| ------------------- | -------------------------- |
| Dagster Cloud prod  | `target="prod"` (explicit) |
| Branch deploy       | Profile default (`dev`)    |
| Local `dagster dev` | Profile default (`dev`)    |

Branch deploys and local dev are identical — both write to dev schemas.

Note: today, local `dagster dev` writes to prod because the shipped profile
default points to the prod schema. This change fixes that.

No other Dagster code changes required — callers continue to call
`get_dbt_cli_resource(DBT_PROJECT)` without arguments.

### dbt Cloud

#### Job target name changes

| Job                      | Current target | New target |
| ------------------------ | -------------- | ---------- |
| Build Modified - CI      | `default`      | `staging`  |
| Build Modified - Staging | `default`      | `staging`  |
| Parse - Staging          | `default`      | `staging`  |
| Parse - Production       | `default`      | `prod`     |

#### Environment changes

- Staging environment dataset: `z_dev_kipptaf` → `zz_stg_kipptaf`

### Power User `--defer`

#### Production manifest generation

A `post-merge` git hook generates prod manifests locally:

```bash
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --target-path target/prod
done
```

The `--target-path target/prod` keeps the prod manifest separate from the
default `target/` directory used during development.

This hook also runs in the devcontainer `postStartCommand` so the manifest is
available from the first session.

#### VS Code configuration

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

Similar entries for regional projects as needed.

`favorState: false` means Power User defers based on the prod manifest only — it
does not skip models whose upstream deps have not changed. New models absent
from the prod manifest are built locally as normal.

> **Open question**: The Power User command palette exposes "Apply defer
> configuration" — it is unclear whether this is a mandatory one-time setup step
> or an optional activation command. This must be verified during
> implementation. There is no confirmed interactive toggle for
> `deferToProduction`; developers who need to disable defer (e.g., new
> integration workflow) should run `dbt build --select <model>+` directly from
> the terminal rather than using Power User's run button.

### VS Code Task: Stage External Sources

A VS Code task with input prompts for project, target, and source selection:

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
"inputs": [
  {
    "id": "dbtProject",
    "type": "pickString",
    "description": "dbt project",
    "options": [
      "kipptaf", "kippnewark", "kippcamden", "kippmiami", "kipppaterson"
    ]
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
]
```

## Developer Workflows

### Modify existing kipptaf models

1. Work on models with `--target dev` (default)
2. Power User `--defer` resolves upstream `ref()` calls to prod manifest — only
   modified models build into `zz_<GITHUB_USER>_kipptaf_*`

### Add/modify an external source (e.g. Google Sheets)

1. Modify source definition in `sources-external.yml`
2. Run VS Code task "dbt: Stage External Sources" → pick project → `dev` → enter
   source name
3. Build/test the staging model locally with `--target dev`. `--defer` can be
   used — unchanged upstream models resolve to prod; the modified staging model
   builds against the dev-prefixed source
4. Run VS Code task again → pick project → `staging` → same source name (CI
   prep)
5. Open PR — CI validates against staging schema

### New integration (new source + staging model)

1. Add source + staging model definitions
2. Run VS Code task "dbt: Stage External Sources" → pick project → `dev` → enter
   source name
3. Build/test locally with `--target dev`. `--defer` can be used — existing
   upstream `ref()` calls resolve to the prod manifest; only the new models
   (absent from prod) build locally
4. Run VS Code task again → pick project → `staging` → same source name (CI
   prep)
5. Open PR

### Everyday kipptaf development (no regional changes)

1. Work on models with `--target dev` (default)
2. `resolve_region_source_schema` returns bare production schema names for
   cross-regional sources — no regional builds required locally
3. Power User `--defer` resolves upstream `ref()` calls to prod manifest

### Cross-project development (regional + kipptaf)

1. Develop regional project with `--target dev` → writes to
   `zz_<user>_kippnewark_*`
2. In kipptaf, use `--target dev-region` → `resolve_region_source_schema`
   returns `zz_<user>_kippnewark_powerschool` → reads your regional dev output
3. Test end-to-end locally
4. Stage to staging for both projects before PR

### dbt Cloud CI — PR check

1. Job runs with `--target staging`, defers to Staging manifest
2. Sources resolve to `zz_stg_*` schemas
3. External tables pre-staged by developer via VS Code task
4. Only modified models build into `dbt_cloud_pr_*` schema

### Dagster — production build

1. `DbtCliResource` passes `target="prod"`
2. Sources resolve to prod schemas
3. Models write to prod schemas
4. External sources staged inline by Dagster's `build_dbt_assets`

## Migration

### Ordering

The migration must be phased to avoid broken builds during the transition.
Source files currently use inline Jinja that checks `target.name`,
`DBT_CLOUD_ENVIRONMENT_TYPE`, and `GITHUB_USER`. The new macros check only
`target.name`. Both old and new logic produce correct results for
`--target prod` (bare schema), so prod is never at risk during migration.

#### Phase 1: Deploy macros, update profiles, and update dbt Cloud (backward-compatible)

dbt Cloud target name changes must happen **before** source files are rewritten.
After Phase 2, `resolve_source_schema` uses only `target.name` — if dbt Cloud
still passes `target: default`, the `else` branch fires and CI reads from prod
schemas instead of `zz_stg_*`.

1. Add `resolve_source_schema` macro to the 5 school/network projects
1. Update `.dbt/profiles.yml` — add `dev`/`staging`/`prod` targets alongside
   existing targets (do not remove old targets yet)
1. Update shipped `src/dbt/<project>/profiles.yml` — add `dev` and `prod`
   targets, set default to `dev`
1. Update `get_dbt_cli_resource` to pass `target="prod"` in Dagster Cloud;
   remove dead `test` parameter
1. Deploy Dagster — prod continues to work (explicit `target="prod"`)
1. Update dbt Cloud job target names (`default` → `staging`/`prod`)
1. Update Staging environment dataset (`z_dev_kipptaf` → `zz_stg_kipptaf`)

#### Phase 2: Rewrite source files

Scope includes all source files with inline Jinja — approximately 61 files
across all 15 projects. This includes:

- Source-system package source files
  (`src/dbt/<source-system>/models/**/sources*.yml`)
- School-project-resident source files that live directly in school projects
  (e.g., `kippnewark/models/edplan/sources-drive.yml`,
  `kippcamden/models/edplan/sources-drive.yml`,
  `kippmiami/models/fldoe/sources.yml`)
- Source files with no existing conditionals are left unchanged

Note: after rewriting source-system package source files to call
`resolve_source_schema`, running `dbt parse` or `dbt compile` directly against a
standalone source-system project (e.g.,
`dbt parse --project-dir src/dbt/powerschool`) will fail — the macro is not
defined in that project's namespace. This is expected; source-system projects
are only compiled as packages within school projects.

Steps:

1. Replace inline Jinja in all in-scope source files with
   `resolve_source_schema()` calls, **except** for kipptaf's four cross-regional
   source files (`sources-kippnewark.yml`, `sources-kippcamden.yml`,
   `sources-kippmiami.yml`, `sources-kipppaterson.yml`) — these use
   `resolve_region_source_schema()` instead
1. Test locally with `--target dev` and `--target prod`

#### Phase 3: Clean up

1. Remove old target names from `.dbt/profiles.yml`; simplify source-system
   profiles to single `dev` target
1. Remove `DBT_CLOUD_ENVIRONMENT_TYPE` env var from `.devcontainer/` and
   `.vscode/settings.json`
1. Delete `scripts/dbt-sxs.py`; update `scripts/CLAUDE.md` to replace its entry
   with the VS Code task equivalent, documenting project selection, source
   filtering (equivalent of `--select`), and the test-bucket option (equivalent
   of `--test`)
1. Set up `post-merge` git hook for prod manifest generation — install to
   `.git/hooks/post-merge`; also wire into devcontainer `postStartCommand` so it
   runs on Codespace creation
1. Configure Power User `--defer` in `.vscode/settings.json`
1. Add VS Code task for staging external sources

### Naming changes

| Current pattern                            | New pattern                        |
| ------------------------------------------ | ---------------------------------- |
| `z_dev_<project>`                          | `zz_stg_<project>`                 |
| Target name: project name (e.g. `kipptaf`) | Target name: `dev`                 |
| Source-system: region-specific targets     | Source-system: single `dev` target |

### Cleanup

Before dropping old datasets, run full staging builds to confirm `zz_stg_*`
datasets are fully populated and CI is healthy. Then drop old `z_dev_*` datasets
from BigQuery.

## Risks

### `GITHUB_USER` unset

If `GITHUB_USER` is not set, `resolve_source_schema` defaults to
`zz_dev_<project>` and `resolve_region_source_schema` defaults to
`zz_dev_<base_schema>`. In practice, `GITHUB_USER` is always set by the
devcontainer (injected from 1Password). In dbt Cloud CI the staging target is
used so `GITHUB_USER` is never needed. A developer outside Codespaces without
`GITHUB_USER` gets a shared `zz_dev_*` namespace — acceptable given that all
development happens in Codespaces.

### `dbt parse --target prod` in git hook

`dbt parse` does not require database access — it only reads project files and
generates a manifest. The prod target's `method: oauth` is irrelevant since no
queries are executed. If parsing fails (e.g., syntax error in a model), the
manifest is stale but not blocking — Power User falls back gracefully.
