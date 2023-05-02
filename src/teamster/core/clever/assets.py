import pathlib

from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    StaticPartitionsDefinition,
    asset,
)
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv

from teamster.core.clever.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_sftp_asset(
    asset_name, code_location, source_system, remote_filepath, op_tags={}
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={
            "remote_filepath": remote_filepath,
            "remote_file_regex": r"(\d{4}-\d{2}-\d{2})[-\w+]+-(\w+).csv",
        },
        io_manager_key="gcs_avro_io",
        partitions_def=MultiPartitionsDefinition(
            {
                "date": DynamicPartitionsDefinition(
                    name=f"{code_location}_{source_system}_{asset_name}_date"
                ),
                "type": StaticPartitionsDefinition(["staff", "students", "teachers"]),
            }
        ),
        op_tags=op_tags,
    )
    def _asset(
        context: OpExecutionContext, sftp_clever_reports: ResourceParam[SSHResource]
    ):
        file_name = context.assets_def.key[-1].replace("_", "-")
        date_partition_key = context.partition_key.keys_by_dimension["date"]
        type_partition_key = context.partition_key.keys_by_dimension["type"]

        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]

        local_filepath = sftp_clever_reports.sftp_get(
            remote_filepath=(
                f"{remote_filepath}/"
                f"{date_partition_key}-{file_name}-{type_partition_key}.csv"
            ),
            local_filepath=f"./data/{pathlib.Path(remote_filepath).name}",
        )

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})

        yield Output(
            value=(
                df.to_dict(orient="records"),
                get_avro_record_schema(
                    name=asset_name, fields=ENDPOINT_FIELDS[asset_name]
                ),
            ),
            metadata={"records": df.shape[0]},
        )

    return _asset
