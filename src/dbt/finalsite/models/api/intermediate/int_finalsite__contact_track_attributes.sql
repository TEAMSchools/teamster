with
    attributes as (
        select
            c.finalsite_enrollment_id,
            a.field_name,
            a.value.string_value as value_string,
        from {{ ref("stg_finalsite__contacts") }} as c
        cross join unnest(c.track_attributes) as a
    )

select
    finalsite_enrollment_id,
    assigned_school_ss,
    bsr_contact_info_updated_yn,
    promotion_status_ss,
from
    attributes pivot (
        max(value_string) for field_name
        in ('assigned_school_ss', 'bsr_contact_info_updated_yn', 'promotion_status_ss')
    )
