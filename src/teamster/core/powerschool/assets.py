import pathlib

import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MonthlyPartitionsDefinition,
    Output,
    asset,
)
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.core.sqlalchemy.resources import OracleResource
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.classes import FiscalYearPartitionsDefinition


def build_powerschool_table_asset(
    code_location,
    asset_name,
    local_timezone,
    partitions_def: (
        FiscalYearPartitionsDefinition | MonthlyPartitionsDefinition | None
    ) = None,
    table_name=None,
    select_columns: list[str] | None = None,
    partition_column=None,
    op_tags: dict | None = None,
) -> AssetsDefinition:
    if table_name is None:
        table_name = asset_name

    if select_columns is None:
        select_columns = ["*"]

    @asset(
        key=[code_location, "powerschool", asset_name],
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

        if not context.has_partition_key:
            constructed_where = ""
        elif context.partition_key == partitions_def.get_first_partition_key():
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
            ssh_tunnel.start()

            file_path: pathlib.Path = db_powerschool.engine.execute_query(
                query=sql, partition_size=100000, output_format="avro"
            )  # type: ignore

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
