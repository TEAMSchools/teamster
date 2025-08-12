{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_edplan", "int_edplan__njsmart_powerschool_union"),
            source("kippcamden_edplan", "int_edplan__njsmart_powerschool_union"),
        ]
    )
}}
