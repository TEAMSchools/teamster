-- TODO: add kipppaterson source once the file is available on their SFTP
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_amplify",
                        "stg_amplify__mclass__sftp__pm_student_summary_aimline",
                    ),
                ]
            )
        }}
    ),

    transformations as (
        -- trunk-ignore(sqlfluff/AM04): union_relations produces dynamic columns
        select
            * except (sync_date, surrogate_key) replace (
                coalesce(device_date, sync_date) as device_date
            ),
        from union_relations
    )

select
    *,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_primary_id",
                "school_year",
                "pm_period",
                "measure",
                "probe_number",
                "device_date",
            ]
        )
    }} as surrogate_key,

from transformations
