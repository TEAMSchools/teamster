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

    final as (
        select
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
        from roster
        left join
            grade_levels
            on roster.powerschool_teacher_number = grade_levels.teachernumber
            and roster.academic_year = grade_levels.academic_year
            and grade_levels.grade_level_rank = 1
    )

select *,
from final
