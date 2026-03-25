# dbt Schema Resolution Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered inline Jinja schema conditionals in all 61 dbt
source files with a centralized `resolve_source_schema` macro, backed by proper
`dev`/`staging`/`prod` profiles, so developers get safe defaults and consistent
schema resolution.

**Architecture:** Target-driven: `--target dev` (default) writes to
`zz_<GITHUB_USER>_*`, `--target staging` writes to `zz_stg_*`, `--target prod`
writes to bare schema names. A single `resolve_source_schema(base_schema)` macro
(in each of the 5 school/network projects) centralizes source schema logic.
Source-system projects resolve the macro from the consuming project's namespace
at compile time. Migration is phased: macros + profiles first
(backward-compatible), then source file rewrites, then cleanup.

**Tech Stack:** dbt (BigQuery), Jinja2 macros, YAML, Python (Dagster
`DbtCliResource`), bash (git hook), VS Code tasks

**Spec:**
[`docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md`](../specs/2026-03-25-dbt-schema-resolution-design.md)

|                 | Status      |
| --------------- | ----------- |
| **Plan**        | IN PROGRESS |
| **Development** | NOT STARTED |

---

## File Map

### Phase 1 — Macros, profiles, Dagster, dbt Cloud

| Action | File                                                    | What changes                                                                                                                   |
| ------ | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Create | `src/dbt/kipptaf/macros/resolve_source_schema.sql`      | New macro                                                                                                                      |
| Create | `src/dbt/kippnewark/macros/resolve_source_schema.sql`   | New macro                                                                                                                      |
| Create | `src/dbt/kippcamden/macros/resolve_source_schema.sql`   | New macro                                                                                                                      |
| Create | `src/dbt/kippmiami/macros/resolve_source_schema.sql`    | New macro                                                                                                                      |
| Create | `src/dbt/kipppaterson/macros/resolve_source_schema.sql` | New macro                                                                                                                      |
| Modify | `.dbt/profiles.yml`                                     | Rename `<project>` target → `dev`; update `staging` schema; add source-system `dev` target; keep old targets during transition |
| Modify | `src/dbt/kipptaf/profiles.yml`                          | Add `dev` + `prod` targets, default `dev`                                                                                      |
| Modify | `src/dbt/kippnewark/profiles.yml`                       | Add `dev` + `prod` targets, default `dev`                                                                                      |
| Modify | `src/dbt/kippcamden/profiles.yml`                       | Add `dev` + `prod` targets, default `dev`                                                                                      |
| Modify | `src/dbt/kippmiami/profiles.yml`                        | Add `dev` + `prod` targets, default `dev`                                                                                      |
| Modify | `src/dbt/kipppaterson/profiles.yml`                     | Add `dev` + `prod` targets, default `dev`                                                                                      |
| Modify | `src/teamster/core/resources.py`                        | Update `get_dbt_cli_resource` — detect prod via env var, remove dead `test` param                                              |
| Modify | `src/teamster/core/CLAUDE.md`                           | Update `get_dbt_cli_resource` docs                                                                                             |
| Manual | dbt Cloud UI                                            | Job target names: `default` → `staging`/`prod`                                                                                 |
| Manual | dbt Cloud UI                                            | Staging environment dataset: `z_dev_kipptaf` → `zz_stg_kipptaf`                                                                |

### Phase 2 — Source file rewrites (~61 files)

All `sources*.yml` files containing inline Jinja conditionals (`target.name`,
`DBT_CLOUD_ENVIRONMENT_TYPE`, `GITHUB_USER`). Grouped by project:

- **kipptaf** (46 files): all `src/dbt/kipptaf/models/**/sources*.yml` files
  with inline Jinja
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

| Action | File                                 | What changes                                                                                           |
| ------ | ------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Modify | `.dbt/profiles.yml`                  | Remove old targets (keep only `dev`/`staging`/`prod` for school/network; `dev` only for source-system) |
| Modify | `.devcontainer/devcontainer.json`    | Remove `DBT_CLOUD_ENVIRONMENT_TYPE` env var                                                            |
| Modify | `.vscode/settings.json`              | Remove `DBT_CLOUD_ENVIRONMENT_TYPE` if present; add Power User defer config                            |
| Modify | `.vscode/tasks.json`                 | Add "dbt: Stage External Sources" task + inputs                                                        |
| Delete | `scripts/dbt-sxs.py`                 | Replaced by VS Code task                                                                               |
| Modify | `scripts/CLAUDE.md`                  | Remove `dbt-sxs.py` entry                                                                              |
| Manual | `.git/hooks/post-merge`              | New bash script for prod manifest generation                                                           |
| Manual | `.devcontainer/scripts/postStart.sh` | Wire manifest generation (protected file — present as manual block)                                    |

