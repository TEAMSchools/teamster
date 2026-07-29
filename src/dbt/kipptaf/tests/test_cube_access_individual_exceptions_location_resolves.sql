with
    live as (
        select employee_number, additional_location_type, additional_location_name,
        from {{ ref("stg_google_sheets__people__cube_access_individual_exceptions") }}
        where
            status = 'active'
            and (expiry_date is null or expiry_date >= current_date('America/New_York'))
            and (grant_date is null or grant_date <= current_date('America/New_York'))
            and additional_location_type in ('region', 'school')
    )

select l.employee_number, l.additional_location_type, l.additional_location_name,
from live as l
left join
    {{ ref("dim_regions") }} as reg on l.additional_location_name = reg.legal_entity
left join {{ ref("dim_locations") }} as loc on l.additional_location_name = loc.name
where
    (l.additional_location_type = 'region' and reg.region_key is null)
    or (l.additional_location_type = 'school' and loc.location_key is null)
