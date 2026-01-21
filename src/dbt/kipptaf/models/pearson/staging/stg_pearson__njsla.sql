{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla"),
            source("kippcamden_pearson", "stg_pearson__njsla"),
            source("kipppaterson_pearson", "stg_pearson__njsla"),
        ]
    )
}}
