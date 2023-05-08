import pendulum
from dagster import (
    AutoMaterializePolicy,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    StaticPartitionsDefinition,
    TimeWindowPartitionsDefinition,
    asset,
)
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema, regex_pattern_replace
from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_sftp_asset(
    asset_name,
    code_location,
    source_system,
    remote_filepath,
    remote_file_regex,
    partition_start_date,
    op_tags={},
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={
            "remote_filepath": remote_filepath,
            "remote_file_regex": remote_file_regex,
        },
        io_manager_key="gcs_avro_io",
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "date": TimeWindowPartitionsDefinition(
                    cron_schedule="0 0 1 7 *",
                    timezone=LOCAL_TIME_ZONE.name,
                    fmt="%Y-%m-%d",
                    start=partition_start_date,
                    end_offset=1,
                ),
            }
        ),
        op_tags=op_tags,
        auto_materialize_policy=AutoMaterializePolicy.eager(),
    )
    def _asset(context: OpExecutionContext, sftp_iready: ResourceParam[SSHResource]):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]
        date_partition = context.partition_key.keys_by_dimension["date"]

        current_fy = FiscalYear(datetime=pendulum.today(), start_month=7)
        date_partition_fy = FiscalYear(
            datetime=pendulum.from_format(string=date_partition, fmt="YYYY-MM-DD"),
            start_month=7,
        )

        remote_filepath = asset_metadata["remote_filepath"]
        if date_partition_fy.fiscal_year == current_fy.fiscal_year:
            remote_filepath += "/Current_Year"
        else:
            remote_filepath += f"/academic_year_{date_partition_fy.fiscal_year - 1}"

        remote_filename = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={
                "subject": context.partition_key.keys_by_dimension["subject"]
            },
        )

        local_filepath = sftp_iready.sftp_get(
            remote_filepath=(f"{remote_filepath}/{remote_filename}"),
            local_filepath=f"./data/{remote_filename}",
        )

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})

        yield Output(
            value=(
                df.to_dict(orient="records"),
                get_avro_record_schema(
                    name=asset_name, fields=ASSET_FIELDS[asset_name]
                ),
            ),
            metadata={"records": df.shape[0]},
        )

    return _asset
