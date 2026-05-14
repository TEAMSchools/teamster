from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "src" / "cube" / "mcp" / "server.py"


def _load_server(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load src/cube/mcp/server.py under sys.modules['cube_mcp_server'].

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
