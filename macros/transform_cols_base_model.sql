{%- macro transform_cols_base_model(source_name, model_name, transform_cols=[]) -%}

{%- set table_name = "src_" ~ model_name -%}
{%- set from_source = source(source_name, table_name) -%}
{%- set star_except = dbt_utils.star(
    from=from_source, except=transform_cols | map(attribute="name")
) -%}

select
    /* column transformations */
    {% for col in transform_cols -%}
    {{ col.name }}.{{ col.type }} as {{ col.name }},
    {% endfor -%}
    /* remaining columns */
    {{ star_except | indent(width=2) }}
from {{ from_source }}

{%- endmacro -%}
