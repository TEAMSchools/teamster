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

## Patterns

- **Definitions validation**: calls `dagster definitions validate` via
  `subprocess.check_output` — tests the real module load, not a mock.
- **Automation condition tests**: use ephemeral in-memory Dagster instances
  (fast, no external deps).
- **No global `conftest.py`**: no shared fixtures at project level. See
  `utils.py` for SSH/DB resource helpers (require env vars).
- **Archived tests**: `_test_` prefix in `archive/` subdirectories — ignored by
  pytest by convention, not markers.
- **`EnvVar` in integration tests**: Use `EnvVar("X")` for `str` fields inside
  `build_resources()`. For non-`str` fields (e.g. `int` ports), use
  `int(check.not_none(EnvVar("X").get_value()))` — `EnvVar` resolves lazily, so
  `int(EnvVar("X"))` casts the marker object, not the value.
- **Worktree tests**: VS Code doesn't discover tests in worktrees. Run manually
  with `set -a && source env/.env && set +a` then
  `cd .worktrees/<branch> && uv run pytest ...`.
- **SSH `test=True`**: `SSHResource` reads the SSH password from a secret file
  by default (`test=False`). Integration tests must set `test=True` and pass
  `password` directly so each district uses its own credentials.
- `dagster definitions validate` requires env vars from `.env` (injected from
  1Password at container start). The hook blocks reading `.env`, so validation
  fails in Claude sessions — this is expected, not a code issue.
