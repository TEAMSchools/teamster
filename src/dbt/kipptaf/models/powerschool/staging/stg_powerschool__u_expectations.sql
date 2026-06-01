{{
    dbt_utils.union_relations(
        relations=[
            source("kippcamden_powerschool", "stg_powerschool__u_expectations"),
            source("kippnewark_powerschool", "stg_powerschool__u_expectations"),
        ]
    )
}}
