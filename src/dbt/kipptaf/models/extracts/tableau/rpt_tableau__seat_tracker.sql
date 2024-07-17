select
    s.academic_year,
    s.adp_dept,
    s.adp_location,
    s.display_name as job_title,
    s.entity,
    s.grade_band,
    s.short_name as location,
    if(s.mid_year_hire=true,1,0) as Mid_Year_Hire,
    s.plan_status,
    s.staffing_status,
    s.status_detail,
    s.staffing_model_id,

    srr.preferred_name_lastfirst as recruiter,
    srr.report_to_preferred_name_lastfirst as recruiter_manager,
    srt.preferred_name_lastfirst as teammate,

    if(s.staffing_status = 'Open', 1, 0) as `Open`,
    if(s.status_detail in ('New Hire', 'Transfer In'), 1, 0) as New_Hire,
    if(s.staffing_status = 'Staffed', 1, 0) as Staffed,
    if(s.plan_status = 'Active', 1, 0) as Active,

from {{ ref("stg_people__seats") }} as s
/* recruiters */
left join
    {{ ref("base_people__staff_roster") }} as srr on s.recruiter = srr.employee_number
/* all staff */
left join
    {{ ref("base_people__staff_roster") }} as srt on s.teammate = srt.employee_number