import re

from dagster import DailyPartitionsDefinition, OpExecutionContext, Output, asset
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv

from teamster.core.edplan.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema
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
        required_resource_keys={f"sftp_{source_system}"},
        io_manager_key="gcs_avro_io",
        partitions_def=DailyPartitionsDefinition(
            start_date=partition_start_date,
            timezone=LOCAL_TIME_ZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
        op_tags=op_tags,
    )
    def _asset(context: OpExecutionContext):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_file_regex = asset_metadata["remote_file_regex"]

        sftp: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        conn = sftp.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)
        conn.close()

        remote_filename = None
        for f in ls:
            match = re.match(pattern=remote_file_regex, string=f.filename)
            if match is not None:
                remote_filename = f.filename
                break

        local_filepath = sftp.sftp_get(
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
