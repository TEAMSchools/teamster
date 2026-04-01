# dbt Schema Resolution Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered inline Jinja conditionals in dbt source files with
centralized macros controlled by a 4-target architecture
(`defer`/`dev`/`staging`/`prod`).

**Architecture:** Two macros (`resolve_source_schema`,
`resolve_region_source_schema`) centralize all source schema resolution. A
`check_prod_guard` macro prevents accidental production writes. Profile changes
across `.dbt/profiles.yml` (local dev) and `src/dbt/<project>/profiles.yml`
(shipped to Dagster) align target names. Phase 1 is backward-compatible; Phase 2
rewrites ~78 source files; Phase 3 cleans up old config and adds developer
tooling.

**Tech Stack:** dbt (Jinja SQL macros, YAML source definitions), BigQuery,
Dagster (Python resource factory), VS Code (tasks, settings), bash (git hooks)

**Spec:**
[`docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md`](../specs/2026-03-25-dbt-schema-resolution-design.md)

---

## File Structure

### New files

| File                                                | Purpose                                                                     |
| --------------------------------------------------- | --------------------------------------------------------------------------- |
| `src/dbt/kipptaf/macros/schema_resolution.sql`      | `resolve_source_schema`, `resolve_region_source_schema`, `check_prod_guard` |
| `src/dbt/kippnewark/macros/schema_resolution.sql`   | `resolve_source_schema`, `check_prod_guard`                                 |
| `src/dbt/kippcamden/macros/schema_resolution.sql`   | `resolve_source_schema`, `check_prod_guard`                                 |
| `src/dbt/kippmiami/macros/schema_resolution.sql`    | `resolve_source_schema`, `check_prod_guard`                                 |
| `src/dbt/kipppaterson/macros/schema_resolution.sql` | `resolve_source_schema`, `check_prod_guard`                                 |
| `.git/hooks/post-merge`                             | Generate prod manifests for Power User `--defer`                            |
| `docs/guides/dbt-development.md`                    | Developer guide for new workflows                                           |

### Modified files

| File                                    | Change                                                                              |
| --------------------------------------- | ----------------------------------------------------------------------------------- |
| `.dbt/profiles.yml`                     | Add `defer`/`dev`/`staging`/`prod` targets for school projects                      |
| `src/dbt/<school>/profiles.yml` (×5)    | Add `defer` + `prod` targets, default `defer`                                       |
| `src/dbt/<school>/dbt_project.yml` (×5) | Add `on-run-start` for `check_prod_guard`                                           |
| `src/teamster/core/resources.py`        | Simplify `get_dbt_cli_resource`                                                     |
| ~78 `sources*.yml` files                | Replace inline Jinja with macro calls                                               |
| `.vscode/settings.json`                 | Add Power User defer config, remove `DBT_CLOUD_ENVIRONMENT_TYPE`                    |
| `.vscode/tasks.json`                    | Add "Stage External Sources" task                                                   |
| `.devcontainer/devcontainer.json`       | Wire `post-merge` hook into `postStartCommand`, remove `DBT_CLOUD_ENVIRONMENT_TYPE` |
| `docs/guides/google-sheets.md`          | Replace `dbt-sxs.py` refs with links to new guide                                   |
| `docs/guides/index.md`                  | Add routing table entry                                                             |
| `mkdocs.yml`                            | Add nav entry                                                                       |
| `scripts/CLAUDE.md`                     | Replace `dbt-sxs.py` entry with VS Code task docs                                   |

### Deleted files

| File                 | Reason                   |
| -------------------- | ------------------------ |
| `scripts/dbt-sxs.py` | Replaced by VS Code task |

---

## Phase 1: Deploy macros, update profiles, update Dagster

Phase 1 is fully backward-compatible. Old source files continue working because
the new macros are not yet called. Old profile targets remain alongside new
ones.

### Task 1: Add macros to school projects

**Files:**

- Create: `src/dbt/kipptaf/macros/schema_resolution.sql`
- Create: `src/dbt/kippnewark/macros/schema_resolution.sql`
- Create: `src/dbt/kippcamden/macros/schema_resolution.sql`
- Create: `src/dbt/kippmiami/macros/schema_resolution.sql`
- Create: `src/dbt/kipppaterson/macros/schema_resolution.sql`
- Modify: `src/dbt/kipptaf/dbt_project.yml` (line 1 area — add `on-run-start`)
- Modify: `src/dbt/kippnewark/dbt_project.yml`
- Modify: `src/dbt/kippcamden/dbt_project.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml`

- [ ] **Step 1: Create kipptaf macro file (all 3 macros)**

Write `src/dbt/kipptaf/macros/schema_resolution.sql`:

