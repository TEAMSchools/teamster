select
    staffing_model_id,
    staffing_status,
    status_detail,
    mid_year_hire as is_mid_year_hire,
    plan_status,
    cast(dbt_valid_from as date) as valid_from,
    cast(dbt_valid_to as date) as valid_to,
    cast(academic_year as string) as academic_year,
    cast(teammate as string) as teammate,
    if(staffing_status = 'Open', true, false) as is_open,
    if(staffing_status = 'Staffed', true, false) as is_staffed,
    if(plan_status in ('Active', 'TRUE'), true, false) as is_active,
    if(status_detail in ('New Hire', 'Transfer In'), true, false) as is_new_hire,
from {{ ref("snapshot__seat_tracker__seats") }}
where dbt_updated_at > ('2024-08-07')

union all

select
    la1.staffing_model_id,
    la1.staffing_status,
    la1.status_detail,
    la1.is_mid_year_hire,
    la1.plan_status,
    la1.valid_from,
    /* using the previous export date minus 1 day as valid_to, 
    if no next export date then using date of last app export, 2024-08-07*/
    if(la2.valid_from - 1 is null, date(2024, 08, 07), la2.valid_from - 1) as valid_to,
    la1.academic_year,
    la1.teammate,
    la1.is_open,
    la1.is_active,
    la1.is_staffed,
    la1.is_new_hire,

from {{ ref("stg_seat_tracker__log_archive") }} as la1
left join
    {{ ref("stg_seat_tracker__log_archive") }} as la2
    on la1.staffing_model_id = la2.staffing_model_id
    and la1.rn_valid_from - 1 = la2.rn_valid_from
