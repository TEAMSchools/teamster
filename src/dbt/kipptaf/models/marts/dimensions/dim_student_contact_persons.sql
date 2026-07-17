with
    contacts as (
        select
            student_number,
            contact_slot,
            contact_name,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_primary,
            address_home,
            _dbt_source_project,

            coalesce(finalsite_contact_id, personid) as person_identity,
        from {{ ref("int_students__contacts") }}
    ),

    /* contact_1 is a real contact record that siblings share, so it keys on the
       person's identity and collapses to one row per person. Every selected
       attribute is functionally determined by (_dbt_source_project,
       person_identity) — grain projection, not a mask for upstream duplicates. */
    contact_1_persons as (
        select distinct
            contact_name,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_primary,
            address_home,
            _dbt_source_project,
            person_identity,
        from contacts
        where contact_slot = 'contact_1'
    ),

    /* emergency contacts have no stable person record under the Finalsite 1+4
       shape, so each (student, slot) is its own person keyed by student + slot. */
    emergency_persons as (
        select
            student_number,
            contact_slot,
            contact_name,
            email_current,
            phone_mobile,
            phone_home,
            phone_daytime,
            phone_work,
            phone_primary,
            address_home,
            _dbt_source_project,
        from contacts
        where contact_slot != 'contact_1'
    )

select
    {{ dbt_utils.generate_surrogate_key(["_dbt_source_project", "person_identity"]) }}
    as student_contact_person_key,

    contact_name as full_name,
    email_current as email,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
    phone_primary,
    address_home as home_address,
from contact_1_persons

union all

select
    {{
        dbt_utils.generate_surrogate_key(
            ["_dbt_source_project", "student_number", "contact_slot"]
        )
    }} as student_contact_person_key,

    contact_name as full_name,
    email_current as email,
    phone_mobile,
    phone_home,
    phone_daytime,
    phone_work,
    phone_primary,
    address_home as home_address,
from emergency_persons
