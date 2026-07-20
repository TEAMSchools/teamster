from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures/cube_ref_sample"
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/generate_cube_reference.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_cube_reference", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_cube_reference"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def test_parse_cubes_indexes_members_and_kinds() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    fact = cubes["sample_fact"]
    assert fact["count_rows"].kind == "measure"
    assert fact["grade_level"].kind == "dimension"
    assert fact["grade_level"].type == "number"
    assert fact["grade_level"].description == "Student grade level."
    # missing description is preserved as None (not the empty string)
    assert fact["no_desc_dim"].description is None


def test_parse_cubes_flattens_extends() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    # sample_alias extends sample_base and defines no members of its own, so it
    # inherits base_key with its description and primary_key flag.
    alias = cubes["sample_alias"]
    assert "base_key" in alias
    assert alias["base_key"].description == "Base key."
    assert alias["base_key"].primary_key is True


def _resolved_view(name: str = "sample_view"):
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    return next(v for v in views if v.name == name)


def test_resolve_view_applies_prefix_rule() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    # prefix: false -> bare member names
    assert "grade_level" in by_name
    assert "count_rows" in by_name
    assert "base_key" in by_name  # from sample_alias (extends sample_base)
    # prefix: true -> <last-join_path-segment>_<member>
    assert "sample_dim_region_name" in by_name
    assert by_name["sample_dim_region_name"].description == "Region name."


def test_resolve_view_classifies_and_types_members() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["count_rows"].kind == "measure"
    assert by_name["grade_level"].kind == "dimension"
    assert by_name["grade_level"].type == "number"
    assert by_name["no_desc_dim"].description is None
    assert by_name["grade_level"].source == "sample_fact.grade_level"


def test_resolve_view_assigns_folders_with_other_fallback() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["grade_level"].folder == "Sample"
    assert by_name["sample_dim_region_name"].folder == "Region"
    # base_key is exposed but listed in no meta folder -> "Other"
    assert by_name["base_key"].folder == "Other"
    # measures are never folder-grouped
    assert by_name["count_rows"].folder == ""
