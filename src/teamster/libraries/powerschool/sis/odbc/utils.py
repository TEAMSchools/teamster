"""PowerSchool SIS ODBC shared utilities.

Context managers, timestamp formatting, partition window calculation,
and staleness evaluation logic shared across assets, schedules, and sensors.
"""

import logging
import sys
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import oracledb
from dagster import (
    AssetKey,
    AssetRecordsFilter,
    AssetsDefinition,
    DagsterInstance,
    EventLogEntry,
    MonthlyPartitionsDefinition,
    TimeWindowPartitionsDefinition,
)
from dagster_shared import check
from dateutil.relativedelta import relativedelta
from sqlalchemy import TextClause, text

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


@contextmanager
def powerschool_connection(
    ssh_resource: SSHResource,
    db_resource: PowerSchoolODBCResource,
    log: logging.Logger,
) -> Generator[oracledb.Connection, None, None]:
    """Open an SSH tunnel and Oracle connection, with guaranteed cleanup.

    Opens the SSH tunnel first, then the database connection. On success,
    yields the connection. Cleans up both on exit.

    If the connection fails, the tunnel is killed immediately. All failures
    (connection or query execution) propagate without logging — logging is
    the caller's responsibility. ``with_powerschool_retry`` logs intermediate
    attempts at WARNING; Dagster captures unrecovered failures at the run
    level. Logging here at ERROR severity would file GCP Error Reporting
    groups for transient issues that the retry layer recovers from.

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
    finally:
        try:
            connection.close()
        finally:
            ssh_tunnel.kill()


def with_powerschool_retry[_T](
    ssh_resource: SSHResource,
    db_resource: PowerSchoolODBCResource,
    log: logging.Logger,
    work_fn: Callable[[oracledb.Connection], _T],
    max_attempts: int = 3,
) -> _T:
    """Run a function with a PowerSchool connection, retrying on failure.

    Opens a tunnel and connection via ``powerschool_connection``, calls
    ``work_fn`` with the connection, and returns the result. If the
    connection or work_fn raises, tears down the tunnel and retries up to
    ``max_attempts`` times before re-raising.

    Args:
        ssh_resource: SSHResource with open_ssh_tunnel() method.
        db_resource: PowerSchoolODBCResource with connect() method.
        log: Dagster logger (context.log).
        work_fn: Callable that receives an open connection and returns a result.
        max_attempts: Total attempts (initial + retries). Defaults to 3.

    Returns:
        The return value of work_fn.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            with powerschool_connection(ssh_resource, db_resource, log) as conn:
                return work_fn(conn)
        except Exception:
            if attempt == max_attempts:
                raise
            exc = sys.exc_info()[1]
            log.warning(
                f"PowerSchool attempt {attempt}/{max_attempts} failed, retrying: "
                f"{type(exc).__name__}: {exc}"
            )

    raise AssertionError("unreachable: max_attempts must be >= 1")


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
) -> TextClause:
    """Build a SQLAlchemy text clause for an Oracle COUNT query.

    Args:
        table: Oracle table name.
        column: Column to filter on. None for full table count.
        start_value: ISO timestamp string for >= or BETWEEN start.
        end_value: ISO timestamp string for BETWEEN end. Requires start_value.

    Returns:
        SQLAlchemy TextClause wrapping the COUNT query.
    """
    # TODO: parameterize sqlalchemy query to resolve bandit/B608
    if column is None:
        query = f"SELECT COUNT(*) FROM {table}"
    elif end_value is None:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} >= "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    else:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} BETWEEN "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
            f"TO_TIMESTAMP('{end_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)


def _fetch_count(
    db_powerschool: PowerSchoolODBCResource,
    connection: oracledb.Connection,
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
) -> int:
    """Execute a COUNT query and return the scalar result."""
    [(count,)] = check.inst(
        db_powerschool.execute_query(
            connection=connection,
            query=get_query_text(
                table=table,
                column=column,
                start_value=start_value,
                end_value=end_value,
            ),
            prefetch_rows=2,
            array_size=1,
        ),
        list,
    )
    return check.int_param(count, "count")


@dataclass
class StalenessResult:
    """A stale asset or partition that needs re-materialization.

    Every entry in the list returned by evaluate_asset_staleness represents
    an asset/partition that is stale. Absence from the list means not stale.

    Attributes:
        asset_key: Dagster AssetKey of the stale asset.
        partitions_def_identifier: Serializable unique identifier for the
            partitions definition. None for non-partitioned assets.
        partition_key: Partition key string. None for non-partitioned assets.
    """

    asset_key: AssetKey
    partitions_def_identifier: str | None
    partition_key: str | None


