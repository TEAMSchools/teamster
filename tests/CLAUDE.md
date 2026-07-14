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
- **`EnvVar` in integration tests**: Use `EnvVar("X")` for `str` fields and
  `EnvVar.int("X")` for `int` fields (e.g. ports) inside `build_resources()` —
  both resolve lazily at resource init and never read the environment at
  construction. Prefer these over `int(EnvVar("X").get_value())`: `.get_value()`
  reads eagerly, which is harmless when a test always sets the var but crashes
  module-load construction in production `resources.py` when it is unset (e.g. a
  codespace) — so never copy that idiom there. Plain `int(EnvVar("X"))` casts
  the marker object, not the value.
- **Worktree tests**: VS Code doesn't discover tests in worktrees. Run manually
  ensuring `OP_SERVICE_ACCOUNT_TOKEN` is set, then
  `cd .worktrees/<branch> && uv run pytest ...`.
- **Unit testing Dagster resources**: `SSHResource` and other
  `ConfigurableResource` subclasses are frozen Pydantic models — use
  `build_resources()` context manager to instantiate, then call methods on
  `resources.<name>`. `PrivateAttr` fields (`_log`, `_service`) accept direct
  assignment; use `object.__setattr__` to monkey-patch methods.
- **Testing resource retry offline**: monkeypatch
  `<Resource>._request.retry.wait = wait_none()` (tenacity) to kill backoff,
  inject `object.__setattr__(r, "_session", SimpleNamespace(request=fake_fn))`
  with a `_FakeResponse` stub, and assert call counts for retry/no-retry paths.
  Reference harness: `tests/resources/test_resource_adp_workforce_now.py`.
- **SSH `test=True`**: `SSHResource` reads the SSH password from a secret file
  by default (`test=False`). Integration tests must set `test=True` and pass
  `password` directly so each district uses its own credentials.
- **Cross-file conftest imports fail** (`tests/` has no `__init__.py`). For
  fixture-injected param types, skip the annotation or use `TYPE_CHECKING` with
  a string forward-ref.
- **Secrets ARE available to Claude inside pytest**: the autouse `conftest.py`
  fixture bootstraps 1Password per run, so credentialed work (live API pulls,
  asset `materialize()`, BigQuery) is runnable via `uv run pytest`. Wrap a
  credentialed one-off as a throwaway `tests/**/test_zz_*.py` and delete it
  after — a plain `uv run python script.py` is NOT bootstrapped. ADC
  (BigQuery/GCS) auth is independent of 1Password and always works (dbt CLI, BQ
  client). `dagster definitions validate` likewise relies on the conftest
  bootstrap.

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
