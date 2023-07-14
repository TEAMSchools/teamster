{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__assignmentsection"),
            source("kippcamden_powerschool", "stg_powerschool__assignmentsection"),
            source("kippmiami_powerschool", "stg_powerschool__assignmentsection"),
        ]
    )
}}
