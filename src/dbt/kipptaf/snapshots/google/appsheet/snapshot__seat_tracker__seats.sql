{% snapshot snapshot__seat_tracker__seats %}

    {{
        config(
            target_schema="kipptaf_appsheet",
            strategy="timestamp",
            updated_at="edited_at",
            unique_key="concat(academic_year, '_', staffing_model_id)",
        )
    }}

    select *
    from {{ ref("stg_seat_tracker__seats") }}

{% endsnapshot %}
