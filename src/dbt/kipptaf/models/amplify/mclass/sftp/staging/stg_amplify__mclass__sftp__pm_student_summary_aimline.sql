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
    ),

    enriched as (
        -- trunk-ignore(sqlfluff/AM04): transformations produces dynamic columns
        select
            t.* except (_dbt_source_relation),

            lc.region,
            lc.abbreviation as school,
            lc.powerschool_school_id as schoolid,

            regexp_replace(
                t._dbt_source_relation, r'kipp[a-z]+_', lc.dagster_code_location || '_'
            ) as _dbt_source_relation,

        from transformations as t
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on t.school_name = lc.name
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
                "assessment_grade",
            ]
        )
    }} as surrogate_key,

from enriched
