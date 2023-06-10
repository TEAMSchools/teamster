{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__storedgrades"),
            source("kippcamden_powerschool", "stg_powerschool__storedgrades"),
            source("kippmiami_powerschool", "stg_powerschool__storedgrades"),
        ]
    )
}}
