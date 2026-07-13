with
    contacts as (
        select
            student_number,
            contact_slot,
            relationship,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,
            _dbt_source_project,

            coalesce(finalsite_contact_id, personid) as person_identity,
        from {{ ref("int_students__contacts") }}
    ),

    keyed as (
        select
            student_number,
            contact_slot,
            relationship,
            is_emergency,
            is_pickup,
            is_custodial,
            is_household_member,

            {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

            -- keyed identically to dim_student_contact_persons: contact_1 by the
            -- person's real identity, emergency by student + contact slot
            if(
                contact_slot = 'contact_1',
                {{
                    dbt_utils.generate_surrogate_key(
                        ["_dbt_source_project", "person_identity"]
                    )
                }},
                {{
                    dbt_utils.generate_surrogate_key(
                        ["_dbt_source_project", "student_number", "contact_slot"]
                    )
                }}
            ) as student_contact_person_key,
        from contacts
    )

select
    student_key,
    student_contact_person_key,
    relationship,
    contact_slot,
    is_emergency,
    is_pickup,
    is_custodial,
    is_household_member,
from keyed
