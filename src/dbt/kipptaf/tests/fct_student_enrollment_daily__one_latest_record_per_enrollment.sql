-- exactly one is_latest_record per student_enrollment_key
select student_enrollment_key, countif(is_latest_record) as n_latest,
from {{ ref("fct_student_enrollment_daily") }}
group by student_enrollment_key
having countif(is_latest_record) != 1
