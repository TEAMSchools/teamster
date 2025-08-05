{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__u_storedgrades_de"),
            source("kippcamden_powerschool", "stg_powerschool__u_storedgrades_de"),
        ]
    )
}}
