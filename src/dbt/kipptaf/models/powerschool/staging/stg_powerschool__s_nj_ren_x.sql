{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__s_nj_ren_x"),
            source("kippcamden_powerschool", "stg_powerschool__s_nj_ren_x"),
        ]
    )
}}

{# source("kippmiami_powerschool", "stg_powerschool__s_nj_ren_x"), #}

