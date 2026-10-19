"""Preflight: free checks before anything costs money or touches Tableau."""

from __future__ import annotations

import collections
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from . import cells
from .capture_cube import row_queries, scope_query

BQ_PROJECT = "teamster-332318"
# BigQuery on-demand price per TiB billed.
USD_PER_TIB = 6.25
_INT = re.compile(r"^-?\d+$")


def usd(n_bytes: float) -> float:
    """Dollars BigQuery bills on demand for scanning n_bytes."""
    return n_bytes / 1024**4 * USD_PER_TIB


class PreflightError(RuntimeError):
    """A preflight check failed; nothing was spent."""


def _in_window(t: dt.time, w) -> bool:
    if w.start <= w.end:
        return w.start <= t < w.end
    return t >= w.start or t < w.end


def check_window(now: dt.datetime, extract_at: dt.datetime, w) -> str:
    """Checks that now is inside the window and the extract is this window's refresh.

    Args:
        now: The current time.
        extract_at: When the Tableau extract last refreshed.
        w: The capture window.

    Returns:
        An empty string when fine, otherwise the reason it is not.
    """
    tz = ZoneInfo(w.tz)
    local = now.astimezone(tz)
    if not _in_window(local.time(), w):
        return (
            f"{local:%H:%M} is outside the capture window "
            f"{w.start:%H:%M}-{w.end:%H:%M} {w.tz}"
        )
    anchor_day = (
        local.date()
        if local.time() >= w.extract_after
        else local.date() - dt.timedelta(days=1)
    )
    anchor = dt.datetime.combine(anchor_day, w.extract_after, tzinfo=tz)
    if extract_at.astimezone(tz) < anchor:
        return (
            f"the extract refreshed at {extract_at.astimezone(tz):%Y-%m-%d %H:%M}, "
            f"before this window's {anchor:%Y-%m-%d %H:%M} refresh"
        )
    return ""


class BigQuery:
    """Dry runs and table metadata. Dry runs read nothing and cost nothing."""

    def __init__(self, client=None):
        if client is None:
            from google.cloud import bigquery

            client = bigquery.Client(project=BQ_PROJECT)
        self.client = client

    def _params(self, params: list, typed: bool) -> list:
        from google.cloud import bigquery

        out = []
        for p in params:
            kind = "INT64" if typed and _INT.match(str(p)) else "STRING"
            value = int(p) if kind == "INT64" else str(p)
            out.append(bigquery.ScalarQueryParameter(None, kind, value))
        return out

    def dry_run(self, sql: str, params: list) -> tuple[int, set[str]]:
        """Dry-runs a query, retrying with every parameter as a string.

        Returns:
            Bytes the query would process and the base tables it references.
        """
        from google.cloud import bigquery

        last = None
        for typed in (True, False):
            cfg = bigquery.QueryJobConfig(
                dry_run=True,
                use_query_cache=False,
                query_parameters=self._params(params, typed),
            )
            try:
                job = self.client.query(sql, job_config=cfg)
            except Exception as e:  # noqa: BLE001 - retried untyped, then reported
                last = e
                continue
            tables = {
                f"{t.project}.{t.dataset_id}.{t.table_id}"
                for t in (job.referenced_tables or [])
            }
            return int(job.total_bytes_processed or 0), tables
        raise PreflightError(f"dry run failed: {last}")

    def fingerprint(self, table: str, at: dt.datetime | None = None) -> tuple:
        """Row count and an order-free hash of every row, now or as of `at`.

        `at` reads BigQuery time travel, which survives a dbt rebuild and reaches
        back 7 days. Unlike a dry run, this scans the table.
        """
        from google.cloud import bigquery

        travel = " for system_time as of @at" if at else ""
        params = [bigquery.ScalarQueryParameter("at", "TIMESTAMP", at)] if at else []
        job = self.client.query(
            # trunk-ignore(bandit/B608): the table name comes from BigQuery's own referenced_tables
            f"select count(*), bit_xor(farm_fingerprint(to_json_string(t))) "
            f"from `{table}` as t{travel}",
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        )
        row = next(iter(job.result()))
        return int(row[0]), row[1]

    def row_hashes(self, table: str, at: dt.datetime) -> collections.Counter:
        """Each row's hash as of `at` (time travel), counted.

        Returns:
            A Counter of farm_fingerprint(to_json_string(row)) values.
        """
        from google.cloud import bigquery

        job = self.client.query(
            # trunk-ignore(bandit/B608): the table name comes from BigQuery's own referenced_tables
            f"select farm_fingerprint(to_json_string(t)) from `{table}` "
            "for system_time as of @at as t",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("at", "TIMESTAMP", at)]
            ),
        )
        return collections.Counter(int(r[0]) for r in job.result())

    def modified(self, table: str) -> str:
        """Returns the table's last-modified time as an ISO UTC string."""
        modified = self.client.get_table(table).modified
        if modified is None:
            raise PreflightError(f"{table} has no modified time")
        return modified.isoformat()


