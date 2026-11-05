{#- Use dbt_overrides' test materialization; see src/dbt/dbt_overrides/CLAUDE.md. -#}
{% materialization test, adapter = "bigquery" -%}
    {{ return(dbt_overrides.materialization_test_bigquery()) }}
{%- endmaterialization %}
