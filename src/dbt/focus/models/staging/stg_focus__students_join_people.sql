with source as (select *, from {{ source("focus", "students_join_people") }})

select
    id,
    student_id,
    person_id,
    address_id,
    custody,
    emergency,
    student_relation,
    imported,
    sort_order,
    pick_up,
    uuid,
    updated_at,
    created_at,
    reunification,
from source
where deleted is null
