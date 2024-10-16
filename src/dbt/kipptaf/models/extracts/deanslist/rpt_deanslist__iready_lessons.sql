select
    student_number as student_id,
    subject,
    quarter as term,
    lessons_passed,
    total_lessons,
    pct_passed,
from {{ ref("int_iready__lesson_rollup") }}
where academic_year = {{ var("current_academic_year") }} and time_period = 'Quarter'
