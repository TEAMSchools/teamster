-- Every completed (school, school week) with attendance rows must have at least
-- one is_enrollment_week_end_record = TRUE. school_week_start_date from
-- dim_dates is the school-week bucket. Scoped to completed weeks only
-- (school_week_start_date < date_trunc(today, week(monday))) to avoid false
-- positives on the in-progress current week.
with
    anchored as (
        select
            d.location_key, dt.school_week_start_date, f.is_enrollment_week_end_record,
        from {{ ref("fct_student_attendance_daily") }} as f
        inner join
            {{ ref("dim_student_enrollments") }} as d
            on f.student_enrollment_key = d.student_enrollment_key
        inner join {{ ref("dim_dates") }} as dt on f.date_key = dt.date_key
        where
            dt.school_week_start_date < date_trunc(
                current_date('{{ var("local_timezone") }}'),
                -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
                week(monday)
            )
    )

select
    location_key,
    school_week_start_date,
    countif(is_enrollment_week_end_record) as n_week_end,
from anchored
group by location_key, school_week_start_date
having countif(is_enrollment_week_end_record) = 0
