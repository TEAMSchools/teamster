# CLAUDE.md Phase 2 — Complete Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the root CLAUDE.md router refactor by relocating all
remaining domain-specific content to subdirectory files, consolidating working
conventions, and creating five new CLAUDE.md files seeded with directory
context.

**Architecture:** Three commit groups — (1) create five new CLAUDE.md files, (2)
add relocated content to four existing subdirectory files, (3) rewrite the root
CLAUDE.md. Root is rewritten last so all its routing targets exist before it
points to them.

**Tech Stack:** Markdown only — no code changes, no tests to run.

---

## Pre-flight Check

Before starting, verify the current state:

```bash
# Confirm root is 137 lines (Phase 1 applied)
wc -l CLAUDE.md

# Confirm new files don't exist yet
ls .devcontainer/CLAUDE.md .k8s/CLAUDE.md .trunk/CLAUDE.md tests/CLAUDE.md scripts/CLAUDE.md 2>&1

# Confirm SQL style section not yet in src/dbt/CLAUDE.md
grep -n "SQL Style" src/dbt/CLAUDE.md

# Confirm BigQuery MCP tip not yet in mcp/CLAUDE.md
grep -n "50 rows" mcp/CLAUDE.md
```

Expected: root is 137 lines; new files produce "No such file"; greps return
nothing.

> **Note on `.claude/hooks/CLAUDE.md`**: The spec listed this file in Files
> Changed to receive the `bash tests/hooks/run_all.sh` command. That command
> already exists at line 97 of that file — no change needed there.

---

## Task 1: Create `.devcontainer/CLAUDE.md`

**Files:**

- Create: `.devcontainer/CLAUDE.md`

- [ ] **Step 1: Verify file does not exist**

```bash
ls .devcontainer/CLAUDE.md 2>&1
```

Expected: `No such file or directory`

- [ ] **Step 2: Create the file**

Write the following content to `.devcontainer/CLAUDE.md`:

```text
# CLAUDE.md — `.devcontainer/`

Container configuration for Codespace and local development.

## Setup Lifecycle

- **`postCreate.sh`** runs once on container creation — installs dependencies,
  sets up GCP auth, removes `sudo`
- **`postStart.sh`** runs on every container start — refreshes GCP ADC, Claude
  auth, VS Code tasks. Keep it idempotent.
- **Post-build VS Code task**: "Setup: Post-Build Init" runs automatically on
  folder open after a rebuild — handles GCloud ADC, Claude auth, plugin
  installation, and dbt dev dataset checks. Individual tasks available via
  `Ctrl+Shift+P` → `Tasks: Run Task`

## Secret Injection

**`inject-secrets.sh`**: manually run to inject 1Password secrets into the
environment. Required for Dagster development; not needed for SQL-only work.
Run after container start if env vars or secrets are missing.

## Quirks

- **`sudo` removed**: at the end of `postCreate.sh` — privileged setup (gcloud
  components, Helm) must go in `postCreate.sh`, not later. To add new
  components, update `postCreate.sh` and rebuild the container.
- **`--cap-add` stripped**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work. Hooks
  are the sole enforcement layer for path-based access control.
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs.
```

- [ ] **Step 3: Verify**

```bash
grep -c "inject-secrets\|postCreate\|postStart" .devcontainer/CLAUDE.md
```

Expected: `3`

---

## Task 2: Create `.k8s/CLAUDE.md`

**Files:**

- Create: `.k8s/CLAUDE.md`

- [ ] **Step 1: Verify file does not exist**

```bash
ls .k8s/CLAUDE.md 2>&1
```

Expected: `No such file or directory`

- [ ] **Step 2: Create the file**

Write the following content to `.k8s/CLAUDE.md`:

````text
# CLAUDE.md — `.k8s/`

Helm charts and scripts for deploying the Dagster Cloud agent and 1Password
Connect to GKE.

## Directory Structure

```text
.k8s/
├── setup.sh                   # Bootstrap kubectl, Helm, gke-mcp
├── dagster/
│   ├── install.sh             # Deploy Dagster Cloud agent via Helm
│   ├── values.yaml            # Downloaded Helm defaults — do not edit
│   └── values-override.yaml   # Custom overrides (edit this)
└── 1password/
    ├── install.sh             # Deploy 1Password Connect via Helm
    ├── values.yaml            # Downloaded Helm defaults — do not edit
    ├── values-override.yaml   # Custom overrides (edit this)
    └── items.yaml             # 1Password secret items to sync
````

## Setup

Run in order:

1. `bash .k8s/setup.sh` — installs kubectl, Helm to `~/.local/bin`, gke-mcp,
   creates `dagster-cloud` namespace
2. `bash .k8s/dagster/install.sh` — deploys Dagster Cloud agent
3. `bash .k8s/1password/install.sh` — deploys 1Password Connect (requires
   `OP_CONNECT_TOKEN` in `env/.env`)

## Conventions

- **`values.yaml`** is auto-downloaded from Helm — never edit it; it will be
  overwritten. All customizations go in `values-override.yaml`.
- **Helm installs to `~/.local/bin`** to avoid `/usr/local/bin` permission
  issues (no `sudo`).
- **gke-mcp binary** includes sha256 checksum verification — `setup.sh` exits on
  mismatch.

- [ ] **Step 3: Verify**

```bash
grep -c "values-override\|setup.sh\|OP_CONNECT_TOKEN" .k8s/CLAUDE.md
```

Expected: `3`

---

## Task 3: Create `.trunk/CLAUDE.md`

**Files:**

- Create: `.trunk/CLAUDE.md`

- [ ] **Step 1: Verify file does not exist**

```bash
ls .trunk/CLAUDE.md 2>&1
```

Expected: `No such file or directory`

- [ ] **Step 2: Create the file**

Write the following content to `.trunk/CLAUDE.md`:

````text
# CLAUDE.md — `.trunk/`

Trunk.io configuration for linting and formatting. Config: `trunk.yaml` (this
directory). Per-linter config: `.trunk/config/`.

## Linter Ignores

Use `# trunk-ignore(<linter>/<rule>)` with a reason comment. Do not use
linter-native disable syntax (`# shellcheck disable=`, `# noqa`, `-- noqa`):

```python
# trunk-ignore(bandit/B603): subprocess args are hardcoded, not user input
subprocess.run(["git", "status"])
````

## Enabled Linters

| Category | Linters                               |
| -------- | ------------------------------------- |
| Python   | ruff, pyright, bandit, isort          |
| SQL      | sqlfluff, sqlfmt                      |
| Shell    | shellcheck, shfmt                     |
| YAML     | yamllint                              |
| Markdown | markdownlint                          |
| CI       | actionlint                            |
| Docker   | hadolint                              |
| Security | gitleaks, git-diff-check, osv-scanner |
| Config   | prettier, taplo                       |
| Images   | oxipng, svgo                          |

## Ignore Rules

- `src/teamster/**` — sqlfluff, sqlfmt ignored (SQL linting is dbt-only)
- `src/teamster/libraries/dlt_sources/**` — pyright additionally ignored
  (third-party library wrappers)
- `src/dbt/**` — all linters except sqlfluff, sqlfmt, and prettier ignored
- `.k8s/**/values.yaml` — all linters ignored (generated Helm values)

## Hooks

- **Pre-commit**: `trunk-fmt-pre-commit` runs `trunk fmt` (auto-formats staged
  files)
- **Pre-push**: `trunk-check-pre-push` runs `trunk check` (blocks on lint
  failures). Never use `--no-verify` — fix reported issues instead.

## Shell Style

`shfmt` enforces tabs (not spaces) in shell scripts.

## Protected Config

`.trunk/config/` is read-only under hooks — present changes as manual
application blocks, not diffs.

- [ ] **Step 3: Verify**

```bash
grep -c "trunk-ignore\|shfmt\|pre-commit\|pre-push" .trunk/CLAUDE.md
```

Expected: `4`

---

## Task 4: Create `tests/CLAUDE.md`

**Files:**

- Create: `tests/CLAUDE.md`

- [ ] **Step 1: Verify file does not exist**

```bash
ls tests/CLAUDE.md 2>&1
```

Expected: `No such file or directory`

- [ ] **Step 2: Create the file**

````markdown
# CLAUDE.md — `tests/`

## Test Categories

- **Root-level `test_*.py`** — unit tests for Dagster definitions, IO managers,
  automation conditions, utils. No external connections required.
- **`tests/assets/`** — integration tests per source system. Require env vars
  and external connections; not run in CI by default.
- **`tests/sensors/`, `tests/schedules/`, `tests/ops/`, `tests/resources/`** —
  component-level tests. Many have `archive/` subdirectories (deprecated tests
  prefixed with `_test_`).

## Running Tests

```bash
uv run pytest                                                          # all tests
uv run pytest tests/test_dagster_definitions.py                        # single file
uv run pytest tests/test_dagster_definitions.py::test_definitions_kipptaf  # single test
uv run pytest tests/assets/test_assets_dbt.py                         # requires env vars
```
````

## Patterns

- **Definitions validation**: calls `dagster definitions validate` via
  `subprocess.check_output` — tests the real module load, not a mock.
- **Automation condition tests**: use ephemeral in-memory Dagster instances
  (fast, no external deps).
- **No global `conftest.py`**: no shared fixtures at project level. See
  `utils.py` for SSH/DB resource helpers (require env vars).
- **Archived tests**: `_test_` prefix in `archive/` subdirectories — ignored by
  pytest by convention, not markers.

- [ ] **Step 3: Verify**

```bash
grep -c "uv run pytest\|external connections\|conftest" tests/CLAUDE.md
```

Expected: `3`

---

## Task 5: Create `scripts/CLAUDE.md`

**Files:**

- Create: `scripts/CLAUDE.md`

- [ ] **Step 1: Verify file does not exist**

```bash
ls scripts/CLAUDE.md 2>&1
```

Expected: `No such file or directory`

- [ ] **Step 2: Create the file**

```markdown
# CLAUDE.md — `scripts/`

Project utilities. Python scripts run with `uv run scripts/<name>.py [args]` —
never bare `python`. Shell scripts run directly: `bash scripts/<name>.sh`.

## Script Catalog

| Script                   | Purpose                                             |
| ------------------------ | --------------------------------------------------- |
| `dagster-dev.py`         | Start Dagster webserver for selected code locations |
| `avro-schema-update.py`  | Rewrite Avro data in GCS with updated schema        |
| `dbt-bq-audit.py`        | Audit BigQuery objects against dbt manifest         |
| `dbt-build-init.sh`      | Initialize dbt build environment                    |
| `dbt-manifest.py`        | Extract dbt manifest model list to CSV              |
| `dbt-sxs.py`             | Run dbt side-by-side source comparison              |
| `dbt-yaml.py`            | Parse and transform dbt YAML files                  |
| `gen-automations-doc.py` | Regenerate `docs/reference/automations.md`          |
| `json2py.py`             | Generate Pydantic models from JSON schemas          |
| `migrate-asset-key.py`   | Migrate asset materialization history to new key    |
| `update.py`              | Update all project dependencies (uv, Trunk, dbt)    |

## Prerequisites

- `dbt-manifest.py` — requires `dbt parse` to have run first (reads
  `target/manifest.json`)
- `gen-automations-doc.py` — requires dbt manifests to be parsed
- `dbt-bq-audit.py` — writes to `scripts/script_output/`; directory must exist

## Caveats

- `migrate-asset-key.py` creates runless materialization events — automation
  cursors will not recognize migrated events.
- `update.py` upgrades all 15 dbt projects sequentially — slow operation.
```

- [ ] **Step 3: Verify**

```bash
grep -c "uv run scripts\|dbt-build-init\|migrate-asset-key" scripts/CLAUDE.md
```

Expected: `3`

- [ ] **Step 4: Commit new files**

```bash
git add .devcontainer/CLAUDE.md .k8s/CLAUDE.md .trunk/CLAUDE.md tests/CLAUDE.md scripts/CLAUDE.md
git commit -m "docs: create CLAUDE.md files for devcontainer, k8s, trunk, tests, and scripts"
```

---

## Task 6: Add SQL Style to `src/dbt/CLAUDE.md`

**Files:**

- Modify: `src/dbt/CLAUDE.md` (append after line 151)

- [ ] **Step 1: Verify section is absent**

```bash
grep -n "SQL Style" src/dbt/CLAUDE.md
```

Expected: no output

- [ ] **Step 2: Append the SQL Style section**

Add the following at the end of `src/dbt/CLAUDE.md` (after the existing
content):

```markdown
## SQL Style

