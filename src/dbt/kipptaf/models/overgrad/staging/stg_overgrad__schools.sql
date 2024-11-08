{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_overgrad", model.name),
            source("kippcamden_overgrad", model.name),
        ]
    )
}}
