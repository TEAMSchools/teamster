{%- snapshot snapshot__stipend_and_bonus__output -%}

    {{
        config(
            target_schema=generate_schema_name("appsheet"),
            strategy="timestamp",
            updated_at="edited_at",
            unique_key="event_id",
        )
    }}

    select *,
    from {{ ref("stg_stipend_and_bonus__output") }}

{%- endsnapshot -%}
