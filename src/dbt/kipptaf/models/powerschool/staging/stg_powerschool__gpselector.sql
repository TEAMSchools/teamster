{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gpselector"),
            source("kippcamden_powerschool", "stg_powerschool__gpselector"),
        ]
    )
}}
