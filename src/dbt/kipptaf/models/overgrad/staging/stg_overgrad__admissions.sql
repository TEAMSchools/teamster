{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_overgrad", "stg_overgrad__admissions"),
            source("kippcamden_overgrad", "stg_overgrad__admissions"),
        ]
    )
}}
