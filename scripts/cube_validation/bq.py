"""Read-only BigQuery access: table kinds, view history, dry-run pricing.

Only SELECTs and dry runs are issued. `Warehouse` is the catalog `as_of` needs.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from google.cloud import bigquery

from .timetravel import PROJECT, TableInfo

USD_PER_TIB = 6.25
_TIB = 2**40
_VIEW_HEAD = re.compile(
    r"create\s+(?:or\s+replace\s+)?(?:materialized\s+)?view\s+"
    r"(?:if\s+not\s+exists\s+)?[`\w.-]+",
    re.IGNORECASE,
)
_OPTIONS = re.compile(r"\s*options\s*\(", re.IGNORECASE)
_AS = re.compile(r"\s*as\b", re.IGNORECASE)
# dbt prepends a `/* {...} */` query comment to every statement.
_LEADING_COMMENTS = re.compile(r"\A\s*(?:/\*.*?\*/\s*)+", re.DOTALL)


class CostCapError(RuntimeError):
    """Summed dry-run prices passed the cap set by `Warehouse.budget`."""


class ViewHistoryError(RuntimeError):
    """No record of how a view was defined at the requested moment."""


class Warehouse:
    """Catalog and query access to the `teamster-332318` project."""

    def __init__(self, client: bigquery.Client | None = None) -> None:
        self._client = client or bigquery.Client(project=PROJECT)
        self._cap: float | None = None
        self._spent = 0.0

    def table(self, ds: str, name: str) -> TableInfo:
        """Return the kind of `ds.name` and, for a view, its current SQL."""
        t = self._client.get_table(f"{PROJECT}.{ds}.{name}")

        if t.table_type == "VIEW":
            return TableInfo("VIEW", t.view_query)

        if t.table_type == "EXTERNAL":
            return TableInfo("EXTERNAL", None)

        return TableInfo("TABLE", None)

    def view_sql_as_of(self, ds: str, name: str, ts: datetime) -> str:
        """Return the SQL body of view `ds.name` as it stood at `ts`.

        Raises:
            ViewHistoryError: the view changed after `ts` and no earlier
                successful `CREATE_VIEW` job is on record.
        """
        t = self._client.get_table(f"{PROJECT}.{ds}.{name}")

        if t.modified <= ts:
            return t.view_query.strip().rstrip(";").rstrip()

        rows = self.rows(
            "SELECT query "
            f"FROM `{PROJECT}`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
            "WHERE statement_type = 'CREATE_VIEW' AND state = 'DONE' "
            "AND error_result IS NULL "
            f"AND destination_table.dataset_id = '{ds}' "
            f"AND destination_table.table_id = '{name}' "
            f"AND start_time < TIMESTAMP '{_literal(ts)}' "
            "ORDER BY start_time DESC LIMIT 1"
        )

        if not rows:
            raise ViewHistoryError(
                f"no CREATE_VIEW job for {ds}.{name} before {_literal(ts)}"
            )

        return _view_body(rows[0]["query"])

    def price(self, sql: str) -> float:
        """Return the USD cost of `sql` from a dry run, without running it.

        Raises:
            CostCapError: inside `budget`, the running total passed the cap.
        """
        config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self._client.query(sql, job_config=config)
        usd = (job.total_bytes_processed or 0) / _TIB * USD_PER_TIB
        self._spent += usd

        if self._cap is not None and self._spent > self._cap:
            raise CostCapError(
                f"spent ${self._spent:.2f}, over the ${self._cap:.2f} cap"
            )

        return usd

    def rows(self, sql: str) -> list[dict]:
        """Run `sql` and return its rows; priced first when a budget is open."""
        if self._cap is not None:
            self.price(sql)

        return [dict(r.items()) for r in self._client.query(sql).result()]

    @contextmanager
    def budget(self, max_usd: float) -> Iterator[None]:
        """Raise `CostCapError` once summed prices inside the block pass the cap."""
        self._cap, self._spent = max_usd, 0.0

        try:
            yield
        finally:
            self._cap = None


def _literal(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")


def _close_paren(text: str, open_at: int) -> int:
    depth, quote, i = 0, "", open_at

    while i < len(text):
        ch = text[i]

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

    raise ViewHistoryError("unbalanced parenthesis in CREATE VIEW statement")


def _view_body(ddl: str) -> str:
    """Return the SELECT after the `AS` that follows the view name or OPTIONS."""
    text = _LEADING_COMMENTS.sub("", ddl).strip()
    head = _VIEW_HEAD.match(text)

    if head is None:
        raise ViewHistoryError(f"not a CREATE VIEW statement: {ddl[:60]!r}")

    pos = head.end()

    if opts := _OPTIONS.match(text, pos):
        pos = _close_paren(text, opts.end() - 1) + 1

    if (kw := _AS.match(text, pos)) is None:
        raise ViewHistoryError(f"no AS after view header: {text[pos : pos + 40]!r}")

    return text[kw.end() :].strip().rstrip(";").rstrip()
