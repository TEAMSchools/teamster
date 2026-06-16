-- At most one is_week_end_record = TRUE per (enrollment stint, PowerSchool school
-- week). It marks the stint's last full-membership day of each school week
-- (week_start_monday, exposed as school_week_start_date) — guards the school-week
-- realignment that backs the attendance CA weekly trend.
select
    student_enrollment_key,
    school_week_start_date,
    countif(is_week_end_record) as n_week_end,
from {{ ref("fct_student_attendance_daily") }}
group by student_enrollment_key, school_week_start_date
having countif(is_week_end_record) > 1
