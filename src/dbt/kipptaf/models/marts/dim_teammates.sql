with
    roster as (
        select
            /* creating academic year to join to grade levels*/
            *,
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

    memberships as (
        select * from {{ ref("int_adp_workforce_now__employee_memberships_by_year") }}
    ),

    final as (
        select
            roster.employee_number,
            roster.effective_date_start,
            roster.effective_date_end,
            roster.worker_termination_date,
            roster.formatted_name,
            roster.assignment_status,
            roster.race_ethnicity_reporting,
            roster.gender_identity,
            roster.home_business_unit_name,
            roster.home_department_name,
            roster.home_work_location_name,
            roster.home_work_location_grade_band,
            roster.job_title,
            roster.reports_to_formatted_name,
            roster.primary_indicator,
            roster.academic_year,
            roster.years_exp_outside_kipp,
            roster.years_teaching_in_njfl,
            roster.years_teaching_outside_njfl,
            roster.is_teacher,

            grade_levels.grade_level as grade_taught,

            memberships.memberships,
            memberships.is_leader_development_program,
            memberships.is_teacher_development_program,

            if(
                roster.assignment_status in ('Terminated', 'Deceased'),
                coalesce(roster.assignment_status_reason, 'Missing/no Reason'),
                null
            ) as termination_reason,

            case
                when contains_substr(roster.job_title, 'Teacher')
                then true
                when contains_substr(roster.job_title, 'Learning Specialist')
                then true
                else false
            end as is_teacher,

        from roster
        left join
            grade_levels
            on roster.powerschool_teacher_number = grade_levels.teachernumber
            and roster.academic_year = grade_levels.academic_year
            and grade_levels.grade_level_rank = 1
        left join
            memberships
            on roster.worker_id = memberships.associate_id
            and roster.academic_year = memberships.academic_year
    )

select *,
from final
