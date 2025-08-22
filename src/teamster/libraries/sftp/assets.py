import os
import re
import zipfile
from typing import Sequence

from dagster import (
    AssetExecutionContext,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    asset,
)
from dagster_shared import check
from pypdf import PdfReader

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.core.utils.functions import file_to_records, regex_pattern_replace
from teamster.libraries.ssh.resources import SSHResource


def compose_regex(
    regexp: str, partition_key: str | MultiPartitionKey | None = None
) -> str:
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


def extract_pdf_to_dict(stream: str, pdf_row_pattern: str):
    records = []

    reader = PdfReader(stream=stream, strict=True)

    for page in reader.pages:
        matches = re.finditer(pattern=pdf_row_pattern, string=page.extract_text())

        records.extend([m.groupdict() for m in matches])

    return records, len(records)


def build_sftp_file_asset(
    asset_key: Sequence[str],
    remote_dir_regex: str,
    remote_file_regex: str,
    ssh_resource_key: str,
    avro_schema,
    partitions_def=None,
    automation_condition=None,
    group_name: str | None = None,
    pdf_row_pattern: str | None = None,
    exclude_dirs: list[str] | None = None,
    ignore_multiple_matches: bool = False,
    file_sep: str = ",",
    file_encoding: str = "utf-8",
    slugify_cols: bool = True,
    skip_asset_checks: bool = False,
    slugify_replacements: list[list[str]] | None = None,
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    if exclude_dirs is None:
        exclude_dirs = []

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
        automation_condition=automation_condition,
        check_specs=(
            [build_check_spec_avro_schema_valid(asset_key)]
            if not skip_asset_checks
            else None
        ),
        kinds={"python", "file"},
    )
    def _asset(context: AssetExecutionContext):
        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        if context.has_partition_key:
            partition_key = context.partition_key
        else:
            partition_key = None

        if group_name == "iready":
            partition_key = check.inst(obj=partition_key, ttype=MultiPartitionKey)

            academic_year_key, subject_key = partition_key.keys_by_dimension.values()

            multi_partitions_def = check.inst(
                obj=context.assets_def.partitions_def, ttype=MultiPartitionsDefinition
            )

            academic_year_last_partition_key = (
                multi_partitions_def.get_partitions_def_for_dimension("academic_year")
            ).get_last_partition_key()

            if academic_year_key == academic_year_last_partition_key:
                remote_dir_regex_composed = compose_regex(
                    regexp=remote_dir_regex,
                    partition_key=MultiPartitionKey(
                        {"academic_year": "Current_Year", "subject": subject_key}
                    ),
                )
            else:
                remote_dir_regex_composed = compose_regex(
                    regexp=remote_dir_regex,
                    partition_key=MultiPartitionKey(
                        {"academic_year": academic_year_key, "subject": subject_key}
                    ),
                )
        else:
            remote_dir_regex_composed = compose_regex(
                regexp=remote_dir_regex, partition_key=partition_key
            )

        remote_file_regex_composed = compose_regex(
            regexp=remote_file_regex, partition_key=partition_key
        )

        files = ssh.listdir_attr_r(
            remote_dir=remote_dir_regex_composed, exclude_dirs=exclude_dirs
        )

        files.sort(key=lambda x: x[0].st_mtime or 0, reverse=True)

        file_matches = [
            path
            for _, path in files
            if re.search(
                pattern=f"{remote_dir_regex_composed}/{remote_file_regex_composed}",
                string=path,
            )
            is not None
        ]

        # exit if no matches
        if not file_matches:
            msg = (
                f"Found no files matching: {remote_dir_regex_composed}/"
                f"{remote_file_regex_composed}"
            )

            context.log.error(msg=msg)
            raise FileNotFoundError(msg)
        # exit if unexpected multiple matches
        elif not ignore_multiple_matches and len(file_matches) > 1:
            msg = (
                f"Found multiple files matching: {remote_dir_regex_composed}/"
                f"{remote_file_regex_composed}\n{file_matches}"
            )

            context.log.error(msg=msg)
            raise Exception(msg)
        else:
            file_match = file_matches[0]

        local_filepath = ssh.sftp_get(
            remote_filepath=file_match,
            local_filepath=f"./env/{context.asset_key.to_user_string()}/{file_match}",
        )

        if os.path.getsize(local_filepath) == 0:
            context.log.warning(msg=f"File is empty: {local_filepath}")
            records, n_rows = ([{}], 0)
        elif remote_file_regex[-4:] == ".pdf":
            records, n_rows = extract_pdf_to_dict(
                stream=local_filepath,
                pdf_row_pattern=check.not_none(value=pdf_row_pattern),
            )
        else:
            records = file_to_records(
                file=local_filepath,
                encoding=file_encoding,
                delimiter=file_sep,
                slugify_cols=slugify_cols,
                slugify_replacements=slugify_replacements,
            )

            n_rows = len(records)

            if n_rows == 0:
                context.log.warning(msg="File contains 0 rows")

        yield Output(value=(records, avro_schema), metadata={"records": n_rows})

        if not skip_asset_checks:
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )

    return _asset