All SQL follows `.trunk/config/.sqlfluff`. Key enforced rules:

- **Dialect**: BigQuery
- **Trailing commas**: required in `SELECT` clauses
- **String literals**: single quotes only (no double quotes)
- **Line length**: 88 characters max

Do not flag code that follows these rules.
```

- [ ] **Step 3: Verify**

```bash
grep -n "trailing comma\|sqlfluff\|SQL Style" src/dbt/CLAUDE.md
```

Expected: three lines with line numbers pointing to the new section

---

## Task 7: Add Development Commands to `src/teamster/CLAUDE.md`

**Files:**

- Modify: `src/teamster/CLAUDE.md` (append after line 139)

- [ ] **Step 1: Verify section is absent**

```bash
grep -n "Development Commands\|dagster dev" src/teamster/CLAUDE.md
```

Expected: no output

- [ ] **Step 2: Append the Development Commands section**

Add the following at the end of `src/teamster/CLAUDE.md`:

````markdown
## Development Commands

```bash
# Start Dagster webserver locally (all code locations)
uv run dagster dev

# Validate Dagster definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions

# Prepare and package a dbt project (required before running dbt assets)
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py
```

- [ ] **Step 3: Verify**

```bash
grep -n "dagster dev\|definitions validate\|prepare-and-package" src/teamster/CLAUDE.md
```
````

Expected: three lines in the new section

---

## Task 8: Add BigQuery MCP Tip to `mcp/CLAUDE.md`

**Files:**

- Modify: `mcp/CLAUDE.md` (append after line 94)

- [ ] **Step 1: Verify tip is absent**

```bash
grep -n "50 rows\|ordinal_position" mcp/CLAUDE.md
```

Expected: no output

- [ ] **Step 2: Append the BigQuery MCP section**

Add the following at the end of `mcp/CLAUDE.md`:

```markdown
## BigQuery MCP

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.
```

- [ ] **Step 3: Verify**

```bash
grep -n "50 rows\|ordinal_position" mcp/CLAUDE.md
```

Expected: two lines in the new section

- [ ] **Step 4: Commit subdirectory updates**

```bash
git add src/dbt/CLAUDE.md src/teamster/CLAUDE.md mcp/CLAUDE.md
git commit -m "docs: relocate SQL style, dev commands, and BigQuery MCP tip to subdirectory files"
```

---

## Task 9: Rewrite Root `CLAUDE.md`

**Files:**

- Modify: `CLAUDE.md` (full rewrite)

- [ ] **Step 1: Verify current state**

```bash
wc -l CLAUDE.md
grep -n "Commands\|Codespace\|GKE\|BigQuery MCP\|SQL style\|shfmt" CLAUDE.md
```

Expected: 137 lines; several matches in the Commands and Codespace/GKE sections

- [ ] **Step 2: Rewrite the file**

Replace the entire contents of `CLAUDE.md` with:

```markdown
# CLAUDE.md

## Project Overview

Teamster is a data engineering platform for KIPP TEAM & Family Schools (Newark,
Camden, and Paterson, NJ & Miami, FL) built on **Dagster** (orchestration),
**dbt** (transformations), and **Google BigQuery** (warehouse), with Google
Cloud Storage (GCS) as the intermediate storage layer.

## Working Conventions

- **Python execution**: Always use `uv run` — never bare `python` or `python3`,
  including inline one-liners (`uv run python -c "..."`, not
  `python3 -c "..."`). The project environment is managed by uv.

- **Git**:
  - Do not commit proactively — ask first when a change is complete and tests
    are passing, then commit if confirmed.
  - Commit messages follow
    [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/)
    format. Avoid checkpoint-style messages (`save`, `oops`, `update`, etc.).
  - Branch naming: `<author>/<commit-type>/<brief-description>` (e.g.,
    `cbini/feat/salesforce-alumni-tracking`). Use `claude` as the author prefix
    for AI-assisted branches.

