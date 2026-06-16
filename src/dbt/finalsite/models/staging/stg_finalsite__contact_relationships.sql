with
    relationships as (
        select
            c.id as finalsite_enrollment_id,
            r.id as relationship_id,
            r.rel_type,
            r.primary as is_primary,
            r.contact.id as guardian_finalsite_id,
            r.contact.first_name as guardian_first_name,
            r.contact.last_name as guardian_last_name,
            r.contact.email as guardian_email,
            r.contact.gender as guardian_gender,
            r.contact.phone_1.number as guardian_phone,
            (
                select av.value
                from unnest(r.contact.id_attributes) as av
                where av.field_name = 'powerschool_contact_id'
                limit 1
            ) as guardian_powerschool_contact_id,
        from {{ source("finalsite", "contacts") }} as c
        cross join unnest(c.relationships) as r
        where r.contact is not null
    )

select
    *,
    case
        when rel_type = 'parent' and guardian_gender = 'F'
        then 'mother'
        when rel_type = 'parent' and guardian_gender = 'M'
        then 'father'
        else rel_type
    end as relationship_label,
from relationships
