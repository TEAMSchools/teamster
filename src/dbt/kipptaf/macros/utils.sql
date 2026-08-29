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

{# Drops a code location from its DeansList cutover year onward. Unlike
   exclude_frozen this is year-scoped: the location's history before the cutover
   stays readable. Apply it in an OUTER select, after any window function --
   filtering inside the same query block changes window partitions and silently
   alters columns for the years you meant to keep. Add or remove a location in
   the deanslist_stopped_code_locations var. #}
{% macro exclude_deanslist_stopped(project_column, year_column) -%}
    {%- set stopped = var("deanslist_stopped_code_locations", {}) -%}
    {%- if not stopped -%} true
    {%- else -%}
        not (
            {%- for location, first_year in stopped.items() %}
                {%- if not loop.first %}or {% endif %}
                (
                    {{ project_column }} = '{{ location }}'
                    and {{ year_column }} >= {{ first_year }}
                )
            {%- endfor %}
        )
    {%- endif -%}
{%- endmacro %}
