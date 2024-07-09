import pendulum
from dagster import StaticPartitionsDefinition

from teamster.libraries.core.utils.classes import FiscalYear
from teamster.libraries.sftp.assets import build_sftp_file_asset


def build_titan_sftp_asset(
    key,
    remote_file_regex,
    schema,
    partition_start_date,
    timezone,
    current_fiscal_year,
):
    start_fy = FiscalYear(
        datetime=pendulum.from_format(
            string=partition_start_date, fmt="YYYY-MM-DD", tz=timezone
        ),
        start_month=7,
    )

    partition_keys = [
        str(y - 1)
        for y in range(start_fy.fiscal_year, (current_fiscal_year.fiscal_year + 1))
    ]

    return build_sftp_file_asset(
        asset_key=key,
        remote_dir_regex=r".",
        remote_file_regex=remote_file_regex,
        ssh_resource_key="ssh_titan",
        avro_schema=schema,
        partitions_def=StaticPartitionsDefinition(partition_keys),
    )
