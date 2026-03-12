# Getting Started

## Account Setup

### GitHub

To contribute, you must be a member of our
[Data Team](https://github.com/orgs/TEAMSchools/teams/data-team). Your ability
to approve and merge pull requests depends on your subgroup:

- [Analytics Engineers](https://github.com/orgs/TEAMSchools/teams/analytics-engineers)
- [Data Engineers](https://github.com/orgs/TEAMSchools/teams/data-engineers)
- [Admins](https://github.com/orgs/TEAMSchools/teams/admins)

### Google Workspace

To access our BigQuery project and its datasets, you must be a member of the
**TEAMster Analysts KTAF** Google security group.

### dbt Cloud

#### Development dataset

dbt Cloud creates a personal development dataset in BigQuery for each user,
named using your username as a prefix. Please prefix yours with an underscore
(`_`) — BigQuery hides datasets starting with `_` from the left nav, keeping the
project list readable.

Set this in **Account settings → Credentials → Development credentials**.

#### sqlfmt

<!-- adapted from https://docs.getdbt.com/docs/cloud/dbt-cloud-ide/lint-format#format-sql -->

We use [sqlfmt](https://sqlfmt.com/) for SQL formatting. To enable it in dbt
Cloud:

1. Open a `.sql` file on a development branch.
2. Click the **Code Quality** tab in the console, then **`</> Config`**.
3. Select the `sqlfmt` radio button.
4. Click **Format** to auto-format the file.

## GitHub Codespaces

The devcontainer is pre-configured for
[GitHub Codespaces](https://github.com/features/codespaces) — no local setup
required.

### Creating a Codespace

1. On the repository page, click **Code → Codespaces → Create codespace on
   main** (or your branch).
2. Select the **4-core / 16 GB** machine type.
3. Wait for the container to finish building. `postCreate.sh` runs
   automatically: installs dependencies, bootstraps all dbt projects
   (`dbt deps` + `dbt parse` in parallel), and injects secrets from 1Password.
   First creation takes a few minutes.

### After the Codespace opens

**Dismiss extension prompts** — all required extensions are already configured
in `devcontainer.json`; dismiss any install prompts VS Code shows.

**Authenticate to Google** — credentials are not persisted across sessions:

```bash
bash .devcontainer/scripts/gcloud-auth-application-default-login.sh
```

**Authenticate Claude Code** — pre-installed; log in once per session:

```bash
claude auth login
```

**Wait for dbt Power User to finish parsing** — the extension parses all
projects in the background, which pegs CPU and makes the extension unresponsive
until complete. Use `htop` to monitor; wait for CPU to settle before using the
extension. This is also the most common cause of "extension not responding"
errors.

**Reload the window** once background processes finish
(<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> → **Developer: Reload Window**)
for a clean editor state.

### Subsequent sessions

`postStart.sh` runs automatically on resume (updates uv, syncs dependencies).
Re-run the Google and Claude Code auth steps above — credentials are not
persisted.

## Local Development

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) for Python package management.

### Setup

```bash
# Install dependencies
uv sync --frozen

# Run Dagster webserver locally
uv run dagster dev

# Validate definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

### dbt

Before running dbt assets locally, prepare and package the dbt project:

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

### Linting and formatting

[Trunk](https://trunk.io/) runs all linters:

```bash
trunk check   # lint
trunk fmt     # format
```

| Language | Linter(s)                                                                                   |
| -------- | ------------------------------------------------------------------------------------------- |
| SQL      | [SQLFluff](https://docs.sqlfluff.com/en/stable/rules.html), [sqlfmt](https://sqlfmt.com/)   |
| Python   | [Ruff](https://docs.astral.sh/ruff/rules/), [Pyright](https://github.com/microsoft/pyright) |

### Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_dagster_definitions.py

# Run asset-specific tests (require env vars / external connections)
uv run pytest tests/assets/test_assets_dbt.py
```
