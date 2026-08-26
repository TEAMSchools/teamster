{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{# Current-state exclusion for regions whose SIS is frozen. `column` is any
   code-location column -- `_dbt_source_project` on a union model, or
   `dagster_code_location` / `home_work_location_dagster_code_location` on the
   staff roster. Add or remove a region in the frozen_code_locations var. #}
{% macro exclude_frozen(column) -%}
    {{ column }} not in ('{{ var("frozen_code_locations") | join("', '") }}')
{%- endmacro %}
