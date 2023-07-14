{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_edplan", "stg_edplan__njsmart_powerschool"),
            source("kippcamden_edplan", "stg_edplan__njsmart_powerschool"),
        ]
    )
}}
