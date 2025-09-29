select
    g.*,

    case
        when g.layer = 'Outstanding Teammates' and g.org_level = 'org'
        then g.org_level
        when g.layer = 'Outstanding Teammates' and g.org_level = 'region'
        then g.entity
        when g.layer = 'Outstanding Teammates' and g.org_level = 'school'
        then s.abbreviation
        when g.org_level = 'org'
        then
            'Org ' || if(
                g.grade_low = g.grade_high,
                cast(g.grade_high as string),
                if(g.grade_low = 0, 'K', g.grade_low || '-' || g.grade_high)
            )
        when g.org_level = 'region'
        then
            g.entity
            || ' '
            || if(
                g.grade_low = g.grade_high,
                cast(g.grade_high as string),
                if(g.grade_low = 0, 'K', g.grade_low || '-' || g.grade_high)
            )
        when g.org_level = 'school'
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
