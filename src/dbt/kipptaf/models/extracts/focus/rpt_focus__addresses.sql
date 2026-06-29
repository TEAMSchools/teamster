-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    concat('8400', ida.focus_student_id) as student_id,

    c.address_1 as address,
    c.address_2 as address2,
    c.city,
    c.state,
    c.zip as zipcode,
    c.phone_1_number as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("stg_finalsite__contacts") }} as c
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
left join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
