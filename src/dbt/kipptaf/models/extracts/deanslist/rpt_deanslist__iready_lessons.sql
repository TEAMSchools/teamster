select
    pl.student_id,
    pl.subject,
    sum(pl.passed_or_not_passed_numeric) as lessons_passed,
    count(pl.lesson_id) as total_lessons,
    round(sum(passed_or_not_passed_numeric) / count(pl.lesson_id), 2)
    * 100 as pct_passed,

    t.name as term,
from {{ ref("stg_iready__personalized_instruction_by_lesson") }} as pl
inner join {{ ref("stg_people__location_crosswalk") }} as sc on pl.school = sc.name
inner join
    {{ ref("stg_reporting__terms") }} as t
    on sc.powerschool_school_id = t.school_id
    and pl.academic_year_int = t.academic_year
    and pl.completion_date between t.start_date and t.end_date
    and t.type = 'RT'
where pl.completion_date >= date({{ var("current_academic_year") }}, 7, 1)
group by pl.student_id, pl.subject, t.name
