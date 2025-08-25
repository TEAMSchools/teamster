{% macro refresh_external_metadata_cache(relation_names) %}
    {% set sql %}
        {% for relation_name in relation_names %}
            call bq.refresh_external_metadata_cache(
                '{{ relation_name | replace("`", "") }}'
            );
        {% endfor %}
    {% endset %}

    {% do run_query(sql) %}
{% endmacro %}
