with
    contact_1_picked as (
        -- contact_1 is the student's Parent 1: the relationship Finalsite flags
        -- `primary`. That flag is a per-student singleton and is never `false`
        -- — it is true or NULL — so a bare `where is_primary` selects exactly
        -- the Parent 1 row. A student with no primary relationship gets no
        -- contact_1, and therefore no contact_2: per Ops, a missing primary
        -- flag is a Finalsite data-entry gap to fix at the source rather than
        -- something to infer from `financial`. A second primary on one student
        -- would surface as a duplicate contact_1 and fail this model's
        -- uniqueness test, which is the intended loud failure. No SIS scoping —
        -- downstream receivers filter to enrolled students by joining on the
        -- student id.
        select finalsite_enrollment_id, rel_id, rel_name, rel_type,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    ),

    primary_household_ids as (
        -- The student's primary household is the household their Parent 1
        -- belongs to. Finalsite's own household-1 designation is per-student and
        -- set in the UI, but it is absent from every field the API exposes (the
        -- Household object is id plus address only), and array position does not
        -- reproduce it — `households[safe_offset(0)]` is the UI's Household 2
        -- for confirmed students. Parent 1's membership is therefore what
        -- defines the household both parent slots must share. Exploded to one
        -- row per household so the contact_2 match below is a plain join.
        select p.finalsite_enrollment_id, p.rel_id as contact_1_rel_id, household_id,
        from contact_1_picked as p
        inner join
            {{ ref("stg_finalsite__contacts") }} as cp
            on p.rel_id = cp.finalsite_enrollment_id
        cross join unnest(cp.household_ids) as household_id
    ),

    contact_household_ids as (
        -- One row per (contact, household) so household co-membership is a join
        -- rather than an array containment check.
        select finalsite_enrollment_id, household_id,
        from {{ ref("stg_finalsite__contacts") }}
        cross join unnest(household_ids) as household_id
    ),

    contact_2_candidates as (
        -- contact_2 is any OTHER contact flagged `primary` or `financial` that
        -- belongs to the primary household. `primary` is a singleton already
        -- taken by contact_1, so in practice these are financial-only rows; the
        -- disjunction states the rule as Ops expressed it and guards a
        -- hypothetical second primary. The rel_id inequality skips every
        -- relationship row pointing at the PERSON already chosen as contact_1,
        -- so contact_2 can never duplicate contact_1. The student's own
        -- `is_parent2` custom field is deliberately NOT part of this gate — it
        -- is false for students who do have a co-resident second parent and true
        -- for students who have none, so it removed real rows without excluding
        -- any wrong ones.
        -- grain projection: every selected column is functionally determined
        -- by the partition key; not a mask for upstream duplicates. A candidate
        -- sharing several households with Parent 1 would otherwise repeat.
        select distinct
            r.finalsite_enrollment_id,
            r.relationship_id,
            r.rel_id,
            r.rel_name,
            r.rel_type,
        from {{ ref("stg_finalsite__contact_relationships") }} as r
        inner join
            primary_household_ids as h
            on r.finalsite_enrollment_id = h.finalsite_enrollment_id
            and r.rel_id != h.contact_1_rel_id
        inner join
            contact_household_ids as ch
            on r.rel_id = ch.finalsite_enrollment_id
            and h.household_id = ch.household_id
        where r.is_primary or r.is_financial
    ),

    contact_2_ranked as (
        -- Multiple qualifying second parents tie-break on relationship_id — an
        -- arbitrary but stable pick, as Finalsite exposes no caregiver ordering
        -- among them. Only the first fills the single contact_2 slot.
        select
            finalsite_enrollment_id,
            rel_id,
            rel_name,
            rel_type,

            row_number() over (
                partition by finalsite_enrollment_id order by relationship_id asc
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
    phone_daytime,
    home_address,
    is_pickup,
    is_custodial,
    is_household_member,
    is_emergency,

    {{ clean_phone("phone_mobile") }} as phone_mobile,
    {{ clean_phone("phone_home") }} as phone_home,
    {{ clean_phone("phone_work") }} as phone_work,
    {{ clean_phone("phone_primary") }} as phone_primary,
from all_contacts
