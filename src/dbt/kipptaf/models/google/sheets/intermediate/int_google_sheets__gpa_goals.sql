select
    academic_year,
    org_level,
    region,
    schoolid,
    grade_low,
    grade_high,
    metric,
    threshold,
    direction,
    goal,

    goal / 100.0 as goal_proportion,

    if(
        grade_low = grade_high,
        cast(grade_high as string),
        grade_low || '-' || grade_high
    ) as grade_band,

    case
        when org_level = 'org'
        then 'org_' || grade_low || '-' || grade_high
        when org_level = 'region'
        then region || '_' || grade_low || '-' || grade_high
        when org_level = 'school'
        then cast(schoolid as string) || '_' || grade_low || '-' || grade_high
    end as aggregation_hash,

    direction in ('>=', '>') as higher_is_better,
from {{ ref("stg_google_sheets__gpa_goals") }}
