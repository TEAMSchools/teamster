import hashlib
import pathlib
from datetime import datetime
from io import BufferedReader

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    TimeWindowPartitionsDefinition,
    asset,
)
from dagster_shared import check
from dateutil.relativedelta import relativedelta
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
            partition_start = datetime.fromisoformat(context.partition_key)

            partition_start_fmt = partition_start.replace(tzinfo=None).isoformat(
                timespec="microseconds"
            )

            if isinstance(partitions_def, FiscalYearPartitionsDefinition):
                date_add_kwargs = {"years": 1}
            elif isinstance(partitions_def, MonthlyPartitionsDefinition):
                date_add_kwargs = {"months": 1}
            else:
                date_add_kwargs = {}

            partition_end_fmt = (
                (
                    partition_start
                    # trunk-ignore(pyright/reportArgumentType)
                    + relativedelta(**date_add_kwargs)
                    - relativedelta(days=1)
                )
                .replace(hour=23, minute=59, second=59, microsecond=999999)
                .replace(tzinfo=None)
                .isoformat(timespec="microseconds")
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

        context.log.info(msg=f"Opening SSH tunnel to {ssh_powerschool.remote_host}")
        ssh_tunnel = ssh_powerschool.open_ssh_tunnel()

        try:
            connection = db_powerschool.connect()
        except Exception as e:
            ssh_tunnel.kill()
            raise e

        try:
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
        finally:
            connection.close()
            ssh_tunnel.kill()

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
