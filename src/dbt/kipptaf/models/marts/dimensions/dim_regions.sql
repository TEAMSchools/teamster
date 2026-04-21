with
    /* All regions use America/New_York (Eastern) as reporting convention — */
    /* Miami observes ET in practice and FL permanent-EST has not taken effect */
    regions as (
        select
            'Newark' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'TEAM Academy Charter School' as legal_entity,
        union all
        select
            'Camden' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'KIPP Cooper Norcross Academy' as legal_entity,
        union all
        select
            'Miami' as region,
            'FL' as state,
            'America/New_York' as timezone,
            'KIPP Miami' as legal_entity,
        union all
        select
            'Paterson' as region,
            'NJ' as state,
            'America/New_York' as timezone,
            'KIPP Paterson' as legal_entity,
    )

select
    {{ dbt_utils.generate_surrogate_key(["region"]) }} as region_key,

    region as region_name,
    state,
    timezone,
    legal_entity,
from regions
