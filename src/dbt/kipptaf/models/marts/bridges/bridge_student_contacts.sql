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
            person_identity,
        from {{ ref("int_students__contacts") }}
        where
            contact_slot in ('contact_1', 'contact_2')
            or contact_slot like 'emergency\\_%'
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

            -- Keyed identically to `dim_student_contact_persons`: parent slots
            -- (`contact_1`, `contact_2`) by the person's real identity,
            -- emergency by student plus contact slot. The `contacts` CTE above
            -- excludes slots outside those 2 shapes, for the same reason the
            -- dimension excludes them, so this key cannot orphan against
            -- `dim_student_contact_persons`.
            if(
                contact_slot in ('contact_1', 'contact_2'),
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
