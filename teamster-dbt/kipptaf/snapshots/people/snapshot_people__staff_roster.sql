{% snapshot snapshot_people__staff_roster %}

    {{
        config(
            target_schema="kipptaf_people",
            unique_key="work_assignment_id",
            strategy="check",
            check_cols="all",
        )
    }}

    select *
    from {{ ref("base_people__staff_roster") }}

{% endsnapshot %}
