select
    {{ dbt_utils.generate_surrogate_key(["dbt_scd_id"]) }} as staffing_position_key,

    {{ dbt_utils.generate_surrogate_key(["adp_location"]) }} as location_key,

    {{ dbt_utils.generate_surrogate_key(["teammate"]) }} as incumbent_staff_key,

    {{ dbt_utils.generate_surrogate_key(["recruiter"]) }} as recruiter_staff_key,

    dbt_scd_id as staffing_position_natural_key,

    academic_year,
    recruitment_group,
    adp_dept as home_department_name,
    adp_title as title,
    staffing_status as status,
    status_detail,
    mid_year_hire as is_mid_year_hire,

    if(plan_status in ('Active', 'TRUE'), true, false) as is_active,

    cast(dbt_valid_from as date) as effective_start_date,
    cast(dbt_valid_to as date) as effective_end_date,
from {{ ref("snapshot_seat_tracker__seats") }}