---

## Phase 1 — Macros, Profiles, Dagster, dbt Cloud

### Task 1: Add `resolve_source_schema` macro to 5 school/network projects

**Files:**

- Create: `src/dbt/kipptaf/macros/resolve_source_schema.sql`
- Create: `src/dbt/kippnewark/macros/resolve_source_schema.sql`
- Create: `src/dbt/kippcamden/macros/resolve_source_schema.sql`
- Create: `src/dbt/kippmiami/macros/resolve_source_schema.sql`
- Create: `src/dbt/kipppaterson/macros/resolve_source_schema.sql`

- [ ] **Step 1: Create the macro in all 5 projects**

All 5 files have identical content:

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

- [ ] **Step 2: Confirm the current default target name in `.dbt/profiles.yml`**

Use the Read tool on `.dbt/profiles.yml`. The `kipptaf:` block currently has
`target: kipptaf`. Note whatever value appears — that is the target name to use
in Step 3 verification. (After Task 2, this becomes `dev`.)

- [ ] **Step 3: Verify macro compiles in kipptaf**

Run using the current target name from Step 2 (currently `kipptaf`):

```bash
uv run dbt parse --target kipptaf --project-dir src/dbt/kipptaf
```

Expected: `Done. PASS=... WARN=0 ERROR=0` (or same count as before). The macro
is additive — no source files call it yet, so behavior is unchanged.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/macros/resolve_source_schema.sql \
        src/dbt/kippnewark/macros/resolve_source_schema.sql \
        src/dbt/kippcamden/macros/resolve_source_schema.sql \
        src/dbt/kippmiami/macros/resolve_source_schema.sql \
        src/dbt/kipppaterson/macros/resolve_source_schema.sql
git commit -m "feat(dbt): add resolve_source_schema macro to school/network projects"
```

---

### Task 2: Update `.dbt/profiles.yml`

**Files:**

- Modify: `.dbt/profiles.yml`

The goal is to add `dev`/`staging`/`prod` targets alongside the existing targets
(don't remove old targets yet — Phase 3 cleanup does that). School/network
projects get all three new targets. Source-system projects get a single `dev`
target added.

- [ ] **Step 1: Update school/network project profiles**

For each of the 5 school/network projects (`kipptaf`, `kippnewark`,
`kippcamden`, `kippmiami`, `kipppaterson`), replace the current profile block
with:

```yaml
# kipptaf example — repeat pattern for all 5, substituting the project name
kipptaf:
  target: dev
  outputs:
    dev:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      threads: 40
      method: oauth
      project: teamster-332318
    staging:
      type: bigquery
      schema: zz_stg_kipptaf
      threads: 40
      method: oauth
      project: teamster-332318
    prod:
      type: bigquery
      schema: kipptaf
      method: oauth
      project: teamster-332318
      threads: 40
    # Legacy targets — kept during migration, removed in Phase 3
    kipptaf:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_kipptaf
      threads: 40
      method: oauth
      project: teamster-332318
```

Apply the same pattern to all 5 projects:

- `kippnewark`: schemas `zz_{{ env_var('GITHUB_USER', 'dev') }}_kippnewark` /
  `zz_stg_kippnewark` / `kippnewark`
- `kippcamden`: schemas `zz_{{ env_var('GITHUB_USER', 'dev') }}_kippcamden` /
  `zz_stg_kippcamden` / `kippcamden`
- `kippmiami`: schemas `zz_{{ env_var('GITHUB_USER', 'dev') }}_kippmiami` /
  `zz_stg_kippmiami` / `kippmiami`
- `kipppaterson`: schemas `zz_{{ env_var('GITHUB_USER', 'dev') }}_kipppaterson`
  / `zz_stg_kipppaterson` / `kipppaterson`

- [ ] **Step 2: Update source-system project profiles**

For each source-system project, replace the multi-target block with a single
`dev` target. Example for `amplify`:

```yaml
amplify:
  target: dev
  outputs:
    dev:
      type: bigquery
      schema: zz_{{ env_var('GITHUB_USER', 'dev') }}_amplify
      threads: 40
      method: oauth
      project: teamster-332318
