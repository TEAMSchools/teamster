with
    enrollment_weeks as (
        select
            student_number,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday,

            /* first instant of the day AFTER the week closes, local — i.e. the
               value in effect at the END of the week */
            timestamp(
                date_add(week_end_sunday, interval 1 day), '{{ var("local_timezone") }}'
            ) as week_end_boundary,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and school_level = 'HS'
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    sat_total as (
        select school_specific_id, test_type, score, dbt_valid_from, dbt_valid_to,
        from {{ ref("snapshot_kippadb__standardized_test_rollup") }}
        where
            test_type in ('SAT', 'PSAT NMSQT', 'PSAT 8/9')
            and test_subject = 'Combined'
            and score is not null
    )

select
    co.student_number,
    co.academic_year,
    co.schoolid,
    co.week_start_monday,
    co.week_end_sunday,

    sat.test_type,
    sat.score,
from enrollment_weeks as co
inner join
    sat_total as sat
    on co.student_number = sat.school_specific_id
    and co.week_end_boundary > sat.dbt_valid_from
    and co.week_end_boundary <= sat.dbt_valid_to
