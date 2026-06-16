-- At most one is_month_end_record = TRUE per (enrollment stint, calendar month).
-- It marks the stint's last full-membership day of the month, so a month with no
-- membership days has zero and a month with membership days has exactly one.
select
    student_enrollment_key,
    date_trunc(date_key, month) as month_start,
    countif(is_month_end_record) as n_month_end,
from {{ ref("fct_student_attendance_daily") }}
group by student_enrollment_key, date_trunc(date_key, month)
having countif(is_month_end_record) > 1