def planned_queries(checks, start: dt.date, end: dt.date) -> list[tuple[str, dict]]:
    """Every query capture will send, clicks left unfiltered (an upper bound)."""
    out = [(f"rows:{p}", q) for p, q in row_queries(checks, start, end)]
    scope = scope_query(checks)
    if scope is not None:
        out.append(("scope", scope))
    for cut in checks.cuts:
        base = cut.__class__(cut.id, cut.filters, cut.params, None)
        for sheet in checks.sheets:
            try:
                q = cells.cube_query(checks, sheet, base, {})
            except cells.MappingGap:
                continue
            # capture_answers adds total too; Cube runs a count query for it.
            out.append(
                (f"answer:{cells.answer_key(cut.id, sheet)}", {**q, "total": True})
            )
    return out


def estimate(cube, bq, queries: list[tuple[str, dict]], workers: int = 8) -> dict:
    """Compiles each query through Cube's /sql and dry-runs it on BigQuery.

    A query with ``total`` set makes Cube run a second count query, so its
    bytes count twice.
    """

    def one(item: tuple[str, dict]) -> tuple[str, str, int, set[str]]:
        qid, q = item
        sql, params = cube.sql(q)
        n, refs = bq.dry_run(sql, params)
        return qid, sql, n * (2 if q.get("total") else 1), refs

    total, tables, sqls = 0, set(), {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for qid, sql, n, refs in pool.map(one, queries):
            total += n
            tables |= refs
            sqls[qid] = sql
    return {"bytes": total, "tables": sorted(tables), "sql": sqls, "skipped": []}


def clock_map(bq, tables) -> dict[str, str]:
    """Each base table's last-modified time (UTC)."""
    return {t: bq.modified(t) for t in sorted(tables)}


def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Tables whose modified time differs between two clock maps."""
    return sorted(t for t in after if before.get(t) != after[t])


def rewritten(bq, before: dict[str, str], tables: list[str]) -> list[str]:
    """Of tables whose modified time moved, those whose rows changed too.

    A dbt rebuild that writes the same rows moves the clock but not the data.
    The earlier rows are read 1 second after the modified time the capture
    recorded. A table BigQuery cannot read back that far counts as changed.
    """
    from google.api_core import exceptions

    out = []
    for t in tables:
        at = dt.datetime.fromisoformat(before[t]) + dt.timedelta(seconds=1)
        try:
            same = bq.fingerprint(t, at) == bq.fingerprint(t)
        except exceptions.GoogleAPIError:
            same = False
        if not same:
            out.append(t)
    return out


def row_diff(bq, table: str, before: str, after: str) -> tuple[int, int]:
    """Rows in one version of a table and not the other, and the later row count.

    Each version is read 1 second after the modified time the capture recorded.

    Args:
        bq: A BigQuery with `row_hashes`.
        table: The table to compare.
        before: Its modified time at capture start (ISO).
        after: Its modified time at capture end (ISO).

    Returns:
        The rows only in the earlier version plus the rows only in the later,
        and the later version's total rows.
    """
    step = dt.timedelta(seconds=1)
    old = bq.row_hashes(table, dt.datetime.fromisoformat(before) + step)
    new = bq.row_hashes(table, dt.datetime.fromisoformat(after) + step)
    return sum((old - new).values()) + sum((new - old).values()), new.total()


def changed_rows(bq, table: str, before: str, after: str) -> int:
    """Rows in one version of a table and not the other (see `row_diff`)."""
    return row_diff(bq, table, before, after)[0]
