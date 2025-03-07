{% snapshot snapshot_seat_tracker__seats %}

    {{
        config(
            target_schema=generate_schema_name("appsheet"),
            strategy="timestamp",
            updated_at="edited_at",
            unique_key="surrogate_key",
            meta={
                "dagster": {
                    "group": "google_appsheet",
                    "asset_key": [
                        "kipptaf",
                        "google",
                        "appsheet",
                        "snapshot_seat_tracker__seats",
                    ],
                }
            },
        )
    }}

    select *,
    from {{ ref("stg_seat_tracker__seats") }}

{% endsnapshot %}
