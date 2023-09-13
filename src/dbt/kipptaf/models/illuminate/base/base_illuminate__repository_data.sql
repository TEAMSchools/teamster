{#
{%- set sql_statement %}
    select
        table_catalog,
        table_schema,
        table_name,
        string_agg(column_name) as column_names,
        string_agg(
            format("safe_cast(%s as string) as %s", column_name, column_name)
        ) as column_names_fmt,
    from illuminate_dna_repositories.`INFORMATION_SCHEMA`.`COLUMNS`
    where
        regexp_contains(table_name, r'repository_\d+')
        and column_name
        not in ("repository_row_id", "student_id", "_fivetran_deleted", "_fivetran_synced")
    group by
        table_catalog,
        table_schema,
        table_name
{% endset -%}

{%- set repos = dbt_utils.get_query_results_as_dict(sql_statement) -%}

{{ repos }}
-- select *
-- from
-- (
-- select repository_row_id, student_id, _fivetran_synced, %s,
-- from `%s`.`%s`.`%s`
-- where not _fivetran_deleted
-- )
-- unpivot (name_column for values_column in (%s))
#}