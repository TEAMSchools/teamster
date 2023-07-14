{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__u_def_ext_students"),
            source("kippcamden_powerschool", "stg_powerschool__u_def_ext_students"),
        ]
    )
}}

{# source("kippmiami_powerschool", "stg_powerschool__u_def_ext_students"), #}

