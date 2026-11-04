select
    student_number,
    academic_year,

    max(cls_treatment_cp) as treatment_cp,
    max(cls_treatment_rdc) as treatment_rdc,
    max(cls_treatment_rr) as treatment_rr,
from {{ ref("int_ignite__treatment_assignment") }}
group by student_number, academic_year
