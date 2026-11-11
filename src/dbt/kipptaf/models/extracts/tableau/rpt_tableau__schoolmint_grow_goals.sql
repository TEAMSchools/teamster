-- trunk-ignore(sqlfluff/ST06): contract column order is mandated
select
    srh.employee_number,
    srh.formatted_name as teammate,
    srh.home_work_location_grade_band as grade_band,
    srh.reports_to_formatted_name as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,

    lc.location_clean_name,
    lc.campus_name,

    case
        srh.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else srh.home_business_unit_name
    end as home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,

    rt.type as tracking_type,
    rt.code as tracking_code,
    rt.name as tracking_rubric,
    rt.academic_year as tracking_academic_year,
    rt.start_date,
    rt.end_date,
    rt.is_current,

    f.staff_observation_assignment_key as assignment_id,
    f.assignment_created_timestamp as assignment_date,

    gt.staff_observation_goal_type_key as goal_code,
    gt.goal_name,
    gt.strand_name,
    gt.bucket_name,
    gt.goal_type as goal_type_name,

    cs.full_name as observer,

    tgl.grade_level as grade_taught,

    if(f.staff_observation_assignment_key is not null, 1, 0) as is_assigned,
from {{ ref("int_people__staff_roster_history") }} as srh
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on srh.home_business_unit_name = rt.region
    and (
        rt.start_date between srh.effective_date_start and srh.effective_date_end
        or rt.end_date between srh.effective_date_start and srh.effective_date_end
    )
    and rt.type = 'MG'
    and rt.academic_year = {{ var("current_academic_year") }}
left join {{ ref("dim_staff") }} as ts on srh.employee_number = ts.staff_unique_id
left join
    {{ ref("fct_staff_observation_goals") }} as f
    on ts.staff_key = f.teacher_staff_key
    and f.assignment_date between rt.start_date and rt.end_date
left join
    {{ ref("dim_staff_observation_goal_types") }} as gt
    on f.staff_observation_goal_type_key = gt.staff_observation_goal_type_key
left join {{ ref("dim_staff") }} as cs on f.creator_staff_key = cs.staff_key
left join
    {{ ref("int_students__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and srh.home_work_location_dagster_code_location = tgl._dbt_source_project
    and rt.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
where
    srh.primary_indicator
    and srh.assignment_status = 'Active'
    /*
     job_function is the durable key, but ADP only began supplying it in 2026 --
     it is 0% populated on roster_history for 2019-2025 and 35% for 2026 -- so a
     job_title allow list carries the historical rows until the backfill in
     #4665 lets the fallback be deleted. This list is kept identical to the one
     in rpt_tableau__teacher_observations; they had silently diverged.
     */
    and (
        srh.job_function in ('Teacher', 'Teacher in Residence')
        or (
            srh.job_function is null
            and srh.job_title in (
                'Teacher',
                'Teacher in Residence',
                'ESE Teacher',
                'Learning Specialist',
                'Learning Specialist Coordinator',
                'Teacher ESL',
                'Teacher in Residence ESL'
            )
        )
    )
