# CLAUDE.md — `.vscode/`

VS Code tasks and scripts. Human-facing GCloud auth and plugin setup docs are in
`docs/guides/codespaces.md`.

## Environment Quirks

- `lib/` is globally gitignored — name shell helper-library dirs `shared/`
  instead (none exists yet; create it rather than `lib/`)
- `GITHUB_USER` is not available in VS Code task shells — derive with
  `gh api user --jq .login` and persist to `~/.bashrc`
- Claude plugin state lives in `~/.claude/plugins/installed_plugins.json` — read
  with `jq` instead of parsing `claude plugins list` output
- VS Code task shells do not inherit `~/.local/bin` in PATH — `uv` is not
  available unless you `source "${HOME}/.local/bin/env"` first
- Task scripts must also use `uv run` for venv-installed tools (`dbt`,
  `dagster`, etc.) — the venv is not activated in task shells
- Trunk actions (`post-merge.sh` runs as one) get no `containerEnv` variables,
  only a bare `HOME` and `PATH`. A script that runs `uv` under trunk exports
  `UV_CACHE_DIR` and `UV_LINK_MODE` itself, or uv copies the whole `.venv`
  through `~/.cache/uv`

## File Watcher

- **`.claude/worktrees/` and file watcher**: do not add `.claude/worktrees/` to
  `files.watcherExclude` — the worktree workflow expects IDE features (explorer
  updates, git decorations, diagnostics) to work from the main workspace
