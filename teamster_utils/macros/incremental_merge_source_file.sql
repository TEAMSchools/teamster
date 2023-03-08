{%- macro incremental_merge_source_file(
    file_uri, unique_key, transform_cols=[], except_cols=[]
) -%}

{%- set from_source = source(model.package_name, model.name | replace("stg", "src")) -%}
{%- set except_cols = except_cols.append(
    [
        "_dagster_partition_fiscal_year",
        "_dagster_partition_date",
        "_dagster_partition_hour",
        "_dagster_partition_minute",
    ]
) -%}

{%- set star = dbt_utils.star(from=from_source, except=except_cols) -%}
{%- set star_except = dbt_utils.star(
    from=from_source, except=transform_cols | map(attribute="name")
) -%}

{{
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key=unique_key,
    )
}}

with
    using_clause as (
        select
            _file_name,
            /* column transformations */
            {% for col in transform_cols %}
            {%- if col.transformation == "cast" -%}
            cast({{ col.name }} as {{ col.type }}) as {{ col.name }},
            {%- elif col.transformation == "extract" -%}
            {{ col.name }}.{{ col.type }} as {{ col.name }},
            {%- endif %}
            {% endfor %}
            /* remaining columns */
            {{- star_except | indent(width=12) }}
        from {{ from_source }}
        {% if is_incremental() -%} where _file_name in ('{{ file_uri }}') {%- endif %}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="using_clause",
                partition_by=unique_key,
                order_by="_file_name desc",
            )
        }}
    ),

    updates as (
        select *
        from deduplicate
        {% if is_incremental() -%}
        where {{ unique_key }} in (select {{ unique_key }} from {{ this }})
        {%- endif %}
    ),

    inserts as (
        select *
        from deduplicate
        where {{ unique_key }} not in (select {{ unique_key }} from updates)
    )

select  --
    {{ star | indent(width=4) }}
from updates

union all

select  --
    {{ star | indent(width=4) }}
from inserts

{% endmacro %}
