{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{# Miami vendor files through SY2025 carry the bare pre-Focus student number; the
   Focus student_number, and so the network student_number, is that number with an
   8400 prefix (#5149). `year` is the row's academic year and `project` the code
   location: extract_source_project() inside a union_relations CTE, or the
   _dbt_source_project column once it exists. #}
{% macro focus_student_number(id, year, project) -%}
    {{ id }} + if(
        {{ project }} = 'kippmiami' and {{ year }} <= 2025 and {{ id }} < 8400000000,
        8400000000,
        0
    )
{%- endmacro %}
