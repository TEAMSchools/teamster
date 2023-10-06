{% snapshot snapshot_iready__instructional_usage_data %}

    {{
        config(
            target_schema="kipptaf_iready",
            unique_key="surrogate_key",
            strategy="check",
            check_cols=[
                "last_week_lessons_completed",
                "last_week_lessons_passed",
                "last_week_time_on_task_min",
            ],
        )
    }}

    select *
    from {{ ref("stg_iready__instructional_usage_data") }}

{% endsnapshot %}
