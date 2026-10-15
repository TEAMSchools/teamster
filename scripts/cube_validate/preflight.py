"""Preflight: free checks before anything costs money or touches Tableau."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

from . import cells
from .capture_cube import row_queries, scope_query

BQ_PROJECT = "teamster-332318"
_INT = re.compile(r"^-?\d+$")


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


def estimate(cube, bq, queries: list[tuple[str, dict]]) -> dict:
    """Compiles each query through Cube's /sql and dry-runs it on BigQuery.

    A query with ``total`` set makes Cube run a second count query, so its
    bytes count twice.
    """
    total, tables, sqls = 0, set(), {}
    for qid, q in queries:
        sql, params = cube.sql(q)
        n, refs = bq.dry_run(sql, params)
        total += n * (2 if q.get("total") else 1)
        tables |= refs
        sqls[qid] = sql
    return {"bytes": total, "tables": sorted(tables), "sql": sqls, "skipped": []}


def clock_map(bq, tables) -> dict[str, str]:
    """Each base table's last-modified time (UTC)."""
    return {t: bq.modified(t) for t in sorted(tables)}


def changed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Tables whose modified time differs between two clock maps."""
    return sorted(t for t in after if before.get(t) != after[t])
