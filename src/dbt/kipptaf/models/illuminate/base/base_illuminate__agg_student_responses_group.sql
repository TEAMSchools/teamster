select asrg.*, arg.performance_band_set_id, arg.sort_order, rg.label,
from {{ ref("stg_illuminate__agg_student_responses_group") }} as asrg
inner join
    {{ ref("stg_illuminate__assessments_reporting_groups") }} as arg
    on asrg.assessment_id = arg.assessment_id
    and asrg.reporting_group_id = arg.reporting_group_id
inner join
    {{ ref("stg_illuminate__reporting_groups") }} as rg
    on asrg.reporting_group_id = rg.reporting_group_id
