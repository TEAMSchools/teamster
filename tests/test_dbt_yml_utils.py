from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".vscode" / "scripts"))

from shared import dbt_yml_utils

# ---------------------------------------------------------------------------
# TestStripJinja
# ---------------------------------------------------------------------------


class TestStripJinja:
    def test_removes_jinja_comments(self):
        sql = "{#- this is a comment #} select 1"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "{#" not in result
        assert "#}" not in result

    def test_replaces_expressions_with_placeholder(self):
        sql = "select {{ ref('my_model') }} from foo"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "__JINJA__" in result
        assert "{{" not in result

    def test_removes_blocks(self):
        sql = "{% if true %} select 1 {% endif %}"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "{%" not in result
        assert "%}" not in result

    def test_removes_sql_line_comments(self):
        sql = "select 1 -- this is a comment\nfrom foo"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "-- this is a comment" not in result

    def test_removes_sql_block_comments(self):
        sql = "select /* block comment */ 1 from foo"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "/* block comment */" not in result

    def test_preserves_sql_structure(self):
        sql = "select a, b from {{ ref('tbl') }} where c = 1"
        result = dbt_yml_utils.strip_jinja(sql)
        assert "select" in result.lower()
        assert "from" in result.lower()
        assert "where" in result.lower()


# ---------------------------------------------------------------------------
# TestFindFirstSelect
# ---------------------------------------------------------------------------


class TestFindFirstSelect:
    def test_simple_select(self):
        sql = "select a, b from foo"
        body = dbt_yml_utils.find_first_select(sql)
        assert "a" in body
        assert "b" in body

    def test_cte_returns_final_select(self):
        sql = """
        with cte as (select x from bar)
        select a, b from cte
        """
        body = dbt_yml_utils.find_first_select(sql)
        assert "a" in body
        assert "b" in body
        # should NOT return the inner CTE body
        assert "x" not in body

    def test_union_all_returns_first(self):
        sql = """
        select a, b from foo
        union all
        select c, d from bar
        """
        body = dbt_yml_utils.find_first_select(sql)
        assert "a" in body
        assert "b" in body
        # second select columns should not be included
        assert "c" not in body
        assert "d" not in body

    def test_subquery_not_confused(self):
        sql = "select a, (select count(*) from bar) as cnt from foo"
        body = dbt_yml_utils.find_first_select(sql)
        # outer columns
        assert "a" in body
        assert "cnt" in body

    def test_select_distinct(self):
        sql = "select distinct a, b from foo"
        body = dbt_yml_utils.find_first_select(sql)
        assert "distinct" not in body.lower()
        assert "a" in body
        assert "b" in body

    def test_raises_if_no_select(self):
        with pytest.raises(ValueError):
            dbt_yml_utils.find_first_select("from foo where 1=1")

    def test_raises_if_no_from(self):
        with pytest.raises(ValueError):
            dbt_yml_utils.find_first_select("select a, b")

    def test_select_distinct_multiline(self):
        sql = "select\n    distinct\n    col_a, col_b,\nfrom t"
        result = dbt_yml_utils.find_first_select(dbt_yml_utils.strip_jinja(sql))
        assert "col_a" in result
        assert "distinct" not in result.lower().split(",")[0].strip()


# ---------------------------------------------------------------------------
# TestParseSelectColumns
# ---------------------------------------------------------------------------


class TestParseSelectColumns:
    def test_simple_columns(self):
        body = "a, b, c"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["a", "b", "c"]

    def test_aliased_columns(self):
        body = "foo as bar, baz as qux"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["bar", "qux"]

    def test_qualified_columns(self):
        body = "t.column_name"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["column_name"]

    def test_function_with_alias(self):
        body = "count(*) as total"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["total"]

    def test_backtick_quoted(self):
        body = "`my_column` as col"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["col"]

    def test_null_literal(self):
        body = "null as missing_col"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["missing_col"]

    def test_window_function(self):
        body = "row_number() over (partition by a order by b) as rn"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["rn"]

    def test_jinja_placeholder(self):
        body = "__JINJA__ as model_col"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["model_col"]

    def test_star_filtered(self):
        body = "*, foo as bar"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert "*" not in cols
        assert "bar" in cols

    def test_no_trailing_comma(self):
        body = "a, b, c,"
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["a", "b", "c"]

    def test_backtick_quoted_alias_after_as(self):
        body = "foo as `last year final`, bar as `Q1 pct`,"
        assert dbt_yml_utils.parse_select_columns(body) == ["last year final", "Q1 pct"]


