with
    {# creating fields to join to academic year fact tables and remove 
    unnecessary rows #}
    roster as (
        select
            *,

            {{
                dbt_utils.generate_surrogate_key(
                    ["employee_number", "effective_date_start"]
                )
            }} as teammate_history_key,
            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator
    ),

    grade_levels as (select *, from {{ ref("int_powerschool__teacher_grade_levels") }}),

    managers as (select distinct reports_to_employee_number, from roster),

    performance_management_tiers as (
        select * from {{ ref('int_performance_management__overall_scores') }}),

    years_experience as (
        select * from {{ ref('int_people__years_experience') }}
    ),

    final as (
        select
            r.teammate_history_key,
            r.academic_year,
            r.assignment_status,
            r.assignment_status_reason,
            r.assignment_status_lag,
            r.assignment_status_effective_date,
            r.base_remuneration_annual_rate_amount as salary,
            r.effective_date_end,
            r.effective_date_start,
            r.employee_number,
            r.formatted_name,
            r.gender_identity,
            r.home_business_unit_name as entity,
            r.home_department_name as department,
            r.home_work_location_grade_band as grade_band,
            r.home_work_location_name as `location`,
            r.is_current_record,
            r.is_prestart,
            r.job_title,
            r.languages_spoken,
            r.mail,
            r.primary_indicator,
            r.race_ethnicity_reporting,
            r.reports_to_formatted_name as manager_name,
            r.worker_hire_date_recent,
            r.worker_original_hire_date,
            r.worker_rehire_date,
            r.worker_termination_date,
            gl.grade_level as grade_taught,
            pm.final_tier as performance_management_tier,
            ye.years_experience_total,
            ye.years_teaching_total,
            if(
                r.job_title in (
                    'Teacher',
                    'Teacher in Residence',
                    'ESE Teacher',
                    'Learning Specialist',
                    'Teacher ESL',
                    'Teacher in Residence ESL'
                ),
                true,
                false
            ) as is_teacher,
            if(
                r.employee_number
                in (select managers.reports_to_employee_number, from managers),
                true,
                false
            ) as is_manager,
            lag(r.base_remuneration_annual_rate_amount) over (
                partition by r.employee_number order by r.effective_date_start
            ) as previous_salary,
            lag(r.job_title) over (
                partition by r.employee_number order by r.effective_date_start
            ) as previous_job_title,
            
        from roster as r
        left join
            grade_levels as gl
            on r.powerschool_teacher_number = gl.teachernumber
            and r.academic_year = gl.academic_year
            and gl.grade_level_rank = 1
        left join performance_management_tiers as pm
        on r.employee_number = pm.employee_number
        and r.academic_year = pm.academic_year
        left join years_experience as ye
        on r.employee_number = ye.employee_number
        and r.academic_year = ye.academic_year
    )

select *,
from final
