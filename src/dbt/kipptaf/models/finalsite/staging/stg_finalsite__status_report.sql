with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippcamden_finalsite", "stg_finalsite__status_report"),
                    source("kippmiami_finalsite", "stg_finalsite__status_report"),
                    source("kippnewark_finalsite", "stg_finalsite__status_report"),
                    source("kipppaterson_finalsite", "stg_finalsite__status_report"),
                ]
            )
        }}
    )

select
    *,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

    {{ extract_source_project() }} as _dbt_source_project,

from union_relations
where
    finalsite_enrollment_id not in (
        select x.finalsite_student_id,
        from {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as x
    )
