# CLAUDE.md Phase 2 — Complete Router

**Date**: 2026-03-23 **Status**: Draft **Builds on**:
[2026-03-17-claude-md-lean-router-design.md](2026-03-17-claude-md-lean-router-design.md)

## Phase 1 Status

Phase 1 targeted removal of the Skills section, Repository Structure tree, Key
Architectural Patterns, and dbt Project Conventions sections (199 lines, ~2,550
tokens). It also planned compression of the Linting subsection. The root is
currently 138 lines — Phase 1 changes were applied. The Commands section
(`### Development`, `### Testing`, `### Linting`, `### BigQuery MCP Queries`,
`### Secrets`) and the Codespace/GKE sections remain, as they were explicitly
out of Phase 1 scope.

## Problem

The root `CLAUDE.md` still contains domain-specific content that violates its
own router principle:

- **SQL style rules** belong in `src/dbt/CLAUDE.md`
- **BigQuery MCP pagination tip** belongs in `mcp/CLAUDE.md`
- **Codespace quirks** belong in `.devcontainer/CLAUDE.md`
- **GKE quirks** belong in `.k8s/CLAUDE.md`
- **Shell style** (`shfmt` tabs) belongs in `.trunk/CLAUDE.md`
- **Testing commands** belong in `tests/CLAUDE.md`
- **Scripts reference** belongs in `scripts/CLAUDE.md`
- **`### Development` commands** (`uv sync`, `dagster dev`,
  `definitions validate`, `dagster-dbt prepare-and-package`) are
  Dagster/dbt-specific and belong in `src/teamster/CLAUDE.md`;
  `inject-secrets.sh` belongs in `.devcontainer/CLAUDE.md`; `uv sync --frozen`
  is automated by the post-build task and low value to document anywhere
- **`### Secrets`** is a routing instruction already covered by the
  `.claude/hooks/CLAUDE.md` row in the Architecture table; the regression test
  command (`bash tests/hooks/run_all.sh`) moves to `.claude/hooks/CLAUDE.md`
- **`## Commands` section** is entirely domain-specific — nothing remains after
  relocation that isn't already in the routing table or a subdirectory file

Additionally, five directories referenced in the routing table have no CLAUDE.md
files yet: `.devcontainer/`, `.k8s/`, `.trunk/`, `tests/`, `scripts/`.

## Goals

1. Reduce root CLAUDE.md to three sections: Project Overview, Working
   Conventions, Architecture
2. Consolidate five git/GitHub convention bullets into two (Git, GitHub) plus
   one standalone (Python execution) and one new one (Linter)
3. Relocate all domain-specific content to the appropriate subdirectory
4. Create five new CLAUDE.md files, each seeded with directory context
5. Expand the Architecture routing table to cover all subdirectory CLAUDE.md
   files

## Non-goals

- Boilerplate stripping across 55 subdirectory files (covered by Phase 1 plan)
- Changes to subdirectory CLAUDE.md files other than those explicitly listed in
  Files Changed below (`src/dbt/CLAUDE.md`, `mcp/CLAUDE.md`,
  `src/teamster/CLAUDE.md`, `.claude/hooks/CLAUDE.md`)
- The five new CLAUDE.md files contain a mix of relocated content and net-new
  context seeded from directory scans — both are in scope

## Target Structure of Root CLAUDE.md

```text
# CLAUDE.md
## Project Overview        (unchanged)
## Working Conventions
   - Python execution      (standalone, first — uv run rule)
   - Git                   (conventional commits, branch naming, ask before committing)
   - GitHub                (issues, PRs, design specs workflow)
   - Linter                (trunk-ignore + reason; no linter-native syntax)
## Architecture            (expanded routing table)
```

### Working Conventions Changes

**Python execution** — promoted to standalone first bullet (was buried in Git).
Rationale: failing to use `uv run` causes immediate failures; it is the highest-
consequence rule in the file.

**Git** consolidates:

- Git commits (don't commit proactively, conventional commits, no checkpoint
  messages)
- Branch naming (`<author>/<commit-type>/<brief-description>`, `claude` prefix)

**GitHub** consolidates:

- Pull requests (squash merge, use PR template)
- GitHub issues (ask first, `gh issue create`, label conventions)
- Design specs (issue → `gh issue develop` → commit spec → push)

**Linter** (new bullet):

> Use `# trunk-ignore(<linter>/<rule>)` with a reason comment. Do not use
> linter-native disable syntax (e.g., `# shellcheck disable=`, `# noqa`,
> `-- noqa`).

### Architecture / Routing Table

