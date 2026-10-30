"""Rewrite SQL so it reads the warehouse as it stood at one moment.

Base tables get `FOR SYSTEM_TIME AS OF`, views are replaced by their own SQL
(as of the same moment, rewritten in turn), and the wall-clock functions are
pinned to that moment. External tables cannot be time-travelled; they are left
as is and reported in `AsOf.live`. The module is pure: the catalog is passed in.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

PROJECT = "teamster-332318"
MAX_VIEW_DEPTH = 12

# A word after a table that starts the next clause, not an alias.
_NOT_ALIAS = (
    "where|join|left|right|inner|full|cross|natural|on|using|group|order|union|"
    "intersect|except|limit|qualify|having|window|for|tablesample|pivot|unpivot|"
    "select|from|with|and|or|when|then|else|end|is|in|not|as"
)
# dbt writes `project`.`dataset`.`table`; a leading quote means the ref sits in a
# string literal (dbt's union_relations), which must stay untouched. The alias
# may come without `as`, as `dbt_utils.deduplicate` writes it.
_DBT_REF = re.compile(
    r"(?<!')`" + re.escape(PROJECT) + r"`\.`(?P<d_ds>\w+)`\.`(?P<d_t>\w+)`"
    r"(?P<d_alias>\s+as\s+`?\w+`?|\s+(?!(?:" + _NOT_ALIAS + r")\b)`?\w+`?)?",
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
    r"\bcurrent_(?P<kind>date|datetime|timestamp|time)\b", re.IGNORECASE
)
# A FROM or JOIN followed by a dotted name, whether or not a pattern above
# understands it; any such name no pattern covers is refused, not skipped.
_REF_CANDIDATE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?P<tok>[`\w-]+(?:\.[`\w-]+)+)", re.IGNORECASE
)
_UNNEST = re.compile(r",\s*unnest\s*\(", re.IGNORECASE)
# BigQuery takes no `FOR SYSTEM_TIME AS OF` between a table and its PIVOT.
_PIVOT_NEXT = re.compile(r"\s*(?:un)?pivot\b", re.IGNORECASE)
# `extract(day from d.col)` and `is distinct from d.col` are not table refs.
_NOT_A_TABLE = re.compile(
    r"(?:extract\s*\(\s*\w+|distinct|trim\s*\([^()]*?'[^()]*?')\s+$", re.IGNORECASE
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


def utc_literal(ts: datetime) -> str:
    """Return `ts` as a UTC BigQuery timestamp literal body, microseconds kept.

    Raises:
        ValueError: `ts` is naive.
    """
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("timestamp is naive; pass an aware datetime")

    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00:00")


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
    literal = utc_literal(ts)
    out: list[str] = []
    pos = 0

    while match := _CLOCK.search(sql, pos):
        kind = match["kind"].lower()
        end = match.end()
        tz = ""
        j = end

        while j < len(sql) and sql[j].isspace():
            j += 1

        if j < len(sql) and sql[j] == "(":
            close = closing_paren(sql, j)
            tz = pin_clock(sql[j + 1 : close].strip(), ts)
            end = close + 1

        if kind == "timestamp":
            new = f"timestamp '{literal}'"
        else:
            new = f"{kind}(timestamp '{literal}'" + (f", {tz}" if tz else "") + ")"

        out.append(sql[pos : match.start()])
        out.append(new)
        pos = end

    out.append(sql[pos:])

    return "".join(out)


def strip_comments(sql: str) -> str:
    """Drop `--`, `#` and `/* */` comments, leaving quoted text and line breaks."""
    out: list[str] = []
    quote, i = "", 0

    while i < len(sql):
        ch = sql[i]

        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < len(sql):
                out.append(sql[i + 1])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
            out.append(ch)
        elif sql.startswith("--", i) or ch == "#":
            end = sql.find("\n", i)
            i = len(sql) if end == -1 else end
            continue
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = len(sql) if end == -1 else end + 2
            out.append(" ")
            continue
        else:
            out.append(ch)

        i += 1

    return "".join(out)


def closing_paren(sql: str, open_at: int) -> int:
    """Return the index of the `)` that closes the `(` at `open_at`.

    Quoted text and backtick identifiers are skipped, with backslash escapes.
    """
    depth, quote, i = 0, "", open_at

    while i < len(sql):
        ch = sql[i]

        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1

            if depth == 0:
                return i

        i += 1

    raise ValueError(
        f"unbalanced parenthesis in SQL near: {sql[open_at : open_at + 40]!r}"
    )


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
    literal = utc_literal(ts)
    tables: set[str] = set()
    live: set[str] = set()

    def rewrite(text: str, depth: int) -> str:
        if depth > MAX_VIEW_DEPTH:
            raise ValueError(f"view depth exceeds {MAX_VIEW_DEPTH}")

        # A ref in a comment (dbt's `-- depends_on:`) is read by nothing.
        text = strip_comments(text)
        _refuse_unmatched(text)

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
            pinned = f"`{PROJECT}.{ds}.{name}`"
            at = f"FOR SYSTEM_TIME AS OF TIMESTAMP '{literal}'"

            if _PIVOT_NEXT.match(match.string, match.end()):
                # trunk-ignore(bandit/B608): the table name is parsed from the query and the timestamp is a formatted literal
                inner = f"(SELECT * FROM {pinned} {at})"
                return f"{prefix}{inner}{_as(alias) if alias else ''}"

            return f"{prefix}{pinned}{alias} {at}"

        return _REF.sub(replace, text)

    rewritten = rewrite(pin_clock(sql, ts), 0)

    if left := _CLOCK.search(rewritten):
        raise ValueError(f"unpinned clock function left in SQL: {left[0]!r}")

    return AsOf(
        sql=rewritten,
        tables=frozenset(tables),
        live=frozenset(live),
    )


def repin(sql: str, tables: Iterable[str], old: datetime, new: datetime) -> str:
    """Move some tables of `as_of` output from moment `old` to moment `new`.

    BigQuery refuses a query that reads 1 table at 2 moments. A query joining
    2 sides rewritten at different moments moves the shared tables of 1 side;
    the caller first checks those tables did not change between the moments.

    Args:
        sql: Output of `as_of(..., old, ...)`.
        tables: `dataset.table` names to move.
        old: The moment `sql` reads them at.
        new: The moment to read them at instead.
    """
    for key in tables:
        pattern = re.compile(
            "("
            + re.escape(f"`{PROJECT}.{key}`")
            + r"(?:\s+as\s+`?\w+`?)?"
            + r" FOR SYSTEM_TIME AS OF TIMESTAMP ')"
            + re.escape(utc_literal(old))
            + "'",
            re.IGNORECASE,
        )
        sql = pattern.sub(lambda m: f"{m[1]}{utc_literal(new)}'", sql)
    return sql


def _as(alias: str) -> str:
    """Return a view's alias clause with a single leading space."""
    return " " + alias.strip()


def _refuse_unmatched(text: str) -> None:
    """Raise if `text` reads a table the rewrite patterns would silently skip."""
    covered = [m.span() for m in _REF.finditer(text)]

    for cand in _REF_CANDIDATE.finditer(text):
        start = cand.start("tok")

        if any(a <= start < b for a, b in covered):
            continue

        if _NOT_A_TABLE.search(text[: cand.start()]):
            continue

        raise ValueError(
            f"table reference not recognized: {cand['tok']!r}; write it as dbt "
            f"compiles it, each part in its own backticks: `{PROJECT}`.`<dataset>`"
            ".`<table>`"
        )

    for _, end in covered:
        # `, unnest(...)` reads an array of the row, not another table.
        after = text[end:].lstrip()
        if after.startswith(",") and not _UNNEST.match(after):
            raise ValueError(
                "comma-joined FROM list is not supported; "
                f"near: {text[max(end - 30, 0) : end + 30]!r}"
            )
