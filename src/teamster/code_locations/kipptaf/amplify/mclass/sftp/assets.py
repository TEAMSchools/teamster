from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.mclass.sftp.schema import (
    BENCHMARK_STUDENT_SUMMARY_SCHEMA,
    PM_STUDENT_SUMMARY_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_file_asset

partitions_def = FiscalYearPartitionsDefinition(
    start_date="2025-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7
)

benchmark_student_summary = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "amplify", "mclass", "sftp", "benchmark_student_summary"],
    remote_dir_regex=r"/data-team/kipptaf/amplify",  # TODO: update for prod
    remote_file_regex=r"UAR_ new DYD columns - D8 BM Sample File.csv",  # TODO: update for prod
    ssh_resource_key="ssh_couchdrop",  # TODO: update for prod
    avro_schema=BENCHMARK_STUDENT_SUMMARY_SCHEMA,
    partitions_def=partitions_def,
)

pm_student_summary = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "amplify", "mclass", "sftp", "pm_student_summary"],
    remote_dir_regex=r"/data-team/kipptaf/amplify",  # TODO: update for prod
    remote_file_regex=r"UAR_ new DYD columns - D8 PM Sample File.csv",  # TODO: update for prod
    ssh_resource_key="ssh_couchdrop",  # TODO: update for prod
    avro_schema=PM_STUDENT_SUMMARY_SCHEMA,
    partitions_def=partitions_def,
)

assets = [
    benchmark_student_summary,
    pm_student_summary,
]
