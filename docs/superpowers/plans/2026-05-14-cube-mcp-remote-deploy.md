# Cube MCP Remote Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy `scripts/cube_rest_mcp.py` as a Cloud Run service
(`src/cube/mcp/server.py`) reachable by Claude.ai Custom Connectors and by
data-team Codespaces via `mcp-remote`, with per-user Google Workspace OAuth
provided by WorkOS AuthKit.

**Architecture:** Two-token model. WorkOS AuthKit handles OAuth 2.1 + DCR,
federating to Google Workspace. The MCP server runs on Cloud Run in a new
`teamster-mcp` GCP project, validates AuthKit JWTs via JWKS, extracts the user
email, and mints a per-request Cube JWT. Cube's `contextToGroups` resolves the
user's `cube-*` groups via the Google Admin SDK Directory API (already
configured by the team).

**Tech Stack:** Python 3.13, `mcp>=1.2` Python SDK (FastMCP), `httpx`, `pyjwt`,
Cloud Run, Artifact Registry, Workload Identity Federation, WorkOS AuthKit,
`mcp-remote` (npm) for the data-team stdio bridge.

**Spec:**
[docs/superpowers/specs/2026-05-11-cube-mcp-remote-deploy-design.md](../specs/2026-05-11-cube-mcp-remote-deploy-design.md)

