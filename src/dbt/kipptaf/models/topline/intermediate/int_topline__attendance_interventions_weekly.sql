with
    enrollment_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week and academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    ca.successful_call_count,
    ca.total_anticipated_calls,
    ca.pct_interventions_complete,
from enrollment_weeks as co
left join
    {{ ref("snapshot_students__attendance_interventions_rollup") }} as ca
    on co.student_number = ca.student_number
    and co.academic_year = ca.academic_year
    and co.week_end_boundary > ca.dbt_valid_from
    and co.week_end_boundary <= ca.dbt_valid_to
