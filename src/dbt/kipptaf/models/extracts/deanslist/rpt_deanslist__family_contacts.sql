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
        -- The network contact surface, not the Finalsite intermediates this
        -- model used to join itself: int_students__contacts' Finalsite branch
        -- IS that join (same two refs, same keys, same crosswalk filter), and
        -- it carries `person_identity`, the shared contact-identity definition
        -- the marts key on. The region filter stays because that model also
        -- unions Miami's Focus contacts, which DeansList does not take.
        from {{ ref("int_students__contacts") }} as sc
        where
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

    -- The DeansList template has no header for a number whose Finalsite type
    -- was never set, so before this fallback such a number reached no column at
    -- all and the family arrived uncallable. CellPhone is where it rides in:
    -- across the NJ regions ~95% of the numbers that DO carry a type are Cell,
    -- so it is the likeliest fit, and a landline sent here is no worse off than
    -- the blank it replaces. A Finalsite-typed Cell still wins outright.
    coalesce(c.phone_mobile, c.phone_untyped) as `CellPhone`,

    -- DeansList has no id of ours to key contact rows on, so its importer keys
    -- them on a hash of the contact's name: two contacts sharing a name
    -- collapse into one row and a family silently loses a contact.
    -- `IntegrationKey` gives it a real key (any string up to 64 chars).
    --
    -- Parents key on their own Finalsite contact UUID, NOT on the slot, because
    -- parent slots are ranked rather than fixed -- flipping a `primary` flag
    -- upstream swaps contact_1 and contact_2. A slot-keyed row would keep its
    -- key while taking on the other parent's name, phone, and email, dragging
    -- whatever DeansList attached to that key onto the wrong person.
    --
    -- Emergency contacts have no `person_identity`: they are scalar `emrg_N`
    -- custom fields on the student's own record, not linked contact records, so
    -- the slot IS their identity. Same split, and same reasoning, as
    -- `bridge_student_contacts.student_contact_person_key`; the student prefix
    -- is what takes this from the dimension's person grain down to DeansList's
    -- (student, contact) grain, so a parent with two enrolled children gets one
    -- key per child rather than one shared key.
    --
    -- Readable rather than hashed like the marts key: a 6-digit student number
    -- plus a 36-char UUID is 43 chars, so it fits inside DeansList's 64, and
    -- staff can trace a row back to its Finalsite contact by eye. No region
    -- component -- `student_number` is unique across the three NJ regions
    -- covered here.
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
-- DeansList's importer displays contacts in the order this file lists them per
-- student (no independent sort on their end), so Parent1/Parent2 must precede
-- Emergency here or families see emergency contacts ranked above parents.
order by c.student_number asc, (c.contact_type = 'Emergency') asc, c.contact_type asc
