import json
import os
import pathlib
import re
import zipfile

from dagster import (
    AssetExecutionContext,
    DagsterInvariantViolationError,
    MultiPartitionsDefinition,
    Output,
    asset,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
    regex_pattern_replace,
)


def match_sftp_files(ssh: SSHResource, remote_dir, remote_file_regex):
    # list files remote filepath
    files = ssh.listdir_attr_r(remote_dir=remote_dir, files=[])

    if remote_dir == ".":
        pattern = remote_file_regex
    else:
        pattern = f"{remote_dir}/{remote_file_regex}"

    return [
        f.filepath
        for f in files
        if re.match(pattern=pattern, string=f.filepath) is not None
    ]


def compose_regex(regexp, context: AssetExecutionContext):
    if regexp is None:
        return regexp

    try:
        partitions_def = context.assets_def.partitions_def
    except DagsterInvariantViolationError:
        return regexp

    if isinstance(partitions_def, MultiPartitionsDefinition):
        return regex_pattern_replace(
            pattern=regexp,
            replacements=context.partition_key.keys_by_dimension,  # type: ignore
        )
    else:
        compiled_regex = re.compile(pattern=regexp)

        pattern_keys = compiled_regex.groupindex.keys()

        return regex_pattern_replace(
            pattern=regexp,
            replacements={key: context.partition_key for key in pattern_keys},
        )


def build_sftp_asset(
    asset_key,
    remote_dir,
    remote_file_regex,
    ssh_resource_key,
    avro_schema,
    archive_filepath=None,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=True,
    slugify_replacements=(),
    op_tags: dict | None = None,
    group_name=None,
    **kwargs,
):
    if group_name is None:
        group_name = asset_key[1]

    @asset(
        key=asset_key,
        metadata={"remote_dir": remote_dir, "remote_file_regex": remote_file_regex},
        required_resource_keys={ssh_resource_key},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        op_tags=op_tags,
        group_name=group_name,
        auto_materialize_policy=auto_materialize_policy,
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
        compute_kind="sftp",
    )
    def _asset(context: AssetExecutionContext):
        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        # find matching file for partition
        remote_file_regex_composed = compose_regex(
            regexp=remote_file_regex, context=context
        )

        file_matches = match_sftp_files(
            ssh=ssh, remote_dir=remote_dir, remote_file_regex=remote_file_regex_composed
        )

        # exit if no matches
        if not file_matches:
            context.log.warning(
                f"Found no files matching: {remote_dir}/{remote_file_regex_composed}"
            )
            records = [{}]
            metadata = {"records": 0}
        else:
            # validate file match
            if len(file_matches) > 1:
                context.log.warning(
                    msg=(
                        f"Found multiple files matching: {remote_file_regex_composed}\n"
                        f"{file_matches}"
                    )
                )

            file_match = file_matches[0]

            # download file match
            local_filepath = ssh.sftp_get(
                remote_filepath=file_match, local_filepath=f"./env/{file_match}"
            )

            # exit if file is empty
            if os.path.getsize(local_filepath) == 0:
                context.log.warning(f"File is empty: {local_filepath}")
                records = [{}]
                metadata = {"records": 0}
            else:
                # unzip file, if necessary
                if archive_filepath is not None:
                    archive_filepath_composed = compose_regex(
                        regexp=archive_filepath, context=context
                    )

                    with zipfile.ZipFile(file=local_filepath) as zf:
                        zf.extract(member=archive_filepath_composed, path="./env")

                    local_filepath = f"./env/{archive_filepath_composed}"

                # exit if extracted file is empty
                if os.path.getsize(local_filepath) == 0:
                    context.log.warning(f"File is empty: {local_filepath}")
                    records = [{}]
                    metadata = {"records": 0}
                else:
                    # load file into pandas and prep for output
                    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

                    df.replace({nan: None}, inplace=True)
                    if slugify_cols:
                        df.rename(
                            columns=lambda x: slugify(
                                text=x, separator="_", replacements=slugify_replacements
                            ),
                            inplace=True,
                        )

                    records = df.to_dict(orient="records")
                    metadata = {"records": df.shape[0]}

        fp = pathlib.Path(f"env/{group_name}/{file_match}")
        fp.parent.mkdir(parents=True, exist_ok=True)
        json.dump(obj=records, fp=fp.open("w"))

        yield Output(value=(records, avro_schema), metadata=metadata)

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset
