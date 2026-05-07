"""Tests for scripts/sync_cube_descriptions.py."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

_SCRIPT = Path("scripts/sync_cube_descriptions.py")
_FIXTURE_DIR = Path("tests/fixtures/cube_yaml")


def _load_script():
    spec = importlib.util.spec_from_file_location("sync_cube_descriptions", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_module_loads() -> None:
    assert _load_script() is not None


def test_resolve_bare_column() -> None:
    mod = _load_script()
    assert mod._resolve_dbt_column("attendance_value") == "attendance_value"


def test_resolve_cube_qualified() -> None:
    mod = _load_script()
    assert mod._resolve_dbt_column("{CUBE}.`name`") == "name"


def test_resolve_cube_unquoted() -> None:
    mod = _load_script()
    assert mod._resolve_dbt_column("{CUBE}.location_key") == "location_key"


def test_resolve_expression_returns_none() -> None:
    mod = _load_script()
    assert mod._resolve_dbt_column("CAST(date_key AS TIMESTAMP)") is None


def test_resolve_non_string_returns_none() -> None:
    mod = _load_script()
    assert mod._resolve_dbt_column(None) is None