```

Apply to all 10 source-system projects: `amplify`, `deanslist`, `edplan`,
`finalsite`, `iready`, `overgrad`, `pearson`, `powerschool`, `renlearn`,
`titan`. The source-system projects are only compiled as packages — the single
`dev` target exists only for direct local testing of package macros/structure.

Keep `integration_tests` unchanged.

- [ ] **Step 3: Verify kipptaf parses with new target**

```bash
uv run dbt parse --target dev --project-dir src/dbt/kipptaf
```

Expected: `Done. PASS=... WARN=0 ERROR=0`

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "feat(dbt): add dev/staging/prod targets to profiles, simplify source-system profiles"
```

---

### Task 3: Update shipped `src/dbt/*/profiles.yml`

**Files:**

- Modify: `src/dbt/kipptaf/profiles.yml`
- Modify: `src/dbt/kippnewark/profiles.yml`
- Modify: `src/dbt/kippcamden/profiles.yml`
- Modify: `src/dbt/kippmiami/profiles.yml`
- Modify: `src/dbt/kipppaterson/profiles.yml`

These are shipped to Dagster. They need `dev` (default) and `prod` targets.

- [ ] **Step 1: Update all 5 shipped profiles**

Replace each file with the two-target pattern:

```yaml
# kipptaf example
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

Current `src/dbt/kipptaf/profiles.yml` has `target: kipptaf` pointing to prod
schema `kipptaf`. The new `dev` default fixes the prod-write risk. Apply the
pattern to all 5 projects.

- [ ] **Step 2: Validate Dagster definitions for kipptaf**

```bash
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

Expected: both commands exit 0.

Also verify the other 4 school projects parse cleanly with the new `dev` target
(they share the same profile pattern):

```bash
for project in kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target dev --project-dir "src/dbt/${project}"
done
```

Expected: all exit 0.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/profiles.yml \
        src/dbt/kippnewark/profiles.yml \
        src/dbt/kippcamden/profiles.yml \
        src/dbt/kippmiami/profiles.yml \
        src/dbt/kipppaterson/profiles.yml
git commit -m "feat(dbt): update shipped profiles to dev/prod targets, default dev"
```

---

### Task 4: Update `get_dbt_cli_resource` in Dagster

**Files:**

- Modify: `src/teamster/core/resources.py:58-64`
- Modify: `src/teamster/core/CLAUDE.md`

- [ ] **Step 1: Replace `get_dbt_cli_resource`**

Current code (`src/teamster/core/resources.py:58-64`):

```python
def get_dbt_cli_resource(dbt_project: DbtProject, test: bool = False) -> DbtCliResource:
    if test:
        return DbtCliResource(
            project_dir=dbt_project, dbt_executable="/workspaces/teamster/.venv/bin/dbt"
        )
    else:
        return DbtCliResource(project_dir=dbt_project)
```

Replace with:

```python
def get_dbt_cli_resource(dbt_project: DbtProject) -> DbtCliResource:
    if os.getenv("DAGSTER_CLOUD_DEPLOYMENT_NAME") and not os.getenv(
        "DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT"
    ):
        return DbtCliResource(project_dir=dbt_project, target="prod")
    return DbtCliResource(project_dir=dbt_project)
```

- [ ] **Step 2: Update `src/teamster/core/CLAUDE.md`**

In the `resources.py` section, update the `get_dbt_cli_resource` entry:

```markdown
- `get_dbt_cli_resource(dbt_project)` → `DbtCliResource`. Passes `target="prod"`
  when `DAGSTER_CLOUD_DEPLOYMENT_NAME` is set and
  `DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT` is not (i.e., Dagster Cloud prod only).
  Local dev and branch deploys use the profile default (`dev`).
