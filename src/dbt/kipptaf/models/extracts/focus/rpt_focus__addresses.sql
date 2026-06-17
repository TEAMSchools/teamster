-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    -- STDT_ID is null until the Finalsite-minted student id lands in
    -- id_attributes; repoint to int_finalsite__contact_id_attributes then.
    cast(null as string) as student_id,
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
    cast(null as string) as mail_zipcode,
from {{ ref("stg_finalsite__contacts") }} as c
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
