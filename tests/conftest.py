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
        ["op", "run", "--no-masking", f"--env-file={_ENV_TPL}", "--", "env", "-0"],
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
