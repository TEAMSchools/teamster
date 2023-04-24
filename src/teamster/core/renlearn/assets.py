import pathlib

import pandas
from dagster import Config, Output, asset
from dagster_ssh import SSHResource

from teamster.core.renlearn.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


class SFTPAssetConfig(Config):
    remote_filepath: str


def build_sftp_asset(asset_name, code_location, source_system, op_tags={}, **kwargs):
    kwargs = kwargs

    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        op_tags=op_tags,
        io_manager_key="gcs_avro_io",
    )
    def _asset(config: SFTPAssetConfig, **kwargs):
        sftp: SSHResource = kwargs[f"sftp_{source_system}"]

        remote_filepath = pathlib.Path(config.remote_filepath)

        local_filepath = sftp.sftp_get(
            remote_filepath=str(remote_filepath), local_filepath=remote_filepath.name
        )

        df = pandas.read_csv(filepath_or_buffer=local_filepath)

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
