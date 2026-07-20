select
    academic_year,
    region,
    grade_min,
    grade_max,
    term_name,
    domain,
    rule_group,
    metric,
    comparator,
    `value`,
    if_missing,
    detail_label,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__reporting__promo_status_policies",
        )
    }}
/* google sheets externals surface the sheet's full grid as null rows */
where academic_year is not null
