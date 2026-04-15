select
    {{ dbt_utils.generate_surrogate_key(["dbt_scd_id"]) }} as staffing_position_key,

    {{ dbt_utils.generate_surrogate_key(["adp_location"]) }} as location_key,

    {{ dbt_utils.generate_surrogate_key(["teammate"]) }} as teammate_staff_key,

    {{ dbt_utils.generate_surrogate_key(["recruiter"]) }} as recruiter_staff_key,

    dbt_scd_id as staffing_position_natural_key,

    academic_year,
    staffing_model_id,
    entity,
    grade_band,
    recruitment_group,
    adp_dept as home_department_name,
    adp_title as job_title,
    adp_location as home_work_location_name,
    short_name as location_short_name,
    recruiter as recruiter_employee_number,
    teammate as teammate_employee_number,
    plan_status,
    staffing_status,
    status_detail,
    mid_year_hire as is_mid_year_hire,

    cast(dbt_valid_from as date) as effective_date_start,
    cast(dbt_valid_to as date) as effective_date_end,
from {{ ref("snapshot_seat_tracker__seats") }}
