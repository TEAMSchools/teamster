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

select u.*, loc.location_key,
from unioned as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
