select
    s.* except (student_aid_index),

    cf.* except (id, source_object, student_aid_index),

    coalesce(s.student_aid_index, cf.student_aid_index) as student_aid_index,
from {{ ref("stg_overgrad__students") }} as s
left join
    {{ ref("int_overgrad__custom_fields_pivot") }} as cf
    on s.id = cf.id
    and cf.source_object = 'students'
