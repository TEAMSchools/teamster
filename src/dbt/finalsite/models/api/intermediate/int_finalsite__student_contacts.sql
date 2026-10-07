with
    parent_candidates as (
        -- The adult guard, not `rel_type`, is what keeps a co-resident sibling
        -- out of a parent slot. Filtering on `rel_type` would also drop an
        -- adult sibling who is a legitimate guardian. Finalsite marks adults
        -- with status `not_in_workflow`; every other status belongs to a
        -- student record, and a student is never a parent.
        select
            r.finalsite_enrollment_id,
            r.relationship_id,
            r.rel_id,
            r.rel_name,
            r.rel_type,

            coalesce(r.is_primary, false) as is_primary,
        from {{ ref("stg_finalsite__contact_relationships") }} as r
        inner join
            {{ ref("stg_finalsite__contacts") }} as rc
            on r.rel_id = rc.finalsite_enrollment_id
            and rc.status = 'not_in_workflow'
        where coalesce(r.is_primary, false) or coalesce(r.is_financial, false)
    ),

    candidates_sharing_student_household as (
        -- One row per (student, candidate) that co-belong to any household.
        -- grain projection: a pair sharing several households would otherwise
        -- repeat and fan out the rank below. Not a mask for upstream duplicates.
        select distinct c.finalsite_enrollment_id, c.rel_id,
        from parent_candidates as c
        inner join
            {{ ref("int_finalsite__contacts__households") }} as sh
            on c.finalsite_enrollment_id = sh.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contacts__households") }} as ch
            on c.rel_id = ch.finalsite_enrollment_id
            and sh.household_id = ch.household_id
    ),

    parent_ranked as (
        select
            c.finalsite_enrollment_id,
            c.rel_id,
            c.rel_name,
            c.rel_type,

            row_number() over (
                partition by c.finalsite_enrollment_id
                order by
                    c.is_primary desc,
                    (s.rel_id is not null) desc,
                    c.relationship_id asc
            ) as contact_rank,
        from parent_candidates as c
        left join
            candidates_sharing_student_household as s
            on c.finalsite_enrollment_id = s.finalsite_enrollment_id
            and c.rel_id = s.rel_id
    ),

    parent_picks as (
        select
            * except (contact_rank),

            concat('contact_', cast(contact_rank as string)) as contact_slot,
        from parent_ranked
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
            coalesce(
                if(cp.phone_1_type is null, cp.phone_1_number, null),
                if(cp.phone_2_type is null, cp.phone_2_number, null),
                if(cp.phone_3_type is null, cp.phone_3_number, null)
            ) as phone_untyped,
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
            phone_untyped,
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
            coalesce(
                if(emrg_1_phone_1_type is null, emrg_1_phone_1_number, null),
                if(emrg_1_phone_2_type is null, emrg_1_phone_2_number, null),
                if(emrg_1_phone_3_type is null, emrg_1_phone_3_number, null)
            ) as phone_untyped,
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
            coalesce(
                if(emrg_2_phone_1_type is null, emrg_2_phone_1_number, null),
                if(emrg_2_phone_2_type is null, emrg_2_phone_2_number, null),
                if(emrg_2_phone_3_type is null, emrg_2_phone_3_number, null)
            ) as phone_untyped,
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
            coalesce(
                if(emrg_3_phone_1_type is null, emrg_3_phone_1_number, null),
                if(emrg_3_phone_2_type is null, emrg_3_phone_2_number, null),
                if(emrg_3_phone_3_type is null, emrg_3_phone_3_number, null)
            ) as phone_untyped,
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
            coalesce(
                if(emrg_4_phone_1_type is null, emrg_4_phone_1_number, null),
                if(emrg_4_phone_2_type is null, emrg_4_phone_2_number, null),
                if(emrg_4_phone_3_type is null, emrg_4_phone_3_number, null)
            ) as phone_untyped,
        from {{ ref("int_finalsite__contact_custom_attributes") }}
        where emrg_4_name_first_name is not null and emrg_4_name_first_name != ''
    ),

    emergency as (
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
            phone_untyped,
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
            phone_untyped,
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
            phone_untyped,
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
    phone_untyped,
    phone_daytime,
    phone_primary,
    home_address,
    is_pickup,
    is_custodial,
    is_household_member,
    is_emergency,
from all_contacts
