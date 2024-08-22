select
    log_id,
    export_date as valid_from,
    academic_year,
    staffing_model_id,
    teammate,
    staffing_status,
    status_detail,
    mid_year_hire as is_mid_year_hire,
    if(staffing_status = 'Open', true, false) as is_open,
    if(staffing_status = 'Staffed', true, false) as is_staffed,
    if(plan_status in ('Active', 'TRUE'), true, false) as is_active,
    if(status_detail in ('New Hire', 'Transfer In'), true, false) as is_new_hire,
    case
        plan_status
        when 'TRUE'
        then 'Active'
        when 'FALSE'
        then 'Inactive'
        else plan_status
    end as plan_status,
from {{ source("google_appsheet", "src_seat_tracker__log_archive") }}
where staffing_status is not null
