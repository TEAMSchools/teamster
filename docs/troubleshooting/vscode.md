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

## Secrets not loaded

Environment variables are fetched on demand from 1Password by
`tests/conftest.py` when pytest runs. For commands outside pytest (e.g.,
`dagster definitions validate`), run them in the VS Code terminal where
`OP_SERVICE_ACCOUNT_TOKEN` is available.

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

If `postCreate` did not run completely, the environment may be partially set up.
Re-run the setup steps manually:

```bash
uv sync --frozen
```

Or rebuild the container from scratch: open the command palette and run **Dev
Containers: Rebuild Container**. Note that a full rebuild re-runs `dbt deps` and
`dbt parse` for all 15 projects, which takes several minutes.

---

**See also:** [Guides](../guides/index.md) · [Troubleshooting dbt](dbt.md) ·
[Troubleshooting Dagster](dagster.md)
