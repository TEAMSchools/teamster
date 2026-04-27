select
    g.layer,
    g.topline_indicator,
    g.goal_type,
    g.entity,
    g.schoolid,
    g.grade_low,
    g.grade_high,
    g.org_level,
    g.has_goal,
    g.aggregation_type,
    g.goal_direction,
    g.goal,
    g.aggregation_hash,
    g.indicator_display,
    g.discipline,
    g.aggregation_data_type,
    g.grade_band,

    case
        when g.layer = 'Outstanding Teammates' and g.org_level = 'org'
        then g.org_level
        when g.layer = 'Outstanding Teammates' and g.org_level = 'region'
        then g.entity
        when g.layer = 'Outstanding Teammates' and g.org_level = 'school'
        then s.abbreviation
        when g.org_level = 'org'
        then 'Org ' || g.grade_band
        when g.org_level = 'region'
        then g.entity || ' ' || g.grade_band
        when g.org_level = 'school'
        then s.abbreviation || ' ' || g.grade_band
    end as aggregation_display,

    if(g.aggregation_data_type = 'Numeric', g.goal, null) as goal_numeric,
    if(g.aggregation_data_type = 'Integer', g.goal, null) as goal_integer,
from {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
left join {{ ref("stg_powerschool__schools") }} as s on g.schoolid = s.school_number
