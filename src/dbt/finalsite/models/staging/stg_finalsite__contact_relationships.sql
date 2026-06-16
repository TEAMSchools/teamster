with
    relationships as (
        select
            c.id as finalsite_enrollment_id,
            r.id as relationship_id,
            r.rel_id,
            r.rel_name,
            r.rel_type,
            r.primary as is_primary,
            r.financial as is_financial,
            r.portal_access as has_portal_access,
            r.contact.id as guardian_finalsite_id,
            r.contact.first_name as guardian_first_name,
            r.contact.middle_name as guardian_middle_name,
            r.contact.last_name as guardian_last_name,
            r.contact.full_name as guardian_full_name,
            r.contact.preferred_name as guardian_preferred_name,
            r.contact.email as guardian_email,
            r.contact.gender as guardian_gender,
            r.contact.phone_1.phone_type as guardian_phone_1_type,
            r.contact.phone_1.number as guardian_phone_1_number,
            r.contact.custom_attributes as guardian_custom_attributes,
            r.contact.id_attributes as guardian_id_attributes,
        from {{ source("finalsite", "contacts") }} as c
        cross join unnest(c.relationships) as r
        where r.contact is not null
    )

select
    finalsite_enrollment_id,
    relationship_id,
    rel_id,
    rel_name,
    rel_type,
    is_primary,
    is_financial,
    has_portal_access,
    guardian_finalsite_id,
    guardian_first_name,
    guardian_middle_name,
    guardian_last_name,
    guardian_full_name,
    guardian_preferred_name,
    guardian_email,
    guardian_gender,
    guardian_phone_1_type,
    guardian_phone_1_number,
    guardian_custom_attributes,
    guardian_id_attributes,

    case
        when rel_type = 'parent' and guardian_gender = 'F'
        then 'mother'
        when rel_type = 'parent' and guardian_gender = 'M'
        then 'father'
        else rel_type
    end as relationship_label,
from relationships