# ---------------------------------------------------------------------------
# TestFindYmlPath
# ---------------------------------------------------------------------------


class TestFindYmlPath:
    def test_standard_path(self, tmp_path):
        sql_path = tmp_path / "models" / "extracts" / "rpt_foo.sql"
        result = dbt_yml_utils.find_yml_path(sql_path)
        expected = tmp_path / "models" / "extracts" / "properties" / "rpt_foo.yml"
        assert result == expected

    def test_nested_subdirectory(self, tmp_path):
        sql_path = tmp_path / "a" / "b" / "c" / "model.sql"
        result = dbt_yml_utils.find_yml_path(sql_path)
        expected = tmp_path / "a" / "b" / "c" / "properties" / "model.yml"
        assert result == expected


# ---------------------------------------------------------------------------
# TestResolveSchema
# ---------------------------------------------------------------------------

REPO_ROOT = Path("/workspaces/teamster")


class TestResolveSchema:
    def test_kipptaf_extracts(self):
        sql_path = (
            REPO_ROOT
            / "src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql"
        )
        schema = dbt_yml_utils.resolve_schema(sql_path, repo_root=REPO_ROOT)
        assert schema == "kipptaf_extracts"

    def test_kipptaf_tableau(self):
        # Find a tableau model
        tableau_dir = REPO_ROOT / "src/dbt/kipptaf/models/extracts/tableau"
        # Use a synthetic path under extracts/tableau
        sql_path = tableau_dir / "rpt_tableau__some_model.sql"
        schema = dbt_yml_utils.resolve_schema(sql_path, repo_root=REPO_ROOT)
        assert schema == "kipptaf_tableau"

    def test_kippnewark_extracts(self):
        sql_path = REPO_ROOT / "src/dbt/kippnewark/models/extracts/rpt_some_model.sql"
        schema = dbt_yml_utils.resolve_schema(sql_path, repo_root=REPO_ROOT)
        assert schema == "kippnewark_extracts"


# ---------------------------------------------------------------------------
# TestQueryColumnTypes
# ---------------------------------------------------------------------------