def _evaluate_non_partitioned(
    asset: AssetsDefinition,
    latest_event: EventLogEntry | None,
    table_name: str,
    partition_column: str | None,
    execution_timezone: ZoneInfo,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log: logging.Logger,
) -> StalenessResult | None:
    """Evaluate staleness for a non-partitioned asset.

    Checks in order: never materialized, modified count > 0, table count
    mismatch. Returns a StalenessResult if stale, None otherwise.

    Args:
        asset: The Dagster asset definition.
        latest_event: Latest materialization event, or None.
        table_name: Oracle table name.
        partition_column: Column for modification tracking, or None.
        execution_timezone: Timezone for timestamp formatting.
        connection: Open oracledb connection.
        db_powerschool: PowerSchool ODBC resource.
        log: Dagster logger.

    Returns:
        StalenessResult if the asset is stale, None otherwise.
    """
    asset_key_identifier = asset.key.to_python_identifier()

    # Check 1: never materialized
    if latest_event is None:
        log.info(f"{asset_key_identifier} never materialized")
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    metadata = check.not_none(value=latest_event.asset_materialization).metadata
    materialization_count = metadata["records"].value

    # Check 2: modified count > 0
    if partition_column is not None:
        timestamp = check.inst(
            obj=metadata["latest_materialization_timestamp"].value,
            ttype=float,
        )

        timestamp_fmt = format_oracle_timestamp(timestamp, execution_timezone)

        modified_count = _fetch_count(
            db_powerschool, connection, table_name, partition_column, timestamp_fmt
        )

        if modified_count > 0:
            log.info(f"{asset_key_identifier}\nmodified count: {modified_count}")
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=None,
                partition_key=None,
            )

    # Check 3: table count mismatch
    table_count = _fetch_count(db_powerschool, connection, table_name, column=None)

    if table_count != materialization_count:
        log.info(
            f"{asset_key_identifier}\n"
            f"PS count ({table_count}) != DB count ({materialization_count})"
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=None,
            partition_key=None,
        )

    return None


def _evaluate_partition(
    asset: AssetsDefinition,
    partition_key: str,
    first_partition_key: str,
    last_partition_key: str,
    table_name: str,
    partition_column: str | None,
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log: logging.Logger,
) -> StalenessResult | None:
    """Evaluate staleness for a single partition.

    Checks in order: skip first partition, never materialized, last partition
    modified count, partition count mismatch.

    Args:
        asset: The Dagster asset definition.
        partition_key: The partition key to evaluate.
        first_partition_key: First partition key in the definition.
        last_partition_key: Last partition key in the definition.
        table_name: Oracle table name.
        partition_column: Column for modification tracking, or None.
        execution_timezone: Timezone for timestamp formatting.
        instance: Dagster instance for materialization lookups.
        connection: Open oracledb connection.
        db_powerschool: PowerSchool ODBC resource.
        log: Dagster logger.

    Returns:
        StalenessResult if the partition is stale, None otherwise.
    """
    asset_key_identifier = asset.key.to_python_identifier()
    partitions_def = check.not_none(value=asset.partitions_def)
    partitions_def_id = partitions_def.get_serializable_unique_identifier()

    # Check 1: skip first partition
    if partition_key == first_partition_key:
        return None

    # Check 2: never materialized
    event_records = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=asset.key, asset_partitions=[partition_key]
        ),
        limit=1,
    )

    if not event_records.records:
        log.info(f"{asset_key_identifier} {partition_key} never materialized")
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=partitions_def_id,
            partition_key=partition_key,
        )

    metadata = check.not_none(
        value=event_records.records[0].asset_materialization
    ).metadata

    # Check 3: last partition modified count > 0
    if partition_key == last_partition_key and partition_column is not None:
        timestamp = check.inst(
            obj=metadata["latest_materialization_timestamp"].value,
            ttype=float,
        )

        timestamp_fmt = format_oracle_timestamp(timestamp, execution_timezone)

        modified_count = _fetch_count(
            db_powerschool, connection, table_name, partition_column, timestamp_fmt
        )

        if modified_count > 0:
            log.info(
                f"{asset_key_identifier}\n{partition_key}\n"
                f"modified count: {modified_count}"
            )
            return StalenessResult(
                asset_key=asset.key,
                partitions_def_identifier=partitions_def_id,
                partition_key=partition_key,
            )

    # Check 4: partition count mismatch
    start_value, end_value = get_partition_window(
        partition_key,
        check.inst(partitions_def, TimeWindowPartitionsDefinition),
    )

    partition_count = _fetch_count(
        db_powerschool, connection, table_name, partition_column, start_value, end_value
    )

    materialization_count = metadata["records"].value

    if partition_count > 0 and partition_count != materialization_count:
        log.info(
            f"{asset_key_identifier}\n{partition_key}\n"
            f"PS count ({partition_count}) != DB count ({materialization_count})"
        )
        return StalenessResult(
            asset_key=asset.key,
            partitions_def_identifier=partitions_def_id,
            partition_key=partition_key,
        )

    return None


