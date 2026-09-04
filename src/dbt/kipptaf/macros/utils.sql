{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{# Drops code locations whose PowerSchool instance is frozen, for extracts
   built on PowerSchool current-state. `column` is any code-location column --
   `_dbt_source_project` on a union model, or `dagster_code_location` /
   `home_work_location_dagster_code_location` on the staff roster. Add or remove
   a region in the frozen_powerschool_code_locations var. #}
{% macro exclude_frozen(column) -%}
    {%- set locations = var("frozen_powerschool_code_locations") -%}
    {{ column }} not in ('{{ locations | join("', '") }}')
{%- endmacro %}

{# Miami vendor files through SY2025 carry the bare pre-Focus student number; the
   Focus student_number, and so the network student_number, is that number with an
   8400 prefix (#5149). `year` is the row's academic year and `project` the code
   location: extract_source_project() inside a union_relations CTE, or the
   _dbt_source_project column once it exists. #}
{% macro focus_student_number(id, year, project) -%}
    {{ id }} + if({{ project }} = 'kippmiami' and {{ year }} <= 2025, 8400000000, 0)
{%- endmacro %}
