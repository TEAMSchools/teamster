with
    source as (
        select
            org_level,
            schoolid,
            grade_low,
            grade_high,
            layer,
            topline_indicator,
            academic_year,
            period_type,
            period_label,

            cast(goal as numeric) as goal,

            {{ region_to_city("entity") }} as entity,
        -- TODO(#4363): swap to the sheet-tab source at cutover (see plan
        -- Task 13) and delete the seed
        from {{ ref("seed_topline_period_goals") }}
        where topline_indicator is not null
    )

select
    org_level,
    schoolid,
    grade_low,
    grade_high,
    layer,
    topline_indicator,
    academic_year,
    period_type,
    period_label,
    goal,
    entity,

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
from source
