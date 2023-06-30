{{-
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key="surrogate_key",
        enables=False,
    )
-}}

{%- set ref_model = ref("base_people__staff_roster") -%}

{%- set surrogate_key_field_list = dbt_utils.get_filtered_columns_in_relation(
    from=ref_model
) -%}

with
    using_clause as (
        select
            *,
            current_datetime('America/New_York') as effective_datetime,
            {{ dbt_utils.generate_surrogate_key(field_list=surrogate_key_field_list) }}
            as surrogate_key,
        from {{ ref_model }}
    ),

    updates as (
        select *
        from using_clause
        {% if is_incremental() %}
            where surrogate_key in (select surrogate_key from {{ this }})
        {% endif %}
    ),

    inserts as (
        select *
        from using_clause
        where surrogate_key not in (select surrogate_key from updates)
    )

{% if is_incremental() %} select * from inserts
{% else %} select * from updates
{% endif %}
