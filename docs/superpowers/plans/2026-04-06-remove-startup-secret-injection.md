# Remove Startup Secret Injection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove startup secret injection from the devcontainer lifecycle and
replace with on-demand 1Password calls triggered by pytest via a root
`conftest.py`.

**Architecture:** Delete `inject-secrets.sh`. Save the 1Password token to a file
on tmpfs during `postCreate.sh`, then revoke it from the environment in
`postStart.sh` (same pattern as today). A new root `conftest.py` reads the saved
token and calls `op run` (env vars) and `op read` (file-based secrets) on demand
when tests run. Hook Rule 4 is hardened to block `op run`.

**Tech Stack:** Bash (devcontainer scripts), Python/pytest (conftest), 1Password
CLI (`op`)

---

## File Map

| File                                      | Action | Responsibility                           |
| ----------------------------------------- | ------ | ---------------------------------------- |
| `.devcontainer/scripts/inject-secrets.sh` | Delete | Startup secret injection (removed)       |
| `.devcontainer/scripts/postCreate.sh`     | Modify | Save token, remove inject call/symlinks  |
| `.devcontainer/scripts/postStart.sh`      | Modify | Remove inject call, keep token revoke    |
| `.vscode/settings.json`                   | Modify | Remove envFile references                |
| `.claude/hooks/check-sensitive.sh`        | Modify | Add `run` to op subcommand blocklist     |
| `tests/hooks/test_bypass_protection.sh`   | Modify | Add `op run` test cases                  |
| `conftest.py`                             | Create | On-demand secret fetching for pytest     |
| `tests/CLAUDE.md`                         | Modify | Document conftest exception and new flow |

---

### Task 1: Harden hook — block `op run`

This must ship first. If any later task is tested before this lands, Claude's
Bash could theoretically invoke `op run`.

**Files:**

- Modify: `.claude/hooks/check-sensitive.sh:116`
- Modify: `tests/hooks/test_bypass_protection.sh:27-31`

- [ ] **Step 1: Add `op run` test case to `test_bypass_protection.sh`**

Insert after line 27 (`op inject` test), before the `expect_allow` block:

```bash
expect_deny "op run" Bash command "op run --env-file=.env.tpl -- env"
expect_deny "op run with no flags" Bash command "op run -- printenv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/hooks/test_bypass_protection.sh`

Expected: The two new `op run` tests fail (currently allowed, should be denied).

- [ ] **Step 3: Add `run` to Rule 4 regex in `check-sensitive.sh`**

This is a protected file — present the change to the user for manual
application.

At line 116, change:

```bash
# before
if echo "${sanitized}" | grep -qE '\bop\b.*\b(vault|item|read|document|inject)\b'; then
# after
if echo "${sanitized}" | grep -qE '\bop\b.*\b(vault|item|read|run|document|inject)\b'; then
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/hooks/test_bypass_protection.sh`

Expected: All tests pass, including the two new `op run` cases.

- [ ] **Step 5: Run full hook test suite**

Run: `bash tests/hooks/run_all.sh`

Expected: All suites pass. No regressions.

- [ ] **Step 6: Commit**

```bash
git add tests/hooks/test_bypass_protection.sh
git commit -m "feat(hooks): block op run subcommand in Rule 4"
```

Note: `check-sensitive.sh` must be staged manually by the user (protected path).

---

### Task 2: Modify `postCreate.sh` — save token, remove injection

**Files:**

- Modify: `.devcontainer/scripts/postCreate.sh:29-32, 106-107, 111`

This is a protected file — present all changes to the user for manual
application.

- [ ] **Step 1: Remove secrets-related chmod lines**

Remove lines 30-31:

```bash
chmod 755 .devcontainer/scripts/inject-secrets.sh
chmod 600 .devcontainer/tpl/*
```

Keep line 32 (`chmod 700 ./env`).

- [ ] **Step 2: Remove inject-secrets call**

Remove lines 106-107:

```bash
# inject secrets
.devcontainer/scripts/inject-secrets.sh
```

- [ ] **Step 3: Remove `.env` symlink**

Remove line 111:

```bash
ln -sfn /etc/secret-volume/.env /workspaces/teamster/env/.env
```

Keep lines 110, 112-113 (secret-volume symlink, dagster-tmp).

