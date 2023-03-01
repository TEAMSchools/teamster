{%- macro incremental_merge_source_file(file_uri, unique_key, transform_cols=[]) -%}

{%- set from_source = source(model.package_name, model.name | replace("stg", "src")) -%}
{%- set star = dbt_utils.star(
    from=from_source, 
    except=["_partition_fiscal_year", "_partition_date", "_partition_hour"]
) -%}
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
            {% for col in transform_cols -%}
            {{ col.name }}.{{ col.type }} as {{ col.name }},
            {% endfor -%}
            /* remaining columns */
            {{ star_except | indent(width=10) }}
        from {{ from_source }}
        {% if is_incremental() -%} where _file_name = '{{ file_uri }}' {%- endif %}
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
    {{ star | indent(width=2) }}
from updates

union all

select  --
    {{ star | indent(width=2) }}
from inserts

{% endmacro %}
