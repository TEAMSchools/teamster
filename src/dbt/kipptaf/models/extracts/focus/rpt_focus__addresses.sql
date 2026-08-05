-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    ida.focus_student_id_prefixed as student_id,

    aor.address_1 as address,
    aor.address_2 as address2,
    aor.city,
    aor.state,
    aor.zip as zipcode,
    aor.primary_contact_phone as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("int_finalsite__student_address_of_record") }} as aor
inner join
    {{ ref("stg_finalsite__contacts") }} as stu
    on aor.finalsite_enrollment_id = stu.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on aor.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on aor.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
-- an unresolved address is withheld, not exported blank: the feed is
-- import-once with no overwrite path, so a blank or wrong address of record is
-- permanent. address_source is not null guarantees a street line, not a
-- complete address — an incomplete one is exported for Ops to correct in Focus,
-- since a missing field is visible there in a way a wrong pick is not.
where stu.status = 'enrolled' and aor.address_source is not null
