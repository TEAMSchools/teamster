{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__assignmentscore"),
            source("kippcamden_powerschool", "stg_powerschool__assignmentscore"),
            source("kippmiami_powerschool", "stg_powerschool__assignmentscore"),
        ]
    )
}}
