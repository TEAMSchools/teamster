select
    student_id,
    school_id,
    first_name,
    last_name,
    relationship,
    mobile,
    secondary_phone,
    email,
from {{ source("kipptaf_extracts", "rpt_parentsquare__parents") }}
where code_location = '{{ project_name }}'
