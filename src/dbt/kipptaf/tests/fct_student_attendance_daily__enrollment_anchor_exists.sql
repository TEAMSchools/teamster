-- Every (school, academic year) with attendance rows must have at least one
-- is_current_record = TRUE. A zero-anchor school means the point-in-time
-- enrollment headcount would read 0 for it — the non-session-day rebuild
-- failure mode (a future-row max collapsing past the last real row). school is
-- identified via dim_student_enrollments (location_key); academic_year is the
-- KIPP July-start year from date_key.
with
    anchored as (
        select
            d.location_key,

            f.is_current_record,

            if(
                extract(month from f.date_key) >= 7,
                extract(year from f.date_key),
                extract(year from f.date_key) - 1
            ) as academic_year,
        from {{ ref("fct_student_attendance_daily") }} as f
        inner join
            {{ ref("dim_student_enrollments") }} as d
            on f.student_enrollment_key = d.student_enrollment_key
    )

select location_key, academic_year, countif(is_current_record) as n_current,
from anchored
group by location_key, academic_year
having countif(is_current_record) = 0
