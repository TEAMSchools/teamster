with
    -- The student's address of record is their primary contact's address.
    -- `households[safe_offset(0)]` is an arbitrary array position, not
    -- Finalsite's primary-household designation — that designation is set in the
    -- UI and absent from every field the API exposes, so it cannot be
    -- reproduced. See #4613.
    --
    -- Parent 1 is the relationship Finalsite flags `primary`. That flag is a
    -- per-student singleton and is never `false` — it is `true` or NULL — so a
    -- bare `where is_primary` selects exactly the Parent 1 row. A second primary
    -- on one student would duplicate `student_id` and fail this model's `unique`
    -- test, which is the intended loud failure.
    primary_contact as (
        select finalsite_enrollment_id, rel_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    ida.focus_student_id_prefixed as student_id,

    p1.address_1 as address,
    p1.address_2 as address2,
    p1.city,
    p1.state,
    p1.zip as zipcode,
    p1.phone_1_number as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("stg_finalsite__contacts") }} as c
-- inner joins, not left: a student with no primary contact gets no address row.
-- Per Ops a missing primary flag is a Finalsite data-entry gap to fix at the
-- source, not something to infer — matching int_finalsite__student_contacts.
inner join
    primary_contact as pc on c.finalsite_enrollment_id = pc.finalsite_enrollment_id
inner join
    {{ ref("stg_finalsite__contacts") }} as p1 on pc.rel_id = p1.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
where
    c.status = 'enrolled'
    -- the primary contact must have a mailable address; a contact whose address
    -- fields are blank would otherwise emit null address columns. Mirrors the
    -- kippmiami completeness gate (#4320) so this view and the feed agree.
    -- address_2 is excluded deliberately — it is legitimately null.
    and p1.address_1 is not null
    and p1.city is not null
    and p1.state is not null
    and p1.zip is not null