```sql
{% macro resolve_source_schema(base_schema) %}
  {%- if target.name in ['defer', 'dev'] -%}
    zz_{{ env_var('GITHUB_USER', 'dev') }}_{{ base_schema }}
  {%- elif target.name == 'staging' -%}
    zz_stg_{{ base_schema }}
  {%- else -%}
    {{ base_schema }}
  {%- endif -%}
{% endmacro %}

{% macro resolve_region_source_schema(base_schema) %}
  {%- if target.name == 'dev' -%}
    zz_{{ env_var('GITHUB_USER', 'dev') }}_{{ base_schema }}
  {%- elif target.name == 'staging' -%}
    zz_stg_{{ base_schema }}
  {%- else -%}
    {{ base_schema }}
  {%- endif -%}
{% endmacro %}

{% macro check_prod_guard() %}
  {%- if target.name == 'prod' and not env_var('DAGSTER_CLOUD_DEPLOYMENT_NAME', '') -%}
    {{ exceptions.raise_compiler_error(
      "target 'prod' is reserved for production deployments. "
      ~ "Use --target defer (default) for development. "
      ~ "Set DAGSTER_CLOUD_DEPLOYMENT_NAME to override."
    ) }}
  {%- endif -%}
{% endmacro %}
```

- [ ] **Step 2: Create regional project macro files (2 macros each)**

Write the same file to each of the 4 regional projects. These get
`resolve_source_schema` and `check_prod_guard` only (no
`resolve_region_source_schema`).

Write `src/dbt/kippnewark/macros/schema_resolution.sql` (identical for
kippcamden, kippmiami, kipppaterson):

```sql
{% macro resolve_source_schema(base_schema) %}
  {%- if target.name in ['defer', 'dev'] -%}
    zz_{{ env_var('GITHUB_USER', 'dev') }}_{{ base_schema }}
  {%- elif target.name == 'staging' -%}
    zz_stg_{{ base_schema }}
  {%- else -%}
    {{ base_schema }}
  {%- endif -%}
{% endmacro %}

{% macro check_prod_guard() %}
  {%- if target.name == 'prod' and not env_var('DAGSTER_CLOUD_DEPLOYMENT_NAME', '') -%}
    {{ exceptions.raise_compiler_error(
      "target 'prod' is reserved for production deployments. "
      ~ "Use --target defer (default) for development. "
      ~ "Set DAGSTER_CLOUD_DEPLOYMENT_NAME to override."
    ) }}
  {%- endif -%}
{% endmacro %}
```

- [ ] **Step 3: Add `on-run-start` to each school project's `dbt_project.yml`**

Add the following block after the `config-version` line (before `profile:`) in
each of the 5 school project `dbt_project.yml` files:

```yaml
on-run-start:
  - "{{ check_prod_guard() }}"
```

Files to modify:

- `src/dbt/kipptaf/dbt_project.yml`
- `src/dbt/kippnewark/dbt_project.yml`
- `src/dbt/kippcamden/dbt_project.yml`
- `src/dbt/kippmiami/dbt_project.yml`
- `src/dbt/kipppaterson/dbt_project.yml`

- [ ] **Step 4: Validate macros parse**

Run `dbt parse` for each school project to confirm the macros are syntactically
valid. Use the existing profile targets (old names still work):

```bash
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --project-dir "src/dbt/${project}" --profiles-dir .dbt
done
```

Expected: all 5 parse successfully with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/macros/schema_resolution.sql \
  src/dbt/kippnewark/macros/schema_resolution.sql \
  src/dbt/kippcamden/macros/schema_resolution.sql \
  src/dbt/kippmiami/macros/schema_resolution.sql \
  src/dbt/kipppaterson/macros/schema_resolution.sql \
  src/dbt/kipptaf/dbt_project.yml \
  src/dbt/kippnewark/dbt_project.yml \
  src/dbt/kippcamden/dbt_project.yml \
  src/dbt/kippmiami/dbt_project.yml \
  src/dbt/kipppaterson/dbt_project.yml
git commit -m "feat(dbt): add schema resolution macros and prod guard to school projects"
```

---

### Task 2: Update `.dbt/profiles.yml`

Add new targets alongside existing ones. Do NOT remove old targets yet — they
remain functional during the transition.

**Files:**

- Modify: `.dbt/profiles.yml`

- [ ] **Step 1: Add new targets to each school profile**

For each of the 5 school profiles (`kipptaf`, `kippnewark`, `kippcamden`,
`kippmiami`, `kipppaterson`), add `defer`, `dev`, `staging`, and `prod` targets.
Change the default target to `defer`. Keep all existing targets intact.

The pattern for each school profile (using kipptaf as example):

```yaml
kipptaf:
  target: defer
  outputs:
    # new targets
    defer:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    dev:
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
    # old targets (kept for backward compatibility)
    kipptaf:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    # ... (keep existing staging target too)
