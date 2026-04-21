select
    {{ dbt_utils.generate_surrogate_key(["location_name"]) }} as location_key,

    location_name,
    region,
    grade_band,
    campus_name as campus,
    is_campus,

    coalesce(abbreviation, location_name) as abbreviation,
from {{ ref("stg_people__locations") }}
where not is_pathways and location_name <> 'KIPP Whittier Elementary'
