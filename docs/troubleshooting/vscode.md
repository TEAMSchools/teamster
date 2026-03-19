# Troubleshooting VS Code

## Python interpreter not found

The project venv is created by `uv` at `.venv/`. The interpreter path is set in
`.vscode/settings.json`:

```text
/workspaces/teamster/.venv/bin/python
```

If VS Code is not picking it up, open the command palette and run **Python:
Select Interpreter**, then choose the `.venv` path above.

If the venv doesn't exist yet:

```bash
uv sync --frozen
```

## Import errors / Pylance red underlines

Pylance resolves imports from the venv. If imports are unresolved after
`uv sync`:

1. Reload the VS Code window (**Developer: Reload Window**).
2. Confirm the interpreter is set to `.venv` (see above).

Type checking is intentionally set to `off` in `.vscode/settings.json` — Pyright
via Trunk handles type checking at lint/commit time instead.

## `.env` file / secrets not loaded

Environment variables are loaded from `env/.env`, which is generated from
1Password templates during `postCreate`. If the file is missing or stale:

```bash
bash .devcontainer/scripts/inject-secrets.sh
```

You must be authenticated with 1Password (`op signin`) for this to work. The
`UV_ENV_FILE` variable points `uv run` at the same file automatically.

## Trunk linter not running

Trunk is the default formatter for Python, SQL, YAML, and Markdown
(`"editor.defaultFormatter": "trunk.io"`). If format-on-save is not working:

1. Confirm the Trunk extension is installed and enabled.
2. Check that `./trunk` is executable:
   ```bash
   chmod +x /workspaces/teamster/trunk
   ./trunk install
   ```
3. Check the Trunk output panel (**View → Output → Trunk**) for errors.

## Container needs a rebuild

If `postCreate` did not run completely (e.g. 1Password auth failed mid-script),
the environment may be partially set up. Re-run the setup steps manually:

```bash
bash .devcontainer/scripts/inject-secrets.sh
uv sync --frozen
```

Or rebuild the container from scratch: open the command palette and run **Dev
Containers: Rebuild Container**. Note that a full rebuild re-runs `dbt deps` and
`dbt parse` for all 15 projects, which takes several minutes.

## dbt Power User

See [Troubleshooting dbt → dbt Power User](dbt.md#dbt-power-user-extension).

---

**See also:** [Getting Started](../getting-started.md) ·
[Troubleshooting dbt](dbt.md) · [Troubleshooting Dagster](dagster.md)
