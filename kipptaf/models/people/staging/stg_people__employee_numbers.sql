{{-
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key="adp_associate_id",
        merge_update_columns=["adp_associate_id"],
    )
-}}

with
    using_clause as (select id from {{ source("adp_workforce_now", "worker") }}),

    updates as (
        select id
        from using_clause
        {% if is_incremental() -%}
            where
                id in (
                    select coalesce(adp_associate_id, adp_associate_id_legacy)
                    from {{ this }}
                )
        {%- endif %}
    ),

    inserts as (select id from using_clause where id not in (select id from updates))

{% if is_incremental() %}
    select
        (
            men.max_employee_number + row_number() over (order by ins.id)
        ) as employee_number,
        ins.id as adp_associate_id,
        cast(null as string) as adp_associate_id_legacy,
        true as is_active
    from inserts ins
    cross join
        (select max(employee_number) as max_employee_number from {{ this }}) as men
{% else %}
    select employee_number, adp_associate_id, adp_associate_id_legacy, is_active
    from {{ source("people", "src_people__employee_numbers") }}
{% endif %}
