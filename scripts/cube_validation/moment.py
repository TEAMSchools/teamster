"""Choose the warehouse moment to validate against and detect drift around it."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from .timetravel import PROJECT, utc_literal

WINDOW = timedelta(days=7)
_MARGIN = timedelta(hours=1)


class MomentError(RuntimeError):
    """No usable build to pin the validation to."""


@dataclass(frozen=True)
class Build:
    start: datetime
    end: datetime
    job_id: str


class _Rows(Protocol):
    def rows(self, sql: str) -> list[dict]: ...


def fact_builds(wh: _Rows, fact: str, since: datetime) -> list[Build]:
    """List successful jobs that wrote `fact` (`dataset.table`) since `since`.

    Any statement type counts: dbt builds with CREATE, MERGE and INSERT.
    """
    ds, name = fact.split(".")
    rows = wh.rows(
        "SELECT job_id, start_time, end_time "
        f"FROM `{PROJECT}`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
        f"WHERE creation_time >= TIMESTAMP '{utc_literal(since)}' "
        "AND state = 'DONE' AND error_result IS NULL "
        f"AND destination_table.dataset_id = '{ds}' "
        f"AND destination_table.table_id = '{name}' "
        "ORDER BY end_time"
    )

    return [Build(r["start_time"], r["end_time"], r["job_id"]) for r in rows]


def pick_moment(
    builds: list[Build],
    now: datetime,
    requested: datetime | None,
    fact: str = "the fact",
) -> Build:
    """Pick the build whose start is the moment to validate at.

    Args:
        builds: Successful builds, any order.
        now: The current time.
        requested: A moment asked for; picks the build ending at or before it.
        fact: Name used in the error message.

    Raises:
        MomentError: no build, none ending by `requested`, or the build began
            before time travel can reach it (7 days, less a 1 hour margin).
    """
    if not builds:
        raise MomentError(f"no successful build of {fact} in the last 7 days")

    if requested is None:
        chosen = max(builds, key=lambda b: b.end)
    else:
        eligible = [b for b in builds if b.end <= requested]

        if not eligible:
            raise MomentError(f"no build of {fact} ended at or before {requested}")

        chosen = max(eligible, key=lambda b: b.end)

    if chosen.start < now - WINDOW + _MARGIN:
        raise MomentError(
            f"build at {chosen.start} is outside the 7 days of warehouse history"
        )

    return chosen


def fingerprint(wh: _Rows, table: str, ts: datetime) -> int:
    """Return an order-independent hash of every row of `dataset.table` at `ts`."""
    ds, name = table.split(".")
    rows = wh.rows(
        "SELECT bit_xor(farm_fingerprint(to_json_string(t))) AS f "
        f"FROM `{PROJECT}`.`{ds}`.`{name}` AS t "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{utc_literal(ts)}'"
    )

    return int(rows[0]["f"] or 0)


def changed_between(
    wh: _Rows, tables: Iterable[str], t1: datetime, t2: datetime
) -> list[str]:
    """Return the tables whose contents differ between `t1` and `t2`."""
    return [t for t in tables if fingerprint(wh, t, t1) != fingerprint(wh, t, t2)]
