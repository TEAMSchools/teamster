select s.*,
from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as d
    on s.aligned_enrollment_academic_year = d.academic_year
    and s.schoolid = d.schoolid
    and s.grade_level = d.grade_level
