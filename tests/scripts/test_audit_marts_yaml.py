from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/audit_marts_yaml.py"


def _load_audit_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_marts_yaml", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_marts_yaml"] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


def test_parse_mart_yaml_extracts_columns_and_tests() -> None:
    parsed = audit.parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")

    assert isinstance(parsed, list)
    assert len(parsed) == 2
    model = parsed[0]
    assert isinstance(model, audit.ParsedModel)
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
    parsed = audit.parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")
    assert [m.name for m in parsed] == ["fct_sample", "dim_sample"]
    dim = parsed[1]
    assert dim.uniqueness_tests == [
        {"columns": ["dim_key"], "severity": "warn", "kind": "unique"},
    ]
