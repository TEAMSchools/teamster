from dagster import DailyPartitionsDefinition, DynamicPartitionsDefinition

from teamster.adp.workforce_manager.assets import build_adp_wfm_asset
from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE

accrual_reporting_period_summary = build_adp_wfm_asset(
    asset_name="accrual_reporting_period_summary",
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
    asset_name="time_details",
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
