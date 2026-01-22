with
    choices_long as (
        select cf.top_choice_schools, a.student__id, u.name,
        from {{ ref("int_overgrad__admissions") }} as a on cf.id = a.id
        inner join
            {{ ref("stg_overgrad__universities") }} as u on a.university__id = u.id
        where top_choice_schools is not null
    ),

    choices_pivot as (
        select
            student__id, first_choice_school, second_choice_school, third_choice_school,
        from
            choices_long pivot (
                max(name)
                for
                top_choice_schools in (
                    '#1 Choice' as first_choice_school,
                    '#2 Choice' as second_choice_school,
                    '#3 Choice' as third_choice_school
                )
            )
    )

select
    s.* except (student_aid_index),

    cf.* except (id, source_object, student_aid_index),

    coalesce(s.student_aid_index, cf.student_aid_index) as student_aid_index,
from {{ ref("stg_overgrad__students") }} as s
left join
    {{ ref("int_overgrad__custom_fields_pivot") }} as cf
    on s.id = cf.id
    and cf.source_object = 'students'
left join choices_pivot as c on s.id = c.student__id
