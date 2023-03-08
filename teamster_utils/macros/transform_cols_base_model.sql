{%- macro transform_cols_base_model(transform_cols=[]) -%}

{%- set from_source = source(model.package_name, model.name | replace("stg", "src")) -%}
{%- set star_except = dbt_utils.star(
    from=from_source, except=transform_cols | map(attribute="name")
) -%}

select
    /* column transformations */
    {% for col in transform_cols %}
    {%- if col.transformation == "cast" -%}
    cast({{ col.name }} as {{ col.type }}) as {{ col.name }},
    {%- elif col.transformation == "extract" -%}
    {{ col.name }}.{{ col.type }} as {{ col.name }},
    {%- endif %}
    {% endfor %}
    /* remaining columns */
    {{ star_except | indent(width=4) }}
from {{ from_source }}

{%- endmacro -%}
