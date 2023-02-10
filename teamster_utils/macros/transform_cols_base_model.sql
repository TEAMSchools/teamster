{%- macro transform_cols_base_model(transform_cols=[]) -%}

{%- set from_source = source(project_name, model.name | replace("stg", "src")) -%}
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
