{% macro illuminate_repository_unpivot(model_name) %}
    with
        dbt_unpivot as (
            {{
                dbt_utils.unpivot(
                    relation=source(
                        "illuminate", model_name | replace("stg_illuminate__", "")
                    ),
                    cast_to="string",
                    exclude=[
                        "_fivetran_deleted",
                        "_fivetran_synced",
                        "repository_row_id",
                        "student_id",
                    ],
                )
            }}
        )

    select
        * except (_fivetran_deleted, _fivetran_synced),
        safe_cast(
            regexp_extract('{{ model_name }}', r'repository_(\d+)') as int
        ) as repository_id,
    from dbt_unpivot
    where not _fivetran_deleted
{% endmacro %}
