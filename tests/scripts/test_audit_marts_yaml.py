from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

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


def _mock_bq_client(rows: list[dict]) -> MagicMock:
    client = MagicMock(spec=audit.BQClient)
    job = MagicMock()
    job.result.return_value = [MagicMock(**r) for r in rows]
    client.query.return_value = job
    return client


def test_fetch_dataset_columns_groups_by_table() -> None:
    client = _mock_bq_client(
        [
            {
                "table_name": "fct_sample",
                "column_name": "student_id",
                "data_type": "INT64",
            },
            {
                "table_name": "fct_sample",
                "column_name": "created_timestamp",
                "data_type": "DATETIME",
            },
            {"table_name": "dim_other", "column_name": "key", "data_type": "STRING"},
        ]
    )
    result = audit.fetch_dataset_columns(client, "teamster-332318", "kipptaf")
    assert result == {
        "fct_sample": {"student_id": "INT64", "created_timestamp": "DATETIME"},
        "dim_other": {"key": "STRING"},
    }


def test_grain_probe_returns_rows_and_distinct_keys() -> None:
    client = _mock_bq_client([{"rows": 100, "keys": 95}])
    rows, keys = audit.grain_probe(
        client,
        "`teamster-332318`.`kipptaf`.`fct_sample`",
        ["student_id", "academic_year"],
    )
    assert (rows, keys) == (100, 95)
    sql = client.query.call_args[0][0]
    assert 'format("%T|%T", `student_id`, `academic_year`)' in sql


def test_trace_column_casts_walks_parent_map() -> None:
    nodes = audit.load_manifest(FIXTURE_DIR / "sample_manifest.json")
    casts = audit.trace_column_casts(
        column="created_timestamp",
        from_node="model.kipptaf.fct_sample",
        nodes=nodes,
    )
    # The mart casts `created` to datetime aliasing as created_timestamp;
    # int_sample passes it through; stg_sample casts the source to datetime.
    assert ("fct_sample", "cast(created as datetime) as created_timestamp") in casts


def test_asset_key_includes_mart_subdir() -> None:
    nodes = audit.load_manifest(FIXTURE_DIR / "sample_manifest.json")
    fct = nodes["model.kipptaf.fct_sample"]
    assert audit.asset_key_for_mart_node(fct) == ["kipptaf", "facts", "fct_sample"]


def test_fetch_dagster_check_status_parses_response() -> None:
    fake_response = {
        "assetChecksOrError": {
            "checks": [
                {
                    "name": "unique_fct_sample_surrogate_key",
                    "executionForLatestMaterialization": {
                        "evaluation": {
                            "severity": "ERROR",
                            "successful": True,
                            "timestamp": 1714521240.0,
                        }
                    },
                }
            ]
        }
    }
    with patch.object(audit, "_dagster_graphql", return_value=fake_response):
        result = audit.fetch_dagster_check_status(
            asset_keys=[["kipptaf", "facts", "fct_sample"]],
            token="fake",
            deployment="prod",
        )
    assert result == {
        ("kipptaf", "facts", "fct_sample"): {
            "unique_fct_sample_surrogate_key": audit.DagsterStatus(
                outcome="PASSED", timestamp=1714521240.0
            )
        }
    }
