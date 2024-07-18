select
    log_id,
    snapshot_staffing_model_id,
    snapshot_teammate,
    snapshot_plan_status,
    snapshot_staffing_status,
    snapshot_status_detail,
    snapshot_mid_year_hire,
    export_date,
    snapshot_academic_year,

    if(snapshot_staffing_status = 'Open', 1, 0) as snapshot_open,
    if(
        snapshot_status_detail in ('New Hire', 'Transfer In'), 1, 0
    ) as snapshot_new_hire,
    if(snapshot_staffing_status = 'Staffed', 1, 0) as snapshot_staffed,
    if(snapshot_plan_status = 'Active', 1, 0) as snapshot_active,
    if(snapshot_mid_year_hire = true, 1, 0) as snapshot_mid_year_hire_int,

from {{ ref("stg_google_appsheet__src_seat_tracker__log_archive") }}
