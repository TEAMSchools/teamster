with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_powerschool__students"),
                    ref("int_focus__students_conformed"),
                ],
                source_column_name=none,
            )
        }}
    ),

    focus_students as (
        select student_number, from {{ ref("int_focus__students_conformed") }}
    )

-- Focus supersedes the frozen archive for every Miami student it carries, so an
-- archive row for such a student would double-count. The archive still holds 493
-- departed students Focus never received; those stay, or dim_students loses them.
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select u.*,
from union_relations as u
left join focus_students as f on u.student_number = f.student_number
where
    u._dbt_source_project != 'kippmiami'
    or u._dbt_source_relation like '%\\_focus%'
    or f.student_number is null
