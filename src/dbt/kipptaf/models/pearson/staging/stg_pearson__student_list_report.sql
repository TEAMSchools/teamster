{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", model.name),
            source("kippcamden_pearson", model.name),
        ]
    )
}}
