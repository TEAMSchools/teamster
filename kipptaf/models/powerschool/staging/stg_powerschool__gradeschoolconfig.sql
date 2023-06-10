{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradeschoolconfig"),
            source("kippcamden_powerschool", "stg_powerschool__gradeschoolconfig"),
            source("kippmiami_powerschool", "stg_powerschool__gradeschoolconfig"),
        ]
    )
}}
