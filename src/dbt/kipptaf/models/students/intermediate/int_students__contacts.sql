with
    -- NJ Finalsite branch: the SIS-agnostic student-contacts union (cutover
    -- regions only — the region scope lives in int_finalsite__student_contacts),
    -- reduced to enrolled students by crosswalking the Finalsite enrollment id
    -- to a PowerSchool student number. The crosswalk union also carries Miami's
    -- Focus contacts, but they never match here because
    -- int_finalsite__student_contacts unions only cutover regions.
    finalsite as (
        select
            fc.contact_slot,
            fc.finalsite_contact_id,
            fc.contact_name,
            fc.relationship,
            fc.phone_mobile,
            fc.phone_home,
            fc.phone_daytime,
            fc.phone_work,
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
    -- pre-migration kippmiami_powerschool snapshot. Focus stores the KIPP
    -- student number 8400-prefixed in local_student_id, so student_number is
    -- derived by stripping that prefix rather than crosswalked. Deriving beats
    -- joining int_finalsite__contact_id_attributes on
    -- focus_student_id_prefixed: its powerschool_student_number agrees with the
    -- stripped value wherever it is populated, but it is null for every
    -- Focus-native student (no pre-migration PowerSchool record), so the join
    -- would silently drop most of Miami.
    focus_base as (
        select
            student_id,
            person_id,
            relationship,
            sort_order,
            contact_name,
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

            safe_cast(substr(local_student_id, 5) as int64) as student_number,
        from {{ ref("int_focus__student_contacts") }}
    ),

    focus_contact_1 as (
        select *, 'contact_1' as contact_slot, from focus_base where sort_order = 1
    ),

    -- Every emergency-flagged link is ranked, including the sort_order 1 row
    -- that also lands in contact_1 — the two are distinct contact_slot values,
    -- so the model's (student_number, _dbt_source_project, contact_slot) grain
    -- holds and one person may legitimately occupy both slots. person_id breaks
    -- sort_order ties so slot assignment is stable across rebuilds. Capped at 4
    -- to match the outgoing PowerSchool branch: int_students__contacts_pivot
    -- enumerates a fixed slot list ending at emergency_4, so higher ranks would
    -- materialize rows no consumer reads.
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
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
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
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
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
            relationship,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
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
    )

select
    student_number,
    _dbt_source_project,
    contact_slot,
    personid,
    finalsite_contact_id,
    contact_name,
    relationship,
    email_current,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
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
    relationship,
    email_current,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
    phone_primary,
    address_home,
    is_emergency,
    is_pickup,
    is_custodial,
    is_household_member,
from focus
