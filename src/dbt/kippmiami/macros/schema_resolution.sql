{% macro resolve_source_schema(base_schema) %}
    {%- if target.name in ["defer", "dev"] -%}
        zz_{{ env_var("GITHUB_USER", "dev") }}_{{ base_schema }}
    {%- elif target.name == "staging" -%} zz_stg_{{ base_schema }}
    {%- else -%} {{ base_schema }}
    {%- endif -%}
{% endmacro %}

{% macro check_prod_guard() %}
    {%- if target.name == "prod" and not env_var(
        "DAGSTER_CLOUD_DEPLOYMENT_NAME", ""
    ) -%}
        {{
            exceptions.raise_compiler_error(
                "target 'prod' is reserved for production deployments. "
                ~ "Use --target defer (default) for development. "
                ~ "Set DAGSTER_CLOUD_DEPLOYMENT_NAME to override."
            )
        }}
    {%- endif -%}
{% endmacro %}
