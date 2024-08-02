select
    srh.employee_number,
    srh.preferred_name_lastfirst,
    srh.business_unit_home_name,
    srh.home_work_location_name,
    srh.home_work_location_grade_band,
    srh.department_home_name,
    srh.primary_grade_level_taught,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.report_to_sam_account_name,

    rt.type as tracking_type,
    rt.code as tracking_code,
    rt.name as tracking_rubric,
    rt.academic_year as tracking_academic_year,
    rt.is_current,

    m.goal_code,
    m.goal_name,
    m.strand_name,
    m.bucket_name,

    a.assignment_id,
    a.created as assignment_date,
    a.creator_name,
    if(a.assignment_id is not null, 1, 0) as is_assigned,

from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on srh.business_unit_home_name = rt.region
    and (
        rt.start_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
        or rt.end_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
    )
    and rt.type = 'MG'
    and rt.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("stg_schoolmint_grow__users") }} as u
    on srh.employee_number = u.internal_id_int
left join
    {{ ref("stg_schoolmint_grow__assignments") }} as a
    on u.user_id = a.user_id
    and a.created_date_local between rt.start_date and rt.end_date
left join
    {{ ref("stg_schoolmint_grow__assignments__tags") }} as t
    on a.assignment_id = t.assignment_id
left join {{ ref("stg_schoolmint_grow__microgoals") }} as m on t.tag_id = m.goal_tag_id
where
    srh.job_title in ('Teacher', 'Teacher in Residence', 'Learning Specialist')
    and srh.assignment_status = 'Active'
