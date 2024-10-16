with
    lesson_union as (
        select
            'Traditional' as lesson_source,
            _dbt_source_relation,
            academic_year_int,
            student_id,
            school,
            `subject`,
            lesson_id,
            completion_date,
            passed_or_not_passed_numeric,
        from {{ ref("stg_iready__instruction_by_lesson") }}

        union all

        select
            'Pro' as lesson_source,
            _dbt_source_relation,
            academic_year_int,
            student_id,
            school,
            `subject`,
            lesson as lesson_id,
            completion_date,
            passed_or_not_passed_numeric,
        from {{ ref("stg_iready__instruction_by_lesson_pro") }}
    ),

    scaffold as (
        select
            co.academic_year,
            co.student_number,

            w.week_start_monday,
            w.quarter,

            subject,

            lu.lesson_source,
            lu.lesson_id,
            lu.passed_or_not_passed_numeric,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on co.academic_year = w.academic_year
            and co.schoolid = w.schoolid
            and w.week_start_monday between co.entrydate and co.exitdate
        cross join unnest(['Reading', 'Math']) as subject
        left join
            lesson_union as lu
            on co.student_number = lu.student_id
            and co.academic_year = lu.academic_year_int
            and subject = lu.subject
            and lu.completion_date between w.week_start_monday and w.week_end_sunday
        where
            co.academic_year >= {{ var("current_academic_year") - 2 }}
            and co.grade_level < 9
    )

select
    'Week' as time_period,
    academic_year,
    student_number,
    week_start_monday,
    null as quarter,
    subject,

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

union all

select
    'Quarter' as time_period,
    academic_year,
    student_number,
    null as week_start_monday,
    quarter,
    subject,

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
