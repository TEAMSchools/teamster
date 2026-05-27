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
    cache_path = server._meta_cache_path("engineer@apps.teamschools.org")
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


def test_rewrite_ay_filters_normalises_ay_string_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["AY2025"],
            }
        ]
    }
    result = server._rewrite_ay_filters(query)
    assert result["filters"][0]["values"] == ["2025"]


def test_rewrite_ay_filters_normalises_range_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    # 2- and 3-digit suffixes normalise to the start year.
    for raw in ["2025-26", "2025-026"]:
        query = {
            "filters": [
                {
                    "member": "attendance_summary.dim_terms_academic_year",
                    "operator": "equals",
                    "values": [raw],
                }
            ]
        }
        result = server._rewrite_ay_filters(query)
        assert result["filters"][0]["values"] == ["2025"], f"failed for {raw!r}"


def test_rewrite_ay_filters_passes_through_four_digit_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    # "2023-2025" / "2025-2026" look like multi-year ranges, not single-AY
    # shorthand — pass through unchanged so Cube surfaces an error rather than
    # silently picking only the start year.
    for raw in ["2025-2026", "2025–2026", "2023-2025"]:
        query = {
            "filters": [
                {
                    "member": "attendance_summary.dim_terms_academic_year",
                    "operator": "equals",
                    "values": [raw],
                }
            ]
        }
        result = server._rewrite_ay_filters(query)
        assert result["filters"][0]["values"] == [raw], f"should not rewrite {raw!r}"


def test_rewrite_ay_filters_leaves_correct_value_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["2025"],
            }
        ]
    }
    result = server._rewrite_ay_filters(query)
    assert result is query  # no copy made when nothing changes


def test_rewrite_ay_filters_ignores_non_equals_operators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "gte",
                "values": ["AY2025"],
            }
        ]
    }
    result = server._rewrite_ay_filters(query)
    assert result["filters"][0]["values"] == ["AY2025"]


def test_validate_query_errors_on_multi_year_ay_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.count_present"],
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["2023-2025"],
            }
        ],
    }
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    assert "2023-2025" in result["error"]
    assert result["suggested_fix"]["filters"][0]["values"] == ["2023", "2024", "2025"]


def test_validate_query_errors_on_two_year_ay_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.count_present"],
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["2025-2026"],
            }
        ],
    }
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    assert result["suggested_fix"]["filters"][0]["values"] == ["2025", "2026"]


def test_validate_query_errors_on_same_year_ay_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.count_present"],
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["2025-2025"],
            }
        ],
    }
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    assert result["suggested_fix"]["filters"][0]["values"] == ["2025"]


def test_validate_query_passes_through_when_no_ca_measure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {"measures": ["attendance_summary.count_present"], "filters": []}
    result = server._validate_query(query)
    assert not result.get(server._QUERY_ERROR_SENTINEL)
    assert result["measures"] == ["attendance_summary.count_present"]


def test_validate_query_passes_through_with_date_day_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.pct_chronically_absent"],
        "filters": [
            {
                "member": "attendance_summary.dim_dates_date_day",
                "operator": "equals",
                "values": ["2026-01-30"],
            }
        ],
    }
    result = server._validate_query(query)
    assert not result.get(server._QUERY_ERROR_SENTINEL)


def test_validate_query_passes_through_with_is_latest_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.count_chronically_absent"],
        "filters": [
            {
                "member": "attendance_summary.is_latest_record",
                "operator": "equals",
                "values": [True],
            }
        ],
    }
    result = server._validate_query(query)
    assert not result.get(server._QUERY_ERROR_SENTINEL)


def test_validate_query_passes_through_with_is_latest_record_string_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    for val in [["true"], ["1"]]:
        query = {
            "measures": ["attendance_summary.count_chronically_absent"],
            "filters": [
                {
                    "member": "attendance_summary.is_latest_record",
                    "operator": "equals",
                    "values": val,
                }
            ],
        }
        result = server._validate_query(query)
        assert not result.get(server._QUERY_ERROR_SENTINEL), f"failed for values={val}"


def test_validate_query_ca_anchor_works_for_attendance_detail_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_detail.pct_chronically_absent"],
        "filters": [
            {
                "member": "attendance_detail.dim_dates_date_day",
                "operator": "equals",
                "values": ["2026-01-30"],
            }
        ],
    }
    result = server._validate_query(query)
    assert not result.get(server._QUERY_ERROR_SENTINEL)


def test_validate_query_ca_error_uses_detail_view_member_in_suggested_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_detail.pct_chronically_absent"],
        "filters": [],
    }
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    stub = result["suggested_fix"]["filters"][-1]
    assert stub["member"] == "attendance_detail.dim_dates_date_day"


def test_validate_query_errors_when_ca_measure_has_no_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {"measures": ["attendance_summary.pct_chronically_absent"], "filters": []}
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    assert "anchor" in result["error"]
    assert "suggested_fix" in result
    # suggested_fix should contain a date_day stub filter
    stub_members = [f["member"] for f in result["suggested_fix"]["filters"]]
    assert any("dim_dates_date_day" in m for m in stub_members)


def test_validate_query_errors_when_multiple_date_day_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.pct_tier_1_2"],
        "filters": [
            {
                "member": "attendance_summary.dim_dates_date_day",
                "operator": "equals",
                "values": ["2026-01-15"],
            },
            {
                "member": "attendance_summary.dim_dates_date_day",
                "operator": "equals",
                "values": ["2026-01-30"],
            },
        ],
    }
    result = server._validate_query(query)
    assert result.get(server._QUERY_ERROR_SENTINEL)
    assert "2026-01-15" in result["error"]
    assert "2026-01-30" in result["error"]
    # suggested_fix keeps only the later date
    date_pins = [
        f
        for f in result["suggested_fix"]["filters"]
        if f.get("member", "").endswith(".dim_dates_date_day")
    ]
    assert len(date_pins) == 1
    assert date_pins[0]["values"] == ["2026-01-30"]


def test_validate_query_normalises_ay_filter_before_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["attendance_summary.count_present"],
        "filters": [
            {
                "member": "attendance_summary.dim_terms_academic_year",
                "operator": "equals",
                "values": ["AY2025"],
            }
        ],
    }
    result = server._validate_query(query)
    assert result["filters"][0]["values"] == ["2025"]


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
    server._meta_cache_path("engineer@apps.teamschools.org").unlink()
    third = asyncio.run(server.meta(ctx))
    assert third == {"cubes": [{"name": "x"}]}
    assert call_count == 1
