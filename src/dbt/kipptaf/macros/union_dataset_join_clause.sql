{% macro union_dataset_join_clause(left_alias, right_alias) -%}
    regexp_extract({{ left_alias }}._dbt_source_relation, r'(kipp\w+)_')
    = regexp_extract({{ right_alias }}._dbt_source_relation, r'(kipp\w+)_')
{%- endmacro %}
