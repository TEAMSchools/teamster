from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import StaticPartitionsDefinition

from teamster.core.utils.classes import FiscalYear
from teamster.libraries.sftp.assets import build_sftp_file_asset


def build_titan_sftp_asset(
    key: list[str],
    remote_file_regex: str,
    schema: dict,
    partition_start_date: str,
    timezone: ZoneInfo,
    current_fiscal_year: FiscalYear,
):
    start_fy = FiscalYear(
        datetime=datetime.strptime(partition_start_date, "%Y-%m-%d").replace(
            tzinfo=timezone
        ),
        start_month=7,
    )

    partition_keys = [
        str(y - 1)
        for y in range(start_fy.fiscal_year, (current_fiscal_year.fiscal_year + 1))
    ]

    return build_sftp_file_asset(
        asset_key=key,
        remote_dir_regex=r"\.",
        remote_file_regex=remote_file_regex,
        ssh_resource_key="ssh_titan",
        avro_schema=schema,
        partitions_def=StaticPartitionsDefinition(partition_keys),
        exclude_dirs=["Script", "Scipt"],
    )
