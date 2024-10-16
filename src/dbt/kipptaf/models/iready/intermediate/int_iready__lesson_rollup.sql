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
    )

-- select lu.academic_year_int, lu.student_id, lu.subject,
-- from lesson_union as lu
-- inner join {{ ref("stg_people__location_crosswalk") }} as sc on lu.school = sc.name
select *
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
    and w.week_start_monday between co.entrydate and co.exitdate
left join
    lesson_union as lu
    on co.student_number = lu.student_id
    and co.academic_year = lu.academic_year
    and lu.completion_date between w.week_start_monday and w.week_end_sunday
where co.academic_year >= {{ var("current_academic_year") - 2 }} and co.grade_level < 9
