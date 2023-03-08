{% macro get_gcs_uri(partition_path) %}

{{
    return(
        "gs://teamster-"
        ~ project_name
        ~ "/dagster/"
        ~ project_name
        ~ "/"
        ~ model.package_name
        ~ "/"
        ~ model.name
        | replace("stg_" ~ model.package_name ~ "__", "") ~ "/" ~ partition_path,
    )
}}

{% endmacro %}
