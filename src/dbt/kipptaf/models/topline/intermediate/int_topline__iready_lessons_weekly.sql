select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,
    co.discipline,

    pw.all_lessons_passed as n_lessons_passed_week,
    pw.total_lesson_time_on_task_min as time_on_task_min_week,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    {{ ref("stg_iready__personalized_instruction_summary") }} as pw
    on co.student_number = pw.student_id
    and co.academic_year = pw.academic_year_int
    and co.iready_subject = pw.subject
    and co.week_start_monday = pw.date_range_start
    and pw.date_range = 'Weekly'
where co.academic_year >= {{ var("current_academic_year") - 1 }}
