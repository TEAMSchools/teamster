-- Rationale lives in this test's tests/properties.yml description.
-- Any returned row is a failure.
select student_number, academic_year, grade_level, cohort, cohort_primary,
from {{ ref("base_powerschool__student_enrollments") }}
where
    academic_year = {{ var("current_academic_year") }}
    and enroll_status = 0
    and grade_level between 9 and 12
    and cohort > cohort_primary
