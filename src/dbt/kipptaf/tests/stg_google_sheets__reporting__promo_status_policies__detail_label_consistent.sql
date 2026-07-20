{{ config(severity="error") }}

select
    academic_year,
    region,
    grade_min,
    grade_max,
    term_name,
    domain,
    rule_group,

    count(distinct detail_label) as n_labels,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
group by academic_year, region, grade_min, grade_max, term_name, domain, rule_group
having count(distinct detail_label) > 1
