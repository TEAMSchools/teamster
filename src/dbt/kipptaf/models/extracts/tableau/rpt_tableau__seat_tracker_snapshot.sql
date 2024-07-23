select
    log_id,
    export_date,
    academic_year as snapshot_academic_year,
    staffing_model_id as snapshot_staffing_model_id,
    teammate as snapshot_teammate,
    staffing_status as snapshot_staffing_status,
    status_detail as snapshot_status_detail,
    plan_status as snapshot_plan_status,
    is_mid_year_hire as snapshot_mid_year_hire,
    is_mid_year_hire_int as snapshot_mid_year_hire_int,

    if(is_open, 1, 0) as snapshot_open,
    if(is_new_hire, 1, 0) as snapshot_new_hire,
    if(is_staffed, 1, 0) as snapshot_staffed,
    if(is_active, 1, 0) as snapshot_active,
from {{ ref("stg_seat_tracker__log_archive") }}
