{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_overgrad", "int_overgrad__students"),
            source("kippcamden_overgrad", "int_overgrad__students"),
        ]
    )
}}
