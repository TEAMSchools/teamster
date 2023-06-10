{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__pgfinalgrades"),
            source("kippcamden_powerschool", "stg_powerschool__pgfinalgrades"),
            source("kippmiami_powerschool", "stg_powerschool__pgfinalgrades"),
        ]
    )
}}
