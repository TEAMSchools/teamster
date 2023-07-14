select
    student_number,
    student_web_id,
    student_web_password,
    student_allowwebaccess,
    web_id,
    web_password,
    allowwebaccess,
    team,
    track,
    eligibility_name,
    total_balance,
    home_room,
    graduation_year,
    district_entry_date,
    school_entry_date,
from {{ source("kipptaf_extracts", "rpt_powerschool__autocomm_students") }}
where code_location = '{{ project_name }}'
