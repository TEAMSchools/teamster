{%- macro transform_cols_base_model(transform_cols=[], except_cols=[]) -%}

{%- set from_source = source(model.package_name, model.name | replace("stg", "src")) -%}
{%- set transform_col_names = transform_cols | map(attribute="name") | list -%}

{%- set except_cols = except_cols + transform_col_names -%}

{%- set star_except = dbt_utils.get_filtered_columns_in_relation(
    from=from_source, except=except_cols
) -%}

select
    /* column transformations */
    {% for col in transform_cols %}
    {%- set col_alias = col.alias or dbt_utils.slugify(col.name) -%}
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
    {%- set col_alias = dbt_utils.slugify(col) -%} {{ col }} as {{ col_alias }},
    {% endfor %}
from {{ from_source }}

{%- endmacro -%}
