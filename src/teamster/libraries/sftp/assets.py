import os
import re
import zipfile
from typing import Sequence

from dagster import (
    AssetExecutionContext,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    _check,
    asset,
)
from numpy import nan
from pandas import read_csv
from pypdf import PdfReader
from slugify import slugify

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.core.utils.functions import regex_pattern_replace
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


def extract_csv_to_dict(
    local_filepath: str, slugify_cols: bool, slugify_replacements: tuple
):
    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

    df.replace({nan: None}, inplace=True)

    if slugify_cols:
        df.rename(
            columns=lambda x: slugify(
                text=x, separator="_", replacements=slugify_replacements
            ),
            inplace=True,
        )

    return df.to_dict(orient="records"), df.shape


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
    slugify_cols: bool | None = True,
    slugify_replacements: tuple | None = (),
    partitions_def=None,
    automation_condition=None,
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
    exclude_dirs: list[str] | None = None,
    pdf_row_pattern: str | None = None,
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
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        compute_kind="python",
    )
    def _asset(context: AssetExecutionContext):
        ssh: SSHResource = getattr(context.resources, ssh_resource_key)

        if context.has_partition_key:
            partition_key = context.partition_key
        else:
            partition_key = None

        if group_name == "iready":
            partition_key = _check.inst(obj=partition_key, ttype=MultiPartitionKey)

            academic_year_key, subject_key = partition_key.keys_by_dimension.values()

            multi_partitions_def = _check.inst(
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
        # exit if multiple matches
        elif len(file_matches) > 1:
            msg = (
                f"Found multiple files matching: {remote_dir_regex_composed}/"
                f"{remote_file_regex_composed}\n{file_matches}"
            )

            context.log.error(msg=msg)
            raise Exception(msg)
        else:
            file_match = file_matches[0]

        local_filepath = ssh.sftp_get(
            remote_filepath=file_match, local_filepath=f"./env/{file_match}"
        )

        if os.path.getsize(local_filepath) == 0:
            context.log.warning(msg=f"File is empty: {local_filepath}")
            records, n_rows = ([{}], 0)
        elif remote_file_regex[-4:] == ".pdf":
            records, n_rows = extract_pdf_to_dict(
                stream=local_filepath,
                pdf_row_pattern=_check.not_none(value=pdf_row_pattern),
            )
        else:
            records, (n_rows, _) = extract_csv_to_dict(
                local_filepath=local_filepath,
                slugify_cols=_check.not_none(value=slugify_cols),
                slugify_replacements=_check.not_none(value=slugify_replacements),
            )

            if n_rows == 0:
                context.log.warning(msg="File contains 0 rows")

        yield Output(value=(records, avro_schema), metadata={"records": n_rows})
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
    slugify_cols=True,
    slugify_replacements=(),
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
    exclude_dirs: list[str] | None = None,
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
            remote_filepath=file_match, local_filepath=f"./env/{file_match}"
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
            zf.extract(member=archive_file_regex_composed, path="./env")

        local_filepath = (
            f"./env/{context.asset_key.to_user_string()}/{archive_file_regex_composed}"
        )

        # exit if extracted file is empty
        if os.path.getsize(local_filepath) == 0:
            context.log.warning(msg=f"File is empty: {local_filepath}")
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

        rows, _ = df.shape

        if rows == 0:
            context.log.warning(msg="File contains 0 rows")

        yield Output(value=(records, avro_schema), metadata={"records": rows})
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
    slugify_cols=True,
    slugify_replacements: tuple = (),
    tags: dict[str, str] | None = None,
    op_tags: dict | None = None,
    group_name: str | None = None,
    exclude_dirs: list[str] | None = None,
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
                remote_filepath=file, local_filepath=f"./env/{file}"
            )

            # skip if file is empty
            if os.path.getsize(local_filepath) == 0:
                context.log.warning(msg=f"File is empty: {local_filepath}")
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

            rows, _ = df.shape

            if rows == 0:
                context.log.warning(msg="File contains 0 rows")

            records.extend(df.to_dict(orient="records"))
            record_count += rows

        yield Output(value=(records, avro_schema), metadata={"records": record_count})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=avro_schema
        )

    return _asset
