select
    pl.student_id,
    pl.subject,
    t.name as term,
    cast(
        sum(case when pl.passed_or_not_passed = 'Passed' then 1 else 0 end) as float64
    ) as lessons_passed,
    cast(count(distinct pl.lesson_id) as float64) as total_lessons,
    round(
        cast(
            sum(
                case when pl.passed_or_not_passed = 'Passed' then 1 else 0 end
            ) as float64
        )
        / cast(count(pl.lesson_id) as float64),
        2
    )
    * 100 as pct_passed
from {{ ref("stg_iready__personalized_instruction_by_lesson") }} as pl
inner join {{ ref("stg_people__location_crosswalk") }} as sc on (pl.school = sc.name)
inner join
    {{ ref("stg_reporting__terms") }} as t
    on (
        sc.powerschool_school_id = t.school_id
        and cast(left(pl.academic_year, 4) as int64) = t.academic_year
        and (
            parse_date('%m/%d/%Y', pl.completion_date)
            between t.start_date and t.end_date
        )
        and t.type = 'RT'
    )
where
    parse_date('%m/%d/%Y', pl.completion_date)
    >= date({{ var("current_academic_year") }}, 7, 1)
group by pl.student_id, pl.subject, t.name
