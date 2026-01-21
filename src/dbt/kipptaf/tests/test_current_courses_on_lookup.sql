{{ config(severity="warn", store_failures=true, enabled=false) }}

select distinct cc_course_number,
from {{ ref("base_powerschool__course_enrollments") }}
where
    cc_academic_year = {{ var("current_academic_year") }}
    and illuminate_subject_area is null
