select
    c.student_number,
    c.family_ident,
    c.person_type,
    c.relationship_type,
    c.isemergency,
    c.schoolpickupflg,

    pc.contact_category,
    pc.contact,
    pc.priority_order as contact_priority_order,

    concat(c.firstname, ' ', c.lastname) as contact_name,

    if(
        pc.contact_category in ('Email', 'Address'),
        lower(pc.contact_category),
        lower(pc.contact_type)
    ) as contact_type,
from {{ ref("int_powerschool__contacts") }} as c
inner join
    {{ ref("int_powerschool__person_contacts") }} as pc
    on c.personid = pc.personid
    and pc.contact_type in ('Current', 'Daytime', 'Home', 'Mobile', 'Not Set', 'Work')
    and (
        (pc.contact_category in ('Address', 'Email') and pc.priority_order = 1)
        or pc.contact_category = 'Phone'
    )
