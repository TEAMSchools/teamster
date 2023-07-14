{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__u_clg_et_stu"),
            source("kippcamden_powerschool", "stg_powerschool__u_clg_et_stu"),
            source("kippmiami_powerschool", "stg_powerschool__u_clg_et_stu"),
        ]
    )
}}
