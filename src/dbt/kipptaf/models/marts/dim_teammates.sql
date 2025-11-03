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
            roster.employee_number,
            roster.formatted_name,
            roster.assignment_status,
            roster.race_ethnicity_reporting,
            roster.home_business_unit_name,
            roster.home_work_location_name,
            roster.home_work_location_powerschool_school_id,
            roster.home_work_location_grade_band,
            roster.home_department_name,
            roster.job_title,
            roster.reports_to_formatted_name,
            roster.effective_date_start,
            roster.effective_date_end,
            roster.primary_indicator,
            roster.is_current_record,
            grade_levels.grade_level as grade_taught,
            if(
                roster.primary_indicator
                and (roster.is_current_record or roster.is_prestart),
                true,
                false
            ) as current_roster,
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
            {{
                dbt_utils.generate_surrogate_key(
                    ["employee_number", "effective_date_start"]
                )
            }} as teammate_event_key,
        from roster
        left join
            grade_levels
            on roster.powerschool_teacher_number = grade_levels.teachernumber
            and roster.academic_year = grade_levels.academic_year
            and grade_levels.grade_level_rank = 1
    )

select *,
from final
