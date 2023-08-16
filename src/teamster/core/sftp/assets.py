import os
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


def compose_remote_file_regex(regexp, context: OpExecutionContext):
    try:
        partitions_def = context.asset_partitions_def_for_output()
    except DagsterInvariantViolationError:
        return regexp

    if isinstance(partitions_def, MultiPartitionsDefinition):
        return regex_pattern_replace(
            pattern=regexp, replacements=context.partition_key.keys_by_dimension
        )
    else:
        compiled_regex = re.compile(pattern=regexp)

        pattern_keys = compiled_regex.groupindex.keys()

        return regex_pattern_replace(
            pattern=regexp,
            replacements={key: context.partition_key for key in pattern_keys},
        )


def build_sftp_asset(
    asset_name,
    code_location,
    source_system,
    remote_filepath,
    remote_file_regex,
    asset_fields,
    ssh_resource_key=None,
    archive_filepath=None,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=True,
    op_tags={},
    **kwargs,
):
    ssh_resource_key = ssh_resource_key or f"ssh_{source_system}"

    asset_metadata = {
        "remote_filepath": remote_filepath,
        "remote_file_regex": remote_file_regex,
        "archive_filepath": archive_filepath,
    }

    avro_schema = get_avro_record_schema(
        name=asset_name, fields=asset_fields[asset_name]
    )

    @asset(
        key=[code_location, source_system, asset_name],
        metadata=asset_metadata,
        required_resource_keys={ssh_resource_key},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        auto_materialize_policy=auto_materialize_policy,
    )
    def _asset(context: OpExecutionContext):
        ssh: SSHConfigurableResource = getattr(context.resources, ssh_resource_key)

        remote_file_regex_composed = compose_remote_file_regex(
            regexp=remote_file_regex, context=context
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
            if re.match(pattern=remote_file_regex_composed, string=f.filename)
            is not None
        ]

        # exit if no matches
        if remote_file_regex_matches:
            remote_filename = remote_file_regex_matches[0]
        else:
            context.log.warning(
                f"Found no files matching: {remote_file_regex_composed}"
            )
            yield Output(value=([{}], avro_schema), metadata={"records": 0})
            return

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

        # exit if file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(f"File is empty: {local_filepath}")
            yield Output(value=([{}], avro_schema), metadata={"records": 0})
            return

        # load file into pandas and prep for output
        df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)
        df.replace({nan: None}, inplace=True)
        if slugify_cols:
            df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        df_records = df.to_dict(orient="records")

        yield Output(value=(df_records, avro_schema), metadata={"records": df.shape[0]})

    return _asset
