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
    ),

    students as (
        select *, {{ extract_source_project() }} as _dbt_source_project,
        from union_relations
    ),

    choices_long as (
        select student__id, top_choice_schools, university_name, _dbt_source_project,
        from {{ ref("int_overgrad__admissions") }}
        where top_choice_schools is not null
    ),

    choices_pivot as (
        select
            student__id,
            _dbt_source_project,
            first_choice_school,
            second_choice_school,
            third_choice_school,
        from
            choices_long pivot (
                max(university_name)
                for
                top_choice_schools in (
                    '#1 Choice' as first_choice_school,
                    '#2 Choice' as second_choice_school,
                    '#3 Choice' as third_choice_school
                )
            )
    )

select s.*, c.first_choice_school, c.second_choice_school, c.third_choice_school,
from students as s
left join
    choices_pivot as c
    on s.id = c.student__id
    and s._dbt_source_project = c._dbt_source_project