def build_sftp_archive_asset(
    asset_key: list[str],
    remote_dir_regex: str,
    remote_file_regex: str,
    archive_file_regex: str,
    ssh_resource_key: str,
    avro_schema,
    partitions_def=None,
    group_name: str | None = None,
    exclude_dirs: list[str] | None = None,
    slugify_cols: bool = True,
    file_sep: str = ",",
    file_encoding: str = "utf-8",
    slugify_replacements: list[list[str]] | None = None,
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    if exclude_dirs is None:
        exclude_dirs = []

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
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        kinds={"python", "file"},
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

        files = ssh.listdir_attr_r(
            remote_dir=remote_dir_regex_composed, exclude_dirs=exclude_dirs
        )

        file_matches = [
            path
            for _, path in files
            if re.search(
                pattern=f"{remote_dir_regex_composed}/{remote_file_regex_composed}",
                string=path,
            )
            is not None
        ]

        # exit if no matches
        if not file_matches:
            context.log.warning(
                msg=(
                    "Found no files matching: "
                    f"{remote_dir_regex_composed}/{remote_file_regex_composed}"
                )
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
                    "Found multiple files matching: "
                    f"{remote_dir_regex_composed}/{remote_file_regex_composed}\n"
                    f"{file_matches}"
                )
            )

        file_match = file_matches[0]

        local_filepath = ssh.sftp_get(
            remote_filepath=file_match,
            local_filepath=f"./env/{context.asset_key.to_user_string()}/{file_match}",
        )

        # exit if file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(msg=f"File is empty: {local_filepath}")
            records = [{}]

            yield Output(value=(records, avro_schema), metadata={"records": 0})
            yield check_avro_schema_valid(
                asset_key=context.asset_key, records=records, schema=avro_schema
            )
            return

        archive_file_regex_composed = compose_regex(
            regexp=archive_file_regex, partition_key=partition_key
        ).replace("\\", "")

        with zipfile.ZipFile(file=local_filepath) as zf:
            zf.extract(
                member=archive_file_regex_composed,
                path=f"./env/{context.asset_key.to_user_string()}",
            )

        local_filepath = (
            f"./env/{context.asset_key.to_user_string()}/{archive_file_regex_composed}"
        )

        if os.path.getsize(local_filepath) == 0:
            context.log.warning(msg=f"File is empty: {local_filepath}")
            records, n_rows = ([{}], 0)
        else:
            records = file_to_records(
                file=local_filepath,
                encoding=file_encoding,
                delimiter=file_sep,
                slugify_cols=slugify_cols,
                slugify_replacements=slugify_replacements,
            )

            n_rows = len(records)

            if n_rows == 0:
                context.log.warning(msg="File contains 0 rows")

        yield Output(value=(records, avro_schema), metadata={"records": n_rows})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset


def build_sftp_folder_asset(
    asset_key: list[str],
    remote_dir_regex: str,
    remote_file_regex: str,
    ssh_resource_key: str,
    avro_schema,
    partitions_def=None,
    group_name: str | None = None,
    exclude_dirs: list[str] | None = None,
    slugify_cols: bool = True,
    file_sep: str = ",",
    file_encoding: str = "utf-8",
    file_dtype: type | None = None,
    slugify_replacements: list[list[str]] | None = None,
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
):
    if group_name is None:
        group_name = asset_key[1]

    if exclude_dirs is None:
        exclude_dirs = []

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
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        kinds={"python", "file"},
    )
    def _asset(context: AssetExecutionContext):
        all_records = []
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

        files = ssh.listdir_attr_r(
            remote_dir=remote_dir_regex_composed, exclude_dirs=exclude_dirs
        )

        file_matches = [
            path
            for _, path in files
            if re.search(
                pattern=f"{remote_dir_regex_composed}/{remote_file_regex_composed}",
                string=path,
            )
            is not None
        ]

        # exit if no matching files
        if not file_matches:
            context.log.warning(
                msg=(
                    "Found no files matching: "
                    f"{remote_dir_regex_composed}/{remote_file_regex_composed}"
                )
            )
            return Output(value=([], avro_schema), metadata={"records": 0})

        for file in file_matches:
            local_filepath = ssh.sftp_get(
                remote_filepath=file,
                local_filepath=f"./env/{context.asset_key.to_user_string()}/{file}",
            )

            # skip if file is empty
            if os.path.getsize(local_filepath) == 0:
                context.log.warning(msg=f"File is empty: {local_filepath}")
                continue

            records = file_to_records(
                file=local_filepath,
                encoding=file_encoding,
                delimiter=file_sep,
                slugify_cols=slugify_cols,
                slugify_replacements=slugify_replacements,
            )

            n_rows = len(records)

            if n_rows == 0:
                context.log.warning(msg="File contains 0 rows")

            all_records.extend(records)
            record_count += n_rows

        yield Output(
            value=(all_records, avro_schema), metadata={"records": record_count}
        )
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=all_records, schema=avro_schema
        )

    return _asset
