{% snapshot snapshot__seat_tracker__seats %}

    {{
        config(
            target_schema=generate_schema_name("appsheet"),
            strategy="timestamp",
            updated_at="edited_at",
            unique_key="surrogate_key",
        )
    }}

    select *
    from {{ ref("stg_seat_tracker__seats") }}

{% endsnapshot %}
