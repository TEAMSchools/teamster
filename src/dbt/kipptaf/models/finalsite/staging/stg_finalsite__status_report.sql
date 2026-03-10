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
    * except (first_name, enrollment_type),

    initcap(first_name) as first_name,

    regexp_replace(active_school_year, r'-\d{2}', '-') as active_school_year_display,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

    if(
        application_grade in ('K', 'Kindergarten'),
        0,
        cast(regexp_extract(application_grade, r'\d+') as int)
    ) as grade_level,

    if(enrollment_type is null, 'New', enrollment_type) as enrollment_type,

from union_relations
where
    finalsite_enrollment_id not in (
        select x.finalsite_student_id,
        from {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as x
    )
