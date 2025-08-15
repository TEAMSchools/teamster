select
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.school,
    co.iready_subject,
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

    sum(coalesce(ir.passed_or_not_passed_numeric, 0)) as n_lessons_passed,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    {{ ref("int_iready__instruction_by_lesson_union") }} as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
    and co.iready_subject = ir.subject
    and ir.completion_date between co.week_start_monday and co.week_end_sunday
where co.academic_year >= {{ var("current_academic_year") - 1 }}
group by
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.school,
    co.iready_subject,
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
    co.enroll_status
