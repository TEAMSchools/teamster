-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus CONTACTS contract
select
    -- STDT_ID is null until the Finalsite-minted student id lands in
    -- id_attributes; repoint to int_finalsite__contact_id_attributes then.
    cast(null as string) as student_id,

    rel.rel_type as student_relation,

    row_number() over (
        partition by rel.finalsite_enrollment_id
        order by rel.is_primary desc, g.last_name asc, g.first_name asc
    ) as sort_order,

    g.first_name,
    g.middle_name,
    g.last_name,

    cast(null as string) as resides_with_stud,
    cast(null as string) as custody,
    cast(null as string) as emergency,
    cast(null as string) as pickup,

    g.address_1 as address,
    g.address_2 as address2,
    g.city,
    g.state,
    g.zip as zipcode,
    g.email,
    g.phone_1_type as contact1_type,
    g.phone_1_number as contact1_value,

    cast(null as string) as contact1_blocked,
    cast(null as string) as contact1_unlisted,
    cast(null as string) as contact1_callout,

    g.phone_2_type as contact2_type,
    g.phone_2_number as contact2_value,

    cast(null as string) as contact2_blocked,
    cast(null as string) as contact2_unlisted,
    cast(null as string) as contact2_callout,
    cast(null as string) as contact3_type,
    cast(null as string) as contact3_value,
    cast(null as string) as contact3_blocked,
    cast(null as string) as contact3_unlisted,
    cast(null as string) as contact3_callout,
    cast(null as string) as contact4_type,
    cast(null as string) as contact4_value,
    cast(null as string) as contact4_blocked,
    cast(null as string) as contact4_unlisted,
    cast(null as string) as contact4_callout,
    cast(null as string) as contact5_type,
    cast(null as string) as contact5_value,
    cast(null as string) as contact5_blocked,
    cast(null as string) as contact5_unlisted,
    cast(null as string) as contact5_callout,
    cast(null as string) as contact6_type,
    cast(null as string) as contact6_value,
    cast(null as string) as contact6_blocked,
    cast(null as string) as contact6_unlisted,
    cast(null as string) as contact6_callout,
    cast(null as string) as contact7_type,
    cast(null as string) as contact7_value,
    cast(null as string) as contact7_blocked,
    cast(null as string) as contact7_unlisted,
    cast(null as string) as contact7_callout,
from {{ ref("stg_finalsite__contact_relationships") }} as rel
inner join
    {{ ref("stg_finalsite__contacts") }} as g on rel.rel_id = g.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on rel.finalsite_enrollment_id = l.finalsite_enrollment_id
where
    rel.rel_type
    in ('parent', 'guardian', 'grandparent', 'stepparent', 'relative', 'aunt/uncle')