```

- [ ] **Step 3: Verify no callers pass `test=True`**

Use the Grep tool: search for `get_dbt_cli_resource` in `src/teamster`, type
`py`.

Expected: every call site is `get_dbt_cli_resource(DBT_PROJECT)` with no second
argument. If any caller passes `test=True`, update it to remove the argument.

- [ ] **Step 4: Validate Dagster definitions**

```bash
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/teamster/core/resources.py src/teamster/core/CLAUDE.md
git commit -m "feat(dagster): update get_dbt_cli_resource to use prod target in Dagster Cloud"
```

---

### Task 5: Update dbt Cloud (manual)

These changes are outside the codebase and must be made in the dbt Cloud UI.
They must be completed **before** Phase 2 source file rewrites.

- [ ] **Step 1: Update job target names**

In dbt Cloud → Jobs, update the "Target name" field for each job:

| Job                      | Current   | New       |
| ------------------------ | --------- | --------- |
| Build Modified - CI      | `default` | `staging` |
| Build Modified - Staging | `default` | `staging` |
| Parse - Staging          | `default` | `staging` |
| Parse - Production       | `default` | `prod`    |

- [ ] **Step 2: Update Staging environment dataset**

In dbt Cloud → Environments → Staging, update the dataset from `z_dev_kipptaf`
to `zz_stg_kipptaf`.

- [ ] **Step 3: Verify CI job runs on next trigger**

After a test PR or manual trigger, confirm the CI job runs without errors and
outputs to a `zz_stg_*` or `dbt_cloud_pr_*` schema (not `z_dev_*`).

---

## Phase 2 — Source File Rewrites

**Pre-condition:** All Task 5 (dbt Cloud) changes are live before starting
Phase 2.

### Substitution rule

Every inline Jinja block of the form:

```yaml
schema: |
  {%- if target.name == 'staging' -%}z_dev_
  {%- elif env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'staging' -%}z_dev_
  {%- elif env_var('GITHUB_USER', '') != '' -%}zz_{{ env_var('GITHUB_USER') }}_
  {%- endif -%}kippnewark_powerschool
