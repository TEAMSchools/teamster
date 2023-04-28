import pathlib
import zipfile

from dagster import OpExecutionContext, Output, ResourceParam, asset
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv

from teamster.core.renlearn.schema import ENDPOINT_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_sftp_asset(
    asset_name,
    code_location,
    source_system,
    remote_filepath,
    archive_filepath=None,
    op_tags={},
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        op_tags=op_tags,
        io_manager_key="gcs_avro_io",
        metadata={"remote_filepath": remote_filepath},
    )
    def _asset(
        context: OpExecutionContext, sftp_clever_reports: ResourceParam[SSHResource]
    ):
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]

        local_filepath = sftp_clever_reports.sftp_get(
            remote_filepath=remote_filepath,
            local_filepath=f"./data/{pathlib.Path(remote_filepath).name}",
        )

        if archive_filepath is not None:
            with zipfile.ZipFile(file=local_filepath) as zf:
                zf.extract(member=archive_filepath, path="./data")

            local_filepath = f"./data/{archive_filepath}"

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
