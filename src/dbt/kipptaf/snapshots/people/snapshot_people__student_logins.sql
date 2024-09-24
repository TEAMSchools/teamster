{%- snapshot snapshot_people__student_logins -%}
    {{
        config(
            target_schema="kipptaf_people",
            unique_key="student_number",
            strategy="check",
            check_cols="all",
        )
    }}

    select *,
    from {{ ref("stg_people__student_logins") }}
{%- endsnapshot -%}
