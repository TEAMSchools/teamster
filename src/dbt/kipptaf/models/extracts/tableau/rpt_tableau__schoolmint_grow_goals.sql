select
    srh.employee_number,
    srh.preferred_name_lastfirst as teammate,
    srh.business_unit_home_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.department_home_name as department,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.report_to_sam_account_name,

    rt.type as tracking_type,
    rt.code as tracking_code,
    rt.name as tracking_rubric,
    rt.academic_year as tracking_academic_year,
    rt.start_date,
    rt.end_date,
    rt.is_current,

    m.goal_code,
    m.goal_name,
    m.strand_name,
    m.bucket_name,

    a.assignment_id,
    a.created as assignment_date,
    a.creator_name as observer,

    tgl.grade_level as grade_taught,

    if(a.assignment_id is not null, 1, 0) as is_assigned,
from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on srh.business_unit_home_name = rt.region
    and (
        rt.start_date
        between srh.work_assignment_start_date and srh.work_assignment_end_date
        or rt.end_date
        between srh.work_assignment_start_date and srh.work_assignment_end_date
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
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and rt.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
where
    (srh.job_title like '%Teacher%' or srh.job_title like '%Learning%')
    and srh.assignment_status = 'Active'