```

Apply this pattern to all 5 school profiles, substituting the project name.

For source-system profiles (`amplify`, `deanslist`, `edplan`, `finalsite`,
`iready`, `overgrad`, `pearson`, `powerschool`, `renlearn`, `titan`): leave them
unchanged for now. They will be simplified in Phase 3.

- [ ] **Step 2: Validate new profiles parse**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target defer
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target dev
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target staging
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target prod
```

Expected: all 4 targets parse successfully. Repeat spot-check for one regional
project (e.g., kippnewark).

- [ ] **Step 3: Commit**

```bash
git add .dbt/profiles.yml
git commit -m "feat(dbt): add defer/dev/staging/prod targets to local profiles"
```

---

### Task 3: Update shipped profiles

**Files:**

- Modify: `src/dbt/kipptaf/profiles.yml`
- Modify: `src/dbt/kippnewark/profiles.yml`
- Modify: `src/dbt/kippcamden/profiles.yml`
- Modify: `src/dbt/kippmiami/profiles.yml`
- Modify: `src/dbt/kipppaterson/profiles.yml`

- [ ] **Step 1: Rewrite each shipped profile**

Each currently has a single target (the project name) pointing to the prod
schema. Replace with two targets: `defer` (default) and `prod`.

Example for kipptaf — write `src/dbt/kipptaf/profiles.yml`:

```yaml
kipptaf:
  target: defer
  outputs:
    defer:
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

Apply the same pattern to all 5 school projects, substituting the project name
in `schema:` and the profile key.

- [ ] **Step 2: Commit**

```bash
git add src/dbt/kipptaf/profiles.yml \
  src/dbt/kippnewark/profiles.yml \
  src/dbt/kippcamden/profiles.yml \
  src/dbt/kippmiami/profiles.yml \
  src/dbt/kipppaterson/profiles.yml
git commit -m "feat(dbt): add defer/prod targets to shipped profiles"
```

---

### Task 4: Update Dagster `get_dbt_cli_resource`

**Files:**

- Modify: `src/teamster/core/resources.py:58-64`

- [ ] **Step 1: Rewrite the function**

Replace the current function (lines 58-64):

```python
def get_dbt_cli_resource(dbt_project: DbtProject, test: bool = False) -> DbtCliResource:
    if test:
        return DbtCliResource(
            project_dir=dbt_project, dbt_executable="/workspaces/teamster/.venv/bin/dbt"
        )
    else:
        return DbtCliResource(project_dir=dbt_project)
```

With:

```python
def get_dbt_cli_resource(dbt_project: DbtProject) -> DbtCliResource:
    if os.getenv("DAGSTER_CLOUD_DEPLOYMENT_NAME") and not os.getenv(
        "DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT"
    ):
        return DbtCliResource(project_dir=dbt_project, target="prod")
    return DbtCliResource(project_dir=dbt_project)
```

Ensure `os` is imported at the top of the file (it likely already is — verify).

- [ ] **Step 2: Verify no callers pass `test=True`**

```bash
cd /workspaces/teamster
```

Search for `test=True` in calls to `get_dbt_cli_resource`:

```text
grep -r "get_dbt_cli_resource.*test" src/teamster/
```

Expected: no matches with `test=True`. All callers use
`get_dbt_cli_resource(DBT_PROJECT)` with no keyword args.

- [ ] **Step 3: Commit**

```bash
git add src/teamster/core/resources.py
git commit -m "feat(dagster): target prod explicitly in Dagster Cloud, remove dead test param"
```

---

### Task 5: Phase 1 validation

- [ ] **Step 1: Parse all school projects with new `defer` target**

```bash
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  echo "=== ${project} ==="
  uv run dbt parse --project-dir "src/dbt/${project}" --profiles-dir .dbt --target defer
done
```

Expected: all 5 parse successfully. Macros are defined but not yet called by any
source file — this just confirms profiles and macros coexist with existing code.

- [ ] **Step 2: Parse with `prod` target to verify guard doesn't fire on parse**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target prod
```

Expected: succeeds (parse does not trigger `on-run-start`).

- [ ] **Step 3: Verify prod guard blocks `dbt run`**

```bash
uv run dbt run --project-dir src/dbt/kipptaf --profiles-dir .dbt --target prod --select nonexistent_model 2>&1 || true
```

Expected: fails with `"target 'prod' is reserved for production deployments"`
error (the guard fires before model selection fails).

---

### Task 6: Manual — dbt Cloud changes

> **This task is performed manually by the project owner in the dbt Cloud UI.**
> It must be completed before Phase 2 begins.

- [ ] **Step 1: Update job target names**

| Job                      | Current target | New target |
| ------------------------ | -------------- | ---------- |
| Build Modified - CI      | `default`      | `staging`  |
| Build Modified - Staging | `default`      | `staging`  |
| Parse - Staging          | `default`      | `staging`  |
| Parse - Production       | `default`      | `prod`     |

