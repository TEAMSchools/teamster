import pathlib

import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    _check,
    asset,
)
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text
from sshtunnel import SSHTunnelForwarder

from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sqlalchemy.resources import OracleResource
from teamster.libraries.ssh.resources import SSHResource


def build_powerschool_table_asset(
    asset_key,
    local_timezone,
    partitions_def: (
        FiscalYearPartitionsDefinition | MonthlyPartitionsDefinition | None
    ) = None,
    table_name=None,
    select_columns: list[str] | None = None,
    partition_column=None,
    op_tags: dict | None = None,
    **kwargs,
) -> AssetsDefinition:
    if table_name is None:
        table_name = asset_key[-1]

    if select_columns is None:
        select_columns = ["*"]

    @asset(
        key=asset_key,
        metadata={"partition_column": partition_column},
        io_manager_key="io_manager_gcs_file",
        partitions_def=partitions_def,
        op_tags=op_tags,
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
            window_start = pendulum.from_format(
                string=context.partition_key, fmt="YYYY-MM-DDTHH:mm:ssZZ"
            )

            window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

            if isinstance(partitions_def, FiscalYearPartitionsDefinition):
                date_add_kwargs = {"years": 1}
            elif isinstance(partitions_def, MonthlyPartitionsDefinition):
                date_add_kwargs = {"months": 1}
            else:
                date_add_kwargs = {}

            window_end_fmt = (
                window_start.add(**date_add_kwargs)
                .subtract(days=1)
                .end_of("day")
                .format("YYYY-MM-DDTHH:mm:ss.SSSSSS")
            )

            constructed_where = (
                f"{partition_column} BETWEEN "
                f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') "
                "AND "
                f"TO_TIMESTAMP('{window_end_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
            )

        sql = (
            select(*[literal_column(col) for col in select_columns])
            .select_from(table(table_name))
            .where(text(constructed_where))
        )

        with ssh_powerschool.get_tunnel(
            remote_port=1521, local_port=1521
        ) as ssh_tunnel:
            ssh_tunnel = _check.inst(ssh_tunnel, SSHTunnelForwarder)

            ssh_tunnel.start()

            file_path = _check.inst(
                db_powerschool.engine.execute_query(
                    query=sql, partition_size=100000, output_format="avro"
                ),
                pathlib.Path,
            )

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
