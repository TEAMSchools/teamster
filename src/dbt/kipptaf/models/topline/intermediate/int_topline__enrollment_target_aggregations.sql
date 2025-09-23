select
    *,

    case
        when org_level = 'org'
        then org_level
        when org_level = 'region'
        then region
        when org_level = 'school'
        then cast(schoolid as string)
    end as join_clause,
from {{ ref("int_topline__dashboard_aggregations") }}
where indicator = 'Total Enrollment'
