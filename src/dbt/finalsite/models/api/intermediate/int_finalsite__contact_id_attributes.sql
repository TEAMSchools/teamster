with
    attributes as (
        select
            c.finalsite_enrollment_id,
            a.field_name,
            a.value.string_value as value_string,
        from {{ ref("stg_finalsite__contacts") }} as c
        cross join unnest(c.id_attributes) as a
    )

select
    finalsite_enrollment_id,
    power_school_contact_id,
    powerschool_student_number,
    focus_student_id,
from
    attributes pivot (
        max(value_string)
        for field_name
        in ('power_school_contact_id', 'powerschool_student_number', 'focus_student_id')
    )