class TestQueryColumnTypes:
    @patch("shared.dbt_yml_utils.bigquery.Client")
    def test_returns_type_mapping(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        row1 = MagicMock()
        row1.column_name = "school_id"
        row1.data_type = "INT64"
        row2 = MagicMock()
        row2.column_name = "section_id"
        row2.data_type = "STRING"

        mock_client.query.return_value.result.return_value = [row1, row2]

        result = dbt_yml_utils.query_column_types(
            "rpt_clever__enrollments", "kipptaf_extracts"
        )
        assert result == {"school_id": "int64", "section_id": "string"}

    @patch("shared.dbt_yml_utils.bigquery.Client")
    def test_returns_empty_on_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.query.side_effect = Exception("BQ error")

        result = dbt_yml_utils.query_column_types("bad_model", "bad_dataset")
        assert result == {}


# ---------------------------------------------------------------------------
# TestSyncYml
# ---------------------------------------------------------------------------


class TestSyncYml:
    def _load_yml(self, yml_path: Path) -> dict:
        with yml_path.open() as f:
            return yaml.safe_load(f)

    def _write_yml(self, yml_path: Path, data: dict) -> None:
        yml_path.parent.mkdir(parents=True, exist_ok=True)
        with yml_path.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def test_adds_new_columns(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "columns": [{"name": "a", "data_type": "string"}],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a", "b"],
            bq_types={"a": "string", "b": "int64"},
        )
        data = self._load_yml(yml_path)
        cols = {c["name"]: c for c in data["models"][0]["columns"]}
        assert "b" in cols
        assert cols["b"]["data_type"] == "int64"

    def test_removes_deleted_columns(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "columns": [
                            {"name": "a", "data_type": "string"},
                            {"name": "old_col", "data_type": "int64"},
                        ],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a"],
            bq_types={"a": "string"},
        )
        data = self._load_yml(yml_path)
        col_names = [c["name"] for c in data["models"][0]["columns"]]
        assert "old_col" not in col_names
        assert "a" in col_names

    def test_preserves_metadata(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "columns": [
                            {
                                "name": "a",
                                "data_type": "string",
                                "description": "Column A",
                                "data_tests": [{"not_null": {}}],
                            }
                        ],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a"],
            bq_types={"a": "string"},
        )
        data = self._load_yml(yml_path)
        col_a = data["models"][0]["columns"][0]
        assert col_a["description"] == "Column A"
        assert col_a["data_tests"] == [{"not_null": {}}]

    def test_column_order_matches_sql(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "columns": [
                            {"name": "b", "data_type": "int64"},
                            {"name": "a", "data_type": "string"},
                        ],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a", "b", "c"],
            bq_types={"a": "string", "b": "int64", "c": "float64"},
        )
        data = self._load_yml(yml_path)
        col_names = [c["name"] for c in data["models"][0]["columns"]]
        assert col_names == ["a", "b", "c"]

    def test_updates_data_type(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "columns": [{"name": "a", "data_type": "string"}],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a"],
            bq_types={"a": "int64"},
        )
        data = self._load_yml(yml_path)
        assert data["models"][0]["columns"][0]["data_type"] == "int64"

    def test_preserves_model_level_keys(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_foo.yml"
        self._write_yml(
            yml_path,
            {
                "models": [
                    {
                        "name": "rpt_foo",
                        "config": {"contract": {"enforced": True}},
                        "data_tests": [
                            {
                                "dbt_utils.unique_combination_of_columns": {
                                    "arguments": {"combination_of_columns": ["a", "b"]}
                                }
                            }
                        ],
                        "columns": [
                            {"name": "a", "data_type": "string"},
                            {"name": "b", "data_type": "int64"},
                        ],
                    }
                ]
            },
        )
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["a", "b"],
            bq_types={"a": "string", "b": "int64"},
        )
        data = self._load_yml(yml_path)
        model = data["models"][0]
        assert model.get("config") == {"contract": {"enforced": True}}
        assert "data_tests" in model

    def test_creates_yml_if_not_exists(self, tmp_path):
        yml_path = tmp_path / "properties" / "rpt_new.yml"
        dbt_yml_utils.sync_yml(
            yml_path,
            sql_columns=["x", "y"],
            bq_types={"x": "string", "y": "int64"},
        )
        assert yml_path.exists()
        data = self._load_yml(yml_path)
        col_names = [c["name"] for c in data["models"][0]["columns"]]
        assert col_names == ["x", "y"]

    def test_new_column_without_bq_type_has_no_data_type(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({"models": [{"name": "m", "columns": []}]}))
        dbt_yml_utils.sync_yml(yml_path=yml_path, sql_columns=["new_col"], bq_types={})
        data = yaml.safe_load(yml_path.read_text())
        col = data["models"][0]["columns"][0]
        assert col == {"name": "new_col"}
        assert "data_type" not in col


# ---------------------------------------------------------------------------
# TestIntegrationRealFiles
# ---------------------------------------------------------------------------


class TestIntegrationRealFiles:
    def test_rpt_clever_enrollments_union_all(self):
        """UNION ALL → first select columns only."""
        sql_path = (
            REPO_ROOT
            / "src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql"
        )
        sql = sql_path.read_text()
        stripped = dbt_yml_utils.strip_jinja(sql)
        body = dbt_yml_utils.find_first_select(stripped)
        cols = dbt_yml_utils.parse_select_columns(body)
        assert cols == ["school_id", "section_id", "student_id"]

    def test_schema_resolution_real_dbt_project(self):
        sql_path = (
            REPO_ROOT
            / "src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql"
        )
        schema = dbt_yml_utils.resolve_schema(sql_path, repo_root=REPO_ROOT)
        assert schema == "kipptaf_extracts"
