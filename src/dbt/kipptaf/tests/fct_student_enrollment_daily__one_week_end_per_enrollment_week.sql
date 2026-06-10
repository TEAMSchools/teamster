-- at most one is_week_end_record = 1 per (enrollment, ISO week)
select
    student_enrollment_key,
    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    date_trunc(date_key, week(monday)) as iso_week,
    sum(is_week_end_record) as n_week_end,
from {{ ref("fct_student_enrollment_daily") }}
group by
    student_enrollment_key,
    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    date_trunc(date_key, week(monday))
having sum(is_week_end_record) > 1
