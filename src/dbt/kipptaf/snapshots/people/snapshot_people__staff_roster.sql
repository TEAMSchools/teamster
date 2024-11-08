{%- snapshot snapshot_people__staff_roster -%}

    {{
        config(
            enabled=false,
            target_schema=generate_schema_name("people"),
            unique_key="work_assignment_id",
            strategy="check",
            check_cols="all",
        )
    }}

    select *,
    from {{ ref("base_people__staff_roster") }}

{%- endsnapshot -%}
