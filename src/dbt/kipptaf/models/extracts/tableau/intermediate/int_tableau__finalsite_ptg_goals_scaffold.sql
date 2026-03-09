with
    goals_base as (
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,
            grade_level,
            goal_granularity,
            goal_type,
            goal_name,
            goal_value,

            case
                when goal_name = 'New Student Target'
                then 'New'
                when goal_name = 'Re-Enroll Projection'
                then 'Returning'
                else 'All'
            end as enrollment_type,

        from {{ ref("stg_google_sheets__finalsite__goals") }}
        /* hardcoding year to avoid issues when PS rollsover and next year because
           current year */
        where goal_type = 'Enrollment' and enrollment_academic_year = 2026
    )

select
    enrollment_academic_year,
    region,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    enrollment_type,

    seat_target,
    fdos_target,
    budget_target,
    new_student_target,
    re_enroll_projection,

from
    goals_base pivot (
        avg(goal_value) for goal_name in (
            'Seat Target' as seat_target,
            'FDOS Target' as fdos_target,
            'Budget Target' as budget_target,
            'New Student Target' as new_student_target,
            'Re-Enroll Projection' as re_enroll_projection
        )
    )