```text
| Path                      | When                                    |
|---------------------------|-----------------------------------------|
| src/teamster/CLAUDE.md    | Dagster code                            |
| src/dbt/CLAUDE.md         | dbt models                              |
| .vscode/CLAUDE.md         | VS Code tasks/scripts                   |
| .claude/hooks/CLAUDE.md   | hooks, deny rules, protected paths      |
| .devcontainer/CLAUDE.md   | Codespace setup                         |
| .k8s/CLAUDE.md            | GKE setup                               |
| .trunk/CLAUDE.md          | linting config                          |
| tests/CLAUDE.md           | testing                                 |
| scripts/CLAUDE.md         | project utilities                       |
| mcp/CLAUDE.md             | MCP servers/tools                       |
| docs/CLAUDE.md            | MkDocs documentation site               |
| Any subdirectory          | that directory's CLAUDE.md              |
```

## Content Relocations

### To existing files

**`src/dbt/CLAUDE.md`** — add SQL style rules currently in root linting section:

- BigQuery dialect, trailing commas required, single quotes for literals, max
  line length 88, reference to `.trunk/config/.sqlfluff`

**`mcp/CLAUDE.md`** — add BigQuery MCP pagination tip:

> The BigQuery MCP tool truncates results at 50 rows. When querying
> `INFORMATION_SCHEMA.COLUMNS` for tables with >50 columns, paginate with
> `WHERE ordinal_position > N` to get all rows.

### To new files

#### `.devcontainer/CLAUDE.md`

Seeded from directory scan:

- **Codespace quirks**: `sudo` removed at end of `postCreate.sh` — privileged
  setup must go in `postCreate.sh`, not later; `gcloud components install` and
  Helm must be added to `postCreate.sh` to persist across rebuilds
- **`--cap-add` stripping**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work
- **Post-build task**: "Setup: Post-Build Init" VS Code task runs automatically
  on folder open after a rebuild — handles GCloud ADC, Claude auth, plugin
  installation, dbt dev dataset checks; individual tasks also available via
  `Ctrl+Shift+P` → `Tasks: Run Task`
- **`postCreate.sh` vs `postStart.sh`**: `postCreate.sh` runs once on container
  creation; `postStart.sh` runs on every start (keep it idempotent)
- **`inject-secrets.sh`**: manually run to inject 1Password secrets into the
  environment (required for Dagster development, not needed for SQL-only work);
  run after container start if secrets are missing
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs

#### `.k8s/CLAUDE.md`

Seeded from directory scan:

- **Purpose**: Helm charts and scripts for deploying the Dagster Cloud agent and
  1Password Connect to GKE
- **`values.yaml` vs `values-override.yaml`**: `values.yaml` is auto-downloaded
  from Helm — never edit it. All customizations go in `values-override.yaml`
- **Bootstrap order**: run `setup.sh` first (installs kubectl, Helm, gke-mcp,
  creates namespace); then run `dagster/install.sh` and `1password/install.sh`
- **1Password prerequisite**: `install.sh` sources `env/.env` for
  `OP_CONNECT_TOKEN` — must be set before running
- **Helm install location**: installs to `~/.local/bin` to avoid
  `/usr/local/bin` permission issues (no sudo)

#### `.trunk/CLAUDE.md`

Seeded from directory scan:

- **Shell style**: `shfmt` enforces tabs (not spaces)
- **Linter ignores**: `# trunk-ignore(<linter>/<rule>)` with a reason comment —
  do not use linter-native syntax (this mirrors the root convention bullet, as
  the full detail belongs here)
- **Enabled linters**: ruff, pyright, bandit, isort (Python); sqlfluff, sqlfmt
  (SQL); shellcheck, shfmt (shell); yamllint (YAML); markdownlint (Markdown);
  actionlint (GitHub Actions); hadolint (Dockerfiles); gitleaks, git-diff-check,
  osv-scanner (security); prettier, taplo (config); oxipng, svgo (images/SVG)
- **Ignore rules**:
  - `src/teamster/**` — sqlfluff, sqlfmt ignored (SQL linting is dbt-only)
  - `src/teamster/libraries/dlt_sources/**` — pyright additionally ignored
    (third-party library wrappers)
  - `src/dbt/**` — all linters except sqlfluff, sqlfmt, and prettier ignored
  - `.k8s/**/values.yaml` — all linters ignored (generated Helm values)
- **Protected config**: `.trunk/config/` is read-only under hooks — present
  changes as manual application blocks
- **Hooks**: `trunk-fmt-pre-commit` runs `trunk fmt` on commit (auto-formats);
  `trunk-check-pre-push` runs `trunk check` on push (blocks on lint failures).
  Never use `--no-verify` — fix reported issues instead

#### `tests/CLAUDE.md`

Seeded from directory scan:

- **Test categories**:
  - Root-level `test_*.py` — unit tests for Dagster definitions, IO managers,
    automation conditions, utils (no external connections required)
  - `tests/assets/` — integration tests per source system; require env vars and
    external connections; not run in CI by default
  - `tests/sensors/`, `tests/schedules/`, `tests/ops/`, `tests/resources/` —
    component-level tests; many have `archive/` subdirectories (deprecated)
