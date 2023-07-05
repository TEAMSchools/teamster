{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_titan", "stg_titan__person_data"),
        ]
    )
}}
