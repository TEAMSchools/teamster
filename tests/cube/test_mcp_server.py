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

sys.path.insert(0, str(SCRIPT_PATH.parent / "eval"))

# trunk-ignore(pyright/reportMissingImports): eval modules load from src/cube/mcp/eval via sys.path
import arms  # noqa: E402


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
    tools = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert tools == {
        "meta",
        "load",
        "sql",
        "dry_run",
        "cubesql",
        "convert_query",
        "graphql_to_json",
    }


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

    assert result == {"cubes": []}
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
    assert first == second == {"cubes": [{"name": "x"}]}
    # Cold call hit /meta once; second call served from memory.
    assert call_count == 1
    # Delete disk cache to prove the second hit didn't read from disk.
    server._meta_cache_path("engineer@apps.teamschools.org", "all").unlink()
    third = asyncio.run(server.meta(ctx))
    assert third == {"cubes": [{"name": "x"}]}
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


def _tool_descriptions(server: ModuleType) -> dict[str, str]:
    tools = asyncio.run(server.mcp.list_tools())
    return {t.name: " ".join((t.description or "").split()) for t in tools}


def test_load_and_meta_docstrings_carry_the_drained_mechanics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    desc = _tool_descriptions(server)
    for sentence in arms.NEW_LOAD_SENTENCES:
        assert sentence in desc["load"], sentence
    for sentence in arms.NEW_META_SENTENCES:
        assert sentence in desc["meta"], sentence


def test_empty_load_result_gets_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return {"data": [], "annotation": {}}

    monkeypatch.setattr(server, "_request", fake_request)
    out = asyncio.run(server.load(MagicMock(), {"measures": ["x.count"]}))
    assert out["note"] == server.EMPTY_RESULT_NOTE
    assert out["data"] == []
    # The check it asks for must be runnable when nothing came back.
    assert "re-run without the narrowing filter" in server.EMPTY_RESULT_NOTE

    async def null_row(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return {"data": [{"x.count": None}]}

    # load hands the query through, so the measure-only null row is caught.
    monkeypatch.setattr(server, "_request", null_row)
    out = asyncio.run(server.load(MagicMock(), {"measures": ["x.count"]}))
    assert out["note"] == server.EMPTY_RESULT_NOTE


def test_multi_query_results_get_the_note_per_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    payload = {"results": [{"data": []}, {"data": [{"x.count": "3"}]}]}
    out = server._with_empty_result_note(payload, {"measures": ["x.count"]})
    assert out["results"][0]["note"] == server.EMPTY_RESULT_NOTE
    assert "note" not in out["results"][1]
    assert "note" not in out


def test_measure_only_query_over_an_empty_slice_gets_the_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cube answers a measure-only query over an empty slice with 1 row of
    # nulls (verified live), or 0 for a plain count, not with `data: []`.
    server = _load_server(monkeypatch)
    query = {"measures": ["x.count_scored", "x.pct_proficient"]}
    nulls = {"data": [{"x.count_scored": None, "x.pct_proficient": None}]}
    assert server._with_empty_result_note(nulls, query)["note"] == (
        server.EMPTY_RESULT_NOTE
    )
    for zero in ("0", 0):
        zeros = {"data": [{"x.count_scored": zero, "x.pct_proficient": None}]}
        assert "note" in server._with_empty_result_note(zeros, query)
    # The same row under a time dimension with no grain is still ungrouped.
    dated = query | {"timeDimensions": [{"dimension": "x.date", "dateRange": "today"}]}
    assert "note" in server._with_empty_result_note(nulls, dated)


def test_non_empty_and_non_result_payloads_are_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {"measures": ["x.count"]}
    rows = {"data": [{"x.count": "3"}]}
    assert "note" not in server._with_empty_result_note(dict(rows), query)
    error = {"error": "Continue wait"}
    assert server._with_empty_result_note(dict(error), query) == error
    assert server._with_empty_result_note({"data": None}, query) == {"data": None}


def test_a_grouped_single_row_is_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    grouped = {"measures": ["x.count"], "dimensions": ["x.region"]}
    newark = {"data": [{"x.region": "Newark", "x.count": "0"}]}
    assert "note" not in server._with_empty_result_note(newark, grouped)
    # A real group whose dimension value is null: only the query tells it
    # apart from Cube's empty-slice row.
    unset = {"data": [{"x.region": None, "x.count": "0"}]}
    assert "note" not in server._with_empty_result_note(unset, grouped)
    by_month = {
        "measures": ["x.count"],
        "timeDimensions": [{"dimension": "x.date", "granularity": "month"}],
    }
    assert "note" not in server._with_empty_result_note(unset, by_month)
    # Two rows are never the empty-slice shape.
    two = {"data": [{"x.count": None}, {"x.count": None}]}
    assert "note" not in server._with_empty_result_note(two, {"measures": ["x.count"]})


def test_no_docstring_names_cube_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    texts = [
        server.__doc__,
        server.UserEmailPrompt.model_fields["email"].description,
    ]
    texts += [t.description for t in server.mcp._tool_manager.list_tools()]
    for text in texts:
        assert "cube-*" not in (text or "")


def test_load_docstring_lists_every_operator_and_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    doc = server.load.__doc__
    for op in [
        "equals",
        "notEquals",
        "contains",
        "notContains",
        "startsWith",
        "notStartsWith",
        "endsWith",
        "notEndsWith",
        "in",
        "notIn",
        "gt",
        "gte",
        "lt",
        "lte",
        "set",
        "notSet",
        "inDateRange",
        "notInDateRange",
        "onTheDate",
        "beforeDate",
        "beforeOrOnDate",
        "afterDate",
        "afterOrOnDate",
        "measureFilter",
    ]:
        assert f"`{op}`" in doc, op
    for field in [
        "ungrouped",
        "responseFormat",
        "cacheMode",
        "compareDateRange",
        "joinHints",
        "subqueryJoins",
        "maskedMembers",
        "usedPreAggregations",
    ]:
        assert field in doc, field


FIXTURES = Path(__file__).parent / "fixtures"


def _sql_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "cube_sql_response.json").read_text())


