"""Tests for scripts/sync_cube_descriptions.py."""

import importlib.util
import shutil
import sys
from pathlib import Path

import yaml as _yaml  # for reading the patched output

_SCRIPT = Path("scripts/sync_cube_descriptions.py")
_FIXTURE_DIR = Path("tests/fixtures/cube_yaml")
_MODULE_NAME = "sync_cube_descriptions"


def _load_script():
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
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


def _patch_cube_with_fixture(tmp_path, cube_fixture: str) -> tuple[Path, dict]:
    """Copy the cube fixture into tmp_path, run the patcher, return path and counts."""
    mod = _load_script()
    cube_path = tmp_path / "cube.yml"
    shutil.copy(_FIXTURE_DIR / cube_fixture, cube_path)
    facts = tmp_path / "facts" / "properties"
    facts.mkdir(parents=True)
    shutil.copy(_FIXTURE_DIR / "dbt_fct_sample.yml", facts / "fct_sample.yml")
    counts = mod._patch_cube_file(cube_path, search_dirs=[facts])
    return cube_path, counts


def test_patch_inserts_descriptions_on_matched_dimensions(tmp_path) -> None:
    cube_path, counts = _patch_cube_with_fixture(tmp_path, "cube_sample.yml")
    doc = _yaml.safe_load(cube_path.read_text())
    dims = {d["name"]: d for d in doc["cubes"][0]["dimensions"]}
    assert dims["sample_key"]["description"] == "Surrogate key."
    assert (
        dims["attendance_value"]["description"] == "Daily attendance value (0.0–1.0)."
    )
    assert dims["bare_name"]["description"] == "Canonical name."
    assert counts["updated"] == 3


def test_patch_skips_expression_dimension(tmp_path) -> None:
    cube_path, counts = _patch_cube_with_fixture(tmp_path, "cube_sample.yml")
    doc = _yaml.safe_load(cube_path.read_text())
    dims = {d["name"]: d for d in doc["cubes"][0]["dimensions"]}
    assert "description" not in dims["attendance_date"]
    assert counts["skipped_expr"] == 1


def test_patch_preserves_existing_description_and_skips_no_match(tmp_path) -> None:
    cube_path, counts = _patch_cube_with_fixture(tmp_path, "cube_sample.yml")
    doc = _yaml.safe_load(cube_path.read_text())
    dims = {d["name"]: d for d in doc["cubes"][0]["dimensions"]}
    assert dims["existing_desc"]["description"] == "Hand-authored, do not touch."
    assert "description" not in dims["no_match"]
    assert counts["skipped_already"] == 1
    assert counts["skipped_no_match"] == 1


def test_patch_leaves_measures_untouched(tmp_path) -> None:
    cube_path, _counts = _patch_cube_with_fixture(tmp_path, "cube_sample.yml")
    doc = _yaml.safe_load(cube_path.read_text())
    measures = doc["cubes"][0]["measures"]
    assert all("description" not in m for m in measures)


def test_patch_skips_other_schema_table(tmp_path) -> None:
    mod = _load_script()
    cube_path = tmp_path / "cube.yml"
    shutil.copy(_FIXTURE_DIR / "cube_other_schema.yml", cube_path)
    counts = mod._patch_cube_file(cube_path, search_dirs=[])
    assert counts["skipped_no_table"] == 1
    assert counts["updated"] == 0
    # File contents unchanged.
    text_after = cube_path.read_text()
    text_before = (_FIXTURE_DIR / "cube_other_schema.yml").read_text()
    assert text_after == text_before
