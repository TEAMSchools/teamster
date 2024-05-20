from dagster import MAX_RUNTIME_SECONDS_TAG

from teamster.amplify.assets import build_mclass_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.kipptaf import LOCAL_TIMEZONE

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2022-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
)

DYD_PAYLOAD = {
    "accounts": "1300588536",
    "districts": "1300588535",
    "roster_option": "2",  # On Test Day
    "dyd_assessments": "7_D8",  # DIBELS 8th Edition
    "tracking_id": None,
}


benchmark_student_summary = build_mclass_asset(
    name="benchmark_student_summary",
    dyd_results="BM",
    op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 15)},
)

pm_student_summary = build_mclass_asset(name="pm_student_summary", dyd_results="PM")

assets = [
    benchmark_student_summary,
    pm_student_summary,
]
