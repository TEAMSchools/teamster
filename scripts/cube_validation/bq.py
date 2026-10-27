"""Read-only BigQuery access: table kinds, view history, dry-run pricing.

Only SELECTs and dry runs are issued. `Warehouse` is the catalog `as_of` needs.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from google.cloud import bigquery

from .timetravel import PROJECT, TableInfo, closing_paren, utc_literal

USD_PER_TIB = 6.25
_TIB = 2**40
JOBS_RETENTION_DAYS = 180
VIEW_HISTORY_FIRST_DAYS = 3
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
        self._views: dict[tuple[str, str], list[tuple[datetime, datetime, str]]] = {}

    def table(self, dataset: str, name: str) -> TableInfo:
        """Return the kind of `dataset.name` and, for a view, its current SQL."""
        t = self._client.get_table(f"{PROJECT}.{dataset}.{name}")

        if t.table_type == "VIEW":
            return TableInfo("VIEW", t.view_query)

        if t.table_type == "EXTERNAL":
            return TableInfo("EXTERNAL", None)

        return TableInfo("TABLE", None)

    def view_sql_as_of(self, dataset: str, name: str, ts: datetime) -> str:
        """Return the SQL body of view `dataset.name` as it stood at `ts`.

        Raises:
            ViewHistoryError: the view changed after `ts` and no earlier
                successful `CREATE_VIEW` job is on record.
        """
        # A job found for moment `at` that started at `since` is also the
        # latest job for any moment in (since, at]: a later one would have
        # been found for `at`. A run reads its 2 moments seconds apart.
        for since, at, body in self._views.get((dataset, name), []):
            if since < ts <= at:
                return body

        t = self._client.get_table(f"{PROJECT}.{dataset}.{name}")

        if t.modified <= ts:
            return t.view_query.strip().rstrip(";").rstrip()

        since, body = self._view_from_jobs(dataset, name, ts)
        self._views.setdefault((dataset, name), []).append((since, ts, body))
        return body

    def _view_from_jobs(
        self, dataset: str, name: str, ts: datetime
    ) -> tuple[datetime, str]:
        """Return the start and body of the latest `CREATE_VIEW` job before `ts`."""
        # The price of a JOBS_BY_PROJECT read grows with the days it spans, and
        # dbt recreates most views on every build, so look back a few days
        # before paying for the whole retention.
        for days in (VIEW_HISTORY_FIRST_DAYS, JOBS_RETENTION_DAYS):
            rows = self.rows(
                # trunk-ignore(bandit/B608): dataset and view names come from validated config.py identifiers; values are literal-escaped
                "SELECT query, start_time "
                f"FROM `{PROJECT}`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
                "WHERE statement_type = 'CREATE_VIEW' AND state = 'DONE' "
                "AND error_result IS NULL "
                f"AND destination_table.dataset_id = '{dataset}' "
                f"AND destination_table.table_id = '{name}' "
                f"AND start_time < TIMESTAMP '{utc_literal(ts)}' "
                f"AND creation_time < TIMESTAMP '{utc_literal(ts)}' "
                f"AND creation_time >= TIMESTAMP_SUB(TIMESTAMP '{utc_literal(ts)}', "
                f"INTERVAL {days} DAY) "
                "ORDER BY start_time DESC LIMIT 1"
            )
            if rows:
                # No start means no interval to reuse: only `ts` itself.
                since = rows[0].get("start_time") or ts - timedelta.resolution
                return since, _view_body(rows[0]["query"])

        raise ViewHistoryError(
            f"no CREATE_VIEW job for {dataset}.{name} before {utc_literal(ts)}"
        )

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

    @property
    def spent(self) -> float:
        """USD priced since the latest `budget` opened."""
        return self._spent

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


def _close_paren(text: str, open_at: int) -> int:
    try:
        return closing_paren(text, open_at)
    except ValueError as exc:
        raise ViewHistoryError(
            "unbalanced parenthesis in CREATE VIEW statement"
        ) from exc


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
