{% macro illuminate_repository_unpivot(model_name) %}
    {% set repository_id = model_name | replace(
        "stg_illuminate__dna_repositories__repository_", ""
    ) %}
    {% set relation = source(
        "illuminate_dna_repositories", "repository_" + repository_id
    ) %}

    {% set cols = adapter.get_columns_in_relation(relation) %}

    with
        dbt_unpivot as (
            {% if cols %}
                {{
                    dbt_utils.unpivot(
                        relation=relation,
                        cast_to="string",
                        exclude=["repository_row_id", "student_id"],
                    )
                }}
            {% else %}
                select
                    cast(null as int) as repository_row_id,
                    cast(null as int) as student_id,
                    cast(null as string) as field_name,
                    cast(null as string) as `value`,
            {% endif %}
        )

    select
        repository_row_id,
        student_id,
        field_name,
        `value`,

        {{ repository_id }} as repository_id,
    from dbt_unpivot
{% endmacro %}
