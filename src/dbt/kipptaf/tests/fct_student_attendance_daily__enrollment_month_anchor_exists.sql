-- Every completed (school, calendar month) with attendance rows must have at
-- least one is_enrollment_month_end_record = TRUE. Scoped to completed months
-- only (month_start < date_trunc(today, month)) to avoid false positives on the
-- in-progress current month, which may not yet have a month-end row.
with
    anchored as (
        select
            d.location_key,

            date_trunc(f.date_key, month) as month_start,

            f.is_enrollment_month_end_record,
        from {{ ref("fct_student_attendance_daily") }} as f
        inner join
            {{ ref("dim_student_enrollments") }} as d
            on f.student_enrollment_key = d.student_enrollment_key
        where
            date_trunc(f.date_key, month)
            < date_trunc(current_date('{{ var("local_timezone") }}'), month)
    )

select
    location_key, month_start, countif(is_enrollment_month_end_record) as n_month_end,
from anchored
group by location_key, month_start
having countif(is_enrollment_month_end_record) = 0
