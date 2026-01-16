with
    roster as (
        select
            *,
            {# creating field to join to PowerSchool grade levels #}
            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("int_people__staff_roster_history") }}
    ),

    grade_levels as (select *, from {{ ref("int_powerschool__teacher_grade_levels") }}),

    managers as (select distinct reports_to_employee_number, from roster),

    attrition as (
        select
            employee_number,
            academic_year,
            max(
                if(
                    effective_date_start < date (academic_year,7,1) and
                    worker_termination_date between date(academic_year, 9, 1) and date(
                        academic_year + 1, 4, 30
                    ),
                    1,
                    0
                )
            ) as is_attrition,
        from roster
        group by employee_number, academic_year
    ),

    final as (
        select
            roster.academic_year,
            roster.assignment_status,
            roster.base_remuneration_annual_rate_amount as salary,
            roster.effective_date_end,
            roster.effective_date_start,
            roster.employee_number,
            roster.formatted_name,
            roster.gender_identity,
            roster.home_business_unit_name as entity,
            roster.home_department_name as department,
            roster.home_work_location_grade_band as grade_band,
            roster.home_work_location_name as location,
            roster.is_current_record,
            roster.is_prestart,
            roster.job_title,
            roster.languages_spoken,
            roster.mail,
            roster.primary_indicator,
            roster.race_ethnicity_reporting,
            roster.reports_to_formatted_name as manager_name,
            roster.worker_hire_date_recent,
            roster.worker_original_hire_date,
            roster.worker_rehire_date,
            roster.worker_termination_date,
            grade_levels.grade_level as grade_taught,
            attrition.is_attrition,
            if(
                roster.job_title in (
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
                roster.employee_number
                in (select managers.reports_to_employee_number, from managers),
                true,
                false
            ) as is_manager,
        from roster
        left join
            grade_levels
            on roster.powerschool_teacher_number = grade_levels.teachernumber
            and roster.academic_year = grade_levels.academic_year
            and grade_levels.grade_level_rank = 1
        left join
            attrition
            on roster.employee_number = attrition.employee_number
            and roster.academic_year = attrition.academic_year
    )

select
    formatted_name,
    academic_year,
    assignment_status,
    effective_date_start,
    effective_date_end,
    worker_termination_date,
    is_attrition,
from final
order by employee_number, academic_year
