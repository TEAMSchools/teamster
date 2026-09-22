"""Contract checks between the PowerSchool plugin and the dbt models."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "ps-plugins" / "gradebook-audit"
DBT_MODEL = (
    REPO
    / "src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql"
)
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"

EXPECTED_HEADER = [
    "school level",
    "quarter",
    "week number",
    "w",
    "h",
    "f",
    "s",
    "notes",
]

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


def test_dbt_model_columns_survives_a_comment_containing_the_word_from(tmp_path):
    # A first-substring search for "from " truncates here, at the comment --
    # before the select list even starts -- so every column below it vanishes
    # from the result. That's the bug: a genuinely new, undeclared column
    # added after a comment like this would never be seen as new.
    sql = tmp_path / "model.sql"
    sql.write_text(
        "-- computed from the raw PS export\n"
        "select\n"
        "    cast(id as int) as id,\n"
        "    cast(cnt_s as int) as cnt_s,\n"
        "from source_table\n"
    )
    assert build_plugin.dbt_model_columns(sql) == {"id", "cnt_s"}


def test_dbt_model_columns_strips_an_inline_trailing_comment(tmp_path):
    sql = tmp_path / "model.sql"
    sql.write_text(
        "select\n    cast(cnt_s as int) as cnt_s, -- audit field\nfrom source_table\n"
    )
    assert build_plugin.dbt_model_columns(sql) == {"cnt_s"}


def test_plugin_csv_header_is_read_from_the_validator():
    assert build_plugin.plugin_csv_header(PLUGIN) == EXPECTED_HEADER


def test_missing_validator_reports_the_file_not_a_type_error(tmp_path):
    pages = tmp_path / "WEB_ROOT" / "admin" / "gradebookaudit"
    pages.mkdir(parents=True)
    (pages / "gradebook_expectations.html").write_text("<html>no validator</html>")
    with pytest.raises(ValueError, match="gradebook_expectations.html"):
        build_plugin.plugin_csv_header(tmp_path)
