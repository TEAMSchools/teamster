{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gradecalculationtype"),
            source("kippcamden_powerschool", "stg_powerschool__gradecalculationtype"),
            source("kippmiami_powerschool", "stg_powerschool__gradecalculationtype"),
        ]
    )
}}
