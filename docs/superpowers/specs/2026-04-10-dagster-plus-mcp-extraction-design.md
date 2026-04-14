# Extract `mcp/dagster_plus` into `TEAMSchools/dagster-plus-mcp`

**Date:** 2026-04-10

## Goal

Move the Dagster+ MCP server out of the teamster monorepo into its own public
GitHub repo (`TEAMSchools/dagster-plus-mcp`). Consume it back in teamster as a
git dependency. Rename the Python package from `dagster_plus` to
`dagster_plus_mcp` to match the repo name.

## Decisions

- **Repo:** `TEAMSchools/dagster-plus-mcp`, public, no license file
- **Package name:** `dagster_plus_mcp`
- **Consumption:** git dependency in teamster's `dev` dependency group (not a
  core dependency — only needed in Codespaces for MCP)
- **Org defaults removed:** `DAGSTER_CLOUD_ORGANIZATION_ID` and
  `DAGSTER_CLOUD_DEPLOYMENT` become required env vars (no hardcoded `kipptaf` /
  `prod` defaults)
- **No PyPI publishing** — installed via `git+https://`

## New repo structure

```text
dagster-plus-mcp/
├── pyproject.toml
├── CLAUDE.md
└── dagster_plus_mcp/
    ├── __init__.py
    ├── __main__.py
    ├── server.py
    ├── queries.py
    ├── tools.py
    └── schema.json
```

### `pyproject.toml`

```toml
[project]
name = "dagster-plus-mcp"
version = "0.1.0"
description = "MCP server for the Dagster+ GraphQL API"
requires-python = ">=3.13"
dependencies = ["mcp>=1.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["dagster_plus_mcp"]
```

### Code changes from `mcp/dagster_plus/`

- **`server.py`**: `DAGSTER_CLOUD_ORGANIZATION_ID` and
  `DAGSTER_CLOUD_DEPLOYMENT` change from `os.environ.get(...)` with defaults to
  `os.environ[...]` (required).
- **All other files**: copied verbatim. Relative imports (`from .server import`,
  `from .queries import`) are package-relative and don't change.

### `CLAUDE.md`

Adapted from `mcp/dagster_plus/CLAUDE.md` — paths updated, teamster-specific
references removed, running instructions updated to reflect standalone repo.

## Teamster-side changes

### Add git dependency

In `pyproject.toml`, add to the `dev` dependency group:

```toml
[dependency-groups]
dev = [
    "cron-descriptor>=1.4",
    "dagster-plus-mcp @ git+https://github.com/TEAMSchools/dagster-plus-mcp.git",
    "dagster-webserver",
    "pytest>=8.3.4",
]
```

### Update `.mcp.json`

Replace the `run.sh` reference. The command becomes
`uv run --group dev python -m dagster_plus_mcp`. The 1Password token fetch
script moves to `.devcontainer/scripts/run-dagster-mcp.sh` (consistent with
other devcontainer scripts).

### Delete `mcp/` directory

Remove entirely: `mcp/pyproject.toml`, `mcp/uv.lock`, `mcp/CLAUDE.md`,
`mcp/dagster_plus/` (all files).

### Update CLAUDE.md references

- Root and `.claude/` CLAUDE.md files that mention `mcp/dagster_plus/` point to
  the new repo instead.
- `docs/superpowers/plans/` historical files left as-is.

## Migration sequence

1. Create `TEAMSchools/dagster-plus-mcp` repo on GitHub (empty).
2. Populate with renamed package, new `pyproject.toml`, `CLAUDE.md`.
3. In teamster: add git dep to `dev` group, update `.mcp.json` + `run.sh`
   location, delete `mcp/`, update CLAUDE.md references.
4. Verify: `uv run --group dev python -m dagster_plus_mcp` imports cleanly with
   a test token.
