{% set ref_responses = ref("stg_illuminate__agg_student_responses_group") %}

select
    {{
        dbt_utils.star(
            from=ref_responses,
            relation_alias="asr",
            except=["performance_band_set_id"],
        )
    }},

    arg.performance_band_set_id,
    arg.sort_order,

    rg.label,
from {{ ref_responses }} as asr
inner join
    {{ ref("stg_illuminate__assessments_reporting_groups") }} as arg
    on asr.assessment_id = arg.assessment_id
    and asr.reporting_group_id = arg.reporting_group_id
inner join
    {{ ref("stg_illuminate__reporting_groups") }} as rg
    on asr.reporting_group_id = rg.reporting_group_id
