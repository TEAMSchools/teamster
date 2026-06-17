select
    c.finalsite_enrollment_id,

    max(
        if(
            a.field_name = '{{ var("finalsite_focus_student_id_field") }}',
            a.value.string_value,
            null
        )
    ) as focus_student_id,
from {{ ref("stg_finalsite__contacts") }} as c
cross join unnest(c.id_attributes) as a
group by c.finalsite_enrollment_id
