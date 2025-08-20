{% macro refresh_external_metadata_cache(source) %}
    {% set source_clean = source | replace("`", "") %}
    call bq.refresh_external_metadata_cache("{{ source_clean }}")
{% endmacro %}
