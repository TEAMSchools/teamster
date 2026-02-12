with
    roster_history as (
        select *,
        from {{ ref("int_people__staff_roster_history") }}
        where
            primary_indicator
            and job_title in (
                'Teacher',
                'Teacher in Residence',
                'ESE Teacher',
                'Learning Specialist',
                'Learning Specialist Coordinator'
            )
    ),

    roster_current as (select *, from {{ ref("int_people__staff_roster") }}),

    observation_details as (
        select *, from {{ ref("int_performance_management__observation_details") }}
    ),

    observation_details_agg as (
        select
            observation_id,

            max(
                if(
                    measurement_name like '%Teacher Moves Track%',
                    measurement_dropdown_selection,
                    null
                )
            ) as teacher_moves_track,

            max(
                if(
                    measurement_name like '%Student Habits Track%',
                    measurement_dropdown_selection,
                    null
                )
            ) as student_habits_track,

            max(
                if(
                    measurement_name like '%Number%',
                    measurement_dropdown_selection,
                    null
                )
            ) as number_of_kids,
        from observation_details
        group by observation_id
    ),

    grade_levels as (
        select *,
        from {{ ref("int_powerschool__teacher_grade_levels") }}
        where grade_level_rank = 1
    ),

    observation_pivot as (
        select o.*, od.teacher_moves_track, od.student_habits_track, od.number_of_kids,
        from {{ ref("int_performance_management__observations") }} as o
        inner join observation_details_agg as od on o.observation_id = od.observation_id
        where o.observation_type_abbreviation in ('WT', 'O3')
    )

select
    rh.employee_number,
    rh.formatted_name as teammate,
    rh.home_business_unit_name as entity,
    rh.home_work_location_name as `location`,
    rh.home_work_location_grade_band as grade_band,
    rh.home_department_name as department,
    rh.job_title,
    rh.reports_to_formatted_name as manager,
    rh.sam_account_name,
    rh.reports_to_sam_account_name,
    rh.race_ethnicity_reporting,

    rt.type,
    rt.code,
    rt.name as `period`,
    rt.academic_year,
    rt.is_current,
    rt.start_date,
    rt.end_date,

    op.observation_id,
    op.observed_at,
    op.rubric_name,
    op.glows,
    op.grows,
    op.observation_score,
    op.teacher_moves_track,
    op.student_habits_track,
    op.number_of_kids,

    od.strand_name,
    od.measurement_name,
    od.row_score,
    od.measurement_comments,

    rc.formatted_name as observer_name,

    gl.grade_taught,

    if(op.observation_id is not null, 1, 0) as is_observed,

from roster_history as rh
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on rh.home_business_unit_name = rt.region
    and rt.start_date between rh.effective_date_start and rh.effective_date_end
    and rt.academic_year = {{ var("current_academic_year") }}
    and rt.type in ('WT', 'O3')
left join
    observation_pivot as op
    on rh.employee_number = op.employee_number
    and rt.type = op.observation_type_abbreviation
    and op.observed_at between rt.start_date and rt.end_date
left join observation_details as od on op.observation_id = od.observation_id
left join roster_current as rc on op.observer_employee_number = rc.employee_number
left join
    grade_levels as gl
    on rh.powerschool_teacher_number = gl.teachernumber
    and rh.home_work_location_dagster_code_location = gl._dbt_source_project
    and op.academic_year = gl.academic_year
where rh.primary_indicator and rh.assignment_status = 'Active'

union all

select
    rh.employee_number,
    rh.formatted_name as teammate,
    rh.home_business_unit_name as entity,
    rh.home_work_location_name as `location`,
    rh.home_work_location_grade_band as grade_band,
    rh.home_department_name as department,
    rh.job_title,
    rh.reports_to_formatted_name as manager,
    rh.sam_account_name,
    rh.reports_to_sam_account_name,
    rh.race_ethnicity_reporting,

    op.observation_type_abbreviation,

    cast(null as string) as code,
    cast(null as string) as `period`,

    op.academic_year,

    false as is_current,

    cast(null as date) as `start_date`,
    cast(null as date) as end_date,

    op.observation_id,
    op.observed_at,
    op.rubric_name,
    op.glows,
    op.grows,
    op.observation_score,
    op.teacher_moves_track,
    op.student_habits_track,
    op.number_of_kids,

    od.strand_name,
    od.measurement_name,
    od.row_score,
    od.measurement_comments,

    rc.formatted_name as observer_name,

    gl.grade_taught,

    if(op.observation_id is not null, 1, 0) as is_observed,

from observation_pivot as op
left join
    roster_history as rh
    on op.employee_number = rh.employee_number
    and op.observed_at between rh.effective_date_start and rh.effective_date_end
left join observation_details as od on op.observation_id = od.observation_id
left join roster_current as rc on op.observer_employee_number = rc.employee_number
left join
    grade_levels as gl
    on rh.powerschool_teacher_number = gl.teachernumber
    and rh.home_work_location_dagster_code_location = gl._dbt_source_project
    and op.academic_year = gl.academic_year
where
    op.academic_year < {{ var("current_academic_year") }}
    and op.observation_id is not null
