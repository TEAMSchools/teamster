with source as (select *, from {{ source("focus", "students_join_people") }})

select
    id,
    student_id,
    person_id,
    address_id,
    student_relation,
    imported,
    uuid,
    updated_at,
    created_at,

    cast(sort_order as numeric) as sort_order,

    custody = 'Y' as is_custodial,
    emergency = 'Y' as is_emergency,
    pick_up = 'Y' as is_pickup,
    reunification = 'Y' as is_reunification,
from source
where deleted is null
