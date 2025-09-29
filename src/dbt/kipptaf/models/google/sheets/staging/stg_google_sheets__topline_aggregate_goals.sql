select
    * except (goal),
    cast(goal as numeric) as goal,

    case
        when layer = 'Outstanding Teammates' and org_level = 'org'
        then org_level
        when layer = 'Outstanding Teammates' and org_level = 'region'
        then entity
        when layer = 'Outstanding Teammates' and org_level = 'school'
        then cast(schoolid as string)
        when org_level = 'org'
        then 'org_' || grade_low || '-' || grade_high
        when org_level = 'region'
        then entity || '_' || grade_low || '-' || grade_high
        when org_level = 'school'
        then schoolid || '_' || grade_low || '-' || grade_high
    end as aggregation_hash,
from {{ source("google_sheets", "src_google_sheets__topline_aggregate_goals") }}
