{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "int_deanslist__comm_log"),
            source("kippcamden_deanslist", "int_deanslist__comm_log"),
            source("kippmiami_deanslist", "int_deanslist__comm_log"),
        ]
    )
}}
