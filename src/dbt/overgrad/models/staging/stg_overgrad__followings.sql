select
    id,
    created_at,
    updated_at,
    rank,
    academic_fit,
    probability_of_acceptance,
    added_by,

    student.id as student__id,
    student.external_student_id as student__external_student_id,

    university.id as university__id,
    university.ipeds_id as university__ipeds_id,
from {{ source("overgrad", "src_overgrad__followings") }}
