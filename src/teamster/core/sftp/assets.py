import re
import zipfile

from dagster import (
    DagsterInvariantViolationError,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    asset,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.functions import get_avro_record_schema, regex_pattern_replace


def compose_remote_file_regex(remote_file_regex, context: OpExecutionContext):
    try:
        partitions_def = context.asset_partitions_def_for_output()
    except DagsterInvariantViolationError:
        return remote_file_regex

    if isinstance(partitions_def, MultiPartitionsDefinition):
        return regex_pattern_replace(
            pattern=remote_file_regex,
            replacements=context.partition_key.keys_by_dimension,
        )
    else:
        compiled_regex = re.compile(pattern=remote_file_regex)

        pattern_keys = compiled_regex.groupindex.keys()

        return regex_pattern_replace(
            pattern=remote_file_regex,
            replacements={key: context.partition_key for key in pattern_keys},
        )


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
    slugify_cols=True,
    op_tags={},
    **kwargs,
):
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={
            "remote_filepath": remote_filepath,
            "remote_file_regex": remote_file_regex,
            "archive_filepath": archive_filepath,
        },
        required_resource_keys={f"ssh_{source_system}"},
        io_manager_key="gcs_avro_io",
        partitions_def=partitions_def,
        op_tags=op_tags,
        output_required=False,
        auto_materialize_policy=auto_materialize_policy,
    )
    def _asset(context: OpExecutionContext):
        ssh: SSHConfigurableResource = getattr(
            context.resources, f"ssh_{source_system}"
        )
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        remote_filepath = asset_metadata["remote_filepath"]
        archive_filepath = asset_metadata["archive_filepath"]
        remote_file_regex = compose_remote_file_regex(
            remote_file_regex=asset_metadata["remote_file_regex"], context=context
        )

        # list files remote filepath
        conn = ssh.get_connection()
        with conn.open_sftp() as sftp_client:
            ls = sftp_client.listdir_attr(path=remote_filepath)
        conn.close()

        # find matching file for partition
        remote_file_regex_matches = [
            f.filename
            for f in ls
            if re.match(pattern=remote_file_regex, string=f.filename) is not None
        ]

        if remote_file_regex_matches:
            remote_filename = remote_file_regex_matches[0]
        else:
            return None

        # download file from sftp
        local_filepath = ssh.sftp_get(
            remote_filepath=f"{remote_filepath}/{remote_filename}",
            local_filepath=f"./data/{remote_filename}",
        )

        # unzip file, if necessary
        if archive_filepath is not None:
            with zipfile.ZipFile(file=local_filepath) as zf:
                zf.extract(member=archive_filepath, path="./data")

            local_filepath = f"./data/{archive_filepath}"

        # load file into pandas and prep for output
        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df = df.replace({nan: None})
        if slugify_cols:
            df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        df_records = df.to_dict(orient="records")

        yield Output(
            value=(
                df_records,
                get_avro_record_schema(
                    name=asset_name, fields=asset_fields[asset_name]
                ),
            ),
            metadata={"records": df.shape[0]},
        )

    return _asset
