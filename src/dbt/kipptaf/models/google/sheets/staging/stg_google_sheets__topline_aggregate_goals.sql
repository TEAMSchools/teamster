select
    * except (goal),
    cast(goal as numeric) as goal,

    case
        org_level
        when 'org'
        then 'org_' || grade_low || '-' || grade_high
        when 'region'
        then entity || '_' || grade_low || '-' || grade_high
        when 'school'
        then schoolid || '_' || grade_low || '-' || grade_high
    end as aggregation_hash,
from {{ source("google_sheets", "src_google_sheets__topline_aggregate_goals") }}
