with
    alias_clean_names as (
        select distinct clean_name,
        from {{ ref("stg_google_sheets__people__location_crosswalk") }}
        where clean_name is not null
    ),

    master_names as (
        select distinct location_name,
        from {{ ref("stg_google_sheets__people__locations") }}
    )

select 'missing_in_master' as direction, alias.clean_name as `name`,
from alias_clean_names as alias
left join master_names as m on alias.clean_name = m.location_name
where m.location_name is null

union all

select 'missing_in_alias' as direction, m.location_name as `name`,
from master_names as m
left join alias_clean_names as alias on m.location_name = alias.clean_name
where alias.clean_name is null
