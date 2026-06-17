with
    addresses as (
        select
            c.address_1,
            c.address_2,
            c.city,
            c.state,
            c.zip,
            c.phone_1_number,
            (
                select av.value.string_value,
                from unnest(c.id_attributes) as av
                where av.field_name = '{{ var("finalsite_focus_student_id_field") }}'
                order by av.field_id
                limit 1
            ) as stdt_id,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
    )

select
    a.stdt_id as student_id,
    a.address_1 as address,
    a.address_2 as address2,
    a.city,
    a.state,
    a.zip as zipcode,
    a.phone_1_number as phone,
    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
    cast(null as string) as mail_zipcode,
from addresses as a
