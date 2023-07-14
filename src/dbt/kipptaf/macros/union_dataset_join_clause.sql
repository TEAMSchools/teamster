{% macro union_dataset_join_clause(left_alias, right_alias) -%}
    split({{ left_alias }}._dbt_source_relation, '.')[1]
    = split({{ right_alias }}._dbt_source_relation, '.')[1]
{%- endmacro %}
