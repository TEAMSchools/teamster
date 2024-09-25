{%- snapshot snapshot_people__employee_numbers -%}
    {{
        config(
            target_schema="kipptaf_people",
            unique_key="surrogate_key",
            strategy="check",
            check_cols="all",
        )
    }}

    select
        *,

        {{ dbt_utils.generate_surrogate_key(["adp_associate_id", "is_active"]) }}
        as surrogate_key,
    from {{ ref("stg_people__employee_numbers") }}
{%- endsnapshot -%}
