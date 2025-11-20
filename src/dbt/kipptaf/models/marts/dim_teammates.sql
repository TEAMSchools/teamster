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
            r.employee_number,
            r.effective_date_start,
            r.effective_date_end,
            r.formatted_name,
            r.assignment_status,
            r.race_ethnicity_reporting,
            r.gender_identity,
            r.home_business_unit_name,
            r.home_department_name,
            r.home_work_location_name,
            r.home_work_location_grade_band,
            r.job_title,
            r.reports_to_formatted_name,
            r.primary_indicator,
            r.academic_year,
            gl.grade_level as grade_taught,
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
        from roster as r
        left join
            grade_levels as gl
            on r.powerschool_teacher_number = gl.teachernumber
            and r.academic_year = gl.academic_year
            and gl.grade_level_rank = 1
    )

select *,
from final
