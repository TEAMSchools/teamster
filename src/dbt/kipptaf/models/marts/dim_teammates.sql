with
    roster as (
        select
            *,
            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
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
                    'ESE Teacher'
                ),
                1,
                0
            ) as is_teacher,
        from {{ ref("int_people__staff_roster_history") }}

    ),

        teammate_aggregations as (
        select
            employee_number,
            academic_year,
            min(effective_date_start) over (
                partition by academic_year, employee_number
            ) as min_effective_date_start,
            sum(1) over (
                partition by employee_number order by academic_year
            ) as years_at_kipp,
            sum(is_teacher) over (
                partition by employee_number order by academic_year
            ) as years_teaching_at_kipp,
        from roster
        ),
--figure out dupes
 attrition as (
 select
            roster.employee_number,
            roster.academic_year,
            max(
                case
                    when
                        date(roster.academic_year, 9, 1)
                        between (teammate_aggregations.min_effective_date_start)
                        and date(roster.academic_year + 1, 4, 30)
                        and worker_termination_date
                        between date(roster.academic_year, 9, 1) 
                        and date(roster.academic_year + 1, 8, 31)
                    then 1
                    else 0
                end
            ) as is_attrition
        from roster
        inner join teammate_aggregations on roster.employee_number = teammate_aggregations.employee_number and roster.academic_year = teammate_aggregations.academic_year
        group by employee_number, academic_year
        order by employee_number, academic_year
 )

    grade_levels as (select *, from {{ ref("int_powerschool__teacher_grade_levels") }}),

    final as (
        select
            r.employee_number,
            r.effective_date_start,
            r.effective_date_end,
            r.worker_termination_date,
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
            r.years_teaching_in_njfl,
            r.years_teaching_outside_njfl,
            r.is_teacher,

            gl.grade_level as grade_taught,

            m.memberships,
            m.is_leader_development_program,
            m.is_teacher_development_program,

            y.years_at_kipp,
            y.years_teaching_at_kipp,

            coalesce(r.years_exp_outside_kipp, 0)
            + y.years_teaching_at_kipp as total_years_teaching,

            if(
                r.assignment_status in ('Terminated', 'Deceased'),
                coalesce(r.assignment_status_reason, 'Missing/no Reason'),
                null
            ) as termination_reason,

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
        left join
            years_experience as y
            on r.employee_number = y.employee_number
            and r.academic_year = y.academic_year
    )

select *,
from final
