with
    student_primary_contacts as (
        -- One row per student record. `relationships.primary` is a per-record
        -- singleton that is true or NULL (never false), and only child/student
        -- records carry it, so a bare `where is_primary` selects exactly the
        -- student rows and `rel_id` is that student's Parent 1. A second primary
        -- on one student would surface as a duplicate and fail this model's
        -- uniqueness test, which is the intended loud failure. No SIS scoping —
        -- receivers filter to enrolled students downstream.
        select finalsite_enrollment_id, rel_id as primary_contact_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    complete_households as (
        select
            finalsite_enrollment_id,
            household_id,
            address_1,
            address_2,
            city,
            state,
            zip,
            country,
        from {{ ref("int_finalsite__contacts__households") }}
        where is_complete_address
    ),

    address_candidates as (
        -- One row per (contact, distinct complete address). Address identity is
        -- the five mailing fields including address_2 — an apartment difference
        -- is a different mailing address. country is NOT part of the identity,
        -- so it comes from the canonical lowest-household_id row rather than
        -- being aggregated across rows, which would blend values from
        -- different households.
        {{
            dbt_utils.deduplicate(
                relation="complete_households",
                partition_by="finalsite_enrollment_id, address_1, address_2, city, state, zip",
                order_by="household_id asc",
            )
        }}
    ),

    candidate_counts as (
        select finalsite_enrollment_id, count(*) as candidate_count,
        from address_candidates
        group by finalsite_enrollment_id
    ),

    counted as (
        select
            spc.finalsite_enrollment_id,
            spc.primary_contact_id,

            coalesce(sc.candidate_count, 0) as student_candidate_count,
            coalesce(pcc.candidate_count, 0) as primary_contact_candidate_count,
        from student_primary_contacts as spc
        left join
            candidate_counts as sc
            on spc.finalsite_enrollment_id = sc.finalsite_enrollment_id
        left join
            candidate_counts as pcc
            on spc.primary_contact_id = pcc.finalsite_enrollment_id
    ),

    sourced as (
        -- The student's household linkage is a subset of their primary contact's
        -- and is the disambiguating signal, so it is tried first. Parents carry
        -- more household rows than students, so anchoring on the parent
        -- unconditionally would move the pick onto the record with more
        -- competing addresses.
        select
            finalsite_enrollment_id,
            primary_contact_id,
            student_candidate_count,
            primary_contact_candidate_count,

            case
                when student_candidate_count = 1
                then 'student_household'
                when primary_contact_candidate_count = 1
                then 'primary_contact_household'
            end as address_source,
            case
                when student_candidate_count = 1
                then finalsite_enrollment_id
                when primary_contact_candidate_count = 1
                then primary_contact_id
            end as address_contact_id,
        from counted
    )

select
    s.finalsite_enrollment_id,
    s.student_candidate_count,
    s.primary_contact_candidate_count,
    s.address_source,

    a.address_1,
    a.address_2,
    a.city,
    a.state,
    a.zip,
    a.country,

    pc.phone_1_number as primary_contact_phone,

    coalesce(s.address_source, 'ambiguous') as resolution_status,
from sourced as s
-- address_contact_id is only ever set to a contact whose candidate_count is
-- exactly 1, so this join cannot fan out; when it is null (an unresolved
-- address) nothing matches and the address fields stay null.
left join address_candidates as a on s.address_contact_id = a.finalsite_enrollment_id
left join
    {{ ref("stg_finalsite__contacts") }} as pc
    on s.primary_contact_id = pc.finalsite_enrollment_id
