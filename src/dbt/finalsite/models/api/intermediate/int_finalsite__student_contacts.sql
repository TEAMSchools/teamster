with
    contact_1_typed as (
        -- contact_1 is EXCLUSIVELY the relationship Finalsite flags `primary`
        -- (its parent1 designation), resolved to the related person's own
        -- contact record. No fallback: a record with no primary flag (a
        -- Finalsite data-entry gap) gets no contact_1. `primary` is a
        -- per-record singleton, so the filter alone is a deterministic pick
        -- (the grain uniqueness test guards any future multi-primary anomaly).
        -- No SIS scoping here — downstream receivers filter to enrolled
        -- students by joining on the student id.
        select
            r.finalsite_enrollment_id,
            r.rel_name,
            r.rel_type,

            cp.email,
            cp.phone_1_number,

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
        from {{ ref("stg_finalsite__contact_relationships") }} as r
        inner join
            {{ ref("stg_finalsite__contacts") }} as cp
            on r.rel_id = cp.finalsite_enrollment_id
        where r.is_primary
    ),

    contact_1 as (
        select
            finalsite_enrollment_id,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            home_address,
            rel_name as contact_name,
            rel_type as relationship,
            phone_1_number as phone_primary,

            'contact_1' as contact_slot,
            false as is_emergency,

            cast(null as string) as phone_daytime,
            cast(null as boolean) as is_pickup,
            cast(null as boolean) as is_custodial,
            cast(null as boolean) as is_household_member,
        from contact_1_typed
    ),

    emergency_long as (
        select
            finalsite_enrollment_id,
            emrg_1_email as email,
            emrg_1_phone_1_number as phone_primary,
            emrg_1_pickup_yn as is_pickup,
            emrg_1_custody_yn as is_custodial,
            emrg_1_lives_with_yn as is_household_member,

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

            cast(null as string) as phone_daytime,
            cast(null as string) as home_address,
        from emergency_long
    )

select
    finalsite_enrollment_id,
    contact_slot,
    contact_name,
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
from contact_1

union all

select
    finalsite_enrollment_id,
    contact_slot,
    contact_name,
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
