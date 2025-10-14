with
    weeks as (
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

            count(distinct ir.lesson_id) as n_lessons_completed_week,
            sum(coalesce(ir.passed_or_not_passed_numeric, 0)) as n_lessons_passed_week,
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
            co.enroll_status
    )

select
    student_number,
    state_studentnumber,
    student_name,
    academic_year,
    region,
    school_level,
    schoolid,
    deanslist_school_id,
    school,
    iready_subject,
    discipline,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,
    grade_level,
    gender,
    ethnicity,
    iep_status,
    is_504,
    lep_status,
    gifted_and_talented,
    entrydate,
    exitdate,
    enroll_status,
    n_lessons_passed_week,
    n_lessons_completed_week,

    sum(n_lessons_passed_week) over (
        partition by iready_subject, academic_year, student_number
        order by week_start_monday asc
    ) as n_lessons_passed_y1,
from weeks
