{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_titan", "stg_titan__income_form_data"),
        ]
    )
}}
