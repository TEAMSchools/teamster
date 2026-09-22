"""Contract checks between the PowerSchool plugin and the dbt models."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "ps-plugins" / "gradebook-audit"
DBT_MODEL = (
    REPO
    / "src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql"
)

_spec = importlib.util.spec_from_file_location(
    "build_plugin", REPO / "ps-plugins" / "scripts" / "build_plugin.py"
)
assert _spec is not None and _spec.loader is not None
build_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_plugin)


def test_named_query_columns_are_the_nine_declared():
    assert build_plugin.named_query_columns(PLUGIN) == {
        "id",
        "school_level",
        "quarter",
        "week_number",
        "cnt_w",
        "cnt_h",
        "cnt_f",
        "cnt_s",
        "notes",
    }


def test_dbt_model_columns_include_the_powerschool_audit_quartet():
    columns = build_plugin.dbt_model_columns(DBT_MODEL)
    assert {"whocreated", "whencreated", "whomodified", "whenmodified"} <= columns
    assert "week_number" in columns


def test_column_contract_holds_today():
    assert build_plugin.check_column_contract(PLUGIN, DBT_MODEL) == []


def test_column_contract_fails_when_the_plugin_declares_an_unknown_column(tmp_path):
    queries = tmp_path / "queries_root"
    queries.mkdir()
    (queries / "q.xml").write_text(
        '<?xml version="1.0"?><queries><query coreTable="u_expectations">'
        '<columns><column column="u_expectations.made_up">made_up</column>'
        "</columns></query></queries>"
    )
    errors = build_plugin.check_column_contract(tmp_path, DBT_MODEL)
    assert any("made_up" in e for e in errors)
