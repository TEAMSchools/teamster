import re

from dagster import (
    AutoMaterializePolicy,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
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
        required_resource_keys={f"sftp_{source_system}"},
        io_manager_key="gcs_avro_io",
        partitions_def=MultiPartitionsDefinition(
            {
                "date": DynamicPartitionsDefinition(
                    name=f"{code_location}__{source_system}__{asset_name}_date"
                ),
                "type": StaticPartitionsDefinition(["staff", "students", "teachers"]),
            }
        ),
        op_tags=op_tags,
        auto_materialize_policy=AutoMaterializePolicy.eager(),
    )
    def _asset(context: OpExecutionContext):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]
        date_partition = context.partition_key.keys_by_dimension["date"]
        type_partition = context.partition_key.keys_by_dimension["type"]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_file_regex = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={"date": date_partition, "type": type_partition},
        )
        context.log.debug(remote_file_regex)

        ssh: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)
        conn.close()
        context.log.debug(ls)

        remote_filename = None
        for f in ls:
            context.log.debug(f)
            match = re.match(pattern=remote_file_regex, string=f.filename)
            if match is not None:
                remote_filename = f.filename
                break

        local_filepath = ssh.sftp_get(
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
