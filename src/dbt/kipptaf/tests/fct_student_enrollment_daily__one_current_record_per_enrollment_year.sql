-- at most one is_current_record = TRUE per (enrollment, academic_year)
select student_enrollment_key, academic_year, countif(is_current_record) as n_current,
from {{ ref("fct_student_enrollment_daily") }}
group by student_enrollment_key, academic_year
having countif(is_current_record) > 1
