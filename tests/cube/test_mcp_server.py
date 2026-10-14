from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

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
    assert called_with["kwargs"] == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 8080,
        "stateless_http": True,
    }


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


def test_main_raises_in_http_mode_when_AUTHKIT_DOMAIN_set_but_PUBLIC_URL_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.setenv("TRANSPORT", "http")
    server = _load_server(monkeypatch)
    with pytest.raises(RuntimeError, match="PUBLIC_URL"):
        server.main()


def test_main_raises_on_unknown_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    monkeypatch.setenv("TRANSPORT", "htp")
    with pytest.raises(RuntimeError, match="TRANSPORT must be one of"):
        server.main()


def test_jwks_verifier_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)
    verifier = server.JWKSTokenVerifier("kipp.authkit.app")
    result = asyncio.run(verifier.verify_token("not-a-jwt"))
    assert result is None


def test_get_user_email_reads_oauth_token_in_http_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)

    access_token = server.CubeAccessToken(
        token="x",
        client_id="director@apps.teamschools.org",
        scopes=[],
        email="director@apps.teamschools.org",
    )
    monkeypatch.setattr(server, "get_access_token", lambda: access_token)

    ctx = MagicMock()
    email = asyncio.run(server._get_user_email(ctx))
    assert email == "director@apps.teamschools.org"


def test_get_user_email_raises_in_http_mode_when_oauth_user_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTHKIT_DOMAIN", "kipp.authkit.app")
    monkeypatch.setenv("PUBLIC_URL", "https://cube-mcp.example.run.app")
    server = _load_server(monkeypatch)

    monkeypatch.setattr(server, "get_access_token", lambda: None)
    ctx = MagicMock()

    with pytest.raises(server.MissingUserEmailError):
        asyncio.run(server._get_user_email(ctx))


def test_get_user_email_falls_through_to_env_var_in_stdio_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)

    ctx = MagicMock()
    email = asyncio.run(server._get_user_email(ctx))
    assert email == "engineer@apps.teamschools.org"


def test_mint_token_puts_email_at_top_level_of_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jwt

    server = _load_server(monkeypatch)
    # CUBE_API_SECRET is bound at module import time; patch the module attribute
    # directly so _mint_token and jwt.decode use the same key.
    secret = server.CUBE_API_SECRET
    token = server._mint_token("director@apps.teamschools.org")
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    # Cube's contextToGroups reads the top-level `email` claim per
    # src/cube/cube.js — do not nest under `securityContext` / `u` / etc.
    assert decoded["email"] == "director@apps.teamschools.org"


def test_mint_token_reuses_cached_token_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    server._token_cache.clear()
    first = server._mint_token("director@apps.teamschools.org")
    second = server._mint_token("director@apps.teamschools.org")
    assert first == second
    # Different email → different token, cache keyed by email.
    other = server._mint_token("teacher@apps.teamschools.org")
    assert other != first


def test_meta_cache_corruption_deletes_cache_file_and_refetches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)

    # Point the meta cache at an isolated tmp dir.
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)
    cache_path = server._meta_cache_path("engineer@apps.teamschools.org", "all")
    cache_path.write_text("not-json-at-all", encoding="utf-8")
    assert cache_path.exists()

    # Stub _request so we don't actually hit Cube.
    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs  # signature matches _request; values unused
        return {"cubes": []}

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    result = asyncio.run(server.meta(ctx))

    assert result["cubes"] == []
    # Fresh cache was written (replacing the corrupt one).
    assert cache_path.exists()
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["payload"] == {"cubes": []}


def test_meta_in_memory_cache_skips_disk_read_on_repeat_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    call_count = 0

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        nonlocal call_count
        call_count += 1
        return {"cubes": [{"name": "x"}]}

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    first = asyncio.run(server.meta(ctx))
    second = asyncio.run(server.meta(ctx))
    assert first["cubes"] == second["cubes"] == [{"name": "x"}]
    # Cold call hit /meta once; second call served from memory.
    assert call_count == 1
    # Delete disk cache to prove the second hit didn't read from disk.
    server._meta_cache_path("engineer@apps.teamschools.org", "all").unlink()
    third = asyncio.run(server.meta(ctx))
    assert third["cubes"] == [{"name": "x"}]
    assert call_count == 1


