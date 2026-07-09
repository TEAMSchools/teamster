{% set attributes = [
    ("name", "contact_name"),
    ("relationship", "relationship"),
    ("email_current", "email_current"),
    ("phone_mobile", "phone_mobile"),
    ("phone_home", "phone_home"),
    ("phone_daytime", "phone_daytime"),
    ("phone_work", "phone_work"),
    ("phone_primary", "phone_primary"),
    ("address_home", "address_home"),
] %}

{% set data_slots = [
    "contact_1",
    "emergency_1",
    "emergency_2",
    "emergency_3",
    "emergency_4",
] %}

{% set null_slots = ["contact_2", "pickup_1", "pickup_2", "pickup_3"] %}

-- Wide one-row-per-student contact surface, pivoted from the long
-- int_students__contacts model. Preserves the legacy column surface so
-- downstream extracts do not churn: contact_1 and emergency_1..4 carry data,
-- while contact_2 and pickup_1..3 are retained as NULL (the 1+4 shape emits no
-- rows for those slots). emergency_4 is a new additive column set.
select
    student_number,
    _dbt_source_project,
    {% for slot in data_slots %}
        {% for attribute, source_column in attributes %}
            max(
                if(contact_slot = '{{ slot }}', {{ source_column }}, null)
            ) as {{ slot }}_{{ attribute }},
        {% endfor %}
    {% endfor %}
    {% for slot in null_slots %}
        {% for attribute, source_column in attributes %}
            cast(null as string) as {{ slot }}_{{ attribute }},
        {% endfor %}
    {% endfor %}
from {{ ref("int_students__contacts") }}
group by student_number, _dbt_source_project
