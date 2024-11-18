with
    scaffold as (
        select
            co.academic_year,
            co.student_number,

            `subject`,

            w.week_start_monday,
            w.quarter,

            lu.lesson_source,
            lu.lesson_id,
            lu.passed_or_not_passed_numeric,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        cross join unnest(['Reading', 'Math']) as `subject`
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on co.academic_year = w.academic_year
            and co.schoolid = w.schoolid
            and w.week_start_monday between co.entrydate and co.exitdate
        left join
            {{ ref("int_iready__instruction_by_lesson_union") }} as lu
            on co.student_number = lu.student_id
            and co.academic_year = lu.academic_year_int
            and `subject` = lu.subject
            and lu.completion_date between w.week_start_monday and w.week_end_sunday
        where
            co.academic_year = {{ var("current_academic_year") }} and co.grade_level < 9
    ),

    -- trunk-ignore(sqlfluff/ST03)
    week_rollup as (
        select
            student_number,
            academic_year,
            week_start_monday,
            `subject`,

            coalesce(sum(passed_or_not_passed_numeric), 0) as lessons_passed,
            coalesce(count(lesson_id), 0) as total_lessons,

            if(
                coalesce(sum(passed_or_not_passed_numeric), 0) >= 2, 1, 0
            ) as is_2plus_lessons_passed_int,

            if(
                coalesce(sum(passed_or_not_passed_numeric), 0) >= 4, 1, 0
            ) as is_4plus_lessons_passed_int,

            coalesce(
                round(sum(passed_or_not_passed_numeric) / count(lesson_id), 2) * 100, 0
            ) as pct_passed,
        from scaffold
        group by all
    ),

    quarter_rollup as (
        select
            student_number,
            academic_year,
            `quarter`,
            `subject`,

            coalesce(sum(passed_or_not_passed_numeric), 0) as lessons_passed,
            coalesce(count(lesson_id), 0) as total_lessons,

            if(
                coalesce(sum(passed_or_not_passed_numeric), 0) >= 2, 1, 0
            ) as is_2plus_lessons_passed_int,

            if(
                coalesce(sum(passed_or_not_passed_numeric), 0) >= 4, 1, 0
            ) as is_4plus_lessons_passed_int,

            coalesce(
                round(sum(passed_or_not_passed_numeric) / count(lesson_id), 2) * 100, 0
            ) as pct_passed,
        from scaffold
        group by all
    )

select
    student_number as student_id,
    `subject`,
    `quarter` as term,
    lessons_passed,
    total_lessons,
    pct_passed,
from quarter_rollup
