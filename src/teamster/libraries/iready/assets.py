from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.libraries.sftp.assets import build_sftp_file_asset


def build_iready_sftp_asset(
    asset_key,
    region_subfolder,
    remote_file_regex,
    avro_schema,
    start_fiscal_year: int,
    current_fiscal_year: int,
):
    partition_keys = [
        str(y - 1) for y in range(start_fiscal_year, current_fiscal_year + 1)
    ]

    return build_sftp_file_asset(
        asset_key=asset_key,
        remote_dir_regex=rf"/exports/{region_subfolder}/(?P<academic_year>\w+)",
        remote_file_regex=remote_file_regex,
        ssh_resource_key="ssh_iready",
        group_name="iready",
        avro_schema=avro_schema,
        slugify_replacements=[["%", "percent"]],
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(partition_keys),
            }
        ),
    )
