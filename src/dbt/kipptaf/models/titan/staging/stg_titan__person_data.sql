{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_titan", "stg_titan__person_data"),
            source("kippcamden_titan", "stg_titan__person_data"),
        ]
    )
}}
