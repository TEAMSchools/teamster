{% snapshot snapshot_people__staff_roster %}

    {{
        config(
            target_schema="target_schema",
            unique_key="work_assignment_id",
            strategy="check",
            check_cols="all",
        )
    }}

    select *
    from {{ ref("base_people__staff_roster") }}

{% endsnapshot %}
