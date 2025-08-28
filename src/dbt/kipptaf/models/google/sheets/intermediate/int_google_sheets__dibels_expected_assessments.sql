select
    m.*,

    t.start_date,
    t.end_date,

    min(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number
    ) as min_pm_round,

    max(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number desc
    ) as max_pm_round,

from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as m
left join
    {{ ref("stg_reporting__terms") }} as t
    on m.academic_year = t.academic_year
    and m.region = t.region
    and m.admin_season = t.name
    and m.test_code = t.code
    and t.type = 'LIT'