def _recording_request(
    monkeypatch: pytest.MonkeyPatch, server: ModuleType, reply: Any
) -> list[tuple[str, str, dict[str, Any]]]:
    """Replace server._request with a fake that records (method, path, kwargs)
    and returns `reply` (or `reply.pop(0)` when it is a list of replies)."""
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        return reply.pop(0) if isinstance(reply, list) else reply

    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.setattr(server, "_request", fake_request)
    return calls


def test_trim_sql_is_small_and_keeps_sql_and_preaggs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    raw = _sql_fixture()
    trimmed = server._trim_sql(raw)
    assert len(json.dumps(raw)) > 40_000
    assert len(json.dumps(trimmed)) < 5_000
    assert trimmed["sql"] == raw["sql"]["sql"]
    assert trimmed["external"] == raw["sql"]["external"]
    assert trimmed["preAggregations"] == [
        p["preAggregationId"] for p in raw["sql"]["preAggregations"]
    ]
    assert "canUseTransformedQuery" not in json.dumps(trimmed)


def test_trim_sql_without_preaggregations(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    trimmed = server._trim_sql({"sql": {"sql": ["SELECT 1", []]}})
    assert trimmed["preAggregations"] == []


def test_sql_posts_object_query_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    fixture = _sql_fixture()
    calls = _recording_request(monkeypatch, server, fixture)
    ctx = MagicMock()

    result = asyncio.run(server.sql(ctx, {"measures": ["x.count"]}))
    method, path, kwargs = calls[0]
    # GET, the method the deployed tool has always used against Cube Cloud.
    assert (method, path) == ("GET", "/sql")
    assert json.loads(kwargs["params"]["query"]) == {
        "measures": ["x.count"],
        "timezone": "UTC",
    }
    assert result == server._trim_sql(fixture)

    assert asyncio.run(server.sql(ctx, {"measures": ["x.count"]}, full=True)) == fixture


def test_sql_posts_sql_string_with_format_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    reply = {"sql": {"sql": "SELECT 1"}}
    calls = _recording_request(monkeypatch, server, reply)

    result = asyncio.run(server.sql(MagicMock(), "SELECT MEASURE(x.count) FROM x"))
    method, path, kwargs = calls[0]
    assert (method, path) == ("GET", "/sql")
    assert kwargs["params"] == {
        "query": "SELECT MEASURE(x.count) FROM x",
        "format": "sql",
    }
    assert result == reply


def _dry_run_body(transformed: list[Any]) -> dict[str, Any]:
    return {
        "queryType": "regularQuery",
        "normalizedQueries": [{}],
        "queryOrder": [{}],
        "pivotQuery": {},
        "transformedQueries": transformed,
    }


def test_dry_run_posts_query_and_summarizes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    real = _sql_fixture()["sql"]["canUseTransformedQuery"]
    body = _dry_run_body([real])
    calls = _recording_request(monkeypatch, server, body)
    ctx = MagicMock()

    result = asyncio.run(server.dry_run(ctx, {"measures": ["x.count"]}))
    method, path, kwargs = calls[0]
    assert (method, path) == ("POST", "/dry-run")
    assert kwargs["json"] == {"query": {"measures": ["x.count"], "timezone": "UTC"}}
    summary = result["transformedQueries"][0]
    assert "granularityHierarchies" not in summary
    assert summary["leafMeasures"] == real["leafMeasures"]
    assert summary["allFiltersWithinSelectedDimensions"] is False
    assert len(json.dumps(result)) < 5_000
    assert result["queryType"] == "regularQuery"

    assert (
        asyncio.run(server.dry_run(ctx, {"measures": ["x.count"]}, full=True)) == body
    )


def test_dry_run_summarizes_every_query_in_multi_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    big = {"leafMeasures": ["v.m"], "granularityHierarchies": {"x": ["y"] * 5000}}
    _recording_request(monkeypatch, server, _dry_run_body([big, big]))

    result = asyncio.run(server.dry_run(MagicMock(), {"measures": ["x.count"]}))
    assert result["transformedQueries"] == [{"leafMeasures": ["v.m"]}] * 2


def test_summarize_transformed_query_handles_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._summarize_transformed_query(None) is None


CUBESQL_STREAM = (
    '{"schema":[{"name":"c","column_type":"Int64"}],'
    '"lastRefreshTime":"t","usedPreAggregations":{}}\n'
    '{"data":[["1"],["2"]]}\n'
    '{"data":[["3"]]}\n'
)


def test_parse_cubesql_stream_assembles_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    out = server._parse_cubesql_stream(CUBESQL_STREAM)
    assert out == {
        "schema": [{"name": "c", "column_type": "Int64"}],
        "lastRefreshTime": "t",
        "usedPreAggregations": {},
        "data": [["1"], ["2"], ["3"]],
    }


def test_parse_cubesql_stream_error_line(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    out = server._parse_cubesql_stream('{"schema":[]}\n{"error":"boom"}\n')
    assert out == {"error": "boom"}


def test_parse_cubesql_stream_truncated_line(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server(monkeypatch)
    with pytest.raises(server.ToolError, match="/cubesql"):
        server._parse_cubesql_stream('{"schema":[]}\n{"data":[[1')


def test_cubesql_posts_sql_with_utc_and_continue_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    calls = _recording_request(monkeypatch, server, CUBESQL_STREAM)

    result = asyncio.run(server.cubesql(MagicMock(), "SELECT 1"))
    method, path, kwargs = calls[0]
    assert (method, path) == ("POST", "/cubesql")
    assert kwargs["raw"] is True
    assert kwargs["json"] == {
        "query": "SELECT 1",
        "timezone": "UTC",
        "throwContinueWait": True,
    }
    assert result["data"] == [["1"], ["2"], ["3"]]


def test_cubesql_polls_on_continue_wait_then_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    calls = _recording_request(
        monkeypatch, server, ['{"error":"Continue wait"}', CUBESQL_STREAM]
    )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(server.asyncio, "sleep", no_sleep)
    result = asyncio.run(server.cubesql(MagicMock(), "SELECT 1"))
    assert len(calls) == 2
    assert len(result["data"]) == 3


def test_cubesql_raises_at_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)

    async def always_wait(*args: Any, **kwargs: Any) -> str:
        del args, kwargs
        return '{"error":"Continue wait"}'

    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    monkeypatch.setattr(server, "_request", always_wait)
    # A zero budget puts the first 'Continue wait' past the deadline. Patching
    # time.monotonic instead would freeze asyncio's own clock and hang.
    monkeypatch.setattr(server, "TIMEOUT_SECONDS", 0)
    with pytest.raises(server.ToolError, match="did not complete"):
        asyncio.run(server.cubesql(MagicMock(), "SELECT 1"))


def test_cubesql_raises_cube_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    _recording_request(monkeypatch, server, '{"error":"Table not found"}\n')
    with pytest.raises(server.ToolError, match="Table not found"):
        asyncio.run(server.cubesql(MagicMock(), "SELECT 1"))


def test_convert_query_posts_sql_to_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    reply = {"query": {"measures": ["v.m"]}}
    calls = _recording_request(monkeypatch, server, reply)

    result = asyncio.run(server.convert_query(MagicMock(), "SELECT 1"))
    method, path, kwargs = calls[0]
    assert (method, path) == ("POST", "/convert-query")
    assert kwargs["json"] == {"input": "sql", "output": "rest", "query": "SELECT 1"}
    assert result == reply


def test_graphql_to_json_returns_json_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    calls = _recording_request(
        monkeypatch, server, {"jsonQuery": {"measures": ["v.m"]}}
    )

    result = asyncio.run(server.graphql_to_json(MagicMock(), "{ cube { v { m } } }"))
    method, path, kwargs = calls[0]
    assert (method, path) == ("POST", "/graphql-to-json")
    assert kwargs["json"] == {"query": "{ cube { v { m } } }", "variables": {}}
    assert result == {"measures": ["v.m"]}


def test_graphql_to_json_raises_on_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    _recording_request(monkeypatch, server, {"jsonQuery": None})
    with pytest.raises(server.ToolError, match="could not parse"):
        asyncio.run(server.graphql_to_json(MagicMock(), "{ nope"))


def test_every_tool_sends_minted_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)
    server._token_cache.clear()
    replies: dict[str, Any] = {
        "/load": {"data": []},
        "/sql": _sql_fixture(),
        "/dry-run": _dry_run_body([]),
        "/cubesql": CUBESQL_STREAM,
        "/convert-query": {"query": {}},
        "/graphql-to-json": {"jsonQuery": {}},
    }
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/cubejs-api/v1")
        seen.append((path, request.headers["Authorization"]))
        reply = replies[path]
        if isinstance(reply, str):
            return httpx.Response(200, text=reply)
        return httpx.Response(200, json=reply)

    monkeypatch.setattr(
        server,
        "client",
        httpx.AsyncClient(
            base_url=server.CUBE_REST_URL, transport=httpx.MockTransport(handler)
        ),
    )
    ctx = MagicMock()
    query = {"measures": ["x.count"]}
    asyncio.run(server.load(ctx, query))
    asyncio.run(server.sql(ctx, query))
    asyncio.run(server.dry_run(ctx, query))
    asyncio.run(server.cubesql(ctx, "SELECT 1"))
    asyncio.run(server.convert_query(ctx, "SELECT 1"))
    asyncio.run(server.graphql_to_json(ctx, "{ x }"))

    token = server._mint_token("engineer@apps.teamschools.org")
    assert [p for p, _ in seen] == list(replies)
    for _, header in seen:
        assert header == token
        assert not header.startswith("Bearer ")


def test_sql_trims_each_query_of_a_multi_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    fixture = _sql_fixture()
    # compareDateRange/blending: Cube returns one {sql, dataSource} per query.
    body = [fixture, fixture]
    # Wrapped: a list reply is read as a queue of replies.
    _recording_request(monkeypatch, server, [body])
    result = asyncio.run(server.sql(MagicMock(), {"measures": ["x.count"]}))
    assert result == [server._trim_sql(fixture)] * 2


def test_sql_string_raises_on_cube_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    _recording_request(monkeypatch, server, {"sql": {"error": "bad sql"}})
    with pytest.raises(server.ToolError, match="bad sql"):
        asyncio.run(server.sql(MagicMock(), "SELECT nope"))


def test_convert_query_raises_on_cube_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    _recording_request(
        monkeypatch, server, {"status": "error", "query": None, "error": "bad sql"}
    )
    with pytest.raises(server.ToolError, match="bad sql"):
        asyncio.run(server.convert_query(MagicMock(), "SELECT nope"))


def test_request_enforces_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)

    class SlowClient:
        async def request(self, *args: Any, **kwargs: Any) -> httpx.Response:
            del args, kwargs
            await asyncio.sleep(5)
            raise AssertionError("deadline not enforced")

    monkeypatch.setattr(server, "client", SlowClient())
    monkeypatch.setattr(server, "TIMEOUT_SECONDS", 0.05)
    with pytest.raises(server.ToolError, match="did not complete"):
        asyncio.run(server.load(MagicMock(), {"measures": ["x.count"]}))

    # A tool that does not poll must not blame 'Continue wait' polling.
    with pytest.raises(server.ToolError, match="did not complete") as excinfo:
        asyncio.run(server.sql(MagicMock(), {"measures": ["x.count"]}))
    assert "Continue wait" not in str(excinfo.value)


