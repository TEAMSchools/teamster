import hashlib
import pathlib
from io import BufferedReader

import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    TimeWindowPartitionsDefinition,
    _check,
    asset,
)
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource


def hash_bytestr_iter(bytesiter, hasher):
    for block in bytesiter:
        hasher.update(block)

    return hasher.hexdigest()


def file_as_blockiter(file: BufferedReader, size: int = 65536):
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
        compute_kind="python",
    )
    def _asset(
        context: AssetExecutionContext,
        ssh_powerschool: SSHResource,
        db_powerschool: PowerSchoolODBCResource,
    ):
        hour_timestamp = pendulum.now().start_of("hour").timestamp()

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
            partition_start = pendulum.from_format(
                string=context.partition_key, fmt="YYYY-MM-DDTHH:mm:ssZZ"
            )

            partition_start_fmt = partition_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

            if isinstance(partitions_def, FiscalYearPartitionsDefinition):
                date_add_kwargs = {"years": 1}
            elif isinstance(partitions_def, MonthlyPartitionsDefinition):
                date_add_kwargs = {"months": 1}
            else:
                date_add_kwargs = {}

            partition_end_fmt = (
                partition_start.add(**date_add_kwargs)
                .subtract(days=1)
                .end_of("day")
                .format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
            )

            constructed_where = (
                f"{partition_column} BETWEEN "
                f"TO_TIMESTAMP('{partition_start_fmt}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
                f"TO_TIMESTAMP('{partition_end_fmt}', "
                "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )

        sql = (
            select(*[literal_column(col) for col in select_columns])
            .select_from(table(table_name))
            .where(text(constructed_where))
        )

        ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

        try:
            ssh_tunnel.start()
            ssh_tunnel.check_tunnels()

            file_path = _check.inst(
                obj=db_powerschool.execute_query(
                    query=sql,
                    output_format="avro",
                    batch_size=partition_size,
                    prefetch_rows=prefetch_rows,
                    array_size=array_size,
                ),
                ttype=pathlib.Path,
            )
        finally:
            ssh_tunnel.stop()

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
                "latest_materialization_timestamp": hour_timestamp,
            },
        )

    return _asset
