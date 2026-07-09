with
    students as (
        -- Scope to Finalsite records carrying a PowerSchool student number. This
        -- is intentional: the downstream kipptaf consumer (Phase 3b) joins
        -- finalsite_enrollment_id -> powerschool_student_number to key contacts
        -- to a student, so records without a PS number cannot be consumed there
        -- yet. Revisit if scoping needs to become SIS-neutral.
        select finalsite_enrollment_id,
        from {{ ref("int_finalsite__contact_id_attributes") }}
        where powerschool_student_number is not null
    ),

    contact_1_parent as (
        select
            finalsite_enrollment_id as rel_finalsite_enrollment_id,
            email,
            phone_1_type,
            phone_1_number,
            phone_2_type,
            phone_2_number,
            phone_3_type,
            phone_3_number,
            address_1,
            address_2,
            city,
            state,
            zip,
        from {{ ref("stg_finalsite__contacts") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    rel_candidates as (
        -- contact_1 is EXCLUSIVELY the relationship Finalsite flags `primary`
        -- (its parent1 designation), resolved to a real contact record. No
        -- fallback: a student with no primary flag (a Finalsite data-entry gap,
        -- ~6% of Newark students) gets no contact_1 rather than an arbitrary
        -- non-primary relationship. The inner join to contact_1_parent also
        -- drops a primary link that points outside the pulled cohort.
        select
            r.finalsite_enrollment_id,
            r.rel_id,
            r.rel_name,
            r.rel_type,
            r.is_primary,
            r.rel_offset,

            cp.email,
            cp.phone_1_type,
            cp.phone_1_number,
            cp.phone_2_type,
            cp.phone_2_number,
            cp.phone_3_type,
            cp.phone_3_number,
            cp.address_1,
            cp.address_2,
            cp.city,
            cp.state,
            cp.zip,
        from {{ ref("stg_finalsite__contact_relationships") }} as r
        inner join
            students as s on r.finalsite_enrollment_id = s.finalsite_enrollment_id
        inner join contact_1_parent as cp on r.rel_id = cp.rel_finalsite_enrollment_id
        where r.is_primary
    ),

    picked_rel as (
        {{
            dbt_utils.deduplicate(
                relation="rel_candidates",
                partition_by="finalsite_enrollment_id",
                order_by="rel_offset asc",
            )
        }}
    ),

    contact_1_typed as (
        select
            finalsite_enrollment_id,
            rel_name,
            rel_type,
            email,
            phone_1_number,

            coalesce(
                if(phone_1_type = 'Cell', phone_1_number, null),
                if(phone_2_type = 'Cell', phone_2_number, null),
                if(phone_3_type = 'Cell', phone_3_number, null)
            ) as phone_mobile,
            coalesce(
                if(phone_1_type = 'Home', phone_1_number, null),
                if(phone_2_type = 'Home', phone_2_number, null),
                if(phone_3_type = 'Home', phone_3_number, null)
            ) as phone_home,
            coalesce(
                if(phone_1_type = 'Work', phone_1_number, null),
                if(phone_2_type = 'Work', phone_2_number, null),
                if(phone_3_type = 'Work', phone_3_number, null)
            ) as phone_work,
            nullif(
                array_to_string([address_1, address_2, city, state, zip], ', '), ''
            ) as home_address,
        from picked_rel
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

    emergency_attrs as (
        select a.*,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            students as s on a.finalsite_enrollment_id = s.finalsite_enrollment_id
    ),

    emergency_long as (
        select
            finalsite_enrollment_id,
            emrg_1_email as email,
            emrg_1_phone_1_number as phone_primary,
            emrg_1_pickup_yn as is_pickup,
            emrg_1_custody_yn as is_custodial,
            emrg_1_lives_with_yn as is_household_member,

            1 as set_order,

            coalesce(emrg_1_relationship_ss, emrg_1_relationship_txt) as relationship,
            array_to_string(
                [emrg_1_name_first_name, emrg_1_name_last_name], ' '
            ) as contact_name,
            safe_cast(emrg_1_priority_ss as int64) as priority,

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
        from emergency_attrs
        where emrg_1_name_first_name is not null and emrg_1_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_2_email as email,
            emrg_2_phone_1_number as phone_primary,
            emrg_2_pickup_yn as is_pickup,
            emrg_2_custody_yn as is_custodial,
            emrg_2_lives_with_yn as is_household_member,

            2 as set_order,

            coalesce(emrg_2_relationship_ss, emrg_2_relationship_txt) as relationship,
            array_to_string(
                [emrg_2_name_first_name, emrg_2_name_last_name], ' '
            ) as contact_name,
            safe_cast(emrg_2_priority_ss as int64) as priority,

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
        from emergency_attrs
        where emrg_2_name_first_name is not null and emrg_2_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_3_email as email,
            emrg_3_phone_1_number as phone_primary,
            emrg_3_pickup_yn as is_pickup,
            emrg_3_custody_yn as is_custodial,
            emrg_3_lives_with_yn as is_household_member,

            3 as set_order,

            coalesce(emrg_3_relationship_ss, emrg_3_relationship_txt) as relationship,
            array_to_string(
                [emrg_3_name_first_name, emrg_3_name_last_name], ' '
            ) as contact_name,
            safe_cast(emrg_3_priority_ss as int64) as priority,

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
        from emergency_attrs
        where emrg_3_name_first_name is not null and emrg_3_name_first_name != ''

        union all

        select
            finalsite_enrollment_id,
            emrg_4_email as email,
            emrg_4_phone_1_number as phone_primary,
            emrg_4_pickup_yn as is_pickup,
            emrg_4_custody_yn as is_custodial,
            emrg_4_lives_with_yn as is_household_member,

            4 as set_order,

            coalesce(emrg_4_relationship_ss, emrg_4_relationship_txt) as relationship,
            array_to_string(
                [emrg_4_name_first_name, emrg_4_name_last_name], ' '
            ) as contact_name,
            safe_cast(emrg_4_priority_ss as int64) as priority,

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
        from emergency_attrs
        where emrg_4_name_first_name is not null and emrg_4_name_first_name != ''
    ),

    emergency_ranked as (
        select
            finalsite_enrollment_id,
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

            row_number() over (
                partition by finalsite_enrollment_id
                order by priority asc nulls last, set_order asc
            ) as rn,
        from emergency_long
    ),

    emergency_slots as (
        select
            finalsite_enrollment_id,
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

            concat('emergency_', cast(rn as string)) as contact_slot,
        from emergency_ranked
        where rn <= 4
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
from emergency_slots
