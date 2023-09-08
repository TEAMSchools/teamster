select
    student_number, grade_category, assign_name, assign_date, course_name, teacher_name,
from {{ ref("rpt_tableau__gradebook_assignments") }}
where
    academic_year = {{ var("current_academic_year") }}
    and ismissing = 1
    and finalgrade_category = 'Q'
