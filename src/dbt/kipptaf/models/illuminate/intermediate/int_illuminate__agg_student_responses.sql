with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_illuminate__agg_student_responses_overall"),
                    ref("base_illuminate__agg_student_responses_standard"),
                    ref("base_illuminate__agg_student_responses_group"),
                ]
            )
        }}
    )

select
    sa.student_assessment_id,
    sa.student_id,
    sa.assessment_id,
    sa.date_taken,
    sa.created_at,
    sa.updated_at,
    sa.version_id,

    ur.mastered,
    ur.percent_correct,
    ur.number_of_questions,
    ur.answered,
    ur.performance_band_id,
    ur.performance_band_level,
    ur.performance_band_set_id,
    regexp_extract(ur._dbt_source_relation, r'_([a-z]+)`$') as response_type,
    coalesce(ur.standard_id, ur.reporting_group_id) as subgroup_id,
    coalesce(ur.standard_description, ur.label) as subgroup_description,
    coalesce(ur.points_possible, ur.raw_score_possible) as points_possible,
    coalesce(ur.points, ur.raw_score) as points,

    ur.custom_code as standard_code,
    ur.root_standard_description,

{#
    ur.raw_score_mastered,
    ur.sort_order,
#}
from {{ ref("stg_illuminate__students_assessments") }} as sa
inner join union_relations as ur on sa.student_assessment_id = ur.student_assessment_id
