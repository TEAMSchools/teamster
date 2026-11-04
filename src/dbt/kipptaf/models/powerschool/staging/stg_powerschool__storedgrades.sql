with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__storedgrades"),
                    source("kippcamden_powerschool", "stg_powerschool__storedgrades"),
                    source("kippmiami_powerschool", "stg_powerschool__storedgrades"),
                    source(
                        "kipppaterson_powerschool", "stg_powerschool__storedgrades"
                    ),
                ]
            )
        }}
    )

select
    u.*,

    if(l.location_name is null, true, false) as is_transfer_grade,

    {{ extract_source_project("u") }} as _dbt_source_project,

from union_relations as u
left join
    {{ ref("int_people__location_crosswalk") }} as l on u.schoolname = l.location_name
