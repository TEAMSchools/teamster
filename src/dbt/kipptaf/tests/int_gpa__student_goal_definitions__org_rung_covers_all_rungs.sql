with
    org_goals as (
        select academic_year, metric, grade_low, grade_high,
        from {{ ref("int_google_sheets__gpa_goals") }}
        where org_level = 'org'
    )

select n.academic_year, n.metric, n.org_level, n.grade_low, n.grade_high,
from {{ ref("int_google_sheets__gpa_goals") }} as n
left join
    org_goals as o
    on n.academic_year = o.academic_year
    and n.metric = o.metric
    and n.grade_low = o.grade_low
    and n.grade_high = o.grade_high
where n.org_level != 'org' and o.academic_year is null
