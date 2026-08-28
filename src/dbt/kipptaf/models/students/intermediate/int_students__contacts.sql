with
    finalsite as (
        select
            fc.contact_slot,
            fc.finalsite_contact_id,
            fc.contact_name,
            fc.contact_first_name,
            fc.contact_last_name,
            fc.relationship,
            fc.phone_mobile,
            fc.phone_home,
            fc.phone_daytime,
            fc.phone_work,
            fc.phone_untyped,
            fc.phone_primary,
            fc.is_emergency,
            fc.is_pickup,
            fc.is_custodial,
            fc.is_household_member,
            fc._dbt_source_project,
            fc.email as email_current,
            fc.home_address as address_home,

            cast(null as string) as personid,

            safe_cast(xw.powerschool_student_number as int64) as student_number,
        from {{ ref("int_finalsite__student_contacts") }} as fc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on fc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and fc._dbt_source_project = xw._dbt_source_project
        where xw.powerschool_student_number is not null
    ),

    -- Miami Focus branch, replacing the branch that read the frozen
    -- pre-migration `kippmiami_powerschool` snapshot. Focus stores the KIPP
    -- student number 8400-prefixed in `local_student_id`, so `student_number`
    -- is derived by stripping that prefix rather than crosswalked. The network
    -- has always keyed Miami students on the unprefixed number, and
    -- `dim_students.student_key` hashes it. Strip on the literal prefix rather
    -- than positionally: 1 id carries no 8400 at all, and dropping its first 4
    -- characters yields a number matching no student, which silently loses that
    -- student's contacts. Deriving also beats joining
    -- `int_finalsite__contact_id_attributes` on `focus_student_id_prefixed`.
    -- Its `powerschool_student_number` agrees with the stripped value wherever
    -- it is populated, but it is null for every Focus-native student, who has
    -- no pre-migration PowerSchool record, so that join would silently drop
    -- most of Miami.
    focus_base as (
        select
            student_id,
            person_id,
            relationship,
            sort_order,
            contact_name,
            contact_first_name,
            contact_last_name,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_primary,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
            _dbt_source_project,
            email as email_current,
            home_address as address_home,

            -- Focus types every phone it stores, so there is no untyped number
            -- to recover on this branch. The column exists to keep both
            -- branches union-compatible.
            cast(null as string) as phone_untyped,

            safe_cast(
                regexp_replace(local_student_id, r'^8400', '') as int64
            ) as student_number,
        from {{ ref("int_focus__student_contacts") }}
    ),

    focus_contact_1 as (
        select *, 'contact_1' as contact_slot, from focus_base where sort_order = 1
    ),

    focus_emergency_ranked as (
        select
            *,

            row_number() over (
                partition by _dbt_source_project, student_id
                order by sort_order asc, person_id asc
            ) as emergency_rank,
        from focus_base
        where is_emergency
    ),

    focus_emergency as (
        select
            * except (emergency_rank),

            concat('emergency_', cast(emergency_rank as string)) as contact_slot,
        from focus_emergency_ranked
        where emergency_rank <= 4
    ),

    focus_slotted as (
        select
            contact_slot,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_untyped,
            phone_primary,
            address_home,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
            _dbt_source_project,
            person_id,
            student_number,
        from focus_contact_1

        union all

        select
            contact_slot,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_untyped,
            phone_primary,
            address_home,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
            _dbt_source_project,
            person_id,
            student_number,
        from focus_emergency
    ),

    focus as (
        select
            contact_slot,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_untyped,
            phone_primary,
            address_home,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
            _dbt_source_project,
            student_number,

            cast(person_id as string) as personid,
            cast(null as string) as finalsite_contact_id,
        from focus_slotted
        where student_number is not null
    ),

    all_contacts as (
        select
            student_number,
            _dbt_source_project,
            contact_slot,
            personid,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_untyped,
            phone_primary,
            address_home,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
        from finalsite

        union all

        select
            student_number,
            _dbt_source_project,
            contact_slot,
            personid,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_untyped,
            phone_primary,
            address_home,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
        from focus
    )

select *, coalesce(finalsite_contact_id, personid) as person_identity,
from all_contacts
