import os
import re
import zipfile

from dagster import AssetExecutionContext, MultiPartitionKey, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.core.utils.functions import regex_pattern_replace
from teamster.libraries.ssh.resources import SSHResource


def compose_regex(regexp: str, partition_key: str | MultiPartitionKey | None) -> str:
    if isinstance(partition_key, MultiPartitionKey):
        return regex_pattern_replace(
            pattern=regexp, replacements=partition_key.keys_by_dimension
        )
    elif isinstance(partition_key, str):
        compiled_regex = re.compile(pattern=regexp)

        return regex_pattern_replace(
            pattern=regexp,
            replacements={
                key: partition_key for key in compiled_regex.groupindex.keys()
            },
        )
    else:
        return regexp


def build_sftp_file_asset(
    asset_key,
    remote_dir_regex,
    remote_file_regex,
    ssh_resource_key,
    avro_schema,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=True,
    slugify_replacements=(),
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    @asset(
        key=asset_key,
        metadata={
            "remote_dir_regex": remote_dir_regex,
            "remote_file_regex": remote_file_regex,
        },
        required_resource_keys={ssh_resource_key},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        tags=tags,
        op_tags=op_tags,
        group_name=group_name,
        auto_materialize_policy=auto_materialize_policy,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        compute_kind="python",
    )
    def _asset(context: AssetExecutionContext):
        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        if context.has_partition_key:
            partition_key = context.partition_key
        else:
            partition_key = None

        remote_dir_regex_composed = compose_regex(
            regexp=remote_dir_regex, partition_key=partition_key
        )

        remote_file_regex_composed = compose_regex(
            regexp=remote_file_regex, partition_key=partition_key
        )

        file_matches = ssh.match_sftp_files(
            remote_dir=remote_dir_regex_composed, remote_file=remote_file_regex_composed
        )

        # exit if no matches
        if not file_matches:
            context.log.warning(
                f"Found no files matching: {remote_dir_regex_composed}/{remote_file_regex_composed}"
            )
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return

        if len(file_matches) > 1:
            context.log.warning(
                msg=(
                    f"Found multiple files matching: {remote_file_regex_composed}\n"
                    f"{file_matches}"
                )
            )

        file_match = file_matches[0]

        local_filepath = ssh.sftp_get(
            remote_filepath=file_match, local_filepath=f"./env/{file_match}"
        )

        # exit if file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(f"File is empty: {local_filepath}")
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return

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

        yield Output(value=(records, avro_schema), metadata={"records": df.shape[0]})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset


def build_sftp_archive_asset(
    asset_key,
    remote_dir_regex,
    remote_file_regex,
    archive_file_regex,
    ssh_resource_key,
    avro_schema,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=True,
    slugify_replacements=(),
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    @asset(
        key=asset_key,
        metadata={
            "remote_dir_regex": remote_dir_regex,
            "remote_file_regex": remote_file_regex,
            "archive_file_regex": archive_file_regex,
        },
        required_resource_keys={ssh_resource_key},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        tags=tags,
        op_tags=op_tags,
        group_name=group_name,
        auto_materialize_policy=auto_materialize_policy,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        compute_kind="python",
    )
    def _asset(context: AssetExecutionContext):
        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        if context.has_partition_key:
            partition_key = context.partition_key
        else:
            partition_key = None

        remote_dir_regex_composed = compose_regex(
            regexp=remote_dir_regex, partition_key=partition_key
        )

        remote_file_regex_composed = compose_regex(
            regexp=remote_file_regex, partition_key=partition_key
        )

        file_matches = ssh.match_sftp_files(
            remote_dir=remote_dir_regex_composed, remote_file=remote_file_regex_composed
        )

        # exit if no matches
        if not file_matches:
            context.log.warning(
                f"Found no files matching: {remote_dir_regex_composed}/{remote_file_regex_composed}"
            )
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return

        if len(file_matches) > 1:
            context.log.warning(
                msg=(
                    f"Found multiple files matching: {remote_file_regex_composed}\n"
                    f"{file_matches}"
                )
            )

        file_match = file_matches[0]

        local_filepath = ssh.sftp_get(
            remote_filepath=file_match, local_filepath=f"./env/{file_match}"
        )

        # exit if file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(f"File is empty: {local_filepath}")
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return

        archive_file_regex_composed = compose_regex(
            regexp=archive_file_regex, partition_key=partition_key
        )

        with zipfile.ZipFile(file=local_filepath) as zf:
            zf.extract(member=archive_file_regex_composed, path="./env")

        local_filepath = f"./env/{archive_file_regex_composed}"

        # exit if extracted file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(f"File is empty: {local_filepath}")
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return
        else:
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

        yield Output(value=(records, avro_schema), metadata={"records": df.shape[0]})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset


def build_sftp_folder_asset(
    asset_key,
    remote_dir_regex: str,
    remote_file_regex: str,
    ssh_resource_key: str,
    avro_schema,
    partitions_def=None,
    auto_materialize_policy=None,
    slugify_cols=True,
    slugify_replacements: tuple = (),
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    @asset(
        key=asset_key,
        metadata={
            "remote_dir_regex": remote_dir_regex,
            "remote_file_regex": remote_file_regex,
        },
        required_resource_keys={ssh_resource_key},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        tags=tags,
        op_tags=op_tags,
        group_name=group_name,
        auto_materialize_policy=auto_materialize_policy,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        compute_kind="python",
    )
    def _asset(context: AssetExecutionContext):
        records = []
        record_count = 0

        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        if context.has_partition_key:
            partition_key = context.partition_key
        else:
            partition_key = None

        remote_dir_regex_composed = compose_regex(
            regexp=remote_dir_regex, partition_key=partition_key
        )

        remote_file_regex_composed = compose_regex(
            regexp=remote_file_regex, partition_key=partition_key
        )

        file_matches = ssh.match_sftp_files(
            remote_dir=remote_dir_regex_composed, remote_file=remote_file_regex_composed
        )

        # exit if no matching files
        if not file_matches:
            context.log.warning(
                f"Found no files matching: {remote_dir_regex_composed}/{remote_file_regex_composed}"
            )
            return Output(value=([], avro_schema), metadata={"records": 0})

        for file in file_matches:
            local_filepath = ssh.sftp_get(
                remote_filepath=file, local_filepath=f"./env/{file}"
            )

            # skip if file is empty
            if os.path.getsize(local_filepath) == 0:
                context.log.warning(f"File is empty: {local_filepath}")
                continue

            df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

            df.replace({nan: None}, inplace=True)
            if slugify_cols:
                df.rename(
                    columns=lambda text: slugify(
                        text=text, separator="_", replacements=slugify_replacements
                    ),
                    inplace=True,
                )

            records.extend(df.to_dict(orient="records"))
            record_count += df.shape[0]

        yield Output(value=(records, avro_schema), metadata={"records": record_count})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset
