from dagster import DailyPartitionsDefinition, DynamicPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_manager.schema import (
    ACCRUAL_REPORTING_PERIOD_SUMMARY_SCHEMA,
    TIME_DETAILS_SCHEMA,
)
from teamster.libraries.adp.workforce_manager.assets import build_adp_wfm_asset

accrual_reporting_period_summary = build_adp_wfm_asset(
    asset_key=[
        CODE_LOCATION,
        "adp_workforce_manager",
        "accrual_reporting_period_summary",
    ],
    schema=ACCRUAL_REPORTING_PERIOD_SUMMARY_SCHEMA,
    report_name="AccrualReportingPeriodSummary",
    hyperfind="All Home",
    symbolic_ids=["Today"],
    date_partitions_def=DailyPartitionsDefinition(
        start_date="2023-05-17",
        timezone=LOCAL_TIMEZONE.name,
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
)

time_details = build_adp_wfm_asset(
    asset_key=[CODE_LOCATION, "adp_workforce_manager", "time_details"],
    schema=TIME_DETAILS_SCHEMA,
    report_name="TimeDetails",
    hyperfind="All Home",
    symbolic_ids=["Previous_SchedPeriod", "Current_SchedPeriod"],
    date_partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}__adp_workforce_manager__time_details_date"
    ),
)

adp_wfm_assets_daily = [
    accrual_reporting_period_summary,
]

adp_wfm_assets_dynamic = [
    time_details,
]

assets = [
    *adp_wfm_assets_daily,
    *adp_wfm_assets_dynamic,
]
