{% macro illuminate_repository_unpivot(model_name) %}
    with
        dbt_unpivot as (
            {{
                dbt_utils.unpivot(
                    relation=source(
                        "illuminate_dna_repositories",
                        model_name
                        | replace("stg_illuminate__dna_repositories__", ""),
                    ),
                    cast_to="string",
                    exclude=["repository_row_id", "student_id"],
                )
            }}
        )

    select
        *,

        safe_cast(
            regexp_extract('{{ model_name }}', r'repository_(\d+)') as int
        ) as repository_id,
    from dbt_unpivot
{% endmacro %}
