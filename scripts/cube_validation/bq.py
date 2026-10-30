"""Read-only BigQuery access: table kinds, view history, dry-run pricing.

Only SELECTs, dry runs and session temp tables (`Warehouse.freeze`) are
issued. `Warehouse` is the catalog `as_of` needs.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.api_core.exceptions import GoogleAPIError
from google.cloud import bigquery

from .timetravel import PROJECT, TableInfo, closing_paren, utc_literal

USD_PER_TIB = 6.25
_TIB = 2**40
JOBS_RETENTION_DAYS = 180
VIEW_HISTORY_DAYS = (3, 30, JOBS_RETENTION_DAYS)
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
    """Summed prices passed the run's cap (`Warehouse.budget`) or the day's cap
    (`Warehouse.configure_local`)."""


class ViewHistoryError(RuntimeError):
    """No record of how a view was defined at the requested moment."""


class Warehouse:
    """Catalog and query access to the `teamster-332318` project."""

    def __init__(self, client: bigquery.Client | None = None) -> None:
        self._client = client or bigquery.Client(project=PROJECT)
        self._cap: float | None = None
        self._spent = 0.0
        self._views: dict[tuple[str, str], list[tuple[datetime, datetime, str]]] = {}
        # A relation's kind and current definition, looked up once per process:
        # `view_sql_as_of` reads a past moment, which a later change cannot alter.
        self._tables: dict[tuple[str, str], bigquery.Table] = {}
        self._cache_dir: Path | None = None
        self._ledger_dir: Path | None = None
        self._daily_cap: float | None = None
        # The open session's id and its temp tables, inside `session`.
        self._session_id: str | None = None
        self._in_session = False
        self._frozen = 0

    def configure_local(
        self, cache_dir: Path, daily_cap: float | None, ledger_dir: Path | None = None
    ) -> None:
        """Keep view versions and each day's spend on disk, shared by every run.

        A view version found once is never looked up again: the definition in
        force over a past span cannot change. A query that would take the
        day's priced total (UTC day) past `daily_cap` USD is refused before it
        runs, whichever run asks. The day's spend sits in `ledger_dir` (the
        cache by default), so runs on another cache still share one cap.
        """
        self._cache_dir = Path(cache_dir)
        self._ledger_dir = Path(ledger_dir) if ledger_dir is not None else None
        self._daily_cap = daily_cap
        for key, spans in _read_json(self._cache_dir / _VIEWS_FILE, {}).items():
            dataset, name = key.split(".", 1)
            known = self._views.setdefault((dataset, name), [])
            known += [
                (datetime.fromisoformat(a), datetime.fromisoformat(b), body)
                for a, b, body in spans
            ]

    def _get_table(self, dataset: str, name: str) -> bigquery.Table:
        key = (dataset, name)
        if key not in self._tables:
            self._tables[key] = self._client.get_table(f"{PROJECT}.{dataset}.{name}")
        return self._tables[key]

    def table(self, dataset: str, name: str) -> TableInfo:
        """Return the kind of `dataset.name` and, for a view, its SQL when first read."""
        t = self._get_table(dataset, name)

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
        spans = self._views.get((dataset, name), [])
        for since, at, body in spans:
            if since < ts <= at:
                return body

        t = self._get_table(dataset, name)

        if t.modified is not None and t.modified <= ts:
            return (t.view_query or "").strip().rstrip(";").rstrip()

        earlier = [span for span in spans if span[1] < ts]
        if earlier:
            # A known version held until `until`: only a job created since then
            # can have replaced it, so scan just those days.
            since, until, body = max(earlier, key=lambda span: span[1])
            row = self._latest_create_view(
                dataset, name, ts, f"creation_time >= TIMESTAMP '{utc_literal(until)}'"
            )
            if row:
                since = row.get("start_time") or ts - timedelta.resolution
                body = _view_body(row["query"])
        else:
            since, body = self._view_from_jobs(dataset, name, ts)
        spans.append((since, ts, body))
        self._views[(dataset, name)] = spans
        self._save_views()
        return body

    def _save_views(self) -> None:
        if self._cache_dir is None:
            return
        _write_json(
            self._cache_dir / _VIEWS_FILE,
            {
                f"{dataset}.{name}": [
                    [a.isoformat(), b.isoformat(), body] for a, b, body in spans
                ]
                for (dataset, name), spans in self._views.items()
            },
        )

    def _latest_create_view(
        self, dataset: str, name: str, ts: datetime, window: str
    ) -> dict | None:
        """The latest successful `CREATE_VIEW` job before `ts` inside `window`."""
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
            f"AND {window} "
            "ORDER BY start_time DESC LIMIT 1"
        )
        return rows[0] if rows else None

    def _view_from_jobs(
        self, dataset: str, name: str, ts: datetime
    ) -> tuple[datetime, str]:
        """Return the start and body of the latest `CREATE_VIEW` job before `ts`."""
        # The price of a JOBS_BY_PROJECT read grows with the days it spans, and
        # dbt recreates most views on every build, so look back a few days,
        # then a month, before paying for the whole retention.
        for days in VIEW_HISTORY_DAYS:
            row = self._latest_create_view(
                dataset,
                name,
                ts,
                f"creation_time >= TIMESTAMP_SUB(TIMESTAMP '{utc_literal(ts)}', "
                f"INTERVAL {days} DAY)",
            )
            if row:
                # No start means no interval to reuse: only `ts` itself.
                since = row.get("start_time") or ts - timedelta.resolution
                return since, _view_body(row["query"])

        raise ViewHistoryError(
            f"no CREATE_VIEW job for {dataset}.{name} before {utc_literal(ts)}"
        )

    def estimate(self, sql: str) -> float:
        """Return the USD cost of `sql` from a dry run, counted against no cap.

        For a query someone else runs outside the validator; `price` is the
        one that counts.
        """
        config = bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False, **self._session_settings(sql)
        )
        job = self._client.query(sql, job_config=config)
        return (job.total_bytes_processed or 0) / _TIB * USD_PER_TIB

    def _session_settings(self, sql: str) -> dict:
        """The open session, for a query that reads one of its temp tables.

        Only those join it: a session runs 1 query at a time, and the rest
        (the trace's dry runs among them) run concurrently.
        """
        if self._session_id is None or _SESSION_REF not in sql:
            return {}
        return {
            "connection_properties": [
                bigquery.ConnectionProperty("session_id", self._session_id)
            ]
        }

    @contextmanager
    def session(self) -> Iterator[None]:
        """Let `freeze` keep temp tables until the block ends, then drop them.

        BigQuery ends an abandoned session itself after 24 hours idle.
        """
        self._in_session = True
        try:
            yield
        finally:
            self._in_session = False
            session_id, self._session_id = self._session_id, None
            if session_id is not None:
                config = bigquery.QueryJobConfig(
                    connection_properties=[
                        bigquery.ConnectionProperty("session_id", session_id)
                    ]
                )
                try:
                    self._client.query(
                        "CALL BQ.ABORT_SESSION()", job_config=config
                    ).result()
                except GoogleAPIError:
                    pass

    def freeze(self, sql: str, timeout_s: float | None = None) -> str:
        """Save `sql`'s rows in a temp table of the session; return its name.

        The rows stay in BigQuery and are read back by name in later queries
        of the session (`rows`, `estimate`), each time without running `sql`
        again. Call inside `session`, and price `sql` first: it bills as
        `rows` does.

        Raises:
            RuntimeError: Called outside `session`.
            CostCapError: As `rows`.
        """
        if not self._in_session:
            raise RuntimeError("freeze needs an open session (Warehouse.session)")
        self._frozen += 1
        name = f"{_SESSION_REF}unmatched_{self._frozen}"
        self.rows(f"CREATE TEMP TABLE {name} AS\n{sql}", timeout_s)
        return name

    def price(self, sql: str) -> float:
        """Return the USD cost of `sql` from a dry run, without running it.

        Raises:
            CostCapError: inside `budget`, the running total passed the cap.
        """
        usd = self.estimate(sql)
        if self._daily_cap is not None:
            today = self.spent_today()
            if today + usd > self._daily_cap:
                raise CostCapError(
                    f"today's validator spend is ${today:.2f}; this query "
                    f"(${usd:.2f}) would pass the ${self._daily_cap:.2f} daily cap "
                    "(UTC day). Wait for tomorrow or raise --max-usd-per-day."
                )
        self._spent += usd

        if self._cap is not None and self._spent > self._cap:
            raise CostCapError(
                f"spent ${self._spent:.2f}, over the ${self._cap:.2f} cap"
            )

        self._record(usd)
        return usd

    def refuse_past_caps(self, usd: float) -> None:
        """Refuse before running queries whose dry-run total is `usd`.

        Counts nothing: each query counts what it bills once it runs.

        Raises:
            CostCapError: `usd` more would pass the run's cap or the day's.
        """
        if self._daily_cap is not None:
            today = self.spent_today()
            if today + usd > self._daily_cap:
                raise CostCapError(
                    f"today's validator spend is ${today:.2f}; these queries "
                    f"(${usd:.2f}) would pass the ${self._daily_cap:.2f} daily cap "
                    "(UTC day). Wait for tomorrow or raise --max-usd-per-day."
                )
        if self._cap is not None and self._spent + usd > self._cap:
            raise CostCapError(
                f"spent ${self._spent:.2f}; these queries (${usd:.2f}) would pass "
                f"the ${self._cap:.2f} cap"
            )

    def spent_today(self) -> float:
        """USD priced or billed today (UTC) by every run sharing this cache."""
        ledger = self._ledger
        if ledger is None:
            return 0.0
        return float(_read_json(ledger / _SPEND_FILE, {}).get(_today(), 0.0))

    @property
    def _ledger(self) -> Path | None:
        return self._ledger_dir or self._cache_dir

    def _record(self, usd: float) -> None:
        if self._ledger is None or not usd:
            return
        path = self._ledger / _SPEND_FILE
        ledger = _read_json(path, {})
        ledger[_today()] = ledger.get(_today(), 0.0) + usd
        _write_json(path, ledger)

    @property
    def spent(self) -> float:
        """USD priced or billed since the latest `budget` opened."""
        return self._spent

    def rows(self, sql: str, timeout_s: float | None = None) -> list[dict]:
        """Run `sql` and return its rows.

        With a run or daily cap set, BigQuery is told the most it may bill
        (`maximum_bytes_billed`, what is left under the tighter cap) and
        refuses a query that would bill more before it runs, at no charge; no
        dry run is needed. The bytes it billed count in both totals. With
        `timeout_s`, BigQuery stops the job after that many seconds and the
        call raises, counting what the job billed before it stopped.

        The daily total counts a query once it ends, so 2 processes sharing a
        ledger can each be allowed what is left while the other's query runs;
        each run's own cap still bounds what it adds.

        Raises:
            CostCapError: Nothing is left under a cap, or BigQuery refused the
                query as billing more than what is left.
        """
        left = self._left()
        settings: dict = {}
        if timeout_s is not None:
            settings["job_timeout_ms"] = int(timeout_s * 1000)
        if left is not None:
            usd, which = left
            if usd <= 0:
                raise CostCapError(f"nothing is left under {which}")
            settings["maximum_bytes_billed"] = int(usd / USD_PER_TIB * _TIB)
        settings |= self._session_settings(sql)
        if self._in_session and self._session_id is None and _SESSION_REF in sql:
            settings["create_session"] = True
        config = bigquery.QueryJobConfig(**settings) if settings else None
        job = self._client.query(sql, job_config=config)
        try:
            out = [dict(r.items()) for r in job.result()]
            if settings.get("create_session"):
                self._session_id = getattr(job.session_info, "session_id", None)
        except GoogleAPIError as exc:
            # A job stopped mid-run (a timeout) still bills what it read.
            self._count_billed(job)
            errors = getattr(exc, "errors", None) or [{}]
            if left is not None and errors[0].get("reason") == _OVER_LIMIT:
                raise CostCapError(
                    f"this query would bill more than the ${left[0]:.2f} left under "
                    f"{left[1]}"
                ) from exc
            # The id finds the job's own record; the message can quote values.
            setattr(exc, JOB_ID, getattr(job, "job_id", ""))
            raise
        self._count_billed(job)
        return out

    def _count_billed(self, job) -> None:
        """Count the bytes a finished or failed job billed in both totals."""
        try:
            if (
                hasattr(job, "reload")
                and getattr(job, "total_bytes_billed", None) is None
            ):
                job.reload()
        except GoogleAPIError:
            return
        billed = getattr(job, "total_bytes_billed", None)
        if isinstance(billed, int):
            usd = billed / _TIB * USD_PER_TIB
            self._spent += usd
            self._record(usd)

    def _left(self) -> tuple[float, str] | None:
        """USD left under the tighter of the run's and the day's caps, and its name."""
        left = []
        if self._cap is not None:
            left.append((self._cap - self._spent, f"the ${self._cap:.2f} cap"))
        if self._daily_cap is not None:
            left.append(
                (
                    self._daily_cap - self.spent_today(),
                    f"the ${self._daily_cap:.2f} daily cap (UTC day); wait for "
                    "tomorrow or raise --max-usd-per-day",
                )
            )
        return min(left, key=lambda pair: pair[0]) if left else None

    @contextmanager
    def budget(self, max_usd: float) -> Iterator[None]:
        """Raise `CostCapError` once summed prices inside the block pass the cap."""
        self._cap, self._spent = max_usd, 0.0

        try:
            yield
        finally:
            self._cap = None


_VIEWS_FILE = "view-history.json"
# How a query names a temp table of its session.
_SESSION_REF = "_SESSION."
# BigQuery's reason for a query over its `maximum_bytes_billed`.
_OVER_LIMIT = "bytesBilledLimitExceeded"
_SPEND_FILE = "spend.json"
# The attribute `rows` sets on a query's error: its BigQuery job id.
JOB_ID = "job_id"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def _write_json(path: Path, data) -> None:
    """Replace `path` whole, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


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
