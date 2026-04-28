with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    )

select
    u.*,

    if(
        loc.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }},
        cast(null as string)
    ) as location_key,
from unioned as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
