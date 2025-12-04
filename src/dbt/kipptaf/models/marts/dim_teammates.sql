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

    years_experience as (
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
            r.years_exp_outside_kipp,

            gl.grade_level as grade_taught,

            m.memberships,
            m.is_leader_development_program,
            m.is_teacher_development_program,

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

            sum(
                if(
                    job_title in (
                        'Teacher',
                        'Teacher in Residence',
                        'Learning Specialist',
                        'Teacher ESL',
                        'Teacher,ESL',
                        'Teacher in Residence ESL',
                        'Co-Teacher',
                        'Co-Teacher_historical'
                    ),
                    1,
                    0
                )
            ) over (partition by r.employee_number order by r.academic_year)
            as years_teaching_at_kipp,

            sum(1) over (
                partition by employee_number order by academic_year
            ) as year_at_kipp,

        from roster as r
        left join
            grade_levels as gl
            on r.powerschool_teacher_number = gl.teachernumber
            and r.academic_year = gl.academic_year
            and gl.grade_level_rank = 1
        left join
            {{ ref("int_adp_workforce_now__employee_memberships_by_year") }} as m
            on r.worker_id = m.associate_id
            and r.academic_year = m.academic_year
    ),

    final as (
        select
            *,
            coalesce(years_exp_outside_kipp, 0)
            + years_teaching_at_kipp as total_years_teaching,
        from years_experience
    )

select *,
from final
