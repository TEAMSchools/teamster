{% macro refresh_external_metadata_cache(source_type, table_name) %}
    {% set source = source("powerschool_" + source_type, table_name) %}
    {% set source_clean = source | replace("`", "") %}
    call bq.refresh_external_metadata_cache("{{ source_clean }}")
{% endmacro %}
