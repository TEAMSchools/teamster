from dagster import (
    AutoMaterializePolicy,
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

from teamster.core.clever.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema, regex_pattern_replace


def build_sftp_asset(
    asset_name,
    code_location,
    source_system,
    remote_filepath,
    remote_file_regex,
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
                "date": DynamicPartitionsDefinition(
                    name=f"{code_location}_{source_system}_{asset_name}_date"
                ),
                "type": StaticPartitionsDefinition(["staff", "students", "teachers"]),
            }
        ),
        op_tags=op_tags,
        auto_materialize_policy=AutoMaterializePolicy.eager(),
    )
    def _asset(
        context: OpExecutionContext, sftp_clever_reports: ResourceParam[SSHResource]
    ):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]
        date_partition = context.partition_key.keys_by_dimension["date"]
        type_partition = context.partition_key.keys_by_dimension["type"]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_filename = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={"date": date_partition, "type": type_partition},
        )

        local_filepath = sftp_clever_reports.sftp_get(
            remote_filepath=f"{remote_filepath}/{remote_filename}",
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
