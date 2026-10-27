"""Rewrite SQL so it reads the warehouse as it stood at one moment.

Base tables get `FOR SYSTEM_TIME AS OF`, views are replaced by their own SQL
(as of the same moment, rewritten in turn), and the wall-clock functions are
pinned to that moment. External tables cannot be time-travelled; they are left
as is and reported in `AsOf.live`. The module is pure: the catalog is passed in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

PROJECT = "teamster-332318"
MAX_VIEW_DEPTH = 12

# dbt writes `project`.`dataset`.`table`; a leading quote means the ref sits in a
# string literal (dbt's union_relations), which must stay untouched.
_DBT_REF = re.compile(
    r"(?<!')`" + re.escape(PROJECT) + r"`\.`(?P<d_ds>\w+)`\.`(?P<d_t>\w+)`"
    r"(?P<d_alias>\s+as\s+`?\w+`?)?",
    re.IGNORECASE,
)
# Cube writes `FROM dataset.table AS `alias``, with no project.
_CUBE_REF = re.compile(
    r"\b(?P<c_kw>FROM|JOIN)(?P<c_sp>\s+)(?P<c_ds>\w+)\.(?P<c_t>\w+)"
    r"\s+AS\s+(?P<c_name>`\w+`)",
    re.IGNORECASE,
)
_REF = re.compile(f"{_DBT_REF.pattern}|{_CUBE_REF.pattern}", re.IGNORECASE)

_CLOCK = re.compile(
    r"\bcurrent_(?P<kind>date|datetime|timestamp)\s*\(\s*(?P<tz>[^()]*?)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TableInfo:
    kind: Literal["TABLE", "VIEW", "EXTERNAL"]
    view_sql: str | None


@dataclass(frozen=True)
class AsOf:
    sql: str
    tables: frozenset[str]
    live: frozenset[str]


class Catalog(Protocol):
    def table(self, dataset: str, name: str) -> TableInfo: ...

    def view_sql_as_of(self, dataset: str, name: str, ts: datetime) -> str: ...


def _utc_literal(ts: datetime) -> str:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("timestamp is naive; pass an aware datetime")

    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")


def pin_clock(sql: str, ts: datetime) -> str:
    """Replace the current-date/time functions with the literal moment `ts`.

    Args:
        sql: SQL text.
        ts: Timezone-aware moment to pin to; converted to UTC.

    Returns:
        The SQL with `current_date`, `current_datetime` and `current_timestamp`
        calls replaced. A zone argument is kept as the zone of the conversion.

    Raises:
        ValueError: `ts` is naive.
    """
    literal = _utc_literal(ts)

    def replace(match: re.Match[str]) -> str:
        kind = match["kind"].lower()
        tz = match["tz"]

        if kind == "timestamp":
            return f"timestamp '{literal}'"

        args = f"timestamp '{literal}'" + (f", {tz}" if tz else "")

        return f"{'date' if kind == 'date' else 'datetime'}({args})"

    return _CLOCK.sub(replace, sql)


def as_of(sql: str, ts: datetime, catalog: Catalog) -> AsOf:
    """Rewrite `sql` to read every table and view as it stood at `ts`.

    Args:
        sql: Cube-compiled or dbt view SQL.
        ts: Timezone-aware moment; converted to UTC.
        catalog: Looks up each referenced relation and view definitions.

    Returns:
        The rewritten SQL, the `dataset.table` names of base tables read through
        time travel (across all inlined views), and the names of external tables
        read live.

    Raises:
        ValueError: `ts` is naive, or views nest deeper than 12 levels.
    """
    literal = _utc_literal(ts)
    tables: set[str] = set()
    live: set[str] = set()

    def rewrite(text: str, depth: int) -> str:
        if depth > MAX_VIEW_DEPTH:
            raise ValueError(f"view depth exceeds {MAX_VIEW_DEPTH}")

        def replace(match: re.Match[str]) -> str:
            if match["d_ds"]:
                prefix, ds, name = "", match["d_ds"], match["d_t"]
                alias = match["d_alias"] or ""
            else:
                prefix = match["c_kw"] + match["c_sp"]
                ds, name = match["c_ds"], match["c_t"]
                alias = f" AS {match['c_name']}"

            info = catalog.table(ds, name)
            key = f"{ds}.{name}"

            if info.kind == "EXTERNAL":
                live.add(key)

                return match[0]

            if info.kind == "VIEW":
                body = rewrite(
                    pin_clock(catalog.view_sql_as_of(ds, name, ts), ts), depth + 1
                )
                alias = alias or f" AS {name}"

                return f"{prefix}({body}){_as(alias)}"

            tables.add(key)

            return (
                f"{prefix}`{PROJECT}.{ds}.{name}`{alias} "
                f"FOR SYSTEM_TIME AS OF TIMESTAMP '{literal}'"
            )

        return _REF.sub(replace, text)

    return AsOf(
        sql=rewrite(pin_clock(sql, ts), 0),
        tables=frozenset(tables),
        live=frozenset(live),
    )


def _as(alias: str) -> str:
    """Return a view's alias clause with a single leading space."""
    return " " + alias.strip()
