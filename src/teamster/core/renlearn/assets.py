import pathlib

from dagster import Config, OpExecutionContext, Output, ResourceParam, asset
from dagster_ssh import SSHResource
from pandas import read_csv

from teamster.core.renlearn.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


class SFTPAssetConfig(Config):
    remote_filepath: str


def build_sftp_asset(asset_name, code_location, source_system, op_tags={}):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        op_tags=op_tags,
        io_manager_key="gcs_avro_io",
    )
    def _asset(
        context: OpExecutionContext,
        config: SFTPAssetConfig,
        sftp_renlearn: ResourceParam[SSHResource],
    ):
        remote_filepath = pathlib.Path(config.remote_filepath)

        local_filepath = sftp_renlearn.sftp_get(
            remote_filepath=str(remote_filepath),
            local_filepath=f"./data/{remote_filepath.name}",
        )

        df = read_csv(filepath_or_buffer=local_filepath)
        context.log.debug(df.dtypes.to_dict())

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
