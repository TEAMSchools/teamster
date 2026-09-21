with
    student_records as (
        -- A student record is a contact carrying a workflow status. Adults sit
        -- at 'not_in_workflow'. This replaces a `where is_primary` spine, which
        -- defined a student as someone with a designated Parent 1 and so
        -- dropped every student without one — even when that student's own
        -- household resolved cleanly.
        select finalsite_enrollment_id,
        from {{ ref("stg_finalsite__contacts") }}
        where status != 'not_in_workflow'
    ),

    student_primary_contacts as (
        -- `relationships.primary` is a per-record singleton that is true or
        -- NULL, never false. A second primary on one student surfaces as a
        -- duplicate and fails this model's uniqueness test, which is the
        -- intended loud failure.
        select finalsite_enrollment_id, rel_id as primary_contact_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    ),

    counted as (
        -- Candidate counting and address identity live in
        -- int_finalsite__contact_address_of_record, so both Focus feeds resolve
        -- an address by one rule. A contact absent from that model has no
        -- household rows at all, which counts as zero candidates.
        select
            s.finalsite_enrollment_id,

            spc.primary_contact_id,

            sa.resolution_status as student_resolution_status,

            pa.resolution_status as primary_contact_resolution_status,

            coalesce(sa.candidate_count, 0) as student_candidate_count,
            coalesce(pa.candidate_count, 0) as primary_contact_candidate_count,
        from student_records as s
        left join
            student_primary_contacts as spc
            on s.finalsite_enrollment_id = spc.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as sa
            on s.finalsite_enrollment_id = sa.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as pa
            on spc.primary_contact_id = pa.finalsite_enrollment_id
    ),

    sourced as (
        -- Parent 1's household is the address of record. The student's own
        -- household is the fallback, and that tier must stay: some students
        -- hold an address while their Parent 1 holds none. The reverse order
        -- was correct while the old rule withheld on any ambiguity, because a
        -- parent carries more households. The contact model now picks a
        -- winner, so the parent's larger household count costs nothing.
        select
            finalsite_enrollment_id,
            primary_contact_id,
            student_candidate_count,
            primary_contact_candidate_count,

            case
                when primary_contact_candidate_count >= 1
                then 'primary_contact_household'
                when student_candidate_count >= 1
                then 'student_household'
            end as address_source,
            case
                when primary_contact_candidate_count >= 1
                then primary_contact_id
                when student_candidate_count >= 1
                then finalsite_enrollment_id
            end as address_contact_id,
            case
                when primary_contact_candidate_count >= 1
                then primary_contact_resolution_status
                when student_candidate_count >= 1
                then student_resolution_status
            end as winning_resolution_status,
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
    a.is_complete_address,

    pc.phone_1_number as primary_contact_phone,

    coalesce(s.address_source, 'unresolved') as resolution_status,

    s.winning_resolution_status = 'picked' as is_picked_address,
from sourced as s
-- address_contact_id is only ever set to a contact that has at least one
-- candidate, so this join cannot fan out; when it is null (no address anywhere)
-- nothing matches and the address fields stay null.
left join
    {{ ref("int_finalsite__contact_address_of_record") }} as a
    on s.address_contact_id = a.finalsite_enrollment_id
left join
    {{ ref("stg_finalsite__contacts") }} as pc
    on s.primary_contact_id = pc.finalsite_enrollment_id
