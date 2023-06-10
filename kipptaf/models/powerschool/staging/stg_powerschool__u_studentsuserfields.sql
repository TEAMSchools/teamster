{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__u_studentsuserfields"),
            source("kippcamden_powerschool", "stg_powerschool__u_studentsuserfields"),
        ]
    )
}}

{# source("kippmiami_powerschool", "stg_powerschool__u_studentsuserfields"), #}

