-- At most one is_week_end_record = TRUE per (enrollment stint, PowerSchool school
-- week). school_week_start_date from dim_dates is the school-week bucket —
-- matches the week_start_monday partition used by the window (verified equal on
-- all historical attendance rows).
select
    f.student_enrollment_key,
    d.school_week_start_date,
    countif(f.is_week_end_record) as n_week_end,
from {{ ref("fct_student_attendance_daily") }} as f
inner join {{ ref("dim_dates") }} as d on f.date_key = d.date_key
group by f.student_enrollment_key, d.school_week_start_date
having countif(f.is_week_end_record) > 1
