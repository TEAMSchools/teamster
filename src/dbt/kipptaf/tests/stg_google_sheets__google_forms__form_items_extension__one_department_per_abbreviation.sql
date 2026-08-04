select
    lower(abbreviation) as abbreviation,

    count(distinct rated_department_code) as distinct_department_codes,
from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
where abbreviation is not null
group by lower(abbreviation)
having count(distinct rated_department_code) > 1
