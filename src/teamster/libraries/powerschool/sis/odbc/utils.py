"""PowerSchool SIS ODBC shared utilities.

Context managers, timestamp formatting, partition window calculation,
and staleness evaluation logic shared across assets, schedules, and sensors.
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import MonthlyPartitionsDefinition, TimeWindowPartitionsDefinition
from dateutil.relativedelta import relativedelta
from sqlalchemy import text

from teamster.core.utils.classes import FiscalYearPartitionsDefinition


@contextmanager
def powerschool_connection(
    ssh_resource, db_resource, log
) -> Generator[object, None, None]:
    """Open an SSH tunnel and Oracle connection, with guaranteed cleanup.

    Opens the SSH tunnel first, then the database connection. On success,
    yields the connection. Cleans up both on exit.

    If the connection fails, the tunnel is killed immediately. If an error
    occurs during query execution, it is logged before re-raising. Connection
    failures propagate without logging (Dagster handles them at the run level).

    Args:
        ssh_resource: SSHResource with open_ssh_tunnel() method.
        db_resource: PowerSchoolODBCResource with connect() method.
        log: Dagster logger (context.log).

    Yields:
        Open oracledb.Connection.
    """
    log.info(f"Opening SSH tunnel to {ssh_resource.remote_host}")
    ssh_tunnel = ssh_resource.open_ssh_tunnel()
    try:
        connection = db_resource.connect()
    except Exception:
        ssh_tunnel.kill()
        raise
    try:
        yield connection
    except Exception:
        log.exception("PowerSchool ODBC error")
        raise
    finally:
        connection.close()
        ssh_tunnel.kill()


def format_oracle_timestamp(timestamp: float, tz: ZoneInfo) -> str:
    """Convert a Unix timestamp to an Oracle-compatible ISO string.

    Produces a timezone-naive ISO string at microsecond precision, suitable
    for Oracle's TO_TIMESTAMP function.

    Args:
        timestamp: Unix timestamp (seconds since epoch).
        tz: Timezone to localize the timestamp before stripping tzinfo.

    Returns:
        ISO 8601 string without timezone, e.g. '2024-07-01T12:00:00.000000'.
    """
    return (
        datetime.fromtimestamp(timestamp, tz=tz)
        .replace(tzinfo=None)
        .isoformat(timespec="microseconds")
    )


def get_partition_window(
    partition_key: str, partitions_def: TimeWindowPartitionsDefinition
) -> tuple[str, str]:
    """Compute Oracle-compatible ISO timestamp bounds for a partition window.

    Args:
        partition_key: ISO date string for the partition start (e.g. '2024-07-01').
        partitions_def: Dagster partitions definition (FiscalYear or Monthly).

    Returns:
        Tuple of (start_value, end_value) as timezone-naive ISO strings at
        microsecond precision.

    Raises:
        TypeError: If partitions_def is not FiscalYearPartitionsDefinition or
            MonthlyPartitionsDefinition.
    """
    partition_start = datetime.fromisoformat(partition_key)

    if isinstance(partitions_def, FiscalYearPartitionsDefinition):
        date_add = relativedelta(years=1)
    elif isinstance(partitions_def, MonthlyPartitionsDefinition):
        date_add = relativedelta(months=1)
    else:
        raise TypeError(
            f"Unsupported partitions_def type: {type(partitions_def).__name__}"
        )

    partition_end = (partition_start + date_add - relativedelta(days=1)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )

    start_value = partition_start.replace(tzinfo=None).isoformat(
        timespec="microseconds"
    )
    end_value = partition_end.replace(tzinfo=None).isoformat(timespec="microseconds")

    return start_value, end_value


def get_query_text(
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
):
    """Build a SQLAlchemy text clause for an Oracle COUNT query.

    Args:
        table: Oracle table name.
        column: Column to filter on. None for full table count.
        start_value: ISO timestamp string for >= or BETWEEN start.
        end_value: ISO timestamp string for BETWEEN end. Requires start_value.

    Returns:
        SQLAlchemy TextClause wrapping the COUNT query.
    """
    # TODO: paramterize sqlalchemy query to resolve bandit/B608
    if column is None:
        # trunk-ignore(bandit/B608)
        query = f"SELECT COUNT(*) FROM {table}"
    elif end_value is None:
        query = (
            # trunk-ignore(bandit/B608)
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} >= "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    else:
        query = (
            # trunk-ignore(bandit/B608)
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} BETWEEN "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
            f"TO_TIMESTAMP('{end_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)
