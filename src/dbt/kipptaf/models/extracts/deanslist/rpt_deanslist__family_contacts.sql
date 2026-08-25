with
    contacts as (
        select
            sc.contact_slot,
            sc.person_identity,
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email_current,
            sc.relationship,
            sc.student_number,
            sc._dbt_source_project,

            -- DeansList phone fields accept only digits and `x` (extension); strip
            -- the E.164 canonical (leading `+`, etc.) to that shape.
            regexp_replace(lower(sc.phone_home), r'[^0-9x]', '') as phone_home,
            regexp_replace(lower(sc.phone_work), r'[^0-9x]', '') as phone_work,
            regexp_replace(lower(sc.phone_mobile), r'[^0-9x]', '') as phone_mobile,
            regexp_replace(lower(sc.phone_untyped), r'[^0-9x]', '') as phone_untyped,

            -- DeansList routes guardian-only automated messaging (reports,
            -- texts, emails) by ContactType, so the slot ordinal need not be
            -- encoded anywhere else; Relationship carries the contact's actual
            -- relationship to the student for every slot, emergency contacts
            -- included. Overwriting it with a literal `Emergency N` (the prior
            -- behavior) discarded a label Finalsite populates on essentially
            -- every emergency row and left school staff unable to tell a parent
            -- from a neighbor. Parent slots past contact_2 are excluded by the
            -- `where` below, upstream of this `case`, so they can never fall
            -- into the `else` branch and be mislabelled `Emergency`. Carrying a
            -- third parent into DeansList is deliberately out of scope for now.
            case
                sc.contact_slot
                when 'contact_1'
                then 'Parent1'
                when 'contact_2'
                then 'Parent2'
                else 'Emergency'
            end as contact_type,
        from {{ ref("int_students__contacts") }} as sc
        where
            -- that model also carries Miami's Focus contacts; DeansList is NJ only
            sc._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and (
                sc.contact_slot in ('contact_1', 'contact_2')
                or sc.contact_slot like 'emergency\\_%'
            )
    )

select
    c.student_number as `StudentID`,
    c.contact_first_name as `ParentFirstName`,
    c.contact_last_name as `ParentLastName`,
    c.phone_home as `HomePhone`,
    c.phone_work as `WorkPhone`,
    c.email_current as `Email`,
    c.relationship as `Relationship`,
    c.contact_type as `ContactType`,

    cast(null as string) as `Language`,

    coalesce(c.phone_mobile, c.phone_untyped) as `CellPhone`,

    -- person_identity is null on emergency slots, so the slot stands in there.
    concat(
        cast(c.student_number as string),
        '-',
        coalesce(c.person_identity, c.contact_slot)
    ) as `IntegrationKey`,
from contacts as c
inner join
    {{ ref("stg_powerschool__students") }} as s
    on c.student_number = s.student_number
    and c._dbt_source_project = s._dbt_source_project
    and s.enroll_status = 0
order by c.student_number asc, (c.contact_type = 'Emergency') asc, c.contact_type asc
