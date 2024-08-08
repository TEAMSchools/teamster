-- depends_on: {{ ref('stg_adp_workforce_now__workers') }}
{{-
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key="adp_associate_id",
        merge_update_columns=["adp_associate_id"],
    )
-}}

{%- if execute -%}
    {%- if flags.FULL_REFRESH -%}
        {{
            exceptions.raise_compiler_error(
                (
                    "Full refresh is not allowed for this model. "
                    "Exclude it from the run via the argument '--exclude model_name'."
                )
            )
        }}
    {%- endif -%}
{%- endif -%}

{% if is_incremental() %}
    with
        workers as (
            select worker_id__id_value,
            from {{ ref("stg_adp_workforce_now__workers") }}
            where is_current_record
        ),

        updates as (
            select worker_id__id_value,
            from workers
            where worker_id__id_value in (select adp_associate_id, from {{ this }})
        ),

        inserts as (
            select
                worker_id__id_value,

                row_number() over (order by worker_id__id_value) as rn,
            from workers
            where worker_id__id_value not in (select worker_id__id_value, from updates)
        ),

        men as (select max(employee_number) as max_employee_number, from {{ this }})

    -- trunk-ignore(sqlfluff/ST06)
    select
        men.max_employee_number + ins.rn as employee_number,

        ins.worker_id__id_value as adp_associate_id,

        cast(null as string) as adp_associate_id_legacy,

        true as is_active,
    from inserts as ins
    cross join men
{% else %}
    select employee_number, adp_associate_id, adp_associate_id_legacy, is_active
    from {{ source("people", "src_people__employee_numbers_archive") }}
{% endif %}
