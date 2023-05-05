import re

from dagster import (
    DynamicPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    asset,
)
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.achieve3k.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_sftp_asset(
    asset_name, code_location, source_system, remote_filepath, op_tags={}
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={
            "remote_filepath": remote_filepath,
            "remote_file_regex": (
                r"(\d{4}[-\d{2}]+)-\d+_D[\d+_]+(\w\d{4}[-\d{2}]+_){2}student\.\w+"
            ),
        },
        io_manager_key="gcs_avro_io",
        partitions_def=DynamicPartitionsDefinition(
            name=f"{code_location}_{source_system}_{asset_name}"
        ),
        op_tags=op_tags,
    )
    def _asset(context: OpExecutionContext, sftp_achieve3k: ResourceParam[SSHResource]):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_file_regex = (
            context.partition_key + asset_metadata["remote_file_regex"][:16]
        )
        context.log.debug(remote_file_regex)

        conn = sftp_achieve3k.get_connection()

        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)

        conn.close()

        remote_filename = None
        for f in ls:
            context.log.debug(f.filename)
            match = re.match(pattern=remote_file_regex, string=f.filename)
            if match is not None:
                context.log.debug(match)
                remote_filename = f.filename

        local_filepath = sftp_achieve3k.sftp_get(
            remote_filepath=f"{remote_filepath}/{remote_filename}",
            local_filepath=f"./data/{remote_filename}",
        )

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

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
