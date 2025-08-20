from dagster import StaticPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kipptaf.amplify.mclass.sftp.schema import (
    BENCHMARK_STUDENT_SUMMARY_SCHEMA,
    PM_STUDENT_SUMMARY_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

partitions_def = StaticPartitionsDefinition(
    [f"{year - 1}-{year}" for year in range(2026, CURRENT_FISCAL_YEAR.fiscal_year + 1)]
)

benchmark_student_summary = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "amplify", "mclass", "sftp", "benchmark_student_summary"],
    remote_dir_regex=r"/BM",
    remote_file_regex=r"dibels8_BM_(?P<school_year>[\d-]+)_[-\w]+\.csv",
    ssh_resource_key="ssh_amplify",
    avro_schema=BENCHMARK_STUDENT_SUMMARY_SCHEMA,
    partitions_def=partitions_def,
    ignore_multiple_matches=True,
)

pm_student_summary = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "amplify", "mclass", "sftp", "pm_student_summary"],
    remote_dir_regex=r"/PM",
    remote_file_regex=r"dibels8_PM_(?P<school_year>[\d-]+)_[-\w]+\.csv",
    ssh_resource_key="ssh_amplify",
    avro_schema=PM_STUDENT_SUMMARY_SCHEMA,
    partitions_def=partitions_def,
    ignore_multiple_matches=True,
)

assets = [
    benchmark_student_summary,
    pm_student_summary,
]
