{% snapshot snapshot_iready__instructional_usage_data %}

    {{
        config(
            target_schema=generate_schema_name("iready"),
            unique_key="surrogate_key",
            strategy="check",
            check_cols=[
                "last_week_lessons_completed",
                "last_week_lessons_passed",
                "last_week_time_on_task_min",
            ],
            meta={
                "dagster": {
                    "asset_key": [
                        "kipptaf",
                        "iready",
                        "snapshot_iready__instructional_usage_data",
                    ]
                }
            },
        )
    }}

    select *,
    from {{ ref("stg_iready__instructional_usage_data") }}

{% endsnapshot %}
