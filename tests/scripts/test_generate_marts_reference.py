from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts/generate_marts_reference.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_marts_reference", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_marts_reference"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def test_parse_fk_edges_reads_foreign_key_constraints() -> None:
    edges = gen.parse_fk_edges(FIXTURE_DIR / "sample_fct_reference.yml")

    # one edge per foreign_key constraint; primary_key ignored; relationships
    # test is NOT double-counted.
    assert edges == [
        gen.FkEdge("fct_sample", "student_enrollment_key", "dim_student_enrollments"),
        gen.FkEdge("fct_sample", "created_date_key", "dim_dates"),
        gen.FkEdge("fct_sample", "solved_date_key", "dim_dates"),
    ]
