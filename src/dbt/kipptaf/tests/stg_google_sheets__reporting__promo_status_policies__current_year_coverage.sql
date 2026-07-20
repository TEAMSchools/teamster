with
    enrolled as (
        /* grain projection: every selected column is functionally determined
        by the partition key; not a mask for upstream duplicates */
        select distinct region, grade_level,
        from {{ ref("int_students__promotional_status_metrics") }}
        where academic_year = {{ var("current_academic_year") }}
    )

select e.region, e.grade_level, d as `domain`,
from enrolled as e
cross join unnest(['attendance', 'academic', 'overall']) as d
left join
    {{ ref("stg_google_sheets__reporting__promo_status_policies") }} as p
    on e.region = p.region
    and e.grade_level between p.grade_min and p.grade_max
    and d = p.domain
    and p.academic_year = {{ var("current_academic_year") }}
where p.rule_group is null
