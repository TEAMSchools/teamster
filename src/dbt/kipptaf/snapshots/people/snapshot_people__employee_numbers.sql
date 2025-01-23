{%- snapshot snapshot_people__employee_numbers -%}

    {{
        config(
            target_schema=generate_schema_name("people"),
            unique_key="surrogate_key",
            strategy="check",
            check_cols="all",
            meta={
                "dagster": {
                    "asset_key": [
                        "kipptaf",
                        "people",
                        "snapshot_people__employee_numbers",
                    ]
                }
            },
        )
    }}

    select
        *,

        {{
            dbt_utils.generate_surrogate_key(
                [
                    "employee_number",
                    "adp_associate_id",
                    "adp_associate_id_legacy",
                    "is_active",
                ]
            )
        }} as surrogate_key,
    from {{ ref("stg_people__employee_numbers") }}

{%- endsnapshot -%}