```

becomes:

```yaml
schema: "{{ resolve_source_schema('kippnewark_powerschool') }}"
```

The `base_schema` argument is whatever literal or expression appeared at the end
of the original inline block (after stripping the prefix logic). Common
patterns:

| Original ending                                            | `resolve_source_schema(...)` argument                |
| ---------------------------------------------------------- | ---------------------------------------------------- |
| `kippnewark_powerschool` (literal)                         | `'kippnewark_powerschool'`                           |
| `{{ var('amplify_schema', project_name + '_amplify') }}`   | `var('amplify_schema', project_name + '_amplify')`   |
| `{{ var('iready_schema', project_name + '_iready') }}`     | `var('iready_schema', project_name + '_iready')`     |
| `{{ var('renlearn_schema', project_name + '_renlearn') }}` | `var('renlearn_schema', project_name + '_renlearn')` |

Verify the resulting argument by searching for the old schema value in
`dbt_project.yml` variables or existing prod BigQuery datasets.

### Task 6: Rewrite kipptaf source files

**Files:** All 46 `src/dbt/kipptaf/models/**/sources*.yml` files with inline
Jinja — see the full list produced by:

```bash
grep -rln "DBT_CLOUD_ENVIRONMENT_TYPE\|target.name\|GITHUB_USER" src/dbt/kipptaf/models --include="sources*.yml"
```

- [ ] **Step 1: Rewrite all kipptaf source files**

For each file in the list, replace every `schema:` block containing inline Jinja
with the `resolve_source_schema` call. The base_schema is the literal or
variable expression at the end of the current inline block.

Common kipptaf patterns and their replacements:

```yaml
# Pattern A — kipptaf cross-school sources (e.g. sources-kippnewark.yml)
# Before:
schema: |
  {%- if target.name == 'staging' -%}z_dev_
  {%- elif env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') == 'staging' -%}z_dev_
  {%- elif env_var('GITHUB_USER', '') != '' -%}zz_{{ env_var('GITHUB_USER') }}_
  {%- endif -%}kippnewark_powerschool
# After:
schema: "{{ resolve_source_schema('kippnewark_powerschool') }}"

# Pattern B — kipptaf external sources (e.g. sources-external.yml)
# Before:
schema: |
  {%- if target.name == 'staging' -%}zz_stg_
  {%- elif env_var('GITHUB_USER', '') != '' -%}zz_{{ env_var('GITHUB_USER') }}_
  {%- endif -%}kipptaf
# After:
schema: "{{ resolve_source_schema('kipptaf') }}"
```

Inspect each file individually — the inline logic varies. Extract the base
schema from the end of each expression.

- [ ] **Step 2: Compile kipptaf with `--target dev` and verify schema names**

```bash
uv run dbt compile --select "source:*" --target dev --project-dir src/dbt/kipptaf 2>&1 | head -40
```

Then spot-check a compiled source to confirm the resolved schema contains
`zz_<GITHUB_USER>_`:

```bash
grep -r "zz_" src/dbt/kipptaf/target/compiled --include="*.sql" | head -5
```

Expected: compiled SQL references `zz_<your-github-user>_*` schemas.

- [ ] **Step 3: Compile with `--target prod` and verify bare schema names**

```bash
uv run dbt compile --select "source:*" --target prod --project-dir src/dbt/kipptaf 2>&1 | head -20
```

```bash
grep -r "kippnewark_powerschool\|kipptaf" src/dbt/kipptaf/target/compiled --include="*.sql" | grep -v "zz_" | head -5
```

Expected: compiled SQL references bare schemas (no `zz_` prefix).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/
git commit -m "refactor(dbt): replace inline schema Jinja in kipptaf sources with resolve_source_schema"
```

---

### Task 7: Rewrite school project source files

**Files:**

- Modify: `src/dbt/kippnewark/models/edplan/sources-drive.yml`
- Modify: `src/dbt/kippcamden/models/edplan/sources-drive.yml`
- Modify: `src/dbt/kippmiami/models/fldoe/sources.yml`

These source files live in school projects (not kipptaf). They use the same
inline Jinja pattern.

- [ ] **Step 1: Rewrite school project source files**

Apply the same substitution rule. The base schemas are:

- `kippnewark/edplan/sources-drive.yml`: inspect the file for the literal schema
  name
- `kippcamden/edplan/sources-drive.yml`: inspect the file for the literal schema
  name
- `kippmiami/fldoe/sources.yml`: inspect the file for the literal schema name

Use Read tool on each file first to confirm the base_schema before editing.

- [ ] **Step 2: Parse each school project**

```bash
uv run dbt parse --target dev --project-dir src/dbt/kippnewark
uv run dbt parse --target dev --project-dir src/dbt/kippcamden
uv run dbt parse --target dev --project-dir src/dbt/kippmiami
```

Expected: all three exit 0.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kippnewark/models/ src/dbt/kippcamden/models/ src/dbt/kippmiami/models/
git commit -m "refactor(dbt): replace inline schema Jinja in school project sources with resolve_source_schema"
```

---

### Task 8: Rewrite source-system package source files

**Files:** One or two source files per source-system project:

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

**Important:** After this change, `dbt parse` on a standalone source-system
project will fail — the macro is not in their namespace. This is expected. They
are compiled as packages within school projects.

- [ ] **Step 1: Read each source file and identify the base_schema expression**

Common patterns in source-system files:

```yaml
# amplify/models/sources.yml (uses a variable with project_name fallback)
# Before:
schema: |
  {% if env_var('DBT_CLOUD_ENVIRONMENT_TYPE', '') in ['dev', 'staging'] -%}z_dev_
  {%- endif -%}{{ var('amplify_schema', project_name + '_amplify') }}
# After:
schema: "{{ resolve_source_schema(var('amplify_schema', project_name + '_amplify')) }}"
```

Read each file to confirm the exact expression before editing.

- [ ] **Step 2: Rewrite all 12 source-system source files**

Apply the substitution rule. The macro call wraps whatever expression currently
provides the base schema name.

- [ ] **Step 3: Verify school projects compile correctly with rewritten
      packages**

```bash
uv run dbt parse --target dev --project-dir src/dbt/kipptaf
uv run dbt parse --target dev --project-dir src/dbt/kippnewark
```

Expected: both exit 0. The macro is resolved from the school project's
namespace.

- [ ] **Step 4: Compile with `--target prod` to verify prod behavior**

```bash
uv run dbt compile --select "source:*" --target prod --project-dir src/dbt/kipptaf 2>&1 | head -20
```

Expected: exit 0, compiled sources reference bare schema names.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/amplify/ src/dbt/deanslist/ src/dbt/edplan/ src/dbt/finalsite/ \
        src/dbt/iready/ src/dbt/overgrad/ src/dbt/pearson/ src/dbt/powerschool/ \
        src/dbt/renlearn/ src/dbt/titan/
git commit -m "refactor(dbt): replace inline schema Jinja in source-system package sources with resolve_source_schema"
```

---

## Phase 3 — Cleanup

### Task 9: Remove old targets from `.dbt/profiles.yml`

**Pre-condition:** All Phase 2 source file rewrites are complete AND dbt Cloud
CI is healthy (recent CI run green with `--target staging`).

**Files:**

- Modify: `.dbt/profiles.yml`

- [ ] **Step 1: Remove legacy target entries**

For each school/network project, remove the legacy `<project-name>` target
output added in Task 2. The final profiles for school/network projects have only
`dev`, `staging`, `prod`. Source-system projects have only `dev`.

Also remove the old multi-school targets from source-system projects (e.g.,
`amplify.kippnewark`, `powerschool.kippnewark`, etc.) — they are no longer
needed since source-system projects compile as packages.

Leave `integration_tests` unchanged.

- [ ] **Step 2: Verify default target works**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: exit 0 (uses default `dev` target).

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "chore(dbt): remove legacy profile targets from .dbt/profiles.yml"
```

---

### Task 10: Remove `DBT_CLOUD_ENVIRONMENT_TYPE`

**Files:**

- Modify: `.devcontainer/devcontainer.json`
- Modify: `.vscode/settings.json` (if present)

Note: `.devcontainer/scripts/` is hook-protected. `devcontainer.json` is not —
edit directly.

- [ ] **Step 1: Remove from `devcontainer.json`**

Find and remove the `"DBT_CLOUD_ENVIRONMENT_TYPE": "dev"` line from the
`containerEnv` block in `.devcontainer/devcontainer.json`.

- [ ] **Step 2: Check VS Code settings**

```bash
grep -n "DBT_CLOUD_ENVIRONMENT_TYPE" .vscode/settings.json
```

If present, remove it from `.vscode/settings.json`.

- [ ] **Step 3: Commit**

```bash
git add .devcontainer/devcontainer.json .vscode/settings.json
git commit -m "chore: remove DBT_CLOUD_ENVIRONMENT_TYPE env var (replaced by --target)"
```

---

### Task 11: Delete `scripts/dbt-sxs.py` and update `scripts/CLAUDE.md`

**Files:**

- Delete: `scripts/dbt-sxs.py`
- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Delete the script**

```bash
git rm scripts/dbt-sxs.py
```

- [ ] **Step 2: Remove from `scripts/CLAUDE.md`**

Remove the `dbt-sxs.py` row from the Script Catalog table.

- [ ] **Step 3: Commit**

```bash
git add scripts/CLAUDE.md
git commit -m "chore: delete dbt-sxs.py (replaced by VS Code task)"
```

---

### Task 12: Set up `post-merge` git hook and devcontainer wiring

**Files:**

- Manual: `.git/hooks/post-merge` (not tracked in git — present as manual block)
- Manual: `.devcontainer/scripts/postStart.sh` (hook-protected — present as
  manual block)

The hook generates prod manifests after every merge so Power User `--defer`
always has a fresh manifest.

- [ ] **Step 1: Present `.git/hooks/post-merge` block for manual installation**

Present this block for the user to install manually:

```bash
#!/bin/bash
# .git/hooks/post-merge
# Regenerate prod manifests for Power User --defer

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  echo "Parsing ${project} (prod)..."
  uv run dbt parse \
    --target prod \
    --project-dir "src/dbt/${project}" \
    --target-path target/prod
done
```

Install command:

```bash
cp .git/hooks/post-merge.sample .git/hooks/post-merge  # if sample exists, else create
chmod +x .git/hooks/post-merge
```

- [ ] **Step 2: Present `postStart.sh` addition for manual application**

The user must manually add this block to the end of
`.devcontainer/scripts/postStart.sh` (protected file). Show only the final
replacement block with file + line number link:

```bash
# Generate prod dbt manifests for Power User --defer
echo "Generating prod dbt manifests..."
# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"
for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse \
    --target prod \
    --project-dir "src/dbt/${project}" \
    --target-path target/prod \
    || echo "Warning: dbt parse failed for ${project} (manifest may be stale)"
done
```

- [ ] **Step 3: Run the hook manually to generate initial manifests**

```bash
bash .git/hooks/post-merge
```

Expected: 5 manifest files created at `src/dbt/*/target/prod/manifest.json`.

---

### Task 13: Configure Power User `--defer` in VS Code

**Files:**

- Modify: `.vscode/settings.json`

- [ ] **Step 1: Add defer configuration**

Add to `.vscode/settings.json`:

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

- [ ] **Step 2: Verify manifest paths exist**

```bash
ls src/dbt/kipptaf/target/prod/manifest.json
```

Expected: file exists (from Task 12 Step 3). If missing, run Task 12 Step 3
first.

- [ ] **Step 3: Confirm "Apply defer configuration" behavior**

Open VS Code Command Palette (`Ctrl+Shift+P`) and run "dbt Power User: Apply
defer configuration". Document whether this is a required one-time activation or
informational. Update `.vscode/CLAUDE.md` with the finding.

- [ ] **Step 4: Commit**

```bash
git add .vscode/settings.json
git commit -m "feat(vscode): configure dbt Power User --defer for school/network projects"
```

---

### Task 14: Add VS Code task for staging external sources

**Files:**

- Modify: `.vscode/tasks.json`

- [ ] **Step 1: Add task and inputs to `.vscode/tasks.json`**

Add to the `tasks` array:

```json
{
  "label": "dbt: Stage External Sources",
  "type": "shell",
  "command": "source \"${HOME}/.local/bin/env\" && uv run dbt run-operation stage_external_sources --project-dir src/dbt/${input:dbtProject} --target ${input:dbtSxsTarget} --vars '{\"ext_full_refresh\": \"true\", \"cloud_storage_uri_base\": \"gs://teamster-${input:dbtProject}/dagster/${input:dbtProject}\"}' --args 'select: ${input:dbtSourceSelect}'",
  "presentation": {
    "reveal": "always",
    "panel": "dedicated",
    "focus": true
  },
  "problemMatcher": []
}
```

Add to the `inputs` array (alongside the existing `dbtProject` input — add the
two new ones; update `dbtProject` options if needed):

```json
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

The existing `dbtProject` input options should include all 5 school/network
projects. Update if needed.

- [ ] **Step 2: Test the task in VS Code**

Open Command Palette → `Tasks: Run Task` → `dbt: Stage External Sources`. Select
`kipptaf`, `dev`, `*`. Confirm the task runs `stage_external_sources` without
errors.

- [ ] **Step 3: Commit**

```bash
git add .vscode/tasks.json
git commit -m "feat(vscode): add dbt Stage External Sources task with project/target/source inputs"
```

---

## Post-Migration Verification

### Task 15: Full staging build and cleanup

- [ ] **Step 1: Stage all external sources to `zz_stg_*`**

Run the "dbt: Stage External Sources" VS Code task for each project with
`--target staging`.

- [ ] **Step 2: Trigger a full staging build in dbt Cloud**

Manually trigger "Build Modified - Staging". Confirm:

- Job uses `--target staging`
- Sources resolve to `zz_stg_*` schemas
- Build completes without errors

- [ ] **Step 3: Update spec and plan statuses**

In `docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md`, update:

```text
| **Development** | COMPLETE |
```

In this plan file, update the header status (add a status table if desired).

- [ ] **Step 4: Audit and drop old `z_dev_*` datasets from BigQuery**

Once staging builds are confirmed healthy, audit all `z_dev_*` datasets in the
BigQuery console. The expected set to drop includes at minimum:

- `z_dev_kipptaf`, `z_dev_kippnewark`, `z_dev_kippcamden`, `z_dev_kippmiami`,
  `z_dev_kipppaterson`

Also check for any source-level `z_dev_*` schemas (e.g.,
`z_dev_kippnewark_powerschool`) that may have been created by old staging jobs.
Confirm each is no longer referenced by any active dbt job or Dagster asset
before dropping. Drop only after confirming `zz_stg_*` equivalents are fully
populated.

- [ ] **Step 5: Final commit and PR**

```bash
git add docs/superpowers/specs/2026-03-25-dbt-schema-resolution-design.md \
        docs/superpowers/plans/2026-03-25-dbt-schema-resolution.md
git commit -m "docs: mark dbt schema resolution rework as COMPLETE"
```

Then open a PR using the `commit-commands:commit-push-pr` skill (or
`gh pr create`), referencing issue #3511.
