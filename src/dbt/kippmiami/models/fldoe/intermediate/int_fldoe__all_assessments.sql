with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_fldoe__eoc"),
                    ref("stg_fldoe__fast"),
                    ref("stg_fldoe__fsa"),
                    ref("stg_fldoe__science"),
                ]
            )
        }}
    ),

    transformed as (
        select
            test_code,
            academic_year,
            administration_window,
            season,
            discipline,
            assessment_subject,
            scale_score,
            achievement_level,
            is_proficient,

            cast(
                coalesce(assessment_grade, test_grade, enrolled_grade) as string
            ) as assessment_grade,

            coalesce(performance_level, achievement_level_int) as performance_level,
            coalesce(student_id, fleid) as student_id,

            regexp_extract(
                _dbt_source_relation, r'stg_fldoe__(\w+)'
            ) as assessment_name,
        from union_relations
    )

select
    * except (assessment_name),

    case assessment_name when 'SCIENCE' then 'Science' end as assessment_name,
from transformed
