{%- macro incremental_merge_source_file(
    file_uri, unique_key, transform_cols=[], except_cols=[]
) -%}

{%- set from_source = source(model.package_name, model.name | replace("stg", "src")) -%}
{%- set transform_col_names = transform_cols | map(attribute="name") | list -%}

{%- set except_cols = except_cols + transform_col_names -%}

{%- set star = [] -%}
{%- set star_except = dbt_utils.get_filtered_columns_in_relation(
    from=from_source, except=except_cols
) -%}

{{-
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key=unique_key,
    )
-}}

with
    using_clause as (
        select
            _file_name,

            /* column transformations */
            {% for col in transform_cols %}
            {%- set col_alias = col.alias or dbt_utils.slugify(col.name) -%}
            {%- do star.append(col_alias) -%}
            {%- if col.cast -%}
            cast(
            {%- endif -%}
                {%- if col.nullif -%}nullif({%- endif -%}{{ col.name }}
                {%- if col.nullif -%}, {{ col.nullif }}) {%- endif -%}
                {%- if col.extract -%}.{{ col.extract }} {% endif -%}
            {%- if col.cast %} as {{ col.cast }}) {%- endif %} as {{ col_alias }},
            {% endfor %}
            /* remaining columns */
            {% for col in star_except %}
            {%- set col_alias = dbt_utils.slugify(col) -%}
            {%- do star.append(col_alias) -%}
            {{ col }} as {{ col_alias }},
            {% endfor %}
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

select {% for col in star -%} {{ col }}, {% endfor %}
from updates

union all

select {% for col in star -%} {{ col }}, {% endfor %}
from inserts

{%- endmacro -%}
