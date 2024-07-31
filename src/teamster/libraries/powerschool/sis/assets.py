import pathlib

import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    SkipReason,
    _check,
    asset,
)
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text
from sshtunnel import HandlerSSHTunnelForwarderError

from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sqlalchemy.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_table_asset(
    code_location,
    local_timezone,
    table_name: str,
    partitions_def: (
        FiscalYearPartitionsDefinition | MonthlyPartitionsDefinition | None
    ) = None,
    partition_column: str | None = None,
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
        db_powerschool: OracleResource,
    ):
        now = pendulum.now(tz=local_timezone).start_of("hour")

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
        except HandlerSSHTunnelForwarderError as e:
            if "An error occurred while opening tunnels." in e.args:
                return SkipReason(str(e))
            else:
                raise HandlerSSHTunnelForwarderError from e

        file_path = _check.inst(
            obj=db_powerschool.engine.execute_query(
                query=sql, partition_size=100000, output_format="avro"
            ),
            ttype=pathlib.Path,
        )

        ssh_tunnel.stop()

        try:
            with file_path.open(mode="rb") as f:
                num_records = sum(block.num_records for block in block_reader(f))

            yield Output(
                value=file_path,
                metadata={
                    "records": num_records,
                    "latest_materialization_timestamp": now.timestamp(),
                },
            )
        except FileNotFoundError:
            pass

    return _asset