- [ ] **Step 4: Add token save before sudo removal**

Insert before line 115 (`# remove sudo — must be last privileged step`):

```bash
# save 1Password token for on-demand use (conftest.py reads this at test time)
echo "${OP_SERVICE_ACCOUNT_TOKEN}" > /etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token
```

- [ ] **Step 5: Verify final state of the file**

The secrets-related section (after tmpfs permission fix) should now read:

```bash
# fix tmpfs permissions (Codespaces may override tmpfs-mode from mount config)
sudo chmod 755 /etc/secret-volume
sudo chown vscode:vscode /etc/secret-volume

# create convenience symlinks (-n: don't follow existing symlink-to-directory)
ln -sfn /etc/secret-volume /workspaces/teamster/secret-volume
mkdir -p /tmp/dagster
ln -sfn /tmp/dagster /workspaces/teamster/dagster-tmp

# save 1Password token for on-demand use (conftest.py reads this at test time)
echo "${OP_SERVICE_ACCOUNT_TOKEN}" > /etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token

# remove sudo — must be last privileged step
sudo rm -f /usr/local/bin/sudo /usr/bin/sudo
```

- [ ] **Step 6: Commit**

`postCreate.sh` must be staged and committed manually by the user (protected
path).

---

### Task 3: Modify `postStart.sh` — remove injection, keep revocation

**Files:**

- Modify: `.devcontainer/scripts/postStart.sh:1-9`

This is a protected file — present changes to the user for manual application.

- [ ] **Step 1: Replace the inject-and-revoke block**

Replace lines 1-9 with:

```bash
#!/bin/bash

# revoke 1Password tokens from future interactive shells
echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
```

The rest of the file (lines 11-21: `set +euo pipefail`, uv updates, trunk
install) stays unchanged.

- [ ] **Step 2: Commit**

`postStart.sh` must be staged and committed manually by the user (protected
path).

---

### Task 4: Delete `inject-secrets.sh`

**Files:**

- Delete: `.devcontainer/scripts/inject-secrets.sh`

This is a protected file — the user must delete and stage it manually.

- [ ] **Step 1: Delete the file**

