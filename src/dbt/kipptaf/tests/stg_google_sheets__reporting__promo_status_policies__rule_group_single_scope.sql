select
    a.academic_year,
    a.region,
    a.domain,
    a.rule_group,
    a.grade_min,
    a.grade_max,
    a.term_name,

    b.grade_min as other_grade_min,
    b.grade_max as other_grade_max,
    b.term_name as other_term_name,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }} as a
inner join
    {{ ref("stg_google_sheets__reporting__promo_status_policies") }} as b
    on a.academic_year = b.academic_year
    and a.region = b.region
    and a.domain = b.domain
    and a.rule_group = b.rule_group
    and a.grade_min <= b.grade_max
    and a.grade_max >= b.grade_min
    and (a.term_name = b.term_name or 'All' in (a.term_name, b.term_name))
-- keeps one direction of each pair; identical scopes never reach this point
where
    a.grade_min < b.grade_min
    or (
        a.grade_min = b.grade_min
        and (
            a.grade_max < b.grade_max
            or (a.grade_max = b.grade_max and a.term_name < b.term_name)
        )
    )
