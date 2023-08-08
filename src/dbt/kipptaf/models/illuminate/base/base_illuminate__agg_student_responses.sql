with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_illuminate__agg_student_responses_overall"),
                    ref("stg_illuminate__agg_student_responses_standard"),
                    ref("stg_illuminate__agg_student_responses_group"),
                ]
            )
        }}
    )

select *, regexp_extract(_dbt_source_relation, r'agg_student_responses_(\w*)'),
from union_relations
