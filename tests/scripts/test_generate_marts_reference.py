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


def test_parse_fk_edges_reads_model_level_constraints() -> None:
    edges = gen.parse_fk_edges(FIXTURE_DIR / "sample_dim_model_level.yml")

    # model-level foreign_key constraints use `to:` + `columns:`;
    # primary_key constraints (column- and model-level) are ignored.
    assert edges == [
        gen.FkEdge("dim_sample_status", "student_key", "dim_students"),
        gen.FkEdge(
            "dim_sample_status",
            "student_enrollment_key",
            "dim_student_enrollments",
        ),
    ]


def test_parse_fk_edges_reads_foreign_key_constraints() -> None:
    edges = gen.parse_fk_edges(FIXTURE_DIR / "sample_fct_reference.yml")

    # one edge per foreign_key constraint; primary_key ignored; relationships
    # test is NOT double-counted.
    assert edges == [
        gen.FkEdge("fct_sample", "student_enrollment_key", "dim_student_enrollments"),
        gen.FkEdge("fct_sample", "created_date_key", "dim_dates"),
        gen.FkEdge("fct_sample", "solved_date_key", "dim_dates"),
    ]


def _sample_edges() -> list:
    return [
        gen.FkEdge("fct_x", "enrollment_key", "dim_enrollments"),
        gen.FkEdge("fct_x", "created_date_key", "dim_dates"),
        gen.FkEdge("fct_x", "solved_date_key", "dim_dates"),
        gen.FkEdge("dim_enrollments", "student_key", "dim_students"),
        gen.FkEdge("dim_enrollments", "location_key", "dim_locations"),
        gen.FkEdge("dim_locations", "region_key", "dim_regions"),
    ]


def test_build_adjacency_groups_edges_by_source() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    assert {e.target for e in adjacency["fct_x"]} == {"dim_enrollments", "dim_dates"}
    assert len(adjacency["fct_x"]) == 3  # two role-qualified date edges kept


def test_snowflake_subgraph_walks_full_chain() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    sub = gen.snowflake_subgraph(adjacency, "fct_x")

    # every reachable edge is collected (full snowflake chain), including both
    # role-qualified edges to dim_dates and the dim->dim chain to dim_regions.
    assert len(sub) == 6
    assert gen.FkEdge("dim_locations", "region_key", "dim_regions") in sub
    targets = {e.target for e in sub}
    assert {"dim_regions", "dim_students", "dim_dates"} <= targets


def test_collect_fact_names_sorted_from_facts_dir() -> None:
    names = gen.collect_fact_names(gen.MARTS_DIR)
    assert names == sorted(names)
    assert all(n.startswith("fct_") for n in names)
    assert "fct_student_attendance_daily" in names
    assert len(names) >= 20