- [ ] **Step 2: Update Staging environment dataset**

Change: `z_dev_kipptaf` → `zz_stg_kipptaf`

- [ ] **Step 3: Verify CI still passes on an existing PR**

Confirm a dbt Cloud CI run completes successfully with the new `staging` target
before proceeding to Phase 2.

---

## Phase 2: Rewrite source files

All source files with inline Jinja are rewritten to use macro calls.
Additionally, kipptaf cross-regional source files that currently have plain
string schemas are converted to use `resolve_region_source_schema` to enable the
`dev` target isolation workflow.

### Source file rewrite rules

**Rule 1 — kipptaf cross-regional files** (filename matches
`sources-kippnewark*`, `sources-kippcamden*`, `sources-kippmiami*`,
`sources-kipppaterson*`, or `sources-kippnj*` under `src/dbt/kipptaf/`):

Use `resolve_region_source_schema`. Extract the base schema name from the
existing `schema:` field.

```yaml
# before (any Jinja variant, or plain string)
schema: |
  {%- if target.name == 'staging' -%}z_dev_
  ...
  {%- endif -%}kippnewark_powerschool

# after
schema: "{{ resolve_region_source_schema('kippnewark_powerschool') }}"
```

**Rule 2 — all other source files with inline Jinja:**

Use `resolve_source_schema`. Extract the base schema name.

For files using `{{ project_name }}_<service>` or
`{{ var('name', project_name + '_service') }}`:

```yaml
# before
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'dev' -%}z_dev_{%- endif -%}
  {{ var('powerschool_schema', project_name + '_powerschool') }}

# after
schema: "{{ resolve_source_schema(var('powerschool_schema', project_name ~ '_powerschool')) }}"
```

For files using literal schema names:

```yaml
# before
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'dev' -%}z_dev_{%- endif -%}
  kipptaf_adp_payroll

# after
schema: "{{ resolve_source_schema('kipptaf_adp_payroll') }}"
```

**Rule 3 — source files with no Jinja and NOT cross-regional:** Leave unchanged.

---

### Task 7: Rewrite source-system package source files

These are source files in the 10 source-system projects. They use
`resolve_source_schema` which resolves from the consuming school project's
namespace at compile time.

**Files (10):**

- `src/dbt/amplify/models/sources.yml`
- `src/dbt/deanslist/models/sources.yml`
- `src/dbt/edplan/models/sources.yml`
- `src/dbt/edplan/models/sources-archive.yml`
- `src/dbt/finalsite/models/sources.yml`
- `src/dbt/iready/models/sources.yml`
- `src/dbt/overgrad/models/sources.yml`
- `src/dbt/pearson/models/sources.yml`
- `src/dbt/powerschool/models/sis/staging/odbc/sources.yml`
- `src/dbt/powerschool/models/sis/staging/sftp/sources.yml`
- `src/dbt/renlearn/models/sources.yml`
- `src/dbt/titan/models/sources.yml`

- [ ] **Step 1: Rewrite each source file**

For each file, read the current `schema:` field, extract the base schema
expression, and wrap it in `resolve_source_schema()`.

These files all use the `var()` pattern. Example for powerschool ODBC:

```yaml
# before (src/dbt/powerschool/models/sis/staging/odbc/sources.yml)
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') in ['dev', 'staging'] -%}z_dev_
  {%- endif -%}{{ var('powerschool_schema', project_name + '_powerschool') }}

# after
schema: "{{ resolve_source_schema(var('powerschool_schema', project_name ~ '_powerschool')) }}"
```

Note: Jinja's `~` operator is string concatenation (equivalent to `+` but
preferred in Jinja template expressions).

Apply the same pattern to all files. Each file's `var()` call uses a different
variable name and default — preserve them exactly.

- [ ] **Step 2: Commit**

```bash
git add src/dbt/amplify/models/sources.yml \
  src/dbt/deanslist/models/sources.yml \
  src/dbt/edplan/models/sources.yml \
  src/dbt/edplan/models/sources-archive.yml \
  src/dbt/finalsite/models/sources.yml \
  src/dbt/iready/models/sources.yml \
  src/dbt/overgrad/models/sources.yml \
  src/dbt/pearson/models/sources.yml \
  src/dbt/powerschool/models/sis/staging/odbc/sources.yml \
  src/dbt/powerschool/models/sis/staging/sftp/sources.yml \
  src/dbt/renlearn/models/sources.yml \
  src/dbt/titan/models/sources.yml
git commit -m "refactor(dbt): replace inline Jinja with resolve_source_schema in source-system packages"
```

---

### Task 8: Rewrite school-project-resident source files

These are source files that live directly in school projects (not kipptaf). They
use `resolve_source_schema`.

**Files (5):**

- `src/dbt/kippcamden/models/edplan/sources-drive.yml`
- `src/dbt/kippnewark/models/edplan/sources-drive.yml`
- `src/dbt/kippmiami/models/fldoe/sources.yml`
- `src/dbt/kippcamden/models/extracts/sources.yml` (verify — may be plain
  string)
- `src/dbt/kippnewark/models/extracts/sources.yml` (verify — may be plain
  string)
- `src/dbt/kippmiami/models/extracts/sources.yml` (verify — may be plain string)

- [ ] **Step 1: Read each file and rewrite if it has inline Jinja**

Apply Rule 2 from the rewrite rules above. Skip files with plain string schemas.

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "refactor(dbt): replace inline Jinja with resolve_source_schema in school project sources"
```

---

### Task 9: Rewrite kipptaf non-regional source files

These are kipptaf source files that are NOT cross-regional (don't match the
`sources-kipp*` naming pattern). They use `resolve_source_schema`.

**Files (~35 — all kipptaf source files with Jinja that are NOT
cross-regional):**

```text
src/dbt/kipptaf/models/adp/payroll/sources-external.yml
src/dbt/kipptaf/models/adp/workforce_manager/sources.yml
src/dbt/kipptaf/models/adp/workforce_now/api/sources-external.yml
src/dbt/kipptaf/models/adp/workforce_now/sftp/sources-external.yml
src/dbt/kipptaf/models/alchemer/sources-bigquery.yml
src/dbt/kipptaf/models/alchemer/sources-external.yml
src/dbt/kipptaf/models/collegeboard/sources.yml
src/dbt/kipptaf/models/coupa/api/sources-external.yml
src/dbt/kipptaf/models/coupa/fivetran/sources-fivetran.yml
src/dbt/kipptaf/models/dayforce/sources.yml
src/dbt/kipptaf/models/dayforce/sources-bigquery.yml
src/dbt/kipptaf/models/deanslist/sftp/sources-external.yml
src/dbt/kipptaf/models/google/appsheet/sources.yml
src/dbt/kipptaf/models/google/directory/sources.yml
src/dbt/kipptaf/models/google/forms/sources.yml
src/dbt/kipptaf/models/google/sheets/sources-external.yml
src/dbt/kipptaf/models/kippadb/sources-airbyte.yml
src/dbt/kipptaf/models/knowbe4/sources-external.yml
src/dbt/kipptaf/models/ldap/sources-external.yml
src/dbt/kipptaf/models/nsc/sources.yml
src/dbt/kipptaf/models/overgrad/sources-external.yml
src/dbt/kipptaf/models/performance_management/sources-bigquery.yml
src/dbt/kipptaf/models/performance_management/sources-external.yml
src/dbt/kipptaf/models/powerschool_enrollment/sources-external.yml
src/dbt/kipptaf/models/schoolmint/grow/sources-external.yml
src/dbt/kipptaf/models/smartrecruiters/sources.yml
src/dbt/kipptaf/models/surveys/sources.yml
src/dbt/kipptaf/models/tableau/sources.yml
src/dbt/kipptaf/models/zendesk/sources-airbyte.yml
src/dbt/kipptaf/models/zendesk/sources-external.yml
```

- [ ] **Step 1: Read each file, extract the base schema, apply Rule 2**

For files using `{{ project_name }}_<service>`:

```yaml
# before
schema: "{{ project_name }}_alchemer"
# after
schema: "{{ resolve_source_schema(project_name ~ '_alchemer') }}"
```

For files using literal strings with Jinja conditionals:

```yaml
# before
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'dev' -%}z_dev_{%- endif -%}
  kipptaf_adp_payroll
# after
schema: "{{ resolve_source_schema('kipptaf_adp_payroll') }}"
```

For files using `{{ var(...) }}`:

```yaml
# before
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'dev' -%}z_dev_{%- endif -%}
  {{ var('amplify_schema', project_name + '_amplify') }}
# after
schema: "{{ resolve_source_schema(var('amplify_schema', project_name ~ '_amplify')) }}"
```

For files with `{{ project_name }}` and no conditional (Pattern 1) — these
currently resolve to the bare schema with no prefix in all environments. They
need the macro to gain dev/staging prefix behavior:

```yaml
# before
schema: "{{ project_name }}_alchemer"
# after
schema: "{{ resolve_source_schema(project_name ~ '_alchemer') }}"
```

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "refactor(dbt): replace inline Jinja with resolve_source_schema in kipptaf sources"
```

---

### Task 10: Rewrite kipptaf cross-regional source files

These are kipptaf source files matching `sources-kipp*` — they use
`resolve_region_source_schema`. This includes files with existing Jinja AND
files with plain string schemas (both need the macro for `dev` target
isolation).

