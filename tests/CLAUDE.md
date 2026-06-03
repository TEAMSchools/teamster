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
- **`conftest.py`**: contains a single session-scoped autouse fixture that
  bootstraps secrets from 1Password on demand. No shared test fixtures — see
  `utils.py` for SSH/DB resource helpers (require env vars).
- **Token file missing**: `_bootstrap_secrets` silently returns when
  `/etc/secret-volume/.op-token` doesn't exist. If ALL env vars are missing,
  check the token file first — don't investigate individual env vars.
- **Archived tests**: `_test_` prefix in `archive/` subdirectories — ignored by
  pytest by convention, not markers.
- **`EnvVar` in integration tests**: Use `EnvVar("X")` for `str` fields inside
  `build_resources()`. For non-`str` fields (e.g. `int` ports), use
  `int(check.not_none(EnvVar("X").get_value()))` — `EnvVar` resolves lazily, so
  `int(EnvVar("X"))` casts the marker object, not the value.
- **Worktree tests**: VS Code doesn't discover tests in worktrees. Run manually
  ensuring `OP_SERVICE_ACCOUNT_TOKEN` is set, then
  `cd .worktrees/<branch> && uv run pytest ...`.
- **Unit testing Dagster resources**: `SSHResource` and other
  `ConfigurableResource` subclasses are frozen Pydantic models — use
  `build_resources()` context manager to instantiate, then call methods on
  `resources.<name>`. `PrivateAttr` fields (`_log`, `_service`) accept direct
  assignment; use `object.__setattr__` to monkey-patch methods.
- **SSH `test=True`**: `SSHResource` reads the SSH password from a secret file
  by default (`test=False`). Integration tests must set `test=True` and pass
  `password` directly so each district uses its own credentials.
- **Cross-file conftest imports fail** (`tests/` has no `__init__.py`). For
  fixture-injected param types, skip the annotation or use `TYPE_CHECKING` with
  a string forward-ref.
- `dagster definitions validate` requires env vars from 1Password. Secrets are
  fetched on demand by the root `conftest.py` during test runs. Outside of
  pytest, run commands in the VS Code terminal where the token is available.
  Claude sessions cannot access secrets — this is expected, not a code issue.

## Hook security tests (`tests/hooks/`)

Shell suites for the two `.claude/hooks/` scripts. `bash tests/hooks/run_all.sh`
runs all of them; each `test_*.sh` covers one rule area; `helpers.sh` provides
`expect_deny`/`expect_allow`/`expect_deny_exit0`.

- **Validate a candidate patch to a protected hook BEFORE handing it off** (the
  `.sh` hooks can't be edited in place): write the patched copy to
  `.claude/scratch/`, then run the suite against it — `helpers.sh` honors `HOOK`
  / `OUTPUT_HOOK` env overrides:
  `HOOK=/abs/scratch/check-sensitive-x.sh OUTPUT_HOOK=/abs/scratch/check-output-x.sh bash tests/hooks/run_all.sh`.
- Reading a `test_*.sh` range that contains secret-shaped fixtures (`op://`, key
  headers, cloud tokens) trips `check-output.sh` on the Read result. Read clean
  ranges only, or anchor Edits on a non-fixture line (e.g. `print_summary`).
- Synthetic secret fixtures: split the literal (`"sk_live""_..."`,
  `'-----BEGIN ''PRIVATE KEY-----'`) so gitleaks' source scan misses it but bash
  rebuilds the value at run time — cleaner than a `trunk-ignore`, which trips
  `trunk/ignore-does-nothing` when gitleaks wouldn't have flagged it anyway.
- New detection rules: add benign outputs to `test_fp_corpus.sh` and measure
  against it — it is the false-positive back-out gauge.
