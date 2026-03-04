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
        then 'Org ' || g.grade_band
        when g.org_level = 'region'
        then g.entity || ' ' || g.grade_band
        when g.org_level = 'school'
        then s.abbreviation || ' ' || g.grade_band
    end as aggregation_display,
from {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
left join {{ ref("stg_powerschool__schools") }} as s on g.schoolid = s.school_number
