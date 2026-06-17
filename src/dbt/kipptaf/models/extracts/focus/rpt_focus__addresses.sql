with
    addresses as (
        select
            c.address_1,
            c.address_2,
            c.city,
            c.state,
            c.zip,
            c.phone_1_number,
            idf.focus_student_id as stdt_id,
        from
            {{
                source(
                    "kippmiami_finalsite",
                    "stg_finalsite__contacts",
                )
            }} as c
        inner join
            {{
                source(
                    "kippmiami_finalsite",
                    "int_finalsite__enrollment_lifecycle",
                )
            }} as l on c.finalsite_enrollment_id = l.finalsite_enrollment_id
        left join
            {{
                source(
                    "kippmiami_finalsite",
                    "int_finalsite__contact_id_attributes",
                )
            }} as idf on c.finalsite_enrollment_id = idf.finalsite_enrollment_id
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
