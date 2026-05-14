from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "src" / "cube" / "mcp" / "server.py"


def _load_server(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load src/cube/mcp/server.py under sys.modules['cube_mcp_server'].

    The script reads CUBE_REST_URL and CUBE_API_SECRET at import time, so we
    set placeholders before exec_module. Always evicts any cached module first
    so monkeypatched env vars are re-read.
    """
    sys.modules.pop("cube_mcp_server", None)
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


def test_run_dispatches_to_stdio_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    monkeypatch.delenv("TRANSPORT", raising=False)
    called_with: dict[str, Any] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        called_with["args"] = args
        called_with["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()
    assert called_with == {"args": (), "kwargs": {}}
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 8080


def test_run_dispatches_to_streamable_http_when_TRANSPORT_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    monkeypatch.setenv("TRANSPORT", "http")
    called_with: dict[str, Any] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        called_with["args"] = args
        called_with["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()
    assert called_with["kwargs"] == {"transport": "streamable-http"}
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 8080


def test_oauth_disabled_when_AUTHKIT_DOMAIN_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    assert server.AUTHKIT_DOMAIN is None
    assert server.mcp.settings.auth is None


def test_oauth_configured_when_AUTHKIT_DOMAIN_and_PUBLIC_URL_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)
    assert server.AUTHKIT_DOMAIN == "kipp.authkit.app"
    settings = server.mcp.settings.auth
    assert settings is not None
    assert str(settings.issuer_url).rstrip("/") == "https://kipp.authkit.app"
    assert (
        str(settings.resource_server_url).rstrip("/")
        == "https://cube-mcp.example.run.app"
    )


def test_oauth_raises_when_AUTHKIT_DOMAIN_set_but_PUBLIC_URL_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    with pytest.raises(RuntimeError, match="PUBLIC_URL"):
        _load_server(monkeypatch)


def test_jwks_verifier_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)
    verifier = server.JWKSTokenVerifier("kipp.authkit.app")
    import asyncio

    result = asyncio.run(verifier.verify_token("not-a-jwt"))
    assert result is None


def test_get_user_email_reads_oauth_token_in_http_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from unittest.mock import MagicMock

    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)

    ctx = MagicMock()
    access_token = server.CubeAccessToken(
        token="x",
        client_id="director@apps.teamschools.org",
        scopes=[],
        email="director@apps.teamschools.org",
    )
    ctx.request_context.user.access_token = access_token

    email = asyncio.run(server._get_user_email(ctx))
    assert email == "director@apps.teamschools.org"


def test_get_user_email_raises_in_http_mode_when_oauth_user_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from unittest.mock import MagicMock

    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)

    ctx = MagicMock()
    # Simulate the MCP SDK not setting access_token (request not authenticated)
    ctx.request_context.user = None

    with pytest.raises(server.MissingUserEmailError):
        asyncio.run(server._get_user_email(ctx))


def test_get_user_email_falls_through_to_env_var_in_stdio_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from unittest.mock import MagicMock

    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)

    ctx = MagicMock()
    email = asyncio.run(server._get_user_email(ctx))
    assert email == "engineer@apps.teamschools.org"
