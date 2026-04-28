select
    {{ dbt_utils.generate_surrogate_key(["location_name"]) }} as location_key,

    if(
        region is not null,
        {{ dbt_utils.generate_surrogate_key(["region"]) }},
        cast(null as string)
    ) as region_key,

    location_name as `name`,
    grade_band,
    campus_name as campus,
    is_campus,
    address,
    city,
    postal_code,

    coalesce(abbreviation, location_name) as abbreviation,
from {{ ref("stg_google_sheets__people__locations") }}
where not is_pathways and location_name <> 'KIPP Whittier Elementary'
