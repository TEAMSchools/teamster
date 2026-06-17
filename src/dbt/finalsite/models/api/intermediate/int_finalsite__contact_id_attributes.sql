select
    c.finalsite_enrollment_id,

    max(
        if(a.field_name = 'power_school_contact_id', a.value.string_value, null)
    ) as power_school_contact_id,

    max(
        if(a.field_name = 'powerschool_student_number', a.value.string_value, null)
    ) as powerschool_student_number,
from {{ ref("stg_finalsite__contacts") }} as c
cross join unnest(c.id_attributes) as a
group by c.finalsite_enrollment_id
