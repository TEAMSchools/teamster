import re

from dagster import (
    AutoMaterializePolicy,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv

from teamster.core.iready.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
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
        required_resource_keys={f"sftp_{source_system}"},
        io_manager_key="gcs_avro_io",
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "date": FiscalYearPartitionsDefinition(
                    start_date=partition_start_date,
                    timezone=LOCAL_TIME_ZONE.name,
                    start_month=7,
                    fmt="%Y-%m-%d",
                ),
            }
        ),
        op_tags=op_tags,
        auto_materialize_policy=AutoMaterializePolicy.eager(),
    )
    def _asset(context: OpExecutionContext):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_file_regex = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={
                "subject": context.partition_key.keys_by_dimension["subject"]
            },
        )
        ssh: SSHResource = getattr(context.resources, f"sftp_{source_system}")

        # list files remote filepath
        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)
        conn.close()

        # find matching file for partition
        remote_filename = [
            f.filename
            for f in ls
            if re.match(pattern=remote_file_regex, string=f.filename) is not None
        ][0]

        local_filepath = ssh.sftp_get(
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
