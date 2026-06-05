select
    f.* except (student, university),

    f.student.id as student__id,
    s.external_student_id as student__external_student_id,

    f.university.id as university__id,
    f.university.ipeds_id as university__ipeds_id,
-- The followings API has the same gap as admissions: student.external_student_id
-- is not returned in the nested student object; join students to resolve it.
from {{ source("overgrad", "src_overgrad__followings") }} as f
left join {{ ref("stg_overgrad__students") }} as s on f.student.id = s.id
