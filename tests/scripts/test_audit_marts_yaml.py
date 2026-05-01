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


def test_normalize_type_strips_params_and_lowercases() -> None:
    assert audit.normalize_type("STRING") == "string"
    assert audit.normalize_type("string") == "string"
    assert audit.normalize_type("STRING(255)") == "string"
    assert audit.normalize_type("NUMERIC(10,2)") == "numeric"
    assert audit.normalize_type("BIGNUMERIC(38, 9)") == "bignumeric"
    assert audit.normalize_type("DATETIME") == "datetime"
    assert audit.normalize_type("TIMESTAMP") == "timestamp"


def test_load_manifest_returns_indexed_nodes() -> None:
    nodes = audit.load_manifest(FIXTURE_DIR / "sample_manifest.json")
    assert "model.kipptaf.fct_sample" in nodes
    assert isinstance(nodes["model.kipptaf.fct_sample"], audit.ManifestNode)
    assert (
        nodes["model.kipptaf.fct_sample"].relation_name
        == "`teamster-332318`.`kipptaf`.`fct_sample`"
    )


def test_mart_models_filters_to_marts_dir() -> None:
    nodes = audit.load_manifest(FIXTURE_DIR / "sample_manifest.json")
    marts = audit.mart_models(nodes)
    assert [n.name for n in marts] == ["fct_sample"]


def test_load_manifest_raises_when_missing() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        audit.load_manifest(FIXTURE_DIR / "does_not_exist.json")