- **Running tests**:
  ```bash
  uv run pytest                                           # all tests
  uv run pytest tests/test_dagster_definitions.py         # single file
  uv run pytest tests/test_dagster_definitions.py::test_definitions_kipptaf  # single test
  uv run pytest tests/assets/test_assets_dbt.py           # asset tests (requires env vars)
  ```
- **Definitions validation**: uses `subprocess.check_output` to call
  `dagster definitions validate` — tests the real module load, not a mock
- **Automation condition tests**: use ephemeral in-memory Dagster instances
  (fast, no external deps)
- **Archived tests**: prefixed with `_test_` in `archive/` subdirectories —
  ignored by pytest by convention, not markers
- **No global conftest.py**: no shared fixtures at project level; see `utils.py`
  for SSH/DB resource helpers (require env vars)

#### `scripts/CLAUDE.md`

Seeded from directory scan:

- **Running scripts**: Python scripts run with `uv run scripts/<name>.py [args]`
  — never bare `python`. Shell scripts run directly: `bash scripts/<name>.sh`
- **Script catalog**:

  | Script                   | Purpose                                             |
  | ------------------------ | --------------------------------------------------- |
  | `dagster-dev.py`         | Start Dagster webserver for selected code locations |
  | `avro-schema-update.py`  | Rewrite Avro data in GCS with updated schema        |
  | `dbt-bq-audit.py`        | Audit BigQuery objects against dbt manifest         |
  | `dbt-build-init.sh`      | Initialize dbt build environment (shell script)     |
  | `dbt-manifest.py`        | Extract dbt manifest model list to CSV              |
  | `dbt-sxs.py`             | Run dbt side-by-side source comparison              |
  | `dbt-yaml.py`            | Parse and transform dbt YAML files                  |
  | `gen-automations-doc.py` | Regenerate `docs/reference/automations.md`          |
  | `json2py.py`             | Generate Pydantic models from JSON schemas          |
  | `migrate-asset-key.py`   | Migrate asset materialization history to new key    |
  | `update.py`              | Update all project dependencies (uv, Trunk, dbt)    |

- **Prerequisites**:
  - `dbt-manifest.py` requires `dbt parse` to have run first (reads
    `target/manifest.json`)
  - `gen-automations-doc.py` requires dbt manifests to be parsed
  - `dbt-bq-audit.py` writes to `scripts/script_output/` — directory must exist
- **`migrate-asset-key.py` caveat**: creates runless materialization events;
  automation cursors will not recognize migrated events

## Files Changed

| File                      | Action  | Notes                                                                               |
| ------------------------- | ------- | ----------------------------------------------------------------------------------- |
| `CLAUDE.md`               | Rewrite | Remove Commands section; consolidate conventions; expand routing table              |
| `src/dbt/CLAUDE.md`       | Add     | SQL style rules                                                                     |
| `src/teamster/CLAUDE.md`  | Add     | Development commands (`dagster dev`, `definitions validate`, `prepare-and-package`) |
| `mcp/CLAUDE.md`           | Add     | BigQuery MCP pagination tip                                                         |
| `.claude/hooks/CLAUDE.md` | Add     | Regression test command (`bash tests/hooks/run_all.sh`)                             |
| `.devcontainer/CLAUDE.md` | Create  | Codespace quirks + `inject-secrets.sh` + directory context                          |
| `.k8s/CLAUDE.md`          | Create  | GKE setup + directory context                                                       |
| `.trunk/CLAUDE.md`        | Create  | Linting config + shell style + directory context                                    |
| `tests/CLAUDE.md`         | Create  | Test categories, patterns, commands                                                 |
| `scripts/CLAUDE.md`       | Create  | Script catalog, conventions, prerequisites                                          |

**Total**: 10 files (5 modified, 5 created)

## Validation

```bash
# Root should be ~60-70 lines after rewrite
wc -l CLAUDE.md

# No domain-specific sections should remain in root
# (scripts/CLAUDE.md in the routing table is expected; check for prose references)
grep -n "BigQuery MCP\|SQL style\|shfmt\|Codespace\|GKE\|uv run pytest\|permissions.deny" CLAUDE.md

# New files should exist
ls .devcontainer/CLAUDE.md .k8s/CLAUDE.md .trunk/CLAUDE.md tests/CLAUDE.md scripts/CLAUDE.md

# Routing table should have all 11 named routes + catch-all (12 data rows total)
grep -c "CLAUDE.md |" CLAUDE.md

# Development commands should now be in src/teamster/CLAUDE.md
grep -n "dagster dev\|definitions validate\|prepare-and-package" src/teamster/CLAUDE.md

# SQL style rules should now be in src/dbt/CLAUDE.md
grep -n "trailing comma\|sqlfluff" src/dbt/CLAUDE.md

# BigQuery MCP tip should now be in mcp/CLAUDE.md
grep -n "50 rows\|ordinal_position" mcp/CLAUDE.md
```
