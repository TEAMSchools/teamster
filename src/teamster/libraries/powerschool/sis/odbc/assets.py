"""PowerSchool SIS ODBC asset factory.

Builds Dagster assets that query PowerSchool's Oracle database via SSH tunnel
and serialize results to Avro files for downstream loading into BigQuery.
"""

import hashlib
import pathlib
from datetime import datetime
from io import BufferedReader

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    Output,
    TimeWindowPartitionsDefinition,
    asset,
)
from dagster_shared import check
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.libraries.powerschool.sis.odbc.resources import PowerSchoolODBCResource
from teamster.libraries.powerschool.sis.odbc.utils import (
    get_partition_window,
    powerschool_connection,
)
from teamster.libraries.ssh.resources import SSHResource


def hash_bytestr_iter(bytesiter, hasher):
    """Compute a hex digest by iterating over byte blocks.

    Args:
        bytesiter: Iterator yielding bytes objects.
        hasher: A hashlib hash object (e.g. hashlib.sha256()).

    Returns:
        Hex digest string.
    """
    for block in bytesiter:
        hasher.update(block)

    return hasher.hexdigest()


def file_as_blockiter(file: BufferedReader, size: int = 65536):
    """Yield fixed-size blocks from a file for hashing.

    Args:
        file: Open file in binary read mode.
        size: Block size in bytes.

    Yields:
        Bytes blocks of the specified size.
    """
    with file:
        block = file.read(size)
        while len(block) > 0:
            yield block
            block = file.read(size)


def build_powerschool_table_asset(
    code_location,
    table_name: str,
    partitions_def: TimeWindowPartitionsDefinition | None = None,
    partition_column: str | None = None,
    partition_size: int = 10000,
    prefetch_rows: int = 10000,
    array_size: int = 500000,
    select_columns: list[str] | None = None,
    op_tags: dict | None = None,
) -> AssetsDefinition:
    """Build a Dagster asset that queries a PowerSchool Oracle table.

    Args:
        code_location: District code location identifier.
        table_name: Oracle table name.
        partitions_def: Optional time-window partitions definition.
        partition_column: Column to filter by partition window.
        partition_size: Avro writer batch size.
        prefetch_rows: Oracle cursor prefetchrows setting.
        array_size: Oracle cursor arraysize setting.
        select_columns: Columns to select. Defaults to ['*'].
        op_tags: Optional Dagster op tags.

    Returns:
        A Dagster AssetsDefinition.
    """
    if select_columns is None:
        select_columns = ["*"]

    @asset(
        key=[code_location, "powerschool", table_name],
        metadata={
            "table_name": table_name,
            "partition_column": partition_column,
            "select_columns": select_columns,
            "op_tags": op_tags,
        },
        partitions_def=partitions_def,
        op_tags=op_tags,
        io_manager_key="io_manager_gcs_file",
        group_name="powerschool",
        kinds={"python"},
    )
    def _asset(
        context: AssetExecutionContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ):
        timestamp = datetime.now().timestamp()

        first_partition_key = (
            partitions_def.get_first_partition_key()
            if partitions_def is not None
            else None
        )

        if not context.has_partition_key:
            constructed_where = ""
        elif context.partition_key == first_partition_key:
            constructed_where = ""
        else:
            start_value, end_value = get_partition_window(
                context.partition_key, partitions_def
            )

            constructed_where = (
                f"{partition_column} BETWEEN "
                f"TO_TIMESTAMP('{start_value}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                f"TO_TIMESTAMP('{end_value}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )

        sql = (
            select(*[literal_column(col) for col in select_columns])
            .select_from(table(table_name))
            .where(text(constructed_where))
        )

        with powerschool_connection(
            ssh_powerschool, db_powerschool, context.log
        ) as connection:
            file_path = check.inst(
                obj=db_powerschool.execute_query(
                    connection=connection,
                    query=sql,
                    output_format="avro",
                    batch_size=partition_size,
                    prefetch_rows=prefetch_rows,
                    array_size=array_size,
                ),
                ttype=pathlib.Path,
            )

        with file_path.open(mode="rb") as f:
            num_records = sum(block.num_records for block in block_reader(f))
            digest = hash_bytestr_iter(
                bytesiter=file_as_blockiter(file=f), hasher=hashlib.sha256()
            )

        return Output(
            value=file_path,
            metadata={
                "records": num_records,
                "digest": digest,
                "latest_materialization_timestamp": timestamp,
            },
        )

    return _asset
