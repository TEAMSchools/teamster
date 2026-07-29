with
    contact_1_candidates as (
        -- contact_1 is the student's FIRST reportable parent contact. Finalsite
        -- has no explicit contact rank, so we take the relationship it flags
        -- `primary` (its parent1 designation) and fall back to the one flagged
        -- `financial` when no primary is set — the two flags Ops maintains to
        -- mark the responsible caregiver. A record with neither flag gets no
        -- contact_1 (a Finalsite data-entry gap for Ops to resolve).
        -- `primary`/`financial` are NULL (not false) when unset, so normalize
        -- to false here to keep the downstream rank ordering deterministic. No
        -- SIS scoping — downstream receivers filter to enrolled students by
        -- joining on the student id.
        select
            finalsite_enrollment_id,
            relationship_id,
            rel_id,
            rel_name,
            rel_type,
            household_1_id,
            is_parent2,

            coalesce(is_primary, false) as is_primary,
            coalesce(is_financial, false) as is_financial,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary or is_financial
    ),

    contact_1_ranked as (
        -- Rank primary above financial; within a tier break on relationship_id.
        -- Ties occur only among multiple `financial` relationships (a student
        -- never has two `primary`); relationship_id is an arbitrary but stable
        -- tiebreak — every candidate in a tier is a valid contact, and
        -- Finalsite exposes no field that reproduces a caregiver ordering.
        select
            finalsite_enrollment_id,
            rel_id,
            rel_name,
            rel_type,
            household_1_id,
            is_parent2,
            is_primary,

            row_number() over (
                partition by finalsite_enrollment_id
                order by is_primary desc, is_financial desc, relationship_id asc
            ) as rn,
        from contact_1_candidates
    ),

    contact_1_picked as (
        select finalsite_enrollment_id, rel_id, rel_name, rel_type,
        from contact_1_ranked
        where rn = 1
    ),

    contact_2_candidates as (
        -- contact_2 is the student's SECOND reportable parent (DeansList
        -- "Parent 2"). Finalsite encodes it as an additional relationship
        -- flagged `financial` without `primary` (`primary` is a per-student
        -- singleton — Parent 1; candidates are financial-only rows, so
        -- `not is_primary` alone expresses that and also guards a hypothetical
        -- two-primary record). Scoped conservatively per Ops: only when the
        -- student's own `is_parent2` custom field is true AND the related
        -- contact is a member of the student's first household ("household
        -- 1") — second parents in other households are intentionally
        -- excluded. rn > 1 skips the ROW picked as contact_1 (the financial
        -- fallback when no primary is set); the rel_id inequality against the
        -- pick additionally skips any other relationship row to the same
        -- PERSON, so contact_2 can never duplicate contact_1. The student-side
        -- gate fields (is_parent2, household_1_id) ride on the relationships
        -- staging grain, so only the related contact's record is joined here.
        select r.finalsite_enrollment_id, r.rel_id, r.rel_name, r.rel_type, r.rn,
        from contact_1_ranked as r
        inner join
            contact_1_picked as p
            on r.finalsite_enrollment_id = p.finalsite_enrollment_id
            and r.rel_id != p.rel_id
        inner join
            {{ ref("stg_finalsite__contacts") }} as cp
            on r.rel_id = cp.finalsite_enrollment_id
            and r.household_1_id in unnest(cp.household_ids)
        where r.rn > 1 and not r.is_primary and r.is_parent2
    ),

    contact_2_ranked as (
        -- Multiple qualifying second-parent relationships tie-break by the
        -- contact_1 ordering (rn carries the relationship_id tiebreak).
        select
            finalsite_enrollment_id,
            rel_id,
            rel_name,
            rel_type,

            row_number() over (
                partition by finalsite_enrollment_id order by rn asc
            ) as rn_contact_2,
        from contact_2_candidates
    ),

    parent_picks as (
        select
            finalsite_enrollment_id,
            rel_id,
            rel_name,
            rel_type,

            'contact_1' as contact_slot,
        from contact_1_picked

        union all

        select
            finalsite_enrollment_id,
            rel_id,
            rel_name,
            rel_type,

            'contact_2' as contact_slot,
        from contact_2_ranked
        where rn_contact_2 = 1
    ),

    parents_typed as (
        select
            p.finalsite_enrollment_id,
            p.contact_slot,
            p.rel_name,
            p.rel_type,

            cp.finalsite_enrollment_id as finalsite_contact_id,
            cp.email,
            cp.phone_1_number,
            cp.first_name,
            cp.last_name,

            coalesce(
                if(cp.phone_1_type = 'Cell', cp.phone_1_number, null),
                if(cp.phone_2_type = 'Cell', cp.phone_2_number, null),
                if(cp.phone_3_type = 'Cell', cp.phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(cp.phone_1_type = 'Home', cp.phone_1_number, null),
                if(cp.phone_2_type = 'Home', cp.phone_2_number, null),
                if(cp.phone_3_type = 'Home', cp.phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(cp.phone_1_type = 'Work', cp.phone_1_number, null),
                if(cp.phone_2_type = 'Work', cp.phone_2_number, null),
                if(cp.phone_3_type = 'Work', cp.phone_3_number, null)
            ) as phone_work,
            nullif(
                array_to_string(
                    [cp.address_1, cp.address_2, cp.city, cp.state, cp.zip], ', '
                ),
                ''
            ) as home_address,
        from parent_picks as p
        inner join
            {{ ref("stg_finalsite__contacts") }} as cp
            on p.rel_id = cp.finalsite_enrollment_id
    ),

    parents as (
        select
            finalsite_enrollment_id,
            contact_slot,
            finalsite_contact_id,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            home_address,
            first_name as contact_first_name,
            last_name as contact_last_name,
            rel_name as contact_name,
            rel_type as relationship,
            phone_1_number as phone_primary,

            false as is_emergency,

            cast(null as string) as phone_daytime,
            cast(null as boolean) as is_pickup,
            cast(null as boolean) as is_custodial,
            cast(null as boolean) as is_household_member,
        from parents_typed
    ),

    emergency_long as (
        select
            finalsite_enrollment_id,
            emrg_1_email as email,
            emrg_1_phone_1_number as phone_primary,
            emrg_1_pickup_yn as is_pickup,
            emrg_1_custody_yn as is_custodial,
            emrg_1_lives_with_yn as is_household_member,
            emrg_1_name_first_name as contact_first_name,
            emrg_1_name_last_name as contact_last_name,

            'emergency_1' as contact_slot,

            coalesce(emrg_1_relationship_ss, emrg_1_relationship_txt) as relationship,
            array_to_string(
                [emrg_1_name_first_name, emrg_1_name_last_name], ' '
            ) as contact_name,

            coalesce(
                if(emrg_1_phone_1_type = 'Cell', emrg_1_phone_1_number, null),
                if(emrg_1_phone_2_type = 'Cell', emrg_1_phone_2_number, null),
                if(emrg_1_phone_3_type = 'Cell', emrg_1_phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(emrg_1_phone_1_type = 'Home', emrg_1_phone_1_number, null),
                if(emrg_1_phone_2_type = 'Home', emrg_1_phone_2_number, null),
                if(emrg_1_phone_3_type = 'Home', emrg_1_phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(emrg_1_phone_1_type = 'Work', emrg_1_phone_1_number, null),
                if(emrg_1_phone_2_type = 'Work', emrg_1_phone_2_number, null),
                if(emrg_1_phone_3_type = 'Work', emrg_1_phone_3_number, null)
            ) as phone_work,
        from {{ ref("int_finalsite__contact_custom_attributes") }}
        where emrg_1_name_first_name is not null and emrg_1_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_2_email as email,
            emrg_2_phone_1_number as phone_primary,
            emrg_2_pickup_yn as is_pickup,
            emrg_2_custody_yn as is_custodial,
            emrg_2_lives_with_yn as is_household_member,
            emrg_2_name_first_name as contact_first_name,
            emrg_2_name_last_name as contact_last_name,

            'emergency_2' as contact_slot,

            coalesce(emrg_2_relationship_ss, emrg_2_relationship_txt) as relationship,
            array_to_string(
                [emrg_2_name_first_name, emrg_2_name_last_name], ' '
            ) as contact_name,

            coalesce(
                if(emrg_2_phone_1_type = 'Cell', emrg_2_phone_1_number, null),
                if(emrg_2_phone_2_type = 'Cell', emrg_2_phone_2_number, null),
                if(emrg_2_phone_3_type = 'Cell', emrg_2_phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(emrg_2_phone_1_type = 'Home', emrg_2_phone_1_number, null),
                if(emrg_2_phone_2_type = 'Home', emrg_2_phone_2_number, null),
                if(emrg_2_phone_3_type = 'Home', emrg_2_phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(emrg_2_phone_1_type = 'Work', emrg_2_phone_1_number, null),
                if(emrg_2_phone_2_type = 'Work', emrg_2_phone_2_number, null),
                if(emrg_2_phone_3_type = 'Work', emrg_2_phone_3_number, null)
            ) as phone_work,
        from {{ ref("int_finalsite__contact_custom_attributes") }}
        where emrg_2_name_first_name is not null and emrg_2_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_3_email as email,
            emrg_3_phone_1_number as phone_primary,
            emrg_3_pickup_yn as is_pickup,
            emrg_3_custody_yn as is_custodial,
            emrg_3_lives_with_yn as is_household_member,
            emrg_3_name_first_name as contact_first_name,
            emrg_3_name_last_name as contact_last_name,

            'emergency_3' as contact_slot,

            coalesce(emrg_3_relationship_ss, emrg_3_relationship_txt) as relationship,
            array_to_string(
                [emrg_3_name_first_name, emrg_3_name_last_name], ' '
            ) as contact_name,

            coalesce(
                if(emrg_3_phone_1_type = 'Cell', emrg_3_phone_1_number, null),
                if(emrg_3_phone_2_type = 'Cell', emrg_3_phone_2_number, null),
                if(emrg_3_phone_3_type = 'Cell', emrg_3_phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(emrg_3_phone_1_type = 'Home', emrg_3_phone_1_number, null),
                if(emrg_3_phone_2_type = 'Home', emrg_3_phone_2_number, null),
                if(emrg_3_phone_3_type = 'Home', emrg_3_phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(emrg_3_phone_1_type = 'Work', emrg_3_phone_1_number, null),
                if(emrg_3_phone_2_type = 'Work', emrg_3_phone_2_number, null),
                if(emrg_3_phone_3_type = 'Work', emrg_3_phone_3_number, null)
            ) as phone_work,
        from {{ ref("int_finalsite__contact_custom_attributes") }}
        where emrg_3_name_first_name is not null and emrg_3_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_4_email as email,
            emrg_4_phone_1_number as phone_primary,
            emrg_4_pickup_yn as is_pickup,
            emrg_4_custody_yn as is_custodial,
            emrg_4_lives_with_yn as is_household_member,
            emrg_4_name_first_name as contact_first_name,
            emrg_4_name_last_name as contact_last_name,

            'emergency_4' as contact_slot,

            coalesce(emrg_4_relationship_ss, emrg_4_relationship_txt) as relationship,
            array_to_string(
                [emrg_4_name_first_name, emrg_4_name_last_name], ' '
            ) as contact_name,

            coalesce(
                if(emrg_4_phone_1_type = 'Cell', emrg_4_phone_1_number, null),
                if(emrg_4_phone_2_type = 'Cell', emrg_4_phone_2_number, null),
                if(emrg_4_phone_3_type = 'Cell', emrg_4_phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(emrg_4_phone_1_type = 'Home', emrg_4_phone_1_number, null),
                if(emrg_4_phone_2_type = 'Home', emrg_4_phone_2_number, null),
                if(emrg_4_phone_3_type = 'Home', emrg_4_phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(emrg_4_phone_1_type = 'Work', emrg_4_phone_1_number, null),
                if(emrg_4_phone_2_type = 'Work', emrg_4_phone_2_number, null),
                if(emrg_4_phone_3_type = 'Work', emrg_4_phone_3_number, null)
            ) as phone_work,
        from {{ ref("int_finalsite__contact_custom_attributes") }}
        where emrg_4_name_first_name is not null and emrg_4_name_first_name != ''
    ),

    emergency as (
        -- Positional passthrough: emergency_N is the emrg_N custom-field set
        -- as-is. No ranking, no priority re-sort, no gap-filling — if an
        -- emrg_N set is empty it simply produces no emergency_N row.
        select
            finalsite_enrollment_id,
            contact_slot,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            phone_primary,
            is_pickup,
            is_custodial,
            is_household_member,

            true as is_emergency,

            cast(null as string) as finalsite_contact_id,
            cast(null as string) as phone_daytime,
            cast(null as string) as home_address,
        from emergency_long
    ),

    all_contacts as (
        select
            finalsite_enrollment_id,
            contact_slot,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            phone_daytime,
            phone_primary,
            home_address,
            is_pickup,
            is_custodial,
            is_household_member,
            is_emergency,
        from parents

        union all

        select
            finalsite_enrollment_id,
            contact_slot,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            phone_daytime,
            phone_primary,
            home_address,
            is_pickup,
            is_custodial,
            is_household_member,
            is_emergency,
        from emergency
    )

select
    finalsite_enrollment_id,
    contact_slot,
    finalsite_contact_id,
    contact_name,
    contact_first_name,
    contact_last_name,
    relationship,
    email,
    phone_mobile,
    phone_home,
    phone_work,
    phone_daytime,
    phone_primary,
    home_address,
    is_pickup,
    is_custodial,
    is_household_member,
    is_emergency,
from all_contacts
