{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation, r'(kipp\w+)_'
    )
{% endmacro %}

{% macro extract_region(table) %}
    initcap(regexp_extract({{ table }}._dbt_source_project, r'kipp(\w+)'))
{% endmacro %}

{% macro is_live_row(status_column, grant_date_column, expiry_date_column) %}
    {{ status_column }} = 'active'
    and (
        {{ expiry_date_column }} is null
        or {{ expiry_date_column }} >= current_date('{{ var("local_timezone") }}')
    )
    and (
        {{ grant_date_column }} is null
        or {{ grant_date_column }} <= current_date('{{ var("local_timezone") }}')
    )
{% endmacro %}
