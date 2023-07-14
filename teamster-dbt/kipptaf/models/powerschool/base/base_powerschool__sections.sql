{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "base_powerschool__sections"),
            source("kippcamden_powerschool", "base_powerschool__sections"),
            source("kippmiami_powerschool", "base_powerschool__sections"),
        ]
    )
}}
