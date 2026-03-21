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
- **Git commits**: Do not commit proactively — ask first when a change is
  complete, tests are passing, and it is ready to commit, then commit if
  confirmed. Commits should have descriptive messages following the
  [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) format.
  Avoid checkpoint-style messages (`save`, `oops`, `update`, etc.).
- **Branch naming**: `<author>/<commit-type>/<brief-description>` (e.g.,
  `cbini/feat/salesforce-alumni-tracking`). Use `claude` as the author prefix
  for AI-assisted branches.
- **Pull requests**: Squash merge. When opening a PR, use
  `.github/pull_request_template.md` as the body — fill in the relevant sections
  based on the changes.
- **GitHub issues**: Do not open issues proactively — ask first when something
  warrants one, then open it if confirmed. Use `gh issue create` (not the web
  UI). Label it with a
  [conventional commit type](https://www.conventionalcommits.org/en/v1.0.0/)
  (`feat`, `fix`, `docs`, `refactor`, `chore`, etc.), any related source systems
  (e.g., `adp`, `powerschool`, `deanslist`), and `dagster` and/or `dbt` when
  applicable.

## Commands

The `scripts/` directory contains project utilities (doc generation, migrations,
etc.) in lieu of a Makefile. Run them with `uv run scripts/<name>.py`.

### Development

```bash
# Install dependencies
uv sync --frozen

# Inject 1Password secrets (required for Dagster development, not needed for SQL-only work)
.devcontainer/scripts/inject-secrets.sh

# Run Dagster webserver locally
uv run dagster dev

# Validate Dagster definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions

# Prepare and package a dbt project (must be done before running dbt assets)
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py
```

### Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dagster_definitions.py

# Run a single test
uv run pytest tests/test_dagster_definitions.py::test_definitions_kipptaf

# Run asset-specific tests (require env vars / external connections)
uv run pytest tests/assets/test_assets_dbt.py
```

### Linting

See `.trunk/trunk.yaml` for the full list of enabled linters and
`.trunk/config/` for per-linter configuration files. A pre-commit hook runs
`trunk check` — if a commit is rejected, fix the reported issues and re-commit.

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.

**Shell style**: `shfmt` enforces tabs. Linter ignores use
`# trunk-ignore(shellcheck/SCXXXX)` with a reason comment, not
`# shellcheck disable=`.

### BigQuery MCP Queries

The BigQuery MCP tool truncates results at 50 rows. When querying
`INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
`WHERE ordinal_position > N` to get all rows.

### Secrets

PreToolUse/PostToolUse hooks in `.claude/hooks/` guard sensitive paths and
content. Read `.claude/hooks/README.md` for full behavior, and the hook scripts
for exact patterns. Hook scripts and `.devcontainer/scripts/` must be drafted
for manual application. Regression tests: `bash tests/hooks/run_all.sh`. Git
commit messages containing sensitive path strings (e.g., `./env/`) also trigger
the scanner — write the message to `/tmp/commit-msg.txt` and use
`git commit -F /tmp/commit-msg.txt`.

## Documentation

Two documentation systems serve different audiences — do not conflate them:

- **dbt YAML** (properties files + exposures) — how analysts document models,
  columns, tests, and external tool dependencies. Required for all dbt model
  changes; enforced by the PR template checklist.
- **MkDocs site** (`docs/`) — how engineers document infrastructure patterns,
  architecture, and operational guides. Update when making engineering-level
  changes:
  - New integration → update `docs/reference/adding-an-integration.md` and the
    code location's `CLAUDE.md`
  - New or changed schedule/sensor → regenerate the automations catalog:
    `uv run scripts/gen-automations-doc.py`
  - New core pattern (IO manager behavior, automation condition, partitioning) →
    update the relevant `docs/reference/` page

Analysts adding or editing SQL models do not need to touch `docs/` — dbt YAML is
the documentation mechanism for that work.

## Codespace / GKE Setup Quirks

- `gcloud components install` requires `sudo` in the codespace
  (`/usr/local/share/google-cloud-sdk` is root-owned)
- `kubectl` and `gke-gcloud-auth-plugin` must be installed via
  `gcloud components install`, not apt
- Helm should be installed to `~/.local/bin` with
  `USE_SUDO=false HELM_INSTALL_DIR=~/.local/bin` to avoid `/usr/local/bin`
  permission errors
- `/usr/local/bin/helm` may exist with `rwxr-xr--` perms (not executable by
  `vscode`) — check for a local copy with `[[ -x "${helm_dir}/helm" ]]`, not
  `command -v helm`
- Claude Code sandbox (`/sandbox`) is a CLI-only command — the VSCode extension
  does not support it. Install the CLI separately:
  `npm install -g @anthropic-ai/claude-code`
- Unprivileged user namespaces are blocked in Codespaces — bubblewrap requires
  `enableWeakerNestedSandbox: true` in sandbox config

## Architecture

**IMPORTANT — you MUST read the relevant CLAUDE.md files before doing any work:
reading, explaining, reviewing, or modifying code. Do NOT skip this step, even
if you think you can answer from source code alone.**

- **Dagster code** (reading or editing) → read `src/teamster/CLAUDE.md` first
- **dbt models** (reading or editing) → read `src/dbt/CLAUDE.md` first
- **Any subdirectory** → read that directory's CLAUDE.md first

These files contain conventions, antipatterns, and architectural decisions that
are not discoverable from source code.
