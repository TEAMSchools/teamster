with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_powerschool__schools"),
                    ref("int_focus__schools_conformed"),
                ],
                source_column_name=none,
            )
        }}
    ),

    focus_schools as (
        select school_number, from {{ ref("int_focus__schools_conformed") }}
    )

-- Focus supersedes the frozen archive for every Miami school it carries, so an
-- archive row for such a school would double-count. The archive still holds the
-- 999999 "Graduated Students" sentinel Focus never received, which the 1,002
-- alumni graduate placeholder enrollment rows (Task 8) join to directly --
-- dropping it would null-fill their school attributes in
-- dim_student_enrollments.
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select u.*,
from union_relations as u
left join focus_schools as f on u.school_number = f.school_number
where
    u._dbt_source_project != 'kippmiami'
    or u._dbt_source_relation like '%\\_focus%'
    or f.school_number is null