- **GitHub**:
  - **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as
    the PR body — fill in the relevant sections based on the changes.
  - **Issues**: Do not open proactively — ask first. Use `gh issue create` (not
    the web UI). Label with a
    [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
    (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source
    systems (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or
    `dbt` when applicable.
  - **Design specs**: After a spec is written and reviewed:
    1. Open a GitHub issue (`gh issue create`)
    2. Create and link the branch
       (`gh issue develop <number> --name <branch> --checkout`)
    3. Commit the spec to that branch
    4. Push the branch

- **Linter**: Use `# trunk-ignore(<linter>/<rule>)` with a reason comment. Do
  not use linter-native disable syntax (e.g., `# shellcheck disable=`, `# noqa`,
  `-- noqa`).

## Architecture

This file is a **router** — it contains project-wide conventions, then routes to
subdirectory CLAUDE.md files for domain-specific context. Keep domain-specific
guidance in the nearest subdirectory CLAUDE.md, not here.

**You MUST read the relevant CLAUDE.md file before doing any work in a
subdirectory — reading, explaining, reviewing, or modifying code. Do NOT skip
this step.**

| Path                      | When                               |
| ------------------------- | ---------------------------------- |
| `src/teamster/CLAUDE.md`  | Dagster code                       |
| `src/dbt/CLAUDE.md`       | dbt models                         |
| `.vscode/CLAUDE.md`       | VS Code tasks/scripts              |
| `.claude/hooks/CLAUDE.md` | hooks, deny rules, protected paths |
| `.devcontainer/CLAUDE.md` | Codespace setup                    |
| `.k8s/CLAUDE.md`          | GKE setup                          |
| `.trunk/CLAUDE.md`        | linting config                     |
| `tests/CLAUDE.md`         | testing                            |
| `scripts/CLAUDE.md`       | project utilities                  |
| `mcp/CLAUDE.md`           | MCP servers/tools                  |
| `docs/CLAUDE.md`          | MkDocs documentation site          |
| Any subdirectory          | that directory's CLAUDE.md         |
```

- [ ] **Step 3: Verify line count and structure**

```bash
wc -l CLAUDE.md
grep -n "Commands\|Codespace\|GKE\|BigQuery MCP\|SQL style\|shfmt\|permissions.deny" CLAUDE.md
```

Expected: ~65 lines; grep returns no matches (those sections are gone)

- [ ] **Step 4: Verify routing table**

```bash
grep -c "| .*CLAUDE\.md" CLAUDE.md
```

Expected: `12` (11 named routes + catch-all)

- [ ] **Step 5: Commit root rewrite**

```bash
git add CLAUDE.md
git commit -m "docs(root): complete router refactor — remove Commands/Codespace/GKE sections, consolidate conventions, expand routing table"
```

---

## Task 10: Full Validation

- [ ] **Step 1: Run all spec validation checks**

```bash
# Root should be ~60-70 lines
wc -l CLAUDE.md

# No domain-specific content remaining in root
grep -n "BigQuery MCP\|SQL style\|shfmt\|Codespace\|GKE\|uv run pytest\|permissions.deny" CLAUDE.md

# All new files exist
ls .devcontainer/CLAUDE.md .k8s/CLAUDE.md .trunk/CLAUDE.md tests/CLAUDE.md scripts/CLAUDE.md

# Routing table has 12 rows (11 named + catch-all)
grep -c "| .*CLAUDE\.md" CLAUDE.md

# Development commands now in src/teamster/CLAUDE.md
grep -n "dagster dev\|definitions validate\|prepare-and-package" src/teamster/CLAUDE.md

# SQL style now in src/dbt/CLAUDE.md
grep -n "trailing comma\|sqlfluff" src/dbt/CLAUDE.md

# BigQuery MCP tip now in mcp/CLAUDE.md
grep -n "50 rows\|ordinal_position" mcp/CLAUDE.md
```

Expected: root ~65 lines; domain grep returns nothing; all files exist; routing
table count is 12; all content checks return matches.
