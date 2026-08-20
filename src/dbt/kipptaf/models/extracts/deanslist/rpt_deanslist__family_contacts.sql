with
    contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc.relationship,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,

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
        from {{ ref("int_finalsite__student_contacts") }} as sc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on sc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and sc._dbt_source_project = xw._dbt_source_project
        where
            sc._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and xw.powerschool_student_number is not null
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
    c.email as `Email`,
    c.relationship as `Relationship`,
    c.contact_type as `ContactType`,

    cast(null as string) as `Language`,

    -- The DeansList template has no header for a number whose Finalsite type
    -- was never set, so before this fallback such a number reached no column at
    -- all and the family arrived uncallable. CellPhone is where it rides in:
    -- across the NJ regions ~95% of the numbers that DO carry a type are Cell,
    -- so it is the likeliest fit, and a landline sent here is no worse off than
    -- the blank it replaces. A Finalsite-typed Cell still wins outright.
    coalesce(c.phone_mobile, c.phone_untyped) as `CellPhone`,
from contacts as c
inner join
    {{ ref("stg_powerschool__students") }} as s
    on c.student_number = s.student_number
    and c._dbt_source_project = s._dbt_source_project
    and s.enroll_status = 0
-- DeansList's importer displays contacts in the order this file lists them per
-- student (no independent sort on their end), so Parent1/Parent2 must precede
-- Emergency here or families see emergency contacts ranked above parents.
order by c.student_number asc, (c.contact_type = 'Emergency') asc, c.contact_type asc
