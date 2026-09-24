# CLAUDE.md — `.devcontainer/`

Container configuration for Codespace and local development. Human-facing setup
and operational docs are in `docs/guides/codespaces.md`.

## Quirks

- **No startup secret injection**: secrets are fetched on demand by
  `tests/conftest.py` when pytest runs. Credentialed one-offs (including
  `dagster definitions validate`) run under pytest; see root `CLAUDE.md` →
  _Tooling_.
- **`--cap-add` stripped**: Codespaces silently strips `--cap-add` from
  `runArgs` — namespace-based sandboxing (bwrap, unshare) will not work. Hooks
  are the sole enforcement layer for path-based access control.
- **Protected scripts**: `.devcontainer/scripts/` is read-only under hooks —
  present changes as manual application blocks, not diffs. `.vscode/scripts/` is
  **not** hook-protected and can be edited directly.
- **Machine-scoped VS Code settings**: devcontainer features auto-seed
  `/home/vscode/.vscode-remote/data/Machine/settings.json` (e.g., wrong
  `python.defaultInterpreterPath`, `ms-python.autopep8` as Python formatter).
  Workspace settings override these at runtime, but warnings appear during
  `postCreate` before the workspace loads. Patch this file early in
  `postCreate.sh` via `jq` to suppress them.
