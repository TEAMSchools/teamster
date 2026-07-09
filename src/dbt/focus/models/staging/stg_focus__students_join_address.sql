with source as (select *, from {{ source("focus", "students_join_address") }})

select
    id,
    student_id,
    address_id,
    mailing,
    residence,
    bus_pickup,
    bus_dropoff,
    imported,
    uuid,
    updated_at,
    created_at,
from source
where deleted is null
