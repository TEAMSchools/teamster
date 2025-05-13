select
    s.academic_year,
    s.adp_dept,
    s.adp_location,
    s.display_name as job_title,
    s.entity,
    s.grade_band,
    s.short_name as `location`,
    s.plan_status,
    s.staffing_status,
    s.status_detail,
    s.staffing_model_id,
    s.surrogate_key,

    srr.formatted_name as recruiter,
    srr.reports_to_formatted_name as recruiter_manager,
    srt.formatted_name as teammate,

    if(s.staffing_status = 'Open', 1, 0) as `open`,
    if(s.status_detail in ('New Hire', 'Transfer In'), 1, 0) as new_hire,
    if(s.staffing_status = 'Staffed', 1, 0) as staffed,
    if(s.plan_status = 'Active', 1, 0) as active,
    if(s.mid_year_hire, 1, 0) as mid_year_hire,
from {{ ref("stg_seat_tracker__seats") }} as s
/* recruiters */
left join
    {{ ref("int_people__staff_roster") }} as srr on s.recruiter = srr.employee_number
/* all staff */
left join
    {{ ref("int_people__staff_roster") }} as srt on s.teammate = srt.employee_number
