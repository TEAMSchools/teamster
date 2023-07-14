{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__testscore"),
            source("kippcamden_powerschool", "stg_powerschool__testscore"),
            source("kippmiami_powerschool", "stg_powerschool__testscore"),
        ]
    )
}}
