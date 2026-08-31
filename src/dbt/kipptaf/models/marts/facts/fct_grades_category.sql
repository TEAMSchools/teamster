with
    reporting_terms as (
        select
            `type`,
            code,
            `name`,
            `start_date`,
            end_date,
            region,
            school_id,
            grade_band,
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "cg.cc_dcid",
                "cg._dbt_source_project",
                "cg.storecode",
                "cg.storecode_type",
            ]
        )
    }} as grades_category_key,

    {{ dbt_utils.generate_surrogate_key(["cg.cc_dcid", "cg._dbt_source_project"]) }}
    as student_section_enrollment_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    cg.academic_year,

    cg.storecode_type as `type`,
    cg.storecode_order as `order`,
    cg.reporting_term,
    cg.quarter,

    cg.percent_grade,
    cg.citizenship_grade,
    cg.percent_grade_y1_running as percent_grade_ytd_running,

    cg.is_current,
from {{ ref("int_students__category_grades") }} as cg
left join
    reporting_terms as rt
    on cg.storecode = rt.name
    and cg.schoolid = rt.school_id
    and cg.region = rt.region
    and cg.yearid = rt.powerschool_year_id
