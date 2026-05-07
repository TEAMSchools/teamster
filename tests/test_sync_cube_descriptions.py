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


def test_resolve_table_kipptaf_marts() -> None:
    mod = _load_script()
    assert mod._resolve_table_from_sql_table("kipptaf_marts.fct_sample") == "fct_sample"


def test_resolve_table_other_schema_returns_none() -> None:
    mod = _load_script()
    assert mod._resolve_table_from_sql_table("other_schema.x") is None


def test_resolve_table_no_dot_returns_none() -> None:
    mod = _load_script()
    assert mod._resolve_table_from_sql_table("kipptaf_marts") is None


def test_resolve_table_none_input_returns_none() -> None:
    mod = _load_script()
    assert mod._resolve_table_from_sql_table(None) is None


def test_load_dbt_descriptions_from_fixture(tmp_path) -> None:
    """Reads a fake mart YAML and returns column→description for non-empty descriptions only."""
    mod = _load_script()
    facts = tmp_path / "facts" / "properties"
    facts.mkdir(parents=True)
    shutil.copy(_FIXTURE_DIR / "dbt_fct_sample.yml", facts / "fct_sample.yml")
    result = mod._load_dbt_descriptions("fct_sample", [facts])
    assert result == {
        "sample_key": "Surrogate key.",
        "attendance_value": "Daily attendance value (0.0–1.0).",
        "name": "Canonical name.",
    }
    assert "computed_col" not in result


def test_load_dbt_descriptions_missing_returns_none(tmp_path) -> None:
    mod = _load_script()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert mod._load_dbt_descriptions("not_there", [empty]) is None


def test_load_dbt_descriptions_searches_multiple_dirs(tmp_path) -> None:
    mod = _load_script()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    shutil.copy(_FIXTURE_DIR / "dbt_fct_sample.yml", b / "fct_sample.yml")
    result = mod._load_dbt_descriptions("fct_sample", [a, b])
    assert result is not None
    assert "sample_key" in result
