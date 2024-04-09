select
    sr.employee_number,
    sr.preferred_name_lastfirst,
    sr.business_unit_home_name,
    sr.home_work_location_name,
    sr.home_work_location_grade_band,
    sr.department_home_name,
    sr.primary_grade_level_taught,
    sr.job_title,
    sr.report_to_preferred_name_lastfirst,
    sr.worker_original_hire_date,
    sr.assignment_status,
    sr.sam_account_name,
    sr.report_to_sam_account_name,

    rt.type as form_type,
    rt.code as form_term,
    rt.name as form_long_name,
    rt.academic_year,
    rt.start_date,
    rt.end_date,

    m.goal_code,
    m.goal_name,
    m.strand_name,
    m.bucket_name,

    a.assignment_id,
    a.created as assignment_date,
    a.creator_name,

from {{ ref("base_people__staff_roster") }} as sr
cross join {{ ref("stg_reporting__terms") }} as rt
left join
    {{ ref("stg_schoolmint_grow__users") }} as u
    on sr.employee_number = u.internal_id_int
left join
    {{ ref("stg_schoolmint_grow__assignments") }} as a
    on u.user_id = a.user_id
    and a.created_date_local between rt.start_date and rt.end_date
left join
    {{ ref("stg_schoolmint_grow__assignments__tags") }} as t
    on a.assignment_id = t.assignment_id
left join {{ ref("stg_schoolmint_grow__microgoals") }} as m on t.tag_id = m.goal_tag_id
/* using O3 weekly assignment as proxy for 1 microgoal per week requirement*/
where
    rt.type = 'O3'
    and sr.assignment_status = 'Active'
    and (sr.job_title like '%Teacher%' or sr.job_title = 'Learning Specialist')
