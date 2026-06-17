select
    c.finalsite_enrollment_id,

    max(
        if(a.field_name = 'latino_hispanic_yn', a.value.boolean_value, null)
    ) as is_latino_hispanic,
from {{ ref("stg_finalsite__contacts") }} as c
cross join unnest(c.custom_attributes) as a
group by c.finalsite_enrollment_id
