{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla_science"),
            source("kippcamden_pearson", "stg_pearson__njsla_science"),
            source("kipppaterson_pearson", "stg_pearson__njsla_science"),
        ]
    )
}}