**Issue:** [#3879](https://github.com/TEAMSchools/teamster/issues/3879)

---

## File Structure

**Files created:**

- `src/cube/mcp/server.py` — the MCP server (moved from
  `scripts/cube_rest_mcp.py`, plus HTTP/OAuth additions)
- `src/cube/mcp/Dockerfile` — Python 3.13 container image, `uv run` entrypoint
- `src/cube/mcp/CLAUDE.md` — service-specific guidance (when to edit, how to
  test locally, deploy mechanics)
- `tests/cube/test_mcp_server.py` — unit tests for transport switching, OAuth
  resource-server config, email resolution
- `tests/cube/__init__.py` — empty marker so pytest discovers the package
- `.github/workflows/deploy-cube-mcp.yaml` — Cloud Run deploy workflow (WIF +
  build + push + `gcloud run deploy`)
- `docs/guides/claude-cube-connector.md` — director-facing setup guide

**Files modified:**

- `scripts/cube-rest-mcp-launch.sh` — repointed at the new server path
- `scripts/CLAUDE.md` — script catalog entry updated; reframed as dev-mode
  launcher
- `CLAUDE.md` (project root) — "MCP tool selection" section updated for the new
  path
- `mkdocs.yml` — nav entry for the new guide

**Files deleted:**

- `scripts/cube_rest_mcp.py` — replaced by `src/cube/mcp/server.py` (use
  `git mv` to preserve history)

**External infrastructure created (no repo files):**

- `teamster-mcp` GCP project + APIs + Artifact Registry repo + Secret Manager
  secret + runtime service account
- WorkOS AuthKit tenant + Google OIDC connection + DCR enabled
- Claude.ai workspace Custom Connector

---

## Phase 1: File reorganization (preserve git history)

### Task 1: Move the MCP server file

**Files:**

- Move: `scripts/cube_rest_mcp.py` → `src/cube/mcp/server.py`
- Modify: `scripts/cube-rest-mcp-launch.sh`

- [ ] **Step 1: Create the destination directory**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
mkdir -p src/cube/mcp
```

- [ ] **Step 2: Move the file with `git mv` to preserve history**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy mv scripts/cube_rest_mcp.py src/cube/mcp/server.py
```

- [ ] **Step 3: Update the launcher to point at the new path**

In `scripts/cube-rest-mcp-launch.sh`, replace line 23:

```bash
exec uv run /workspaces/teamster/src/cube/mcp/server.py
```

(was: `exec uv run /workspaces/teamster/scripts/cube_rest_mcp.py`)

- [ ] **Step 4: Verify the launcher still works (stdio mode unchanged)**

The launcher requires the OP token to fetch the Cube API secret, which is only
available in a running Codespace with the secret-volume mounted. If running this
step locally:

```bash
bash scripts/cube-rest-mcp-launch.sh < /dev/null 2>&1 | head -5
```

Expected: server starts and prints its FastMCP banner (or fails at `op read` if
the token isn't available — that's also acceptable; the change being tested is
the path, not the secret fetch).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add scripts/cube-rest-mcp-launch.sh src/cube/mcp/server.py
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "refactor(cube): move cube MCP server to src/cube/mcp/server.py

Refs #3879

Server file moves out of scripts/ — it's no longer a standalone executable
but a deployable service. Launcher in scripts/ updated to invoke the new
path. No behavior change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2: Update `scripts/CLAUDE.md` catalog entry

**Files:**

- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Present the proposed CLAUDE.md change to the user**

CLAUDE.md edits require user approval before applying. Show the user this
proposed replacement for the `cube_rest_mcp.py` catalog row:

```text
| `cube_rest_mcp.py` (now `src/cube/mcp/server.py`) | MCP server. Default path is the remote Cloud Run deploy (per `src/cube/mcp/CLAUDE.md`); stdio mode via `cube-rest-mcp-launch.sh` is dev-mode only for iterating on the server. |
```

And update the `cube-rest-mcp-launch.sh` row:

```text
| `cube-rest-mcp-launch.sh` | MCP launcher (dev mode only). Fetches `CUBEJS_API_SECRET`, execs `src/cube/mcp/server.py` in stdio mode. Default cube MCP path is the Cloud Run deploy — use this only when iterating on the server itself. |
```

- [ ] **Step 2: Apply the approved edit**

Once approved, use the Edit tool to replace both rows in `scripts/CLAUDE.md`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add scripts/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "docs(claude-md): reframe cube launcher as dev-mode only

Refs #3879

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2: Test scaffolding for the MCP server

### Task 3: Create the test package and a smoke test that loads the module

**Files:**

- Create: `tests/cube/__init__.py`
- Create: `tests/cube/test_mcp_server.py`

- [ ] **Step 1: Create the empty package marker**

```bash
mkdir -p /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy/tests/cube
touch /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy/tests/cube/__init__.py
```

- [ ] **Step 2: Write the module-loader fixture and a baseline test**

Create `tests/cube/test_mcp_server.py` with the PEP 723 module-loader pattern
documented in `scripts/CLAUDE.md`:

```python
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "cube" / "mcp" / "server.py"
)


def _load_server(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load src/cube/mcp/server.py as a module under sys.modules['cube_mcp_server'].

    The script reads CUBE_REST_URL and CUBE_API_SECRET at import time, so we
    set placeholders before exec_module.
    """
    monkeypatch.setenv("CUBE_REST_URL", "https://example.invalid/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_SECRET", "test-secret-not-used")
    spec = importlib.util.spec_from_file_location("cube_mcp_server", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cube_mcp_server"] = module
    spec.loader.exec_module(module)
    return module


def test_module_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    assert hasattr(server, "mcp"), "FastMCP instance not found"
    assert hasattr(server, "load"), "load tool not found"
    assert hasattr(server, "meta"), "meta tool not found"
    assert hasattr(server, "sql"), "sql tool not found"
```

- [ ] **Step 3: Run the baseline test and confirm it passes**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
uv run pytest tests/cube/test_mcp_server.py -v
```

Expected: PASS. (If the test fails with `ModuleNotFoundError: jwt`, the PEP 723
inline dependencies aren't being installed — workaround: run via
`uv run --with mcp --with httpx --with pyjwt pytest ...` or check the PEP 723
block at the top of `src/cube/mcp/server.py`.)

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add tests/cube/__init__.py tests/cube/test_mcp_server.py
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "test(cube): scaffold cube MCP server module-load test

Refs #3879

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3: HTTP transport mode

### Task 4: TRANSPORT env var routing to streamable-http

**Files:**

- Modify: `src/cube/mcp/server.py` (the `__main__` block at the bottom)
- Modify: `tests/cube/test_mcp_server.py`

- [ ] **Step 1: Write the failing test for HTTP transport routing**

Add to `tests/cube/test_mcp_server.py`:

```python
def test_run_dispatches_to_stdio_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    monkeypatch.delenv("TRANSPORT", raising=False)
    called_with: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        called_with["args"] = args
        called_with["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()  # introduced in Step 3
    assert called_with == {"args": (), "kwargs": {}}


def test_run_dispatches_to_streamable_http_when_TRANSPORT_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    monkeypatch.setenv("TRANSPORT", "http")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    called_with: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        called_with["args"] = args
        called_with["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()
    assert called_with["kwargs"]["transport"] == "streamable-http"
    assert called_with["kwargs"]["host"] == "0.0.0.0"
    assert called_with["kwargs"]["port"] == 8080
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
uv run pytest tests/cube/test_mcp_server.py::test_run_dispatches_to_stdio_by_default -v
```

Expected: FAIL —
`AttributeError: module 'cube_mcp_server' has no attribute 'main'`.

- [ ] **Step 3: Replace the `__main__` block in `src/cube/mcp/server.py`**

At the bottom of `src/cube/mcp/server.py`, replace:

```python
if __name__ == "__main__":
    mcp.run()
```

with:

```python
def main() -> None:
    transport = os.environ.get("TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run both transport-routing tests and verify they pass**

```bash
uv run pytest tests/cube/test_mcp_server.py -v -k "dispatches"
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "feat(cube-mcp): add HTTP transport mode via TRANSPORT env var

Refs #3879

TRANSPORT=http selects streamable-http on 0.0.0.0:8080 (Cloud Run default).
Unset or stdio preserves the existing stdio path unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 4: OAuth resource-server configuration

### Task 5: AUTHKIT_DOMAIN env var wires up TokenVerifier + AuthSettings

**Files:**

- Modify: `src/cube/mcp/server.py`
- Modify: `tests/cube/test_mcp_server.py`

**Reference for the engineer:**
[MCP Python SDK README — Authentication section](https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#authentication)
for the canonical `TokenVerifier` + `AuthSettings` API. If the SDK version
pinned in the PEP 723 inline deps doesn't expose these names exactly, consult
the SDK release notes — the names changed across early `mcp` releases. The plan
below assumes the names per the README at the time of writing.

- [ ] **Step 1: Write the failing test for OAuth wiring**

Add to `tests/cube/test_mcp_server.py`:

```python
def test_oauth_disabled_when_AUTHKIT_DOMAIN_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    assert server.AUTHKIT_DOMAIN is None
    assert server._token_verifier is None


def test_oauth_configured_when_AUTHKIT_DOMAIN_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    server = _load_server(monkeypatch)
    assert server.AUTHKIT_DOMAIN == "kipp.authkit.app"
    assert server._token_verifier is not None
    # The verifier should know the JWKS URL pattern.
    assert "kipp.authkit.app" in server._jwks_url
    assert server._jwks_url.endswith("/oauth2/jwks")
```

- [ ] **Step 2: Run and verify failure**

```bash
uv run pytest tests/cube/test_mcp_server.py -v -k "AUTHKIT_DOMAIN"
```

Expected: FAIL — module has no `AUTHKIT_DOMAIN`, `_token_verifier`, or
`_jwks_url`.

- [ ] **Step 3: Add OAuth config to `src/cube/mcp/server.py`**

Near the top of `src/cube/mcp/server.py`, after the existing `CUBE_REST_URL` /
`CUBE_API_SECRET` reads (around line 44–52), add:

```python
AUTHKIT_DOMAIN = os.environ.get("AUTHKIT_DOMAIN")
_jwks_url = (
    f"https://{AUTHKIT_DOMAIN}/oauth2/jwks" if AUTHKIT_DOMAIN else ""
)
```

Then update the PEP 723 inline-deps block at the top of the file to include the
MCP SDK's auth extras (the engineer should verify the exact extras name against
the SDK README at implementation time — likely `mcp[cli]` or a JWT validation
package like `authlib` or `python-jose`).

Replace the existing FastMCP instantiation:

```python
mcp = FastMCP(
    "cube",
    instructions=(
        # ... existing instructions block, unchanged ...
    ),
)
```

with a version that conditionally adds auth when `AUTHKIT_DOMAIN` is set:

```python
def _build_token_verifier() -> object | None:
    """Construct a JWKS-backed token verifier when OAuth is configured.

    Returns None when AUTHKIT_DOMAIN is unset (stdio dev mode).
    """
    if not AUTHKIT_DOMAIN:
        return None
    # Per https://github.com/modelcontextprotocol/python-sdk — exact class
    # name and import path may vary by SDK version. Common pattern:
    from mcp.server.auth.providers.bearer import JWTBearerTokenVerifier

    return JWTBearerTokenVerifier(
        jwks_uri=_jwks_url,
        issuer=f"https://{AUTHKIT_DOMAIN}",
        audience=None,  # WorkOS AuthKit issues audience-less tokens by default
    )


_token_verifier = _build_token_verifier()

_mcp_kwargs: dict[str, object] = {}
if _token_verifier is not None:
    from mcp.server.auth.settings import AuthSettings

    _mcp_kwargs["token_verifier"] = _token_verifier
    _mcp_kwargs["auth"] = AuthSettings(
        issuer_url=f"https://{AUTHKIT_DOMAIN}",
        resource_server_url=os.environ.get("PUBLIC_URL", ""),
        required_scopes=[],
    )

mcp = FastMCP(
    "cube",
    instructions=(
        # ... existing instructions block, unchanged ...
    ),
    **_mcp_kwargs,
)
```

(The engineer should consult the MCP Python SDK README at implementation time to
confirm exact class names and the `PUBLIC_URL` plumbing — the spec deliberately
doesn't pin SDK internal names that may have shifted.)

- [ ] **Step 4: Run the tests and verify they pass**

```bash
uv run pytest tests/cube/test_mcp_server.py -v -k "AUTHKIT_DOMAIN"
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "feat(cube-mcp): configure FastMCP as OAuth resource server

Refs #3879

When AUTHKIT_DOMAIN is set, FastMCP gets a JWT token verifier backed by
WorkOS AuthKit's JWKS and AuthSettings pointing at the AuthKit issuer.
The MCP SDK serves /.well-known/oauth-protected-resource per RFC 9728
(MUST per the MCP spec). Unset preserves stdio dev mode behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6: HTTP-mode email resolution reads from OAuth claims

**Files:**

- Modify: `src/cube/mcp/server.py` (the `_get_user_email` function around lines
  74–105)
- Modify: `tests/cube/test_mcp_server.py`

- [ ] **Step 1: Write the failing test for OAuth claim extraction**

Add to `tests/cube/test_mcp_server.py`:

```python
import asyncio
from unittest.mock import MagicMock


def test_get_user_email_reads_oauth_claim_in_http_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    server = _load_server(monkeypatch)
    ctx = MagicMock()
    # MCP SDK exposes the verified token via ctx.request_context — wire up
    # the access_token attribute with an `email` claim.
    ctx.request_context.user.claims = {"email": "director@apps.teamschools.org"}

    email = asyncio.run(server._get_user_email(ctx))
    assert email == "director@apps.teamschools.org"


def test_get_user_email_falls_through_to_stdio_path_when_no_oauth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)
    ctx = MagicMock()

    email = asyncio.run(server._get_user_email(ctx))
    assert email == "engineer@apps.teamschools.org"
```

- [ ] **Step 2: Run and verify failure**

```bash
uv run pytest tests/cube/test_mcp_server.py -v -k "get_user_email"
```

Expected: FAIL — first test fails because `_get_user_email` doesn't yet check
OAuth claims.

- [ ] **Step 3: Update `_get_user_email` in `src/cube/mcp/server.py`**

Replace the existing function (around lines 74–105) with:

```python
async def _get_user_email(ctx: Context) -> str:
    # HTTP/OAuth mode: pull the verified email from the bearer-token claims.
    if AUTHKIT_DOMAIN:
        try:
            email = ctx.request_context.user.claims["email"]
        except (AttributeError, KeyError) as exc:
            raise MissingUserEmailError(
                "cube MCP: OAuth token has no `email` claim. Check the "
                "WorkOS AuthKit user-info scope configuration."
            ) from exc
        return email.strip()

    # Stdio dev mode: env var → cache file → elicit → set_user_email error.
    env_override = os.environ.get("CUBE_USER_EMAIL", "").strip()
    if env_override:
        return env_override
    if USER_EMAIL_CACHE.exists():
        cached = USER_EMAIL_CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    try:
        result = await ctx.elicit(
            message=(
                "cube MCP needs your Google Workspace email to set the JWT "
                f"security context. Will be cached at {USER_EMAIL_CACHE} for "
                "future sessions."
            ),
            schema=UserEmailPrompt,
        )
    except Exception as exc:
        raise MissingUserEmailError(
            "cube MCP has no user email configured. Call the `set_user_email` "
            "tool with the user's Google Workspace email (e.g. "
            "firstlast@apps.teamschools.org), then retry. The value is cached "
            f"at {USER_EMAIL_CACHE} for future sessions."
        ) from exc
    if result.action != "accept" or not result.data:
        raise MissingUserEmailError(
            "cube MCP: email required for security context. Call the "
            "`set_user_email` tool to set it."
        )
    email = result.data.email.strip()
    _write_user_email(email)
    return email
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
uv run pytest tests/cube/test_mcp_server.py -v -k "get_user_email"
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "feat(cube-mcp): read email from verified OAuth claims in HTTP mode

Refs #3879

When AUTHKIT_DOMAIN is set, _get_user_email returns the verified email
claim from the bearer token. Stdio path (env var → cache → elicit →
set_user_email error) is preserved for dev mode.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 7: Full pytest run to verify no regressions

- [ ] **Step 1: Run the complete cube MCP test module**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
uv run pytest tests/cube/ -v
```

Expected: all tests PASS. If any unrelated test elsewhere in the suite breaks,
investigate — but Phase 3-4 changes should be local to the server file.

---

## Phase 5: Dockerfile and service-specific CLAUDE.md

### Task 8: Author the Dockerfile

**Files:**

- Create: `src/cube/mcp/Dockerfile`

- [ ] **Step 1: Create `src/cube/mcp/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS base

# Install uv (used to install PEP 723 inline deps at run time).
RUN pip install --no-cache-dir uv==0.5.18

WORKDIR /app
COPY server.py /app/server.py

# Cloud Run sets PORT; our server reads TRANSPORT and binds 8080 explicitly.
EXPOSE 8080

# Use uv run to honor the PEP 723 inline dependency block at the top of server.py.
CMD ["uv", "run", "/app/server.py"]
```

- [ ] **Step 2: Build the image locally**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
docker build -t cube-mcp-local:dev -f src/cube/mcp/Dockerfile src/cube/mcp/
```

Expected: image builds without error. First build will take 1-3 minutes (pulls
Python base image, installs uv, dependencies install on first run).

- [ ] **Step 3: Run the image locally in HTTP mode (no OAuth yet — stdio
      fallback)**

```bash
docker run --rm -p 8080:8080 \
  -e TRANSPORT=http \
  -e CUBE_REST_URL="https://example.invalid/cubejs-api/v1" \
  -e CUBE_API_SECRET="not-used-without-real-cube" \
  cube-mcp-local:dev &
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/mcp
docker stop $(docker ps -q --filter ancestor=cube-mcp-local:dev) 2>/dev/null
```

Expected: HTTP 401 or 400 (because no OAuth bearer token + AUTHKIT_DOMAIN not
configured will yield a permissive endpoint, but FastMCP's MCP protocol expects
an MCP-shaped request, not a bare GET). The key signal is **the server is
reachable** — any HTTP code that's not "connection refused" passes this smoke
test.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add src/cube/mcp/Dockerfile
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "feat(cube-mcp): add Dockerfile for Cloud Run deployment

Refs #3879

Python 3.13-slim base; uv installs PEP 723 inline deps at container start.
Exposes 8080 (Cloud Run default). Tested locally with TRANSPORT=http.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 9: Create `src/cube/mcp/CLAUDE.md`

**Files:**

- Create: `src/cube/mcp/CLAUDE.md`

- [ ] **Step 1: Present the proposed CLAUDE.md content to the user**

CLAUDE.md edits require user approval. Show the user this proposed content:

````markdown
# CLAUDE.md — `src/cube/mcp/`

Custom MCP server wrapping Cube Cloud's REST API. Deployed to Cloud Run
(`teamster-mcp` project) and reached by `claude.ai` Custom Connectors and by
data-team Codespaces via `npx mcp-remote`.

## Files

- `server.py` — FastMCP server (PEP 723 inline deps). Tools: `meta`, `load`,
  `sql`, `set_user_email`.
- `Dockerfile` — Python 3.13-slim, `uv run` entrypoint.

## Transport modes

- `TRANSPORT=stdio` (default) — for dev iteration via
  `scripts/cube-rest-mcp-launch.sh`. Email resolution: env var → cache → elicit.
- `TRANSPORT=http` — Cloud Run runtime. Email resolution: verified OAuth claim
  from the bearer token validated against WorkOS AuthKit JWKS.

## When to edit

- Tool descriptions or `instructions=`: edit `server.py`; redeploy is required
  for changes to reach `claude.ai` users.
- Tool surface changes (add/remove tools): edit `server.py` + add tests in
  `tests/cube/test_mcp_server.py`.
- Container changes (Python version, system deps): edit `Dockerfile`.

## Local testing

```bash
# Stdio mode (uses CUBE_USER_EMAIL):
CUBE_USER_EMAIL=you@apps.teamschools.org \
  CUBE_API_SECRET="$(op read 'op://Data Team/Cube Cloud REST API/credential')" \
  CUBE_REST_URL="https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1" \
  uv run src/cube/mcp/server.py

# HTTP mode (no OAuth — for protocol smoke testing only):
docker build -t cube-mcp-local:dev -f src/cube/mcp/Dockerfile src/cube/mcp/
docker run --rm -p 8080:8080 -e TRANSPORT=http ... cube-mcp-local:dev
```

## Deploy

GitHub Actions workflow `.github/workflows/deploy-cube-mcp.yaml` builds and
deploys on push to `main` when `src/cube/mcp/**` changes. Target project:
`teamster-mcp`. Secrets: `cube-api-secret` in Secret Manager.

## PII reminder

Tools return Cube query results. `*_detail` views carry row-level student
identifiers (per the FastMCP `instructions=` block in `server.py`). Never emit
detail-view values to PR comments, issues, or scheduled-agent outputs — only to
the local conversation. See project CLAUDE.md PII reference.
````

- [ ] **Step 2: Apply the approved content**

Use the Write tool to create `src/cube/mcp/CLAUDE.md` with the approved content.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add src/cube/mcp/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "docs(claude-md): add cube MCP service guidance

Refs #3879

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 6: External infrastructure setup

Phases 6 and 7 are **manual / external** — they happen in vendor consoles and
via `gcloud`, not in the repo. Pause execution to coordinate with the user; mark
each step done only after verifying the expected output.

### Task 10: Provision the `teamster-mcp` GCP project

**Prerequisite:** `gcloud` authenticated as a user with project-creation
permission in the org.

- [ ] **Step 1: Create the project and link billing**

```bash
gcloud projects create teamster-mcp --name="Teamster MCP Services"
gcloud billing accounts list  # capture the BILLING_ACCOUNT_ID
gcloud beta billing projects link teamster-mcp \
  --billing-account=<BILLING_ACCOUNT_ID>
```

Expected: `Created project [teamster-mcp].` and `billingEnabled: true`.

- [ ] **Step 2: Enable required APIs**

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  --project=teamster-mcp
```

Expected: each API listed as `Enabled`.

- [ ] **Step 3: Create the Artifact Registry repo**

```bash
gcloud artifacts repositories create cube-mcp \
  --repository-format=docker \
  --location=us-central1 \
  --project=teamster-mcp
```

Expected: `Created repository [cube-mcp].`

- [ ] **Step 4: Create the Cloud Run runtime service account**

```bash
gcloud iam service-accounts create cube-mcp-runtime \
  --display-name="Cube MCP Cloud Run runtime" \
  --project=teamster-mcp
```

Expected: `Created service account [cube-mcp-runtime].`

- [ ] **Step 5: Store the Cube signing secret in Secret Manager**

```bash
gcloud secrets create cube-api-secret \
  --replication-policy=automatic \
  --project=teamster-mcp

# In a terminal where 1Password is available:
op read 'op://Data Team/Cube Cloud REST API/credential' \
  | gcloud secrets versions add cube-api-secret \
    --data-file=- --project=teamster-mcp

gcloud secrets add-iam-policy-binding cube-api-secret \
  --member="serviceAccount:cube-mcp-runtime@teamster-mcp.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=teamster-mcp
```

Expected: secret `cube-api-secret` exists with one version; the runtime SA
appears in the IAM policy with `roles/secretmanager.secretAccessor`.

### Task 11: Cross-project IAM for the GitHub Actions deploy SA

- [ ] **Step 1: Identify the existing deploy SA**

Open `.github/workflows/dagster-cloud-deploy.yaml` and read the
`google-github-actions/auth@v3` block. The `workload_identity_provider`
references the WIF pool in `teamster-332318`. Identify the service account that
GH Actions impersonates via `vars.GCP_PROJECT_ID` / WIF (likely
`github-actions@teamster-332318.iam.gserviceaccount.com` or similar — check the
GCP console under IAM → service accounts).

- [ ] **Step 2: Grant cross-project IAM bindings**

Replace `<DEPLOY_SA>` with the SA identified above:

```bash
gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding teamster-mcp \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

Also bind the deploy SA to act-as the runtime SA so it can deploy services that
run as `cube-mcp-runtime`:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  cube-mcp-runtime@teamster-mcp.iam.gserviceaccount.com \
  --member="serviceAccount:<DEPLOY_SA>@teamster-332318.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" \
  --project=teamster-mcp
```

Expected: each command prints the updated IAM policy.

### Task 12: WorkOS AuthKit tenant

- [ ] **Step 1: Sign up at workos.com using a data-team `@apps.teamschools.org`
      account**

Create the WorkOS account. Capture the AuthKit domain (e.g.,
`teamster.authkit.app` or a custom subdomain) — this will be the
`AUTHKIT_DOMAIN` env var in Cloud Run.

- [ ] **Step 2: Configure the Google OIDC connection**

In the WorkOS dashboard → Authentication → Connections, add Google as an OIDC
provider. Configure:

- OAuth client ID + secret from a GCP OAuth Web Application credential (create
  in `teamster-mcp` project → APIs & Services → Credentials → OAuth client ID;
  add the WorkOS callback URL as an authorized redirect URI per the WorkOS setup
  wizard).
- Domain restriction: limit sign-ins to `apps.teamschools.org` (via Google's
  `hd` parameter, set in the connection's advanced settings or per WorkOS
  guidance).

Expected: a test sign-in with a `@apps.teamschools.org` account succeeds; a
personal Gmail sign-in is rejected.

- [ ] **Step 3: Enable Dynamic Client Registration**

In the WorkOS dashboard → Authentication → MCP / Dynamic Client Registration
(exact location varies — consult the WorkOS MCP guide:
<https://workos.com/docs/authkit/mcp>). Enable DCR for the tenant.

Expected: DCR endpoint advertised at the tenant's
`/.well-known/oauth-authorization-server` document.

- [ ] **Step 4: Configure token lifetimes**

Set access-token lifetime to 1 hour and refresh-token lifetime to 30 days in the
tenant's session settings.

- [ ] **Step 5: Capture configuration for the spec**

Record the final `AUTHKIT_DOMAIN` value. It'll be passed to Cloud Run as an env
var in Task 13.

---

## Phase 7: First Cloud Run deploy (manual)

### Task 13: Build, push, and deploy the image manually

This is a manual end-to-end smoke deploy before wiring up GH Actions.
Establishes that everything works once before automating it.

- [ ] **Step 1: Authenticate `gcloud` and configure Docker**

```bash
gcloud auth login  # if not already authenticated
gcloud auth configure-docker us-central1-docker.pkg.dev
```

- [ ] **Step 2: Build and push the image**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
SHA=$(git rev-parse --short HEAD)
IMAGE="us-central1-docker.pkg.dev/teamster-mcp/cube-mcp/cube-mcp:${SHA}"
docker build -t "$IMAGE" -f src/cube/mcp/Dockerfile src/cube/mcp/
docker push "$IMAGE"
```

Expected: image push completes.

- [ ] **Step 3: Deploy to Cloud Run**

```bash
gcloud run deploy cube-mcp \
  --image="$IMAGE" \
  --project=teamster-mcp \
  --region=us-central1 \
  --service-account=cube-mcp-runtime@teamster-mcp.iam.gserviceaccount.com \
  --port=8080 \
  --min-instances=0 \
  --max-instances=10 \
  --memory=256Mi \
  --cpu=0.25 \
  --ingress=all \
  --allow-unauthenticated \
  --set-env-vars="TRANSPORT=http,CUBE_REST_URL=https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1,AUTHKIT_DOMAIN=<your-authkit-domain>" \
  --set-secrets="CUBE_API_SECRET=cube-api-secret:latest"
```

(`--allow-unauthenticated` here means Cloud Run's IAM layer is open; the **MCP
layer's OAuth middleware is the actual access boundary**. Without
`--allow-unauthenticated`, Claude.ai can't reach the service at all.)

Expected: a Cloud Run service URL like
`https://cube-mcp-<hash>.us-central1.run.app`.

- [ ] **Step 4: Smoke-test the OAuth metadata endpoint**

```bash
SERVICE_URL="https://cube-mcp-<hash>.us-central1.run.app"
curl -s "${SERVICE_URL}/.well-known/oauth-protected-resource" | jq .
```

Expected: a JSON response per RFC 9728 pointing at the WorkOS AuthKit
authorization server (`authorization_servers: ["https://<AUTHKIT_DOMAIN>"]`).

- [ ] **Step 5: Smoke-test that unauthenticated MCP requests are rejected**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "${SERVICE_URL}/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: `401`. If `200`, the OAuth middleware isn't wired in correctly —
revisit Task 5.

---

## Phase 8: GitHub Actions deploy workflow

### Task 14: Author the deploy workflow

**Files:**

- Create: `.github/workflows/deploy-cube-mcp.yaml`

- [ ] **Step 1: Create the workflow file**

```yaml
# uses:
# https://github.com/actions/checkout
# https://github.com/docker/build-push-action
# https://github.com/docker/setup-buildx-action
# https://github.com/google-github-actions/auth
# https://github.com/google-github-actions/setup-gcloud

name: Cube MCP Cloud Run Deployment

on:
  push:
    branches:
      - main
    paths:
      - src/cube/mcp/**
      - .github/workflows/deploy-cube-mcp.yaml

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  GCP_PROJECT_ID: teamster-mcp
  GCP_REGION: us-central1
  SERVICE_NAME: cube-mcp
  REGISTRY_IMAGE: us-central1-docker.pkg.dev/teamster-mcp/cube-mcp/cube-mcp

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    if: github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Authenticate to Google Cloud
        id: auth
        uses: google-github-actions/auth@v3
        with:
          project_id: ${{ env.GCP_PROJECT_ID }}
          workload_identity_provider: |
            projects/${{ vars.GCP_PROJECT_NUMBER }}/locations/global/workloadIdentityPools/github/providers/teamster

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v3

      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker ${{ env.GCP_REGION }}-docker.pkg.dev

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: src/cube/mcp
          file: src/cube/mcp/Dockerfile
          push: true
          tags: ${{ env.REGISTRY_IMAGE }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE_NAME }} \
            --image=${{ env.REGISTRY_IMAGE }}:${{ github.sha }} \
            --project=${{ env.GCP_PROJECT_ID }} \
            --region=${{ env.GCP_REGION }} \
            --service-account=cube-mcp-runtime@${{ env.GCP_PROJECT_ID }}.iam.gserviceaccount.com \
            --port=8080 \
            --min-instances=0 \
            --max-instances=10 \
            --memory=256Mi \
            --cpu=0.25 \
            --ingress=all \
            --allow-unauthenticated \
            --set-env-vars=TRANSPORT=http,CUBE_REST_URL=${{ vars.CUBE_REST_URL }},AUTHKIT_DOMAIN=${{ vars.AUTHKIT_DOMAIN }} \
            --set-secrets=CUBE_API_SECRET=cube-api-secret:latest
```

- [ ] **Step 2: Add repository variables**

In GitHub repo → Settings → Variables → Actions, add:

- `CUBE_REST_URL` =
  `https://safe-hollsopple.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`
- `AUTHKIT_DOMAIN` = `<from Task 12 Step 5>`

`GCP_PROJECT_NUMBER` likely already exists for the Dagster deploy workflow;
verify it's set to the project number of `teamster-332318` (where the WIF pool
lives).

- [ ] **Step 3: Commit and merge to trigger a deploy**

Manual verification happens on the first PR merge after this workflow lands.

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add .github/workflows/deploy-cube-mcp.yaml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "ci(cube-mcp): add Cloud Run deploy workflow

Refs #3879

Triggered on push to main when src/cube/mcp/** changes. Builds the
image, pushes to Artifact Registry in teamster-mcp, deploys to Cloud Run
with the runtime SA and Secret Manager reference for CUBE_API_SECRET.
Reuses the existing WIF pool in teamster-332318 via cross-project IAM.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 9: Director-facing docs page

### Task 15: Author the connector setup guide

**Files:**

- Create: `docs/guides/claude-cube-connector.md`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Create the docs page**

Create `docs/guides/claude-cube-connector.md`:

```markdown
# Claude + Cube Connector

This guide walks through connecting your Claude account to the KIPP TEAM &
Family Cube data layer. Once connected, you can ask Claude questions about
attendance, enrollment, grades, and other school metrics directly from
`claude.ai`.

You'll need a `@apps.teamschools.org` Google Workspace account.

## One-time setup

1. Open <https://claude.ai>.
2. In the tools menu (bottom of the chat input), find the **Cube** connector.
3. Click **Connect**. A new browser tab opens.
4. Click **Sign in with Google**.
5. Pick your `@apps.teamschools.org` account.
6. Click **Allow** on the consent screen.
7. The browser returns you to `claude.ai`. The Cube connector now shows
   **Connected**.

That's it. Future sessions reuse this connection silently.

## Asking questions

In a new chat, try:

- "What's network-wide attendance for the last 30 days?"
- "Which schools have the highest enrollment this year?"
- "Show me the absence rate trend over the past three months."

Claude will pick the right Cube tool, run the query under your identity, and
return the answer.

## Troubleshooting

**"Access denied" or empty results** — your account isn't in a `cube-*`
Workspace group with the right permissions. Email the data team to be added.

**"Disconnected" status** — your session has expired. Click **Connect** again
and re-sign-in.

**Wrong account picked at sign-in** — sign out of the other Google account in
that browser tab, then retry the Connect flow.

## Privacy note

Aggregate data (school-level, network-level, grade-level totals) is fine to
share. **Row-level student details should never be copied into emails,
documents, or shared chats** — Claude can show them to you in conversation, but
they're not for redistribution. If you're not sure, ask aggregate-only questions
(use words like "average", "total", "rate").
```

- [ ] **Step 2: Add the page to `mkdocs.yml` nav**

Edit `mkdocs.yml` — under the `Guides` section, after the existing `Cube` entry:

```yaml
- Cube: guides/cube.md
- Claude + Cube Connector: guides/claude-cube-connector.md
```

- [ ] **Step 3: Verify the docs build locally**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy
uv run --with mkdocs --with mkdocs-material mkdocs build --strict
```

Expected: `Documentation built in ...` with no warnings or errors.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add docs/guides/claude-cube-connector.md mkdocs.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "docs(cube-connector): director-facing setup guide

Refs #3879

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 10: Claude.ai Custom Connector + smoke tests

### Task 16: Register the Custom Connector at the workspace level

Manual — performed by a Claude.ai workspace admin.

- [ ] **Step 1: Open the workspace connector settings**

`claude.ai` → Settings → Connectors → Add custom connector.

- [ ] **Step 2: Paste the Cloud Run URL**

Enter the service URL from Task 13 with `/mcp` appended (e.g.,
`https://cube-mcp-<hash>.us-central1.run.app/mcp`).

- [ ] **Step 3: Verify Claude.ai discovers the OAuth metadata**

Expected: claude.ai shows "Connector requires authentication" and offers the
OAuth Connect flow rather than rejecting the URL.

- [ ] **Step 4: Complete the OAuth flow once as a data-team member**

Click **Connect**, sign in with your `@apps.teamschools.org` account, allow,
return to claude.ai. Status should read **Connected**.

- [ ] **Step 5: Ask a smoke-test query**

In a new chat, ask "Use the cube tool to list available views." Expected: Claude
calls `meta`, receives the catalog scoped to your `cube-*` group memberships,
and lists views. If the tool returns empty or `WHERE 1=0`, your account isn't in
any `cube-*` group — fix that before declaring success.

### Task 17: Director-account smoke test

- [ ] **Step 1: Pick one director with `cube-*` group access**

Coordinate with the user to identify a director who has at least one `cube-*`
group membership and willingness to test.

- [ ] **Step 2: Walk them through the
      [docs/guides/claude-cube-connector.md](../../guides/claude-cube-connector.md)
      flow**

Confirm:

- Connect button visible in their `claude.ai` tools menu.
- Google sign-in completes with their `@apps.teamschools.org` account.
- Status reads **Connected**.
- A test query (e.g., "what's our network attendance rate this month?") returns
  data, not an "access denied" or empty result.

- [ ] **Step 3: Update the issue with the smoke-test result**

Post a comment on issue #3879 confirming the director-side smoke test passed or
noting any issues found. Do not include PII in the comment — use generic
placeholders if any director identifying info would be referenced.

---

## Phase 11: Data-team Codespace migration

### Task 18: Smoke-test `mcp-remote` in a single engineer's Codespace

This is the gating step before rolling out to the rest of the data team.

- [ ] **Step 1: Pick one engineer**

Coordinate with the user. The engineer should be comfortable rolling back to the
stdio path if anything breaks.

- [ ] **Step 2: Switch their `.mcp.json` `cube` entry**

In the engineer's Codespace `.mcp.json`, replace the existing `cube` entry:

```json
{
  "mcpServers": {
    "cube": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://cube-mcp-<hash>.us-central1.run.app/mcp"
      ]
    }
  }
}
```

- [ ] **Step 3: Restart Claude Code MCP servers**

In the VS Code Claude Code extension, run the `/mcp` command and reconnect. The
first connection will open a browser tab for OAuth.

- [ ] **Step 4: Complete the OAuth flow**

Sign in with Google → consent → tab returns. The MCP server should now show as
connected in the extension.

- [ ] **Step 5: Run a test query through Claude Code**

Ask Claude "Use the cube MCP to list available views." Confirm it returns the
expected catalog scoped to the engineer's `cube-*` groups.

- [ ] **Step 6: If smoke test passes, document the new path in the project
      CLAUDE.md**

If the smoke test fails (OAuth callback flow broken in Codespaces, or any other
blocker), file an issue against `mcp-remote` or the Claude Code extension
upstream and revert the engineer's `.mcp.json` to the stdio launcher. The Cloud
Run service remains live for directors.

### Task 19: Update project CLAUDE.md MCP tool selection

**Files:**

- Modify: `CLAUDE.md` (project root)

- [ ] **Step 1: Present the proposed CLAUDE.md edit to the user**

Show the user this replacement for the `cube` MCP user-email-seeding section
(currently in `CLAUDE.md` around line "**`cube` MCP user email seeding**"):

```markdown
**`cube` MCP path**: The `cube` MCP is served from Cloud Run (`teamster-mcp`
project) and reached via `npx mcp-remote` per the data-team `.mcp.json` entry.
OAuth identity is verified by WorkOS AuthKit federating to Google Workspace; no
`CUBE_USER_EMAIL` env var or `set_user_email` tool call needed.

Stdio dev mode (`scripts/cube-rest-mcp-launch.sh`) is retained for iterating on
`src/cube/mcp/server.py` itself. In dev mode the original user-email resolution
applies: `CUBE_USER_EMAIL` env var → `~/.config/teamster/cube-user-email` cache
→ `ctx.elicit()` prompt → `set_user_email` tool. The VS Code extension swallows
elicit prompts, so in dev mode call `set_user_email` with the `# userEmail`
system context value when prompted.
```

- [ ] **Step 2: Apply the approved edit**

Use the Edit tool.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add CLAUDE.md
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "docs(claude-md): default cube MCP to Cloud Run via mcp-remote

Refs #3879

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 20: Roll out the `.mcp.json` switch to the rest of the data team

- [ ] **Step 1: Update the canonical `.mcp.json` in the repo**

Edit `.mcp.json` at the repo root — replace the existing `cube` entry with the
`mcp-remote` form from Task 18 Step 2. Other entries (`bigquery`, `dagster`,
`dbt`, etc.) are untouched.

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy add .mcp.json
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy commit -m "chore(mcp): switch cube MCP to Cloud Run via mcp-remote

Refs #3879

Closes the dogfooding loop — data team uses the same OAuth-backed path
as directors. Stdio dev mode via scripts/cube-rest-mcp-launch.sh remains
available for iterating on the MCP server itself.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: Announce to the data team in Slack / standup**

Notify engineers that:

1. Rebuild your Codespace (or restart Claude Code MCP) to pick up the new
   `.mcp.json` entry.
2. The first cube query will trigger a one-time OAuth Connect flow.
3. The stdio launcher remains available for editing the MCP server.

(Coordinate this notification with the user — they own the channel.)

---

## Phase 12: PR and merge

### Task 21: Open the PR

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-mcp-remote-deploy push -u origin cristinabaldor/feat/claude-cube-mcp-remote-deploy
```

- [ ] **Step 2: Open the PR using the template**

```bash
gh pr create --title "feat(cube): deploy MCP server to Cloud Run with per-user OAuth" \
  --body "$(cat <<'EOF'
## Summary

Closes #3879. Deploys `scripts/cube_rest_mcp.py` (relocated to `src/cube/mcp/server.py`) as a Cloud Run service with per-user Google Workspace OAuth via WorkOS AuthKit. Directors connect via Claude.ai Custom Connectors; the data team connects via `npx mcp-remote` from Codespaces.

See [the design spec](docs/superpowers/specs/2026-05-11-cube-mcp-remote-deploy-design.md) for the architecture decisions and rationale.

## Test plan

- [ ] `uv run pytest tests/cube/ -v` passes (transport routing, OAuth wiring, email resolution)
- [ ] `docker build -f src/cube/mcp/Dockerfile src/cube/mcp/` succeeds locally
- [ ] Manual Cloud Run deploy reachable; `/.well-known/oauth-protected-resource` returns RFC 9728 JSON
- [ ] Unauthenticated `/mcp` POST returns HTTP 401
- [ ] Director smoke test on Claude.ai completes successfully (Task 17)
- [ ] One data-team engineer's Codespace successfully uses `mcp-remote` end to end (Task 18)
- [ ] `uv run --with mkdocs --with mkdocs-material mkdocs build --strict` succeeds (docs page renders)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL returned. Capture and share with the user.

- [ ] **Step 3: Verify CI passes**

Watch the PR's CI checks. The new `deploy-cube-mcp.yaml` workflow only fires on
`push` to `main`, so it won't run on the PR — the merge itself triggers it.
Standard PR checks (trunk, etc.) should pass.

- [ ] **Step 4: Squash-merge once approved**

After review approval and director smoke-test success, squash-merge per project
conventions. The deploy workflow runs on merge and replaces the manual deploy
from Task 13.

---

## Self-review checklist (for the engineer)

After completing all tasks, run through:

- [ ] `uv run pytest tests/cube/ -v` — all tests pass
- [ ] `docker build -f src/cube/mcp/Dockerfile src/cube/mcp/` succeeds
- [ ] `uv run --with mkdocs --with mkdocs-material mkdocs build --strict`
      succeeds
- [ ] `git -C <worktree> diff main --stat` matches the File Structure section
      above
- [ ] No PII in the PR body, commit messages, or `.mcp.json` (just the Cloud Run
      URL)
- [ ] All CLAUDE.md edits were presented to the user before applying
- [ ] Director smoke test (Task 17) and data-team smoke test (Task 18) both
      passed
- [ ] Issue #3879 closed via PR merge
