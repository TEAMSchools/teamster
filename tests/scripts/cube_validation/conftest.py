import importlib.util
import sys
from pathlib import Path

import pytest

# `tests/scripts/__init__.py` makes `scripts` resolve to the test package, so
# load the package under its own top-level name instead.
_pkg_dir = Path(__file__).resolve().parents[3] / "scripts" / "cube_validation"

if "cube_validation" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "cube_validation",
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    assert _spec is not None and _spec.loader is not None
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["cube_validation"] = _module
    _spec.loader.exec_module(_module)


@pytest.fixture
def duck():
    """Run BigQuery SQL on toy tables in DuckDB, offline.

    Skipped without DuckDB: run `uv run --with duckdb pytest ...`. The SQL is
    transpiled with sqlglot; table paths and time travel are dropped, so a
    table is found by its bare name. `FARM_FINGERPRINT` is DuckDB's `hash`.
    """
    duckdb = pytest.importorskip("duckdb")
    import sqlglot
    from sqlglot import exp

    con = duckdb.connect()
    con.execute("CREATE MACRO farm_fingerprint(x) AS hash(x)")

    class Duck:
        def __init__(self):
            self.ran: list[str] = []

        def table(self, name: str, columns: str, rows: list[tuple]) -> None:
            con.execute(f"CREATE OR REPLACE TABLE {name} ({columns})")
            if rows:
                marks = ", ".join("?" for _ in rows[0])
                con.executemany(f"INSERT INTO {name} VALUES ({marks})", rows)

        def rows(self, sql: str, timeout_s=None) -> list[dict]:
            self.ran.append(sql)
            tree = sqlglot.parse_one(sql, read="bigquery")
            for t in tree.find_all(exp.Table):
                for arg in ("version", "catalog", "db"):
                    t.set(arg, None)
            cur = con.execute(tree.sql(dialect="duckdb"))
            if cur.description is None:
                return []
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]

    return Duck()
