{%- macro incremental_merge(
    code_location, system_name, model_name, unique_key, transform_cols=[]
) -%}

{%- set source_name = code_location ~ "_" ~ system_name -%}
{%- set table_name = "src_" ~ model_name -%}
{%- set from_source = source(source_name, table_name) -%}
{%- set star = dbt_utils.star(from=from_source, except=["dt"]) -%}
{%- set star_except = dbt_utils.star(
    from=from_source, except=transform_cols | map(attribute="name") | list
) -%}
{%- set file_uri = (
    "gs://teamster-"
    ~ code_location
    ~ "/dagster/"
    ~ code_location
    ~ "/"
    ~ system_name
    ~ "/"
    ~ table_name
    ~ "/"
    ~ var("_file_name")
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
            {{ star_except }}
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

select {{ star }}
from updates

union all

select {{ star }}
from inserts

{% endmacro %}
