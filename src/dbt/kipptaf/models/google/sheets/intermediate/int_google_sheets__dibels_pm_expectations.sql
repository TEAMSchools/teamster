select
    e.academic_year,
    e.region,
    e.grade,
    e.admin_season,
    e.`round`,
    e.expected_measure_name_code,
    e.expected_measure_standard,

from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as e
inner join
    {{ ref("stg_reporting__terms") }} as t
    on e.academic_year = t.academic_year
    and e.region = t.region
    and e.admin_season = t.name
    and e.test_code = t.code
    and t.type = 'LIT'
where e.academic_year >= 2024
