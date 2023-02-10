{% macro get_gcs_uri(code_location, system_name, model_name, partition_path) %}

{{
    return(
        "gs://teamster-"
        ~ code_location
        ~ "/dagster/"
        ~ code_location
        ~ "/"
        ~ system_name
        ~ "/"
        ~ model_name
        ~ "/"
        ~ partition_path
    )
}}

{% endmacro %}
