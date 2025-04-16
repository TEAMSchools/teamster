select student_number, count(distinct grad_eligibility) as n,
from {{ ref("int_students__graduation_path_codes") }}
group by all
having count(distinct grad_eligibility) > 1