```bash
rm .devcontainer/scripts/inject-secrets.sh
```

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "chore: delete inject-secrets.sh"
```

---

### Task 5: Remove envFile references from `.vscode/settings.json`

**Files:**

- Modify: `.vscode/settings.json:18, 62`

- [ ] **Step 1: Remove `python.envFile` setting**

Remove line 18:

```json
"python.envFile": "${workspaceFolder}/env/.env",
```

- [ ] **Step 2: Remove `UV_ENV_FILE` from terminal env**

Remove line 62 (inside `terminal.integrated.env.linux`):

```json
"UV_ENV_FILE": "${workspaceFolder}/env/.env",
```

- [ ] **Step 3: Commit**

```bash
git add .vscode/settings.json
git commit -m "chore(vscode): remove envFile references to deleted .env"
```

---

### Task 6: Create root `conftest.py` — on-demand secret fetching

**Files:**

- Create: `conftest.py`

- [ ] **Step 1: Write the conftest**

```python
"""Session-scoped secret bootstrapping for integration tests.

Reads the 1Password service account token from /etc/secret-volume/.op-token
(saved by postCreate.sh) and fetches secrets on demand:
- Environment variables via `op run --env-file`
- File-based secrets via `op read` to /etc/secret-volume/
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_TOKEN_PATH = Path("/etc/secret-volume/.op-token")
_SECRET_VOLUME = Path("/etc/secret-volume")
_ENV_TPL = Path(".devcontainer/tpl/.env.tpl")

_FILE_SECRETS: list[tuple[str, str, str]] = [
    ("Data Team", "ADP Workforce Now API", "adp_wfn_api.cer"),
    ("Data Team", "ADP Workforce Now API", "adp_wfn_api.key"),
    ("Data Team", "TEAMster 1Password Credentials File", "1password-credentials.json"),
    ("Data Team", "DeansList API", "deanslist_api_key_map.yaml"),
    ("Data Team", "Egencia SFTP", "id_rsa_egencia"),
]


def _read_token() -> str:
    """Read the saved 1Password service account token."""
    token = _TOKEN_PATH.read_text().strip()
    if not token or token == "revoked-after-injection":
        pytest.skip("1Password token not available — run postCreate.sh first")
    return token


def _inject_env_vars(token: str) -> None:
    """Use `op run` to resolve .env.tpl and inject vars into os.environ."""
    if not _ENV_TPL.exists():
        pytest.skip(f"{_ENV_TPL} not found")

    result = subprocess.run(
        ["op", "run", f"--env-file={_ENV_TPL}", "--", "env", "-0"],
        capture_output=True,
        text=True,
        env={**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": token},
        check=True,
    )

    for entry in result.stdout.split("\0"):
        if "=" in entry:
            key, _, value = entry.partition("=")
            os.environ[key] = value


def _fetch_file_secrets(token: str) -> None:
    """Fetch file-based secrets via `op read` to /etc/secret-volume/."""
    env = {**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": token}

    for vault, item, filename in _FILE_SECRETS:
        dest = _SECRET_VOLUME / filename
        if dest.exists() and dest.stat().st_size > 0:
            continue

        result = subprocess.run(
            ["op", "read", f"op://{vault}/{item}/{filename}"],
            capture_output=True,
            env=env,
            check=True,
        )

        dest.write_bytes(result.stdout)
        dest.chmod(0o600)


@pytest.fixture(autouse=True, scope="session")
def _bootstrap_secrets() -> None:
    """Fetch secrets from 1Password on first test run."""
    if not _TOKEN_PATH.exists():
        return

    token = _read_token()
    _inject_env_vars(token)
    _fetch_file_secrets(token)
```

- [ ] **Step 2: Verify conftest is picked up by pytest**

Run: `uv run pytest --co -q 2>&1 | head -5`

Expected: pytest collects tests without import errors. The fixture will skip
gracefully if the token file doesn't exist (container hasn't been rebuilt yet).

- [ ] **Step 3: Commit**

```bash
git add conftest.py
git commit -m "feat: add root conftest.py for on-demand 1Password secret fetching"
```

---

### Task 7: Update `tests/CLAUDE.md`

**Files:**

- Modify: `tests/CLAUDE.md:28-29, 37, 42-44`

- [ ] **Step 1: Update the "No global conftest.py" note**

Replace line 28-29:

```markdown
- **No global `conftest.py`**: no shared fixtures at project level. See
  `utils.py` for SSH/DB resource helpers (require env vars).
```

With:

```markdown
- **Root `conftest.py`**: contains a single session-scoped autouse fixture that
  bootstraps secrets from 1Password on demand. No shared test fixtures — see
  `utils.py` for SSH/DB resource helpers (require env vars).
```

- [ ] **Step 2: Update the worktree tests note**

Replace line 37 (the `source env/.env` instruction):

```markdown
with `set -a && source env/.env && set +a` then
```

With:

```markdown
ensuring `OP_SERVICE_ACCOUNT_TOKEN` is set, then
```

- [ ] **Step 3: Update the dagster definitions note**

Replace lines 42-44:

```markdown
- `dagster definitions validate` requires env vars from `.env` (injected from
  1Password at container start). The hook blocks reading `.env`, so validation
  fails in Claude sessions — this is expected, not a code issue.
```

With:

```markdown
- `dagster definitions validate` requires env vars from 1Password. Secrets are
  fetched on demand by the root `conftest.py` during test runs. Outside of
  pytest, run commands in the VS Code terminal where the token is available.
  Claude sessions cannot access secrets — this is expected, not a code issue.
```

- [ ] **Step 4: Commit**

```bash
git add tests/CLAUDE.md
git commit -m "docs: update tests/CLAUDE.md for on-demand secret fetching"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full hook test suite**

Run: `bash tests/hooks/run_all.sh`

Expected: All suites pass.

- [ ] **Step 2: Run pytest collection**

Run: `uv run pytest --co -q 2>&1 | head -20`

Expected: Tests collect without errors. The `_bootstrap_secrets` fixture appears
in the session fixtures.

- [ ] **Step 3: Verify no secrets on disk**

Run: `ls -la /etc/secret-volume/`

Expected: Only `.op-token` exists (if container has been rebuilt). No `.env`, no
certificate files, no YAML files.

- [ ] **Step 4: Squash-merge commit (optional)**

If all tasks were committed separately, the user may squash before PR:

```bash
git rebase -i origin/main
```
