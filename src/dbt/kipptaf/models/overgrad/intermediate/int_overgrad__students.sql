with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_overgrad", "int_overgrad__students"),
                    source("kippcamden_overgrad", "int_overgrad__students"),
                ]
            )
        }}
    )

    choices_long as (
        select student__id, top_choice_schools, name,
        from {{ ref("int_overgrad__admissions") }}
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

select ur.*, c.first_choice_school, c.second_choice_school, c.third_choice_school,
from union_relations as ur
left join choices_pivot as c on ur.id = c.student__id
