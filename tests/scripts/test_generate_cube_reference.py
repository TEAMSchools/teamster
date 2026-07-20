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