**Files (~27):**

```text
src/dbt/kipptaf/models/amplify/mclass/sources-kippnewark.yml
src/dbt/kipptaf/models/amplify/mclass/sources-kipppaterson.yml
src/dbt/kipptaf/models/amplify/dds/sources-bigquery.yml  (verify naming)
src/dbt/kipptaf/models/deanslist/api/sources-kippcamden.yml
src/dbt/kipptaf/models/deanslist/api/sources-kippmiami.yml
src/dbt/kipptaf/models/deanslist/api/sources-kippnewark.yml
src/dbt/kipptaf/models/edplan/sources-kippcamden.yml
src/dbt/kipptaf/models/edplan/sources-kippnewark.yml
src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml
src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml
src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml
src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml
src/dbt/kipptaf/models/fldoe/sources-kippmiami.yml
src/dbt/kipptaf/models/iready/sources-kippmiami.yml
src/dbt/kipptaf/models/iready/sources-kippnj.yml
src/dbt/kipptaf/models/overgrad/sources-kippcamden.yml
src/dbt/kipptaf/models/overgrad/sources-kippnewark.yml
src/dbt/kipptaf/models/pearson/sources-kippcamden.yml
src/dbt/kipptaf/models/pearson/sources-kippnewark.yml
src/dbt/kipptaf/models/pearson/sources-kipppaterson.yml
src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml
src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml
src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml
src/dbt/kipptaf/models/renlearn/sources-kippmiami.yml
src/dbt/kipptaf/models/renlearn/sources-kippnj.yml
src/dbt/kipptaf/models/titan/sources-kippcamden.yml
src/dbt/kipptaf/models/titan/sources-kippnewark.yml
```

- [ ] **Step 1: Read each file and apply Rule 1**

For files with inline Jinja — extract the base schema:

```yaml
# before (powerschool/sources-kippnewark.yml)
schema: |
  {%- if target.name == 'staging' -%}z_dev_
  {%- elif env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'staging' -%}z_dev_
  {%- elif env_var('GITHUB_USER', '') != '' -%}zz_{{ env_var('GITHUB_USER') }}_
  {%- endif -%}kippnewark_powerschool

# after
schema: "{{ resolve_region_source_schema('kippnewark_powerschool') }}"
```

For files with plain string schemas — add the macro call:

```yaml
# before (edplan/sources-kippnewark.yml — if plain string)
schema: kippnewark_edplan

# after
schema: "{{ resolve_region_source_schema('kippnewark_edplan') }}"
```

**Important:** Read each file to determine the actual base schema name. Do not
guess — extract it from the existing `schema:` field by stripping any Jinja
prefix logic.

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "refactor(dbt): replace inline Jinja with resolve_region_source_schema in kipptaf cross-regional sources"
```

---

### Task 11: Phase 2 validation

- [ ] **Step 1: Parse all school projects with `defer` target**

```bash
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  echo "=== ${project} (defer) ==="
  uv run dbt parse --project-dir "src/dbt/${project}" --profiles-dir .dbt --target defer
done
```

Expected: all 5 parse successfully.

- [ ] **Step 2: Parse kipptaf with `dev` target (cross-regional isolation)**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target dev
```

Expected: succeeds.

- [ ] **Step 3: Parse with `prod` target (bypass guard for validation)**

```bash
DAGSTER_CLOUD_DEPLOYMENT_NAME=prod uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target prod
```

Expected: succeeds.

- [ ] **Step 4: Compile a sample model to verify schema resolution**

```bash
uv run dbt compile --project-dir src/dbt/kipptaf --profiles-dir .dbt --target defer --select "source:kippnewark_powerschool+" 2>&1 | head -20
```

Verify the compiled SQL references `zz_<user>_kippnewark_powerschool` (not the
bare prod schema), confirming `resolve_source_schema` is working in `defer`
mode. Then repeat with `--target dev` for a cross-regional source to verify
`resolve_region_source_schema`:

```bash
uv run dbt compile --project-dir src/dbt/kipptaf --profiles-dir .dbt --target dev --select "source:kippnewark_powerschool+" 2>&1 | head -20
```

Verify the compiled SQL references `zz_<user>_kippnewark_powerschool` (personal
namespace for `dev` target via `resolve_region_source_schema`).

---

## Phase 3: Clean up

### Task 12: Clean up `.dbt/profiles.yml`

**Files:**

- Modify: `.dbt/profiles.yml`

- [ ] **Step 1: Remove old target names from school profiles**

For each school profile, remove the old target entries (e.g., `kipptaf:`,
`staging:` with `z_dev_` prefix) that were kept for backward compatibility. Only
`defer`, `dev`, `staging` (with `zz_stg_` prefix), and `prod` remain.

- [ ] **Step 2: Simplify source-system profiles**

