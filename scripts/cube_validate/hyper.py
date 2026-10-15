"""Read and write .hyper files with the Hyper API, added per run with --with."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

EXTRACT_TABLE = '"Extract"."Extract"'


def _api():
    # trunk-ignore(pyright/reportMissingImports): added per run with uv run --with
    import tableauhyperapi

    return tableauhyperapi


def _sql_type(api, name: str):
    return {
        "text": api.SqlType.text(),
        "double": api.SqlType.double(),
        "bigint": api.SqlType.big_int(),
        "date": api.SqlType.date(),
        "bool": api.SqlType.bool(),
    }[name]


def _py(v):
    """Hyper's Date and Timestamp values as Python's."""
    for attr in ("to_date", "to_datetime"):
        if hasattr(v, attr):
            return getattr(v, attr)()
    return v


def write_table(
    path: Path,
    schema: str,
    table: str,
    columns: list[tuple[str, str]],
    rows: Iterable[Sequence],
) -> int:
    """Write one table to a new .hyper file, replacing any file at path.

    Args:
        path: The .hyper file to create.
        schema: Schema name, e.g. "cube".
        table: Table name, e.g. "rows".
        columns: (name, type) pairs; type is text, double, bigint, date or bool.
        rows: Row values in column order.

    Returns:
        The number of rows written.
    """
    api = _api()
    definition = api.TableDefinition(
        api.TableName(schema, table),
        [
            api.TableDefinition.Column(n, _sql_type(api, t), api.NULLABLE)
            for n, t in columns
        ],
    )
    n = 0
    with api.HyperProcess(api.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with api.Connection(
            hp.endpoint, str(path), api.CreateMode.CREATE_AND_REPLACE
        ) as con:
            con.catalog.create_schema(schema)
            con.catalog.create_table(definition)
            with api.Inserter(con, definition) as ins:
                for r in rows:
                    ins.add_row(list(r))
                    n += 1
                ins.execute()
    return n


class Workspace:
    """A Hyper session over a scratch database, with other files attached.

    Args:
        scratch: The database created (replaced) for this session's tables.
        attach: Alias to .hyper file; query them as "<alias>"."<schema>"."<table>".
    """

    def __init__(self, scratch: Path, attach: dict[str, Path]):
        self.scratch, self.attach = Path(scratch), dict(attach)

    def __enter__(self) -> Workspace:
        api = _api()
        self._hp = api.HyperProcess(api.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU)
        self._con = api.Connection(
            self._hp.endpoint, str(self.scratch), api.CreateMode.CREATE_AND_REPLACE
        )
        for alias, path in self.attach.items():
            self._con.catalog.attach_database(str(path), alias=alias)
        return self

    def __exit__(self, *exc) -> None:
        self._con.close()
        self._hp.close()

    def execute(self, sql: str) -> None:
        self._con.execute_command(sql)

    def query(self, sql: str) -> list[tuple]:
        with self._con.execute_query(sql) as result:
            return [tuple(_py(v) for v in r) for r in result]

    def dicts(self, sql: str) -> list[dict]:
        with self._con.execute_query(sql) as result:
            names = [c.name.unescaped for c in result.schema.columns]
            return [dict(zip(names, (_py(v) for v in r), strict=True)) for r in result]

    def columns(self, alias: str, schema: str, table: str) -> list[str]:
        api = _api()
        d = self._con.catalog.get_table_definition(api.TableName(alias, schema, table))
        return [c.name.unescaped for c in d.columns]

    def count(self, from_where: str) -> int:
        """count(*) over `<table> [where ...]`."""
        # trunk-ignore(bandit/B608): from_where is a table and filter written by the caller in code, never user input
        return int(self.query(f"select count(*) from {from_where}")[0][0])
