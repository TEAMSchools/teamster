select
    ref_id,
    school_name,
    academic_year,
    course_number,
    section_number,
    class_period,
    treatment_cp,
    treatment_rdc,
    treatment_rr,
    status,
from {{ source("google_sheets", "src_google_sheets__ignite__treatment_sections") }}
where ref_id is not null