Source-system profiles currently have multiple targets for different school
districts. Replace with a single `dev` target matching the `integration_tests`
pattern:

```yaml
powerschool:
  target: dev
  outputs:
    dev:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_powerschool
      method: oauth
      project: teamster-332318
      threads: 40
```

Apply to all 10 source-system profiles. Note: standalone `dbt parse` against
source-system projects will fail after Phase 2 (macro not in namespace) — this
is expected and documented in the spec.

- [ ] **Step 3: Validate**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target defer
```

- [ ] **Step 4: Commit**

```bash
git add .dbt/profiles.yml
git commit -m "refactor(dbt): clean up profiles, remove old targets, simplify source-system profiles"
```

---

### Task 13: Remove `DBT_CLOUD_ENVIRONMENT_TYPE`

**Files:**

- Modify: `.devcontainer/devcontainer.json` (line ~24 — remove
  `DBT_CLOUD_ENVIRONMENT_TYPE`)
- Modify: `.vscode/settings.json` (line ~58 — remove
  `DBT_CLOUD_ENVIRONMENT_TYPE`)

- [ ] **Step 1: Remove from both files**

In `.devcontainer/devcontainer.json`, remove the line:

```json
"DBT_CLOUD_ENVIRONMENT_TYPE": "dev",
```

In `.vscode/settings.json`, remove the same line from
`terminal.integrated.env.linux`.

- [ ] **Step 2: Validate parse still works (no env var dependency)**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --profiles-dir .dbt --target defer
```

- [ ] **Step 3: Commit**

These are protected files — draft the changes and present to the user for manual
application per `.claude/CLAUDE.md` hook rules. After manual edit, the user
stages and commits.

---

### Task 14: Delete `scripts/dbt-sxs.py` and update `scripts/CLAUDE.md`

**Files:**

- Delete: `scripts/dbt-sxs.py`
- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Delete the script**

```bash
git rm scripts/dbt-sxs.py
```

- [ ] **Step 2: Update `scripts/CLAUDE.md`**

Read `scripts/CLAUDE.md` and replace the `dbt-sxs.py` entry with documentation
for the VS Code task equivalent. Include:

- Task name: "dbt: Stage External Sources"
- Project selection (pickString: kipptaf, kippnewark, kippcamden, kippmiami,
  kipppaterson)
- Target selection (defer, dev, staging)
- Source selection (promptString, default `*`)
- Terminal equivalent command for non-VS-Code usage

- [ ] **Step 3: Commit**

```bash
git add scripts/CLAUDE.md
git commit -m "refactor: replace dbt-sxs.py with VS Code task documentation"
```

---

### Task 15: Set up `post-merge` git hook

**Files:**

- Create: `.git/hooks/post-merge`
- Modify: `.devcontainer/devcontainer.json` (add to `postStartCommand`)

- [ ] **Step 1: Create the hook script**

Write `.git/hooks/post-merge`:

```bash
#!/usr/bin/env bash
# Generate prod manifests for Power User --defer
# Runs in parallel — dbt parse is CPU-only (no DB access)

cd "$(git rev-parse --show-toplevel)" || exit 0

for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --profiles-dir .dbt \
    --target-path target/prod &
done
wait
```

Make it executable:

```bash
chmod +x .git/hooks/post-merge
```

- [ ] **Step 2: Wire into devcontainer `postStartCommand`**

The `.devcontainer/devcontainer.json` `postStartCommand` currently runs
`bash .devcontainer/scripts/postStart.sh`. Update `postStart.sh` to include the
manifest generation at the end:

```bash
# Generate prod manifests for Power User --defer
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --profiles-dir .dbt \
    --target-path target/prod &
done
wait
```

Note: `.devcontainer/scripts/` is a protected path — draft the change and
present to the user for manual application.

- [ ] **Step 3: Test the hook locally**

```bash
bash .git/hooks/post-merge
ls src/dbt/kipptaf/target/prod/manifest.json
```

Expected: manifest file exists.

- [ ] **Step 4: Commit**

The `.git/hooks/` directory is not tracked by git. The hook is installed via the
devcontainer `postStartCommand` (which copies/creates it) or manually. Only
commit the `postStart.sh` change.

---

### Task 16: Configure Power User `--defer`

**Files:**

- Modify: `.vscode/settings.json`

- [ ] **Step 1: Add defer configuration**

Add the following to `.vscode/settings.json`:

```json
"dbt.deferConfigPerProject": {
  "kipptaf": {
    "deferToProduction": true,
    "manifestPathForDeferral": "src/dbt/kipptaf/target/prod/manifest.json",
    "favorState": false
  },
  "kippnewark": {
    "deferToProduction": true,
    "manifestPathForDeferral": "src/dbt/kippnewark/target/prod/manifest.json",
    "favorState": false
  },
  "kippcamden": {
    "deferToProduction": true,
    "manifestPathForDeferral": "src/dbt/kippcamden/target/prod/manifest.json",
    "favorState": false
  },
  "kippmiami": {
    "deferToProduction": true,
    "manifestPathForDeferral": "src/dbt/kippmiami/target/prod/manifest.json",
    "favorState": false
  },
  "kipppaterson": {
    "deferToProduction": true,
    "manifestPathForDeferral": "src/dbt/kipppaterson/target/prod/manifest.json",
    "favorState": false
  }
}
```

Note: `.vscode/settings.json` is a protected path — draft the change and present
to the user for manual application.

---

### Task 17: Add VS Code task for staging external sources

**Files:**

- Modify: `.vscode/tasks.json`

- [ ] **Step 1: Add the task and inputs**

Add the following task to the `tasks` array in `.vscode/tasks.json`:

```json
{
  "label": "dbt: Stage External Sources",
  "type": "shell",
  "command": "uv run dbt run-operation stage_external_sources --project-dir src/dbt/${input:dbtProject} --target ${input:dbtSxsTarget} --vars '{\"ext_full_refresh\": \"true\", \"cloud_storage_uri_base\": \"gs://teamster-${input:dbtProject}/dagster/${input:dbtProject}\"}' --args 'select: ${input:dbtSourceSelect}'",
  "problemMatcher": []
}
```

Add the following inputs (if not already present, merge with existing `inputs`
array — note the existing `dbtProject` input from the "dbt: Build Init" task may
need the options list updated):

```json
{
  "id": "dbtSxsTarget",
  "type": "pickString",
  "description": "Target environment",
  "options": ["defer", "dev", "staging"],
  "default": "defer"
},
{
  "id": "dbtSourceSelect",
  "type": "promptString",
  "description": "Source selection (e.g. google_sheets.my_source). Use * to stage all sources.",
  "default": "*"
}
```

Note: `.vscode/tasks.json` is a protected path — draft the change and present to
the user for manual application.

---

### Task 18: Update developer-facing docs

**Files:**

- Create: `docs/guides/dbt-development.md`
- Modify: `docs/guides/google-sheets.md`
- Modify: `docs/guides/index.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Create `docs/guides/dbt-development.md`**

Write a guide covering:

- **Targets**: `defer` (default), `dev`, `staging`, `prod` — when to use each
- **Power User `--defer`**: How it works, `favorState: false` behavior, stale
  dev schema cleanup (drop `zz_<user>_*` datasets in BigQuery if needed)
- **VS Code task: Stage External Sources**: Project selection, target selection,
  source selection, terminal equivalent command
- **Cross-project development**: `--target dev` for kipptaf when working on
  regional models
- **Prod guard**: `check_prod_guard` blocks `--target prod` outside Dagster
  Cloud; override with `DAGSTER_CLOUD_DEPLOYMENT_NAME=prod`
- **Post-merge hook**: Generates prod manifests automatically; runs on
  `postStartCommand` for new Codespaces

- [ ] **Step 2: Update `docs/guides/google-sheets.md`**

Replace lines 41-47 (bare `stage_external_sources` command) with a link:

```markdown
4. Stage the external source definition. See the
   [dbt Development guide](dbt-development.md#staging-external-sources) for
   details on using the VS Code task or terminal command.
```

Replace lines 91-99 (dbt-sxs.py verification section) with:

```markdown
### Verifying a Google Sheets source against production

Power User's `--defer` mode automatically resolves unchanged upstream models to
production. Build your modified staging model and downstream consumers will
reference prod data for anything you haven't changed. See the
[dbt Development guide](dbt-development.md#power-user-defer) for details.
```

Also replace the second `stage_external_sources` command (lines 120-123) with
the same link pattern.

- [ ] **Step 3: Add routing table entry to `docs/guides/index.md`**

Add a row to the guide routing table:

```markdown
| [dbt Development](dbt-development.md) | Targets, defer, staging external
sources, cross-project workflows |
```

- [ ] **Step 4: Add nav entry to `mkdocs.yml`**

Add after the "Google Sheets & Forms" entry in the `nav:` → `Guides:` section:

```yaml
- dbt Development: guides/dbt-development.md
```

- [ ] **Step 5: Commit**

```bash
git add docs/guides/dbt-development.md \
  docs/guides/google-sheets.md \
  docs/guides/index.md \
  mkdocs.yml
git commit -m "docs: add dbt development guide, update google-sheets and nav"
```

---

### Task 19: Update spec status

**Files:**

- Modify: `docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md`

- [ ] **Step 1: Update status table**

```markdown
| **Spec** | APPROVED | | **Plan** | APPROVED | | **Development** | COMPLETE |
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md
git commit -m "docs: mark dbt schema resolution spec as complete"
```
