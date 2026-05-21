with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__schools"),
                    source("kippcamden_powerschool", "stg_powerschool__schools"),
                    source("kippmiami_powerschool", "stg_powerschool__schools"),
                    source("kipppaterson_powerschool", "stg_powerschool__schools"),
                ]
            )
        }}
    )

select u.*, {{ extract_code_location("u") }} as _dbt_source_project, loc.location_key,
from unioned as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_number = loc.powerschool_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
