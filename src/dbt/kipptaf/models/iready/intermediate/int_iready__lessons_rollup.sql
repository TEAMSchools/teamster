select
    il.academic_year_int,
    il.student_id,
    il.subject,

    cw.powerschool_school_id,

    pw.week_start_monday,
    pw.week_end_sunday,

    round(avg(il.passed_or_not_passed_numeric), 2) as pct_lessons_passed,
    sum(il.passed_or_not_passed_numeric) as sum_lessons_passed,
    if(sum(il.passed_or_not_passed_numeric) >= 2, 1, 0) as is_pass_2_lessons_int,
    if(sum(il.passed_or_not_passed_numeric) >= 4, 1, 0) as is_pass_4_lessons_int,
    count(il.lesson_id) as total_lessons_attempted,
    count(distinct il.lesson_id) as total_lessons_attempted_distinct,
from {{ ref("stg_iready__personalized_instruction_by_lesson") }} as il
inner join {{ ref("stg_people__location_crosswalk") }} as cw on il.school = cw.name
inner join
    {{ ref("int_powerschool__calendar_week") }} as pw
    on il.academic_year_int = pw.academic_year
    and cw.powerschool_school_id = pw.schoolid
    and il.completion_date between pw.week_start_monday and pw.week_end_sunday
group by
    il.academic_year_int,
    il.student_id,
    il.subject,
    cw.powerschool_school_id,
    pw.week_start_monday,
    pw.week_end_sunday
