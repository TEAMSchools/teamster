{% snapshot snapshot_leadership_development__output %}

    {{
        config(
            target_schema=generate_schema_name("appsheet"),
            strategy="timestamp",
            updated_at="edited_at_timestamp",
            unique_key="assignment_id",
            meta={
                "dagster": {
                    "group": "google_appsheet",
                    "asset_key": [
                        "kipptaf",
                        "google",
                        "appsheet",
                        "snapshot_leadership_development__output",
                    ],
                }
            },
        )
    }}

    select *,
    from {{ ref("stg_leadership_development__output") }}

{% endsnapshot %}
