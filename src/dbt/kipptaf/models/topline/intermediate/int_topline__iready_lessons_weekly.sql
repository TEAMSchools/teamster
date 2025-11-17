select
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.deanslist_school_id,
    co.school,
    co.iready_subject,
    co.discipline,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,
    co.grade_level,
    co.gender,
    co.ethnicity,
    co.iep_status,
    co.is_504,
    co.lep_status,
    co.gifted_and_talented,
    co.entrydate,
    co.exitdate,
    co.enroll_status,

    pw.all_lessons_completed as n_lessons_completed_week,
    pw.all_lessons_passed as n_lessons_passed_week,
    pw.total_lesson_time_on_task_min as time_on_task_min_week,

    py.all_lessons_passed as n_lessons_passed_y1,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    {{ ref("stg_iready__personalized_instruction_summary") }} as pw
    on co.student_number = pw.student_id
    and co.academic_year = pw.academic_year_int
    and co.iready_subject = pw.subject
    and co.week_start_monday = pw.date_range_start
    and pw.date_range = 'Weekly'
left join
    {{ ref("stg_iready__personalized_instruction_summary") }} as py
    on co.student_number = py.student_id
    and co.academic_year = py.academic_year_int
    and co.iready_subject = py.subject
    and py.date_range = 'Year-to-Date'
where co.academic_year >= {{ var("current_academic_year") - 1 }}
