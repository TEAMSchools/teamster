{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", model.name),
            source("kippcamden_powerschool", model.name),
        ]
    )
}}


{# source("kippmiami_powerschool", "stg_powerschool__studentrace"), #}

