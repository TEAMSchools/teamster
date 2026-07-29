# CLAUDE.md — `.vscode/`

VS Code tasks and scripts. Human-facing GCloud auth, Claude auth, and plugin
setup docs are in `docs/guides/codespaces.md`.

## Environment Quirks

- `lib/` is globally gitignored — name shell helper-library dirs `shared/`
  instead (none exists yet; create it rather than `lib/`)
- `task.allowAutomaticTasks` has application scope — cannot be set in workspace
  settings or `devcontainer.json` customizations; must go in the user's local VS
  Code User Settings
- `GITHUB_USER` is not available in VS Code task shells — derive with
  `gh api user --jq .login` and persist to `~/.bashrc`
- Claude plugin state lives in `~/.claude/plugins/installed_plugins.json` — read
  with `jq` instead of parsing `claude plugins list` output
- VS Code task shells do not inherit `~/.local/bin` in PATH — `uv` is not
  available unless you `source "${HOME}/.local/bin/env"` first
- Task scripts must also use `uv run` for venv-installed tools (`dbt`,
  `dagster`, etc.) — the venv is not activated in task shells

## File Watcher

- **`.worktrees/` and file watcher**: do not add `.worktrees/` to
  `files.watcherExclude` — the worktree workflow expects IDE features (explorer
  updates, git decorations, diagnostics) to work from the main workspace
