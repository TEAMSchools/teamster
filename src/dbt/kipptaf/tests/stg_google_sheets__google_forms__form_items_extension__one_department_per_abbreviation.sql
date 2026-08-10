with
    sheet_rows as (
        select
            format(
                '%T|%T', rated_department_code, rated_department_name
            ) as department_mapping,

            lower(abbreviation) as abbreviation,
        from {{ ref("stg_google_sheets__google_forms__form_items_extension") }}
        where abbreviation is not null
    ),

    department_mappings as (
        select
            abbreviation,

            count(distinct department_mapping) as distinct_department_mappings,
        from sheet_rows
        group by abbreviation
    )

select *,
from department_mappings
where distinct_department_mappings > 1
