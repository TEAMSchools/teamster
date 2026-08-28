select
    id,
    assignment_type_id,
    course_period_id,
    marking_period_id,
    template_id,
    template_category_id,
    final_grade_percent,
    drop_lowest_grades,
    color,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignment_types_join_course_periods") }}
