{%- snapshot snapshot_people__staff_roster -%}

    {{
        config(
            enabled=false,
            target_schema=generate_schema_name("people"),
            unique_key="item_id",
            strategy="check",
            check_cols="all",
            meta={
                "dagster": {
                    "asset_key": [
                        "kipptaf",
                        "people",
                        "snapshot_people__staff_roster",
                    ]
                }
            },
        )
    }}

    select *,
    from {{ ref("int_people__staff_roster") }}

{%- endsnapshot -%}
