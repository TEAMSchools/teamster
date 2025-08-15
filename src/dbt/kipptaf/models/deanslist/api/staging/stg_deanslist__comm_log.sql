{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "stg_deanslist__comm_log"),
            source("kippcamden_deanslist", "stg_deanslist__comm_log"),
            source("kippmiami_deanslist", "stg_deanslist__comm_log"),
        ]
    )
}}
