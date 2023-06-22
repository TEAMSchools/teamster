{%- macro generate_staging_model(unique_key, transform_cols=[], except_cols=[]) -%}

    {%- set source_model = source(
        model.package_name, model.name | replace("stg", "src")
    ) -%}
    {%- set transform_col_names = transform_cols | map(attribute="name") | list -%}

    {%- set except_cols = except_cols + transform_col_names -%}

    {%- set star_except = dbt_utils.get_filtered_columns_in_relation(
        from=source_model, except=except_cols
    ) -%}

    with
        deduplicate as (
            {{
                dbt_utils.deduplicate(
                    relation=source_model,
                    partition_by=unique_key,
                    order_by="_file_name desc",
                )
            }}
        ),

        staging as (
            select
                /* column transformations */
                {% for col in transform_cols %}
                    {%- set col_alias = col.alias or dbt_utils.slugify(col.name) -%}
                    {%- if col.cast -%}
                        safe_cast(
                    {%- endif -%}
                        {%- if col.nullif -%}nullif({%- endif -%}{{ col.name }}
                        {%- if col.nullif -%}, {{ col.nullif }}) {%- endif -%}
                        {%- if col.extract -%}.{{ col.extract }} {% endif -%}
                    {%- if col.cast %}
                            as {{ col.cast }})
                    {%- endif %} as {{ col_alias }},
                {% endfor %}
                /* remaining columns */
                {% for col in star_except -%}
                    {{ col }} as {{ dbt_utils.slugify(col) }},
                {% endfor %}
            from deduplicate
        )
{%- endmacro -%}
