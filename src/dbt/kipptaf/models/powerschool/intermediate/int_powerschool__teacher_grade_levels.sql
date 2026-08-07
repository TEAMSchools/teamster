with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__teacher_grade_levels",
                    ),
                    ref("int_focus__teacher_grade_levels_conformed"),
                ]
            )
        }}
    ),

    -- The Focus branch is a kipptaf relation, so the usual relation-name regex
    -- would read 'kipptaf' from it. It carries its own _dbt_source_project
    -- instead; the four PowerSchool relations null-fill that column and fall
    -- back to the regex.
    with_project as (
        -- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
        select
            * except (_dbt_source_project),

            _dbt_source_relation like '%\\_focus%' as is_focus,

            coalesce(
                _dbt_source_project, regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
            ) as _dbt_source_project,
        from union_relations
    )

-- Miami cuts over to Focus at AY2026, matching the enrollment and terms
-- unions. The frozen archive keeps every closed year.
select * except (is_focus),
from with_project
where
    _dbt_source_project != 'kippmiami'
    or (is_focus and academic_year >= 2026)
    or (not is_focus and academic_year <= 2025)
