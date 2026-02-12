select s.academic_year, s.org, s.region, s.schoolid, s.school, s.grade_level,

from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as d
    on s.academic_year = d.aligned_enrollment_academic_year
    and s.schoolid = d.schoolid
    and s.grade_level = d.grade_level
