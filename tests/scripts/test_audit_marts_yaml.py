from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_marts_yaml import ParsedModel, parse_mart_yaml

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_mart_yaml_extracts_columns_and_tests() -> None:
    parsed = parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")

    assert isinstance(parsed, list)
    assert len(parsed) == 2
    model = parsed[0]
    assert isinstance(model, ParsedModel)
    assert model.name == "fct_sample"
    assert model.column_data_types == {
        "surrogate_key": "string",
        "student_id": "int64",
        "academic_year": "int64",
        "created_timestamp": "timestamp",
    }
    assert model.uniqueness_tests == [
        {"columns": ["surrogate_key"], "severity": "error", "kind": "unique"},
        {
            "columns": ["student_id", "academic_year"],
            "severity": "warn",
            "kind": "unique_combination_of_columns",
        },
    ]


def test_parse_mart_yaml_handles_multi_model_and_column_severity() -> None:
    parsed = parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")
    assert [m.name for m in parsed] == ["fct_sample", "dim_sample"]
    dim = parsed[1]
    assert dim.uniqueness_tests == [
        {"columns": ["dim_key"], "severity": "warn", "kind": "unique"},
    ]
