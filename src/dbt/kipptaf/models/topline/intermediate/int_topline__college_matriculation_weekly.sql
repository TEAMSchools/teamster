with
    enrollment_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            salesforce_id,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and grade_level = 12
            and academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    m.is_submitted_ba,
    m.is_accepted_ba,
    m.is_matriculated_ba,
    m.is_submitted_quality_bar_4yr_int,
from enrollment_weeks as co
left join
    {{ ref("snapshot_kippadb__app_rollup") }} as m
    on co.salesforce_id = m.applicant
    and co.week_end_boundary > m.dbt_valid_from
    and co.week_end_boundary <= m.dbt_valid_to
