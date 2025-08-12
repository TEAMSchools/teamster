select
    co.academic_year,
    co.student_number,
    co.schoolid,
    co.iready_subject,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,

    coalesce(sum(ir.passed_or_not_passed_numeric), 0) as n_lessons_passed,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    {{ ref("int_iready__instruction_by_lesson_union") }} as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
    and co.iready_subject = ir.subject
    and ir.completion_date between co.week_start_monday and co.week_end_sunday
group by
    co.academic_year,
    co.student_number,
    co.schoolid,
    co.iready_subject,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year
