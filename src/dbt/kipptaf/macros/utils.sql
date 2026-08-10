{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{# Focus stores the network student number prefixed with 8400, Miami-Dade's
FLDOE district number. Strip it to get the canonical network student number,
and pass any other value through unchanged rather than guessing at a different
prefix, so the one known anomalous id stays visible instead of being silently
mangled. The string round-trip is unavoidable: the id is INT64 on both sides. #}
{% macro unprefix_focus_student_id(column) %}
    cast(regexp_replace(cast({{ column }} as string), r'^8400', '') as int64)
{% endmacro %}
