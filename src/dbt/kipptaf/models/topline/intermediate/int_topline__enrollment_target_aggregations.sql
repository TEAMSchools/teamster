with
    enrollment as (
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
    )

select e.*, t.seat_target, t.budget_target,
from enrollment as e
inner join
    {{ ref("stg_google_sheets__topline_enrollment_targets") }} as t
    on e.academic_year = t.academic_year
    and e.join_clause = t.join_clause
