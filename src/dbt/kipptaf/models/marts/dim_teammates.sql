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
            {{
                date_to_fiscal_year(
                    date_field="worker_termination_date",
                    start_month=7,
                    year_source="start",
                )
            }} as termination_academic_year,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator

    ),

    {# limiting system generated actions to records <= worker termination year
    for academic year fact tables #}
    remove_system_generated_updates as (
        select *
        from roster
        where
            academic_year
            <= coalesce(termination_academic_year, {{ var("current_academic_year") }})
            and assignment_status_reason
            not in ('Import Created Action', 'Upgrade Created Action')
    ),

    grade_levels as (select *, from {{ ref("int_powerschool__teacher_grade_levels") }}),

    managers as (select distinct reports_to_employee_number, from roster),

    final as (
        select
            rm.teammate_history_key,
            rm.academic_year,
            rm.assignment_status,
            rm.assignment_status_reason,
            rm.assignment_status_lag,
            rm.base_remuneration_annual_rate_amount as salary,
            rm.effective_date_end,
            rm.effective_date_start,
            rm.employee_number,
            rm.formatted_name,
            rm.gender_identity,
            rm.home_business_unit_name as entity,
            rm.home_department_name as department,
            rm.home_work_location_grade_band as grade_band,
            rm.home_work_location_name as location,
            rm.is_current_record,
            rm.is_prestart,
            rm.job_title,
            rm.languages_spoken,
            rm.mail,
            rm.primary_indicator,
            rm.race_ethnicity_reporting,
            rm.reports_to_formatted_name as manager_name,
            rm.worker_hire_date_recent,
            rm.worker_original_hire_date,
            rm.worker_rehire_date,
            rm.worker_termination_date,
            rm.termination_academic_year,
            gl.grade_level as grade_taught,
            if(
                rm.job_title in (
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
                rm.employee_number
                in (select managers.reports_to_employee_number, from managers),
                true,
                false
            ) as is_manager,
        from remove_system_generated_updates as rm
        left join
            grade_levels as gl
            on rm.powerschool_teacher_number = gl.teachernumber
            and rm.academic_year = gl.academic_year
            and gl.grade_level_rank = 1
    )

select *,
from final
