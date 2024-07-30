select
    gsa_id,
    group_id,
    student_id,
    start_date,
    end_date,
    eligibility_start_date,
    eligibility_end_date,
from {{ source("illuminate", "group_student_aff") }}
where not _fivetran_deleted
