{# {{
    dbt_utils.union_relations(
        relations=[ref("my_model"), source("my_source", "my_table")],
        exclude=["_loaded_at"],
    )
}} #}

