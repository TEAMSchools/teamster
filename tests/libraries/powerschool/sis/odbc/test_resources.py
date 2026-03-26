"""Unit tests for PowerSchoolODBCResource."""

from unittest.mock import MagicMock, patch

from sqlalchemy import TextClause

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource


def _make_resource() -> PowerSchoolODBCResource:
    """Return a resource instance with setup_for_execution already applied."""
    resource = PowerSchoolODBCResource(
        user="testuser",
        password="testpass",
        host="127.0.0.1",
        port="1521",
        service_name="PSDB",
    )
    ctx = MagicMock()
    ctx.log = MagicMock()
    resource.setup_for_execution(ctx)
    return resource


class TestConnect:
    def test_returns_connection_from_oracledb(self):
        resource = _make_resource()
        mock_conn = MagicMock()

        with patch(
            "teamster.libraries.powerschool.sis.odbc.resources.connect",
            return_value=mock_conn,
        ) as mock_connect:
            result = resource.connect()

        mock_connect.assert_called_once()
        assert result is mock_conn

    def test_passes_connect_params(self):
        resource = _make_resource()

        with patch(
            "teamster.libraries.powerschool.sis.odbc.resources.connect",
            return_value=MagicMock(),
        ) as mock_connect:
            resource.connect()

        _, kwargs = mock_connect.call_args
        assert "params" in kwargs


class TestExecuteQueryTupleMode:
    def _make_cursor(self, rows):
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        return cursor

    def _make_connection(self, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    def test_returns_fetchall_rows(self):
        rows = [(1, "Alice"), (2, "Bob")]
        cursor = self._make_cursor(rows)
        conn = self._make_connection(cursor)

        resource = _make_resource()
        query = MagicMock()
        query.__str__ = lambda _: "SELECT * FROM STUDENTS"

        result = resource.execute_query(connection=conn, query=query)

        assert result == rows

    def test_applies_prefetch_and_array_size(self):
        cursor = self._make_cursor([])
        conn = self._make_connection(cursor)

        resource = _make_resource()
        query = MagicMock()
        query.__str__ = lambda _: "SELECT * FROM STUDENTS"

        resource.execute_query(
            connection=conn, query=query, prefetch_rows=500, array_size=250
        )

        assert cursor.prefetchrows == 500
        assert cursor.arraysize == 250

    def test_default_output_format_is_tuple_mode(self):
        """Passing no output_format should not trigger avro mode."""
        rows = [(42,)]
        cursor = self._make_cursor(rows)
        conn = self._make_connection(cursor)

        resource = _make_resource()
        query = MagicMock()
        query.__str__ = lambda _: "SELECT COUNT(*) FROM STUDENTS"

        result = resource.execute_query(
            connection=conn, query=query, output_format=None
        )

        cursor.fetchall.assert_called_once()
        assert result == rows


class TestExecuteQueryAvroMode:
    def _make_cursor_with_description(self):
        """Return a cursor mock with a minimal description for avro schema building."""
        mock_db_type = MagicMock()
        mock_db_type.name = "DB_TYPE_VARCHAR"

        cursor = MagicMock()
        # description: list of (name, type, display_size, internal_size, precision, scale, null_ok)
        cursor.description = [("ID", mock_db_type, None, None, None, None, None)]
        cursor.fetchmany.return_value = []  # empty result — avro writer exits immediately
        return cursor

    def _make_text_clause_query(self, sql: str, description: str) -> MagicMock:
        """Return a mock that isinstance-checks as TextClause."""
        query = MagicMock(spec=TextClause)
        query.__str__ = lambda _: sql
        query.description = description
        return query

    def test_returns_path(self, tmp_path):
        cursor = self._make_cursor_with_description()
        conn = MagicMock()
        conn.cursor.return_value = cursor

        query = self._make_text_clause_query("SELECT ID FROM STUDENTS", "students")
        avro_path = tmp_path / "out.avro"

        # ConfigurableResource is a frozen Pydantic model — patch on the class
        with patch(
            "teamster.libraries.powerschool.sis.odbc.resources.PowerSchoolODBCResource.result_to_avro",
            return_value=avro_path,
        ) as mock_r2a:
            resource = _make_resource()
            result = resource.execute_query(
                connection=conn,
                query=query,
                output_format="avro",
                batch_size=100,
            )

        mock_r2a.assert_called_once()
        assert result is avro_path

    def test_result_to_avro_called_with_batch_size(self, tmp_path):
        cursor = self._make_cursor_with_description()
        conn = MagicMock()
        conn.cursor.return_value = cursor

        query = self._make_text_clause_query("SELECT ID FROM STUDENTS", "students")
        avro_path = tmp_path / "out.avro"

        with patch(
            "teamster.libraries.powerschool.sis.odbc.resources.PowerSchoolODBCResource.result_to_avro",
            return_value=avro_path,
        ) as mock_r2a:
            resource = _make_resource()
            resource.execute_query(
                connection=conn,
                query=query,
                output_format="avro",
                batch_size=42,
            )

        call_kwargs = mock_r2a.call_args.kwargs
        assert call_kwargs["batch_size"] == 42
        assert call_kwargs["cursor"] is cursor
