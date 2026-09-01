select
    id,
    assignment_type_id,
    course_period_id,
    marking_period_id,
    template_id,
    template_category_id,
    color,
    uuid,
    created_at,
    updated_at,

    cast(drop_lowest_grades as numeric) as drop_lowest_grades,
    cast(final_grade_percent as numeric) as final_grade_percent,
from {{ source("focus", "gradebook_assignment_types_join_course_periods") }}
