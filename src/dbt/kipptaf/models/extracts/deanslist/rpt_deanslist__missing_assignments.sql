select
    student_number,
    assignmentsectionid,
    category_name as grade_category,
    assignment_name as assign_name,
    duedate as assign_date,
    course_name,
    teacher_name,
from {{ ref("int_powerschool__gradebook_assignments_scores") }}
where
    academic_year = {{ var("current_academic_year") }}
    and is_expected_missing = 1
    and _dbt_source_project != 'kippmiami'
    and school_level_alt != 'ES'
