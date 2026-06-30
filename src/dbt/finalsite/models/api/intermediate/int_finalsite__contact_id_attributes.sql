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

    -- Focus stores student_id as the FLDOE district number (8400) prefixed to
    -- the Finalsite-minted id; this prefixed value equals Focus
    -- `students.student_id` directly and is what every Focus extract emits.
    concat('8400', focus_student_id) as focus_student_id_prefixed,
from
    attributes pivot (
        max(value_string)
        for field_name
        in ('power_school_contact_id', 'powerschool_student_number', 'focus_student_id')
    )
