import re
import zipfile

import pendulum
from dagster import OpExecutionContext, Output, asset
from dagster_ssh import SSHResource
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema, regex_pattern_replace
from teamster.core.utils.variables import CURRENT_FISCAL_YEAR


def build_sftp_asset(
    asset_name,
    code_location,
    source_system,
    remote_filepath,
    remote_file_regex,
    asset_fields,
    archive_filepath=None,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=False,
    op_tags={},
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={
            "remote_filepath": remote_filepath,
            "remote_file_regex": remote_file_regex,
            "archive_filepath": archive_filepath,
        },
        required_resource_keys={f"sftp_{source_system}"},
        io_manager_key="gcs_avro_io",
        partitions_def=partitions_def,
        op_tags=op_tags,
        auto_materialize_policy=auto_materialize_policy,
    )
    def _asset(context: OpExecutionContext):
        ssh: SSHResource = getattr(context.resources, f"sftp_{source_system}")
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]
        remote_file_regex = asset_metadata["remote_file_regex"]
        archive_filepath = asset_metadata["archive_filepath"]

        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)
        conn.close()

        remote_filename = None
        for f in ls:
            match = re.match(pattern=remote_file_regex, string=f.filename)
            if match is not None:
                remote_filename = f.filename
                break

        local_filepath = ssh.sftp_get(
            remote_filepath=f"{remote_filepath}/{remote_filename}",
            local_filepath=f"./data/{remote_filename}",
        )

        if archive_filepath is not None:
            with zipfile.ZipFile(file=local_filepath) as zf:
                zf.extract(member=archive_filepath, path="./data")

            local_filepath = f"./data/{archive_filepath}"

        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})
        if slugify_cols:
            df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        yield Output(
            value=(
                df.to_dict(orient="records"),
                get_avro_record_schema(
                    name=asset_name, fields=asset_fields[asset_name]
                ),
            ),
            metadata={"records": df.shape[0]},
        )

    return _asset


def build_sftp_asset_1():
    @asset()
    def _asset(context: OpExecutionContext):
        remote_file_regex = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={"date": context.partition_key},
        )


def build_sftp_asset_2():
    @asset()
    def _asset(context: OpExecutionContext):
        date_partition = context.partition_key.keys_by_dimension["date"]
        type_partition = context.partition_key.keys_by_dimension["type"]

        remote_file_regex = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={"date": date_partition, "type": type_partition},
        )


def build_sftp_asset_3():
    @asset()
    def _asset(context: OpExecutionContext):
        date_partition = context.partition_key.keys_by_dimension["date"]

        date_partition_fy = FiscalYear(
            datetime=pendulum.from_format(string=date_partition, fmt="YYYY-MM-DD"),
            start_month=7,
        )

        if date_partition_fy.fiscal_year == CURRENT_FISCAL_YEAR.fiscal_year:
            remote_filepath += "/Current_Year"
        else:
            remote_filepath += f"/academic_year_{date_partition_fy.fiscal_year - 1}"

        remote_filename = regex_pattern_replace(
            pattern=asset_metadata["remote_file_regex"],
            replacements={
                "subject": context.partition_key.keys_by_dimension["subject"]
            },
        )
