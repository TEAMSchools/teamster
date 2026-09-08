with
    form_abbreviations as (
        select distinct lower(abbreviation) as abbreviation,
        from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
        where abbreviation is not null
    ),

    crosswalk as (
        select distinct lower(abbreviation) as abbreviation,
        from {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
        where abbreviation is not null
    )

select fa.abbreviation,
from form_abbreviations as fa
left join crosswalk as cw on fa.abbreviation = cw.abbreviation
where cw.abbreviation is null
