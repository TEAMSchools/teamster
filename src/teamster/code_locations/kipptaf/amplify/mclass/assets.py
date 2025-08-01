from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.mclass.schema import (
    BENCHMARK_STUDENT_SUMMARY_SCHEMA,
    PM_STUDENT_SUMMARY_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.amplify.mclass.assets import build_mclass_asset

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2022-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7
)

DYD_PAYLOAD = {
    "accounts": "1300588536",
    "districts": "1300588535",
    "roster_option": "2",  # On Test Day
    "dyd_assessments": "7_D8",  # DIBELS 8th Edition
    "tracking_id": None,
}

benchmark_student_summary = build_mclass_asset(
    asset_key=[CODE_LOCATION, "amplify", "benchmark_student_summary"],
    dyd_payload={**DYD_PAYLOAD, "dyd_results": "BM"},
    partitions_def=PARTITIONS_DEF,
    schema=BENCHMARK_STUDENT_SUMMARY_SCHEMA,
)

pm_student_summary = build_mclass_asset(
    asset_key=[CODE_LOCATION, "amplify", "pm_student_summary"],
    dyd_payload={**DYD_PAYLOAD, "dyd_results": "PM"},
    partitions_def=PARTITIONS_DEF,
    schema=PM_STUDENT_SUMMARY_SCHEMA,
)

assets = [
    benchmark_student_summary,
    pm_student_summary,
]
