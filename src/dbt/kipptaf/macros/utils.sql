{%- macro extract_code_location(table) -%}
    regexp_extract({{ table }}._dbt_source_relation, r'(kipp\w+)_')
{%- endmacro -%}

{%- macro union_dataset_join_clause(left_alias, right_alias) -%}
    {{ extract_code_location(left_alias) }} = {{ extract_code_location(right_alias) }}
{%- endmacro -%}
