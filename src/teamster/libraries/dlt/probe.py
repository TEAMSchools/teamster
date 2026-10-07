"""Source-agnostic probe-and-gate primitives for dlt full-replace pipelines.

A probe reads a cheap change signature for a table — `COUNT(*)` plus
`MAX(cursor_column)` — and compares it to the signature stored in dlt
`resource_state` by the last successful load. Drift selects the table for a full
`replace`; equality skips it.

Shared by `powerschool/` and `focus/`. Each library keeps its own sensor: the
connection lifecycles differ (an SSH tunnel plus an Oracle resource vs. a plain
Postgres URL), so a common sensor factory would be indirection without a payer.
"""

from dataclasses import dataclass
from datetime import date, datetime

import sqlalchemy as sa
from dagster import (
    Config,
    DagsterInstance,
    DagsterRunStatus,
    RunRecord,
    RunsFilter,
)

IN_FLIGHT_STATUSES = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


@dataclass(frozen=True)
class ProbeTable:
    """One source table's sync config.

    cursor_column None means the table has no change-tracking column. Its
    signature is then count-only, so a net row add or remove still selects it,
    but an in-place edit is caught only by the unconditional full refresh.
    """

    name: str
    cursor_column: str | None


class ProbeSignatureConfig(Config):
    """One table's probed change signature, passed by a gating sensor."""

    count: int
    max_cursor: str | None = None


def probe_signature(
    connection, table_name: str, cursor_column: str | None
) -> dict[str, int | str | None]:
    """Fetch the change signature for a table: total count + max cursor.

    Equality-compared against the stored signature; drift in either value
    (including a cursor regression) triggers a full replace. Tables without a
    cursor column are count-only — the signature still carries
    ``max_cursor: None`` so it compares equal to the run-config round-trip
    shape (which defaults the key to None). Values are JSON-serializable for
    dlt resource state.
    """
    if cursor_column is None:
        (count,) = connection.execute(
            # trunk-ignore(bandit/B608): table name from static YAML config
            sa.text(f"SELECT COUNT(*) FROM {table_name}")
        ).one()

        return {"count": int(count), "max_cursor": None}

    count, max_cursor = connection.execute(
        # trunk-ignore(bandit/B608): table/column names from static YAML config
        sa.text(f"SELECT COUNT(*), MAX({cursor_column}) FROM {table_name}")
    ).one()

    if max_cursor is None:
        max_cursor_value = None
    elif isinstance(max_cursor, (datetime, date)):
        max_cursor_value = max_cursor.isoformat()
    else:
        # Non-temporal cursor (e.g. a numeric change column); store its string
        # form so the signature stays JSON-serializable.
        max_cursor_value = str(max_cursor)

    # int(count): mirror the JSON-safe-scalar normalization done for max_cursor
    # above (the driver returns int today, but keep the state doc
    # driver-agnostic).
    return {"count": int(count), "max_cursor": max_cursor_value}


def compute_changed(
    selected: list[ProbeTable],
    current: dict[str, dict],
    stored: dict[str, dict],
) -> list[ProbeTable]:
    """Select tables whose just-probed signature differs from the stored one.

    Drift in count or max cursor — or a missing stored entry (first tick, or a
    table new to the config) — selects the table. No-cursor tables carry a
    count-only signature (``max_cursor: None``), so a net row add/remove
    selects them; in-place edits are caught by the unconditional full refresh.
    """
    return [
        table for table in selected if current.get(table.name) != stored.get(table.name)
    ]


def stored_signatures(dlt_pipeline, source_name: str) -> dict[str, dict]:
    """Read last-run per-resource signatures from dlt pipeline state."""
    resources = (
        dlt_pipeline.state.get("sources", {}).get(source_name, {}).get("resources", {})
    )
    return {
        name: res_state["signature"]
        for name, res_state in resources.items()
        if isinstance(res_state, dict) and "signature" in res_state
    }


def in_flight_run(
    instance: DagsterInstance, sensor_name: str, nightly_schedule_name: str
) -> RunRecord | None:
    """Return the first in-flight run launched by this sensor or the nightly
    schedule, or None.

    The baseline advances only on load success, so while a run launched by
    either trigger is still committing, re-selecting its tables would
    double-launch. Checked over the non-terminal status set
    (``IN_FLIGHT_STATUSES``) against the auto-applied ``dagster/sensor_name``
    and ``dagster/schedule_name`` run tags.
    """
    for tag, value in (
        ("dagster/sensor_name", sensor_name),
        ("dagster/schedule_name", nightly_schedule_name),
    ):
        records = instance.get_run_records(
            filters=RunsFilter(tags={tag: value}, statuses=IN_FLIGHT_STATUSES),
            limit=1,
        )
        if records:
            return records[0]
    return None
