-- at most one is_month_end_record = TRUE per (enrollment, calendar month)
select
    student_enrollment_key,
    date_trunc(date_key, month) as cal_month,
    countif(is_month_end_record) as n_month_end,
from {{ ref("fct_student_enrollment_daily") }}
group by student_enrollment_key, date_trunc(date_key, month)
having countif(is_month_end_record) > 1