def test_summarize_transformed_query_marks_omitted_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    wide = [f"v.dimension_{i}" for i in range(200)]
    summary = server._summarize_transformed_query(
        {"sortedDimensions": wide, "granularityHierarchies": {"x": []}}
    )
    # Too large to inline, but the key stays so the caller knows to ask for it.
    assert "full=True" in summary["sortedDimensions"]
    assert "granularityHierarchies" not in summary


def test_load_docstring_describes_multi_query_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert "`results`" in server.load.__doc__


def test_cube_error_reaches_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    # The SDK replaces any non-ToolError exception text with a generic message.
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    _recording_request(monkeypatch, server, {"jsonQuery": None})
    with pytest.raises(server.ToolError, match="could not parse"):
        asyncio.run(
            server.mcp.call_tool("graphql_to_json", {"query": "{ nope"}, MagicMock())
        )


def test_request_raises_tool_error_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    server = _load_server(monkeypatch)

    class RejectingClient:
        async def request(self, *args: Any, **kwargs: Any) -> httpx.Response:
            del args, kwargs
            return httpx.Response(400, text='{"error": "Cube member not found"}')

    monkeypatch.setattr(server, "client", RejectingClient())
    with pytest.raises(server.ToolError, match="400.*member not found"):
        asyncio.run(server.load(MagicMock(), {"measures": ["x.count"]}))