def _evaluate_partitioned(
    asset: AssetsDefinition,
    partition_keys: Sequence[str],
    table_name: str,
    partition_column: str | None,
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log: logging.Logger,
) -> list[StalenessResult]:
    """Evaluate staleness for all partitions of a partitioned asset.

    Gets first/last partition keys from the full partition definition and
    delegates each key to _evaluate_partition.

    Args:
        asset: The Dagster asset definition.
        partition_keys: List of partition keys to evaluate (may be sliced).
        table_name: Oracle table name.
        partition_column: Column for modification tracking, or None.
        execution_timezone: Timezone for timestamp formatting.
        instance: Dagster instance for materialization lookups.
        connection: Open oracledb connection.
        db_powerschool: PowerSchool ODBC resource.
        log: Dagster logger.

    Returns:
        List of StalenessResult for stale partitions.
    """
    partitions_def = check.not_none(value=asset.partitions_def)
    first_partition_key = check.not_none(value=partitions_def.get_first_partition_key())
    last_partition_key = check.not_none(value=partitions_def.get_last_partition_key())

    results = []
    for partition_key in partition_keys:
        result = _evaluate_partition(
            asset=asset,
            partition_key=partition_key,
            first_partition_key=first_partition_key,
            last_partition_key=last_partition_key,
            table_name=table_name,
            partition_column=partition_column,
            execution_timezone=execution_timezone,
            instance=instance,
            connection=connection,
            db_powerschool=db_powerschool,
            log=log,
        )
        if result is not None:
            results.append(result)
    return results


def evaluate_asset_staleness(
    asset_selection: list[AssetsDefinition],
    execution_timezone: ZoneInfo,
    instance: DagsterInstance,
    connection: oracledb.Connection,
    db_powerschool: PowerSchoolODBCResource,
    log: logging.Logger,
    limit_monthly_partitions: int | None = None,
) -> list[StalenessResult]:
    """Evaluate staleness for a list of assets.

    For non-partitioned assets, checks whether the latest materialization is
    up to date with the source table. For partitioned assets, checks each
    partition individually.

    Args:
        asset_selection: List of Dagster asset definitions to evaluate.
        execution_timezone: Timezone for timestamp formatting.
        instance: Dagster instance for materialization lookups.
        connection: Open oracledb connection.
        db_powerschool: PowerSchool ODBC resource.
        log: Dagster logger.
        limit_monthly_partitions: If set, only check the last N partition
            keys for assets with MonthlyPartitionsDefinition.

    Returns:
        List of StalenessResult for stale assets/partitions.
    """
    asset_keys = [asset.key for asset in asset_selection]
    latest_materialization_events = instance.get_latest_materialization_events(
        asset_keys
    )

    results: list[StalenessResult] = []

    for asset in asset_selection:
        metadata = asset.metadata_by_key[asset.key]
        table_name = metadata["table_name"]
        partition_column = metadata["partition_column"]

        if asset.partitions_def is None:
            # Non-partitioned asset
            latest_event = latest_materialization_events.get(asset.key)
            result = _evaluate_non_partitioned(
                asset=asset,
                latest_event=latest_event,
                table_name=table_name,
                partition_column=partition_column,
                execution_timezone=execution_timezone,
                connection=connection,
                db_powerschool=db_powerschool,
                log=log,
            )
            if result is not None:
                results.append(result)
        else:
            # Partitioned asset
            partition_keys = asset.partitions_def.get_partition_keys()

            if limit_monthly_partitions is not None and isinstance(
                asset.partitions_def, MonthlyPartitionsDefinition
            ):
                partition_keys = partition_keys[-limit_monthly_partitions:]

            results.extend(
                _evaluate_partitioned(
                    asset=asset,
                    partition_keys=partition_keys,
                    table_name=table_name,
                    partition_column=partition_column,
                    execution_timezone=execution_timezone,
                    instance=instance,
                    connection=connection,
                    db_powerschool=db_powerschool,
                    log=log,
                )
            )

    return results
