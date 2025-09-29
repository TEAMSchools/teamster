select
    g.*,

    case
        when layer = 'Outstanding Teammates' and org_level = 'org'
        then org_level
        when layer = 'Outstanding Teammates' and org_level = 'region'
        then entity
        when layer = 'Outstanding Teammates' and org_level = 'school'
        then s.abbreviation
        when org_level = 'org'
        then
            'Org ' || if(
                g.grade_low = g.grade_high,
                cast(g.grade_high as string),
                if(g.grade_low = 0, 'K', g.grade_low || '-' || g.grade_high)
            )
        when org_level = 'region'
        then
            entity
            || ' '
            || if(
                g.grade_low = g.grade_high,
                cast(g.grade_high as string),
                if(g.grade_low = 0, 'K', g.grade_low || '-' || g.grade_high)
            )
        when org_level = 'school'
        then
            s.abbreviation
            || ' '
            || if(
                g.grade_low = g.grade_high,
                cast(g.grade_high as string),
                if(g.grade_low = 0, 'K', g.grade_low || '-' || g.grade_high)
            )
    end as aggregation_display,
from {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
left join {{ ref("stg_powerschool__schools") }} as s on g.schoolid = s.school_number
