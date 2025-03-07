{%- snapshot snapshot_people__student_logins -%}

    {{
        config(
            target_schema=generate_schema_name("people"),
            unique_key="student_number",
            strategy="check",
            check_cols="all",
            meta={
                "dagster": {
                    "asset_key": [
                        "kipptaf",
                        "people",
                        "snapshot_people__student_logins",
                    ]
                }
            },
        )
    }}

    select *,
    from {{ ref("stg_people__student_logins") }}

{%- endsnapshot -%}