def test_meta_scoped_call_filters_full_catalog_client_side(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    calls: list[tuple[str, str]] = []

    async def fake_request(method: str, path: str, *, email: str) -> dict[str, Any]:
        del email
        calls.append((method, path))
        return {
            "cubes": [
                {"name": "student_attendance_view", "measures": []},
                {"name": "staff_directory", "measures": []},
            ]
        }

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    result = asyncio.run(server.meta(ctx, views=["student_attendance_view"]))

    # No /entities endpoint — Cube's REST API only exposes filtering via a
    # differently-scoped token this server doesn't mint (verified live: it
    # 403s "Required scope is missing" against our JWT). Filter the one
    # working /meta fetch client-side instead.
    assert calls == [("GET", "/meta")]
    assert result["cubes"] == [{"name": "student_attendance_view", "measures": []}]


def test_meta_scoped_and_full_catalog_calls_cache_separately(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    call_count = 0

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        nonlocal call_count
        call_count += 1
        return {
            "cubes": [
                {"name": "student_attendance_view", "measures": []},
                {"name": "staff_directory", "measures": []},
            ]
        }

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    full = asyncio.run(server.meta(ctx))
    scoped = asyncio.run(server.meta(ctx, views=["student_attendance_view"]))

    # Distinct cache entries — the filtered result didn't overwrite (or read
    # from) the full-catalog cache entry, or vice versa.
    assert full != scoped
    assert len(full["cubes"]) == 2
    assert len(scoped["cubes"]) == 1
    # One network call for the full catalog, reused (not refetched) to build
    # the filtered result.
    assert call_count == 1

    # Repeat calls hit cache, not the network, for each scope independently.
    asyncio.run(server.meta(ctx))
    asyncio.run(server.meta(ctx, views=["student_attendance_view"]))
    assert call_count == 1


def test_meta_scoped_call_with_multiple_views(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return {
            "cubes": [
                {"name": "student_attendance_view"},
                {"name": "staff_directory"},
                {"name": "staff_pii"},
            ]
        }

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    result = asyncio.run(
        server.meta(ctx, views=["student_attendance_view", "staff_pii"])
    )
    assert {c["name"] for c in result["cubes"]} == {
        "student_attendance_view",
        "staff_pii",
    }


def test_meta_scoped_call_for_unknown_view_returns_empty_cubes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return {"cubes": [{"name": "student_attendance_view"}]}

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    result = asyncio.run(server.meta(ctx, views=["does_not_exist"]))
    assert result["cubes"] == []


def test_meta_scoped_call_first_also_populates_full_catalog_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reverse of test_meta_scoped_and_full_catalog_calls_cache_separately: a
    cold scoped call must populate the full-catalog cache entry too, so a
    subsequent full call is served from cache rather than refetching."""
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    call_count = 0

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        nonlocal call_count
        call_count += 1
        return {
            "cubes": [
                {"name": "student_attendance_view", "measures": []},
                {"name": "staff_directory", "measures": []},
            ]
        }

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    scoped = asyncio.run(server.meta(ctx, views=["student_attendance_view"]))
    full = asyncio.run(server.meta(ctx))

    assert call_count == 1
    assert len(scoped["cubes"]) == 1
    assert len(full["cubes"]) == 2


def test_meta_force_refresh_on_scoped_call_refetches_full_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)

    call_count = 0

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        nonlocal call_count
        call_count += 1
        return {"cubes": [{"name": "student_attendance_view"}]}

    monkeypatch.setattr(server, "_request", fake_request)

    ctx = MagicMock()
    asyncio.run(server.meta(ctx, views=["student_attendance_view"], force_refresh=True))
    asyncio.run(server.meta(ctx, views=["student_attendance_view"], force_refresh=True))
    assert call_count == 2


def test_with_default_timezone_injects_utc_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {"measures": ["student_attendance_view.avg_daily_attendance"]}
    result = server._with_default_timezone(query)
    assert result["timezone"] == "UTC"
    # Original query object is not mutated.
    assert "timezone" not in query


def test_with_default_timezone_preserves_caller_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {"measures": ["x.count"], "timezone": "America/New_York"}
    assert server._with_default_timezone(query) is query


def test_load_and_sql_send_utc_timezone_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")

    sent: list[dict[str, Any]] = []

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args
        sent.append(dict(kwargs))
        return {"data": []}

    monkeypatch.setattr(server, "_request", fake_request)
    ctx = MagicMock()

    asyncio.run(server.load(ctx, {"measures": ["x.count"]}))
    assert sent[0]["json"]["query"]["timezone"] == "UTC"

    asyncio.run(server.sql(ctx, {"measures": ["x.count"]}))
    assert json.loads(sent[1]["params"]["query"])["timezone"] == "UTC"

    # Caller-provided timezone passes through untouched on both tools.
    asyncio.run(
        server.load(ctx, {"measures": ["x.count"], "timezone": "America/New_York"})
    )
    assert sent[2]["json"]["query"]["timezone"] == "America/New_York"


def test_clip_cuts_long_text_and_passes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._clip(None) is None
    assert server._clip("short") == "short"
    assert len(server._clip("x" * 20_000)) == server.CALL_RECORD_TEXT_LIMIT


def test_resolve_session_id_mints_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uuid

    server = _load_server(monkeypatch)
    for raw in (None, "", "   "):
        session_id, minted = server._resolve_session_id(raw)
        assert minted is True
        assert str(uuid.UUID(session_id)) == session_id


def test_resolve_session_id_reuses_and_normalizes_a_valid_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    canonical = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    for raw in (canonical, canonical.upper(), "{" + canonical + "}", f" {canonical} "):
        assert server._resolve_session_id(raw) == (canonical, False)


def test_resolve_session_id_replaces_a_non_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    session_id, minted = server._resolve_session_id("Student A's session")
    assert minted is True
    assert "Student" not in session_id


def test_members_referenced_walks_every_query_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["v.count_students"],
        "dimensions": ["v.school_name"],
        "segments": ["v.active"],
        "timeDimensions": [{"dimension": "v.dates_date_day", "granularity": "month"}],
        "filters": [
            {"member": "v.region", "operator": "equals", "values": ["Newark"]},
            {
                "or": [
                    {"member": "v.grade", "operator": "equals", "values": ["9"]},
                    {"and": [{"dimension": "v.is_iep", "operator": "set"}]},
                ]
            },
        ],
        "order": {"v.count_students": "desc"},
    }
    assert server._members_referenced(query) == [
        "v.active",
        "v.count_students",
        "v.dates_date_day",
        "v.grade",
        "v.is_iep",
        "v.region",
        "v.school_name",
    ]
    # Filter VALUES never appear: only member names.
    assert "Newark" not in server._members_referenced(query)


def test_members_referenced_accepts_list_form_order_and_skips_junk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["a.x", 7],
        "order": [["b.y", "asc"], "not-a-pair", []],
        "filters": ["not-a-dict"],
        "timeDimensions": [{"granularity": "day"}],
    }
    assert server._members_referenced(query) == ["a.x", "b.y"]
    assert server._members_referenced({}) == []


def test_views_referenced_takes_the_text_before_the_first_dot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._views_referenced(["b.y", "a.x", "a.z", "bare"]) == ["a", "b", "bare"]


def test_load_summary_reads_the_load_response_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    payload = {
        "data": [{"v.count": "1"}, {"v.count": "2"}],
        "external": True,
        "usedPreAggregations": {
            "prod_pre_aggregations.v_rollup_abc123": {
                "preAggregationId": "v.rollup",
                "targetTableName": "prod_pre_aggregations.v_rollup_abc123",
            }
        },
        "lastRefreshTime": "2026-10-08T03:00:00.000Z",
    }
    assert server._load_summary(payload) == {
        "external": True,
        "used_pre_aggregations": ["v.rollup"],
        "last_refresh_time": "2026-10-08T03:00:00.000Z",
        "row_count": 2,
    }


def test_load_summary_tolerates_missing_and_odd_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._load_summary({"data": []}) == {
        "external": None,
        "used_pre_aggregations": [],
        "last_refresh_time": None,
        "row_count": 0,
    }
    # An entry without preAggregationId falls back to its key.
    odd = {"data": [], "usedPreAggregations": {"some_table": "not-a-dict"}}
    assert server._load_summary(odd)["used_pre_aggregations"] == ["some_table"]
    assert (
        server._load_summary({"usedPreAggregations": []})["used_pre_aggregations"] == []
    )


def test_load_summary_combines_a_multi_query_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    payload = {
        "results": [
            {
                "data": [{"a": 1}],
                "external": True,
                "lastRefreshTime": "2026-10-08T03:00:00Z",
            },
            {
                "data": [{"a": 2}, {"a": 3}],
                "external": False,
                "lastRefreshTime": "2026-10-07T03:00:00Z",
            },
            "not-a-dict",
        ]
    }
    summary = server._load_summary(payload)
    assert summary["row_count"] == 3
    # Served by a pre-aggregation only if every part was.
    assert summary["external"] is False
    # The stalest refresh time: how old the oldest part of the answer is.
    assert summary["last_refresh_time"] == "2026-10-07T03:00:00Z"


CALL_RECORD_ENVELOPE = {"event", "severity"}


def _call_records(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    """Parse every call-record line the server wrote to stderr."""
    records = []
    for line in capsys.readouterr().err.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("event") == "cube_mcp_call":
            records.append(parsed)
    return records


def _stdio_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str
) -> ModuleType:
    """Load the server in stdio mode with an isolated meta cache and the
    call-record settings unset unless passed in `env`."""
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    for name in (
        "AUTHKIT_DOMAIN",
        "PUBLIC_URL",
        "CUBE_MCP_LOG_FREE_TEXT",
        "SERVER_SHA",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)
    return server


def _sample_record(server: ModuleType, **overrides: Any) -> Any:
    fields = {
        "tool": "load",
        "session_id": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
        "session_id_minted": False,
        "question": "How many students are enrolled?",
        "assumptions": "Current academic year",
        "query": {"measures": ["v.count_students"], "timezone": "UTC"},
        "email": "engineer@apps.teamschools.org",
        "result": {"data": [{"v.count_students": "5"}]},
    }
    fields.update(overrides)
    return server._CallRecord(**fields)


def test_row_keys_equal_the_allowlist_on_every_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    variants = [
        {},
        {"result": {"data": []}},
        {"result": None, "error": "boom"},
        {"tool": "meta", "query": None, "views": ["v"], "result": None},
        {"tool": "sql", "result": {"sql": {"sql": ["select 1", []]}}},
    ]
    for overrides in variants:
        row = _sample_record(server, **overrides).row()
        assert tuple(row) == server.CALL_RECORD_FIELDS


def test_row_outcome_and_load_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    ok = _sample_record(server).row()
    assert ok["outcome"] == "ok"
    assert ok["row_count"] == 1
    assert ok["members_referenced"] == ["v.count_students"]
    assert ok["views_referenced"] == ["v"]
    assert json.loads(ok["query_json"]) == {
        "measures": ["v.count_students"],
        "timezone": "UTC",
    }

    assert _sample_record(server, result={"data": []}).row()["outcome"] == "empty"

    error = _sample_record(server, result=None, error="Cube POST /load 400: bad").row()
    assert error["outcome"] == "error"
    assert error["error_message"] == "Cube POST /load 400: bad"


def test_row_leaves_load_fields_null_on_meta_and_sql(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    meta_row = _sample_record(
        server, tool="meta", query=None, views=["b", "a"], result={"cubes": []}
    ).row()
    assert meta_row["views_referenced"] == ["a", "b"]
    assert meta_row["members_referenced"] is None
    assert meta_row["query_json"] is None
    for key in ("external", "used_pre_aggregations", "last_refresh_time", "row_count"):
        assert meta_row[key] is None
    assert _sample_record(server, tool="sql").row()["row_count"] is None


def test_row_never_emits_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    row = _sample_record(server, tool="meta", query=None, views=None).row()
    assert row["views_referenced"] is None
    assert row["used_pre_aggregations"] is None
    assert not any(value == [] for value in row.values())


def test_row_drops_free_text_when_the_switch_is_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for env in (
        {},
        {"CUBE_MCP_LOG_FREE_TEXT": "false"},
        {"CUBE_MCP_LOG_FREE_TEXT": "yes"},
    ):
        server = _stdio_server(monkeypatch, tmp_path, **env)
        row = _sample_record(server, error="echoed filter value").row()
        assert row["question"] is None
        assert row["assumptions"] is None
        assert row["question_provided"] is True
        # Always logged, whatever the switch says.
        assert row["query_json"] is not None
        assert row["error_message"] == "echoed filter value"


def test_row_keeps_free_text_when_the_switch_is_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT=" TRUE ")
    row = _sample_record(server).row()
    assert row["question"] == "How many students are enrolled?"
    assert row["assumptions"] == "Current academic year"


def test_row_question_provided_ignores_blank_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    for question in (None, "", "   "):
        assert (
            _sample_record(server, question=question).row()["question_provided"]
            is False
        )


def test_row_clips_long_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT="true")
    huge = {
        "filters": [
            {
                "member": "v.student_number",
                "operator": "equals",
                "values": ["1" * 50_000],
            }
        ]
    }
    row = _sample_record(
        server, query=huge, question="q" * 50_000, error="e" * 50_000
    ).row()
    for key in ("query_json", "question", "error_message"):
        assert len(row[key]) == server.CALL_RECORD_TEXT_LIMIT
    assert len(json.dumps(row)) < 256_000


def test_server_sha_defaults_to_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    assert _sample_record(server).row()["server_sha"] == "local"
    server = _stdio_server(monkeypatch, tmp_path, SERVER_SHA="abc123")
    assert _sample_record(server).row()["server_sha"] == "abc123"


def test_emit_writes_one_json_line_with_the_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    server._emit_call_record(_sample_record(server))
    records = _call_records(capsys)
    assert len(records) == 1
    assert records[0]["severity"] == "INFO"
    assert set(records[0]) - CALL_RECORD_ENVELOPE == set(server.CALL_RECORD_FIELDS)


def test_emit_failure_does_not_break_the_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    record = _sample_record(server)

    def broken_row() -> dict[str, Any]:
        raise RuntimeError("serializer exploded")

    monkeypatch.setattr(record, "row", broken_row)
    server._emit_call_record(record)  # must not raise


def test_recorded_marks_errors_and_reraises_the_same_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    boom = ValueError("bad query")

    async def run() -> None:
        async with server._recorded(MagicMock(), "load", session_id=None, query={}):
            raise boom

    with pytest.raises(ValueError) as caught:
        asyncio.run(run())
    assert caught.value is boom
    [record] = _call_records(capsys)
    assert record["outcome"] == "error"
    assert record["error_message"] == "bad query"
    assert record["session_id_minted"] is True
    assert server._current_call.get() is None


def test_recorded_reads_the_client_user_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    ctx = MagicMock()
    ctx.headers = {"user-agent": "claude-ai/1.0"}

    async def run() -> None:
        async with server._recorded(ctx, "meta", session_id=None):
            pass

    asyncio.run(run())
    assert _call_records(capsys)[0]["client"] == "claude-ai/1.0"
    # A MagicMock ctx (no real headers) or stdio's None gives null, not junk.
    assert server._client_user_agent(MagicMock()) is None


class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self.status_code = 200
        self.text = json.dumps(body)
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeClient:
    """Stands in for the httpx client: returns `bodies` in order and keeps the
    headers of every request."""

    def __init__(self, bodies: list[dict[str, Any]]) -> None:
        self.bodies = list(bodies)
        self.sent_headers: list[dict[str, str]] = []

    async def request(
        self, method: str, path: str, *, headers: dict[str, str], **kwargs: Any
    ) -> _FakeResponse:
        del method, path, kwargs
        self.sent_headers.append(dict(headers))
        return _FakeResponse(self.bodies.pop(0))


def test_request_sends_the_call_id_on_every_poll(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    fake = _FakeClient(
        [{"error": "Continue wait"}, {"error": "Continue wait"}, {"data": []}]
    )
    monkeypatch.setattr(server, "client", fake)

    async def no_sleep(_seconds: float) -> None:
        return None

    # Replace the server module's `asyncio` name only, never the real
    # `asyncio.sleep` the test's own event loop uses.
    from types import SimpleNamespace

    monkeypatch.setattr(server, "asyncio", SimpleNamespace(sleep=no_sleep))

    async def run() -> None:
        async with server._recorded(
            MagicMock(), "load", session_id=None, query={}
        ) as record:
            record.result = await server._request(
                "POST",
                "/load",
                email="engineer@apps.teamschools.org",
                poll=True,
                json={},
            )

    asyncio.run(run())
    [logged] = _call_records(capsys)
    ids = {h["x-request-id"] for h in fake.sent_headers}
    assert len(fake.sent_headers) == 3
    assert ids == {logged["cube_request_id"]}
    assert isinstance(logged["latency_ms"], int)


def test_request_without_a_recorded_call_sends_no_request_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    fake = _FakeClient([{"data": []}])
    monkeypatch.setattr(server, "client", fake)
    asyncio.run(server._request("GET", "/meta", email="engineer@apps.teamschools.org"))
    assert "x-request-id" not in fake.sent_headers[0]


def _fake_cube(
    server: ModuleType, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]
) -> None:
    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return body

    monkeypatch.setattr(server, "_request", fake_request)


def test_each_tool_logs_one_allowlisted_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(
        server, monkeypatch, {"data": [{"v.count": "1"}], "cubes": [], "sql": {}}
    )
    ctx = MagicMock()
    asyncio.run(server.meta(ctx))
    asyncio.run(server.load(ctx, {"measures": ["v.count"]}))
    asyncio.run(server.sql(ctx, {"measures": ["v.count"]}))
    records = _call_records(capsys)
    assert [r["tool"] for r in records] == ["meta", "load", "sql"]
    for record in records:
        assert set(record) - CALL_RECORD_ENVELOPE == set(server.CALL_RECORD_FIELDS)
        assert record["outcome"] == "ok"
        assert record["email"] == "engineer@apps.teamschools.org"


def test_load_logs_empty_and_the_query_sent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": []})
    asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}))
    [record] = _call_records(capsys)
    assert record["outcome"] == "empty"
    assert record["row_count"] == 0
    # The logged query is the one sent, UTC default included.
    assert json.loads(record["query_json"])["timezone"] == "UTC"


def test_load_never_logs_response_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT="true")
    marker = "ROW-MARKER-7f3c"
    _fake_cube(
        server,
        monkeypatch,
        {"data": [{"v.full_name": marker}, {"v.full_name": marker}]},
    )
    asyncio.run(server.load(MagicMock(), {"dimensions": ["v.full_name"]}))
    err = capsys.readouterr().err
    assert marker not in err
    [record] = [
        json.loads(line) for line in err.splitlines() if "cube_mcp_call" in line
    ]
    assert record["row_count"] == 2


def test_tools_return_and_reuse_a_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [], "cubes": []})
    ctx = MagicMock()
    first = asyncio.run(server.meta(ctx))
    second = asyncio.run(
        server.load(ctx, {"measures": ["v.count"]}, session_id=first["session_id"])
    )
    assert second["session_id"] == first["session_id"]
    records = _call_records(capsys)
    assert [r["session_id_minted"] for r in records] == [True, False]
    assert records[0]["session_id"] == records[1]["session_id"]


def test_invalid_session_id_is_never_logged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": []})
    junk = "Student A asked about attendance"
    result = asyncio.run(
        server.load(MagicMock(), {"measures": ["v.count"]}, session_id=junk)
    )
    assert result["session_id"] != junk
    assert junk not in capsys.readouterr().err


def test_meta_cache_never_holds_a_session_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"cubes": [{"name": "v"}]})
    ctx = MagicMock()
    first = asyncio.run(server.meta(ctx))
    second = asyncio.run(server.meta(ctx, views=["v"]))
    third = asyncio.run(server.meta(ctx))
    assert len({first["session_id"], second["session_id"], third["session_id"]}) == 3
    for (_email, _scope), (_expires, payload) in server._meta_memory_cache.items():
        assert "session_id" not in payload
    for cache_file in tmp_path.glob("cube-meta-*.json"):
        assert (
            "session_id"
            not in json.loads(cache_file.read_text(encoding="utf-8"))["payload"]
        )


def test_question_and_assumptions_follow_the_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for switch, expect_text in (("false", False), ("true", True)):
        server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT=switch)
        _fake_cube(server, monkeypatch, {"data": []})
        asyncio.run(
            server.load(
                MagicMock(),
                {"measures": ["v.count"]},
                question="How many?",
                assumptions="This year",
            )
        )
        [record] = _call_records(capsys)
        assert record["question_provided"] is True
        assert (record["question"] == "How many?") is expect_text
        assert (record["assumptions"] == "This year") is expect_text


def test_error_before_email_is_recorded_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    missing = server.MissingUserEmailError("no email")

    async def no_email(_ctx: object) -> str:
        raise missing

    monkeypatch.setattr(server, "_get_user_email", no_email)
    with pytest.raises(server.MissingUserEmailError) as caught:
        asyncio.run(server.sql(MagicMock(), {"measures": ["v.count"]}))
    assert caught.value is missing
    [record] = _call_records(capsys)
    assert record["email"] is None
    assert record["outcome"] == "error"
    assert record["error_message"] == "no email"


def test_cube_error_is_recorded_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)

    async def failing_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        raise RuntimeError("Cube POST /load 400: Unknown member v.nope")

    monkeypatch.setattr(server, "_request", failing_request)
    with pytest.raises(RuntimeError, match="Unknown member"):
        asyncio.run(server.load(MagicMock(), {"measures": ["v.nope"]}))
    [record] = _call_records(capsys)
    assert record["outcome"] == "error"
    assert record["members_referenced"] == ["v.nope"]


def test_tool_returns_result_when_emit_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [{"v.count": "3"}]})

    def broken_print(*args: object, **kwargs: object) -> None:
        raise OSError("stderr closed")

    monkeypatch.setattr("builtins.print", broken_print)
    result = asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}))
    assert result["data"] == [{"v.count": "3"}]


def test_tool_schemas_expose_the_new_optional_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import inspect

    server = _load_server(monkeypatch)
    expected = {
        "meta": {"session_id"},
        "load": {"question", "session_id", "assumptions"},
        "sql": {"question", "session_id"},
    }
    for name, params in expected.items():
        signature = inspect.signature(getattr(server, name))
        for param in params:
            assert signature.parameters[param].default is None


def test_malformed_query_still_writes_its_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)

    async def failing_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        raise RuntimeError("Cube POST /load 400: bad query")

    monkeypatch.setattr(server, "_request", failing_request)
    for bad in (
        {"measures": 5},
        {"dimensions": True},
        {"timeDimensions": 1},
        {"measures": "v.x"},
    ):
        with pytest.raises(RuntimeError):
            asyncio.run(server.load(MagicMock(), bad))
        [record] = _call_records(capsys)
        assert record["outcome"] == "error"
        # A non-list member field is skipped, never iterated character by
        # character.
        assert record["members_referenced"] is None


def test_cancelled_call_logs_a_stable_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)

    async def run() -> None:
        async with server._recorded(MagicMock(), "load", session_id=None, query={}):
            raise asyncio.CancelledError("Cancelled by cancel scope 7f0011223344")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    [record] = _call_records(capsys)
    assert record["outcome"] == "error"
    assert record["error_message"] == "cancelled"
