with
    course_enrollments as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            cc_studentid,
            cc_abs_sectionid,
            cc_dcid,
            cc_yearid,
            cc_academic_year,
            cc_schoolid,
            students_student_number,
            region,
        from {{ ref("base_powerschool__course_enrollments") }}
    ),

    reporting_terms as (
        select
            `type`,
            code,
            `name`,
            `start_date`,
            end_date,
            region,
            school_id,
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ce.cc_dcid",
                "ce._dbt_source_relation",
                "cg.storecode",
                "cg.storecode_type",
            ]
        )
    }} as grades_category_key,

    {{ dbt_utils.generate_surrogate_key(["ce.cc_dcid", "ce._dbt_source_project"]) }}
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
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    ce.cc_academic_year as academic_year,

    cg.storecode_type as `type`,
    cg.storecode_order as `order`,
    cg.reporting_term,
    cg.quarter,

    cg.percent_grade,
    cg.citizenship_grade,
    cg.percent_grade_y1_running as percent_grade_ytd_running,

    cg.is_current,
from {{ ref("int_powerschool__category_grades") }} as cg
inner join
    course_enrollments as ce
    on cg.studentid = ce.cc_studentid
    and cg.sectionid = ce.cc_abs_sectionid
    and cg.yearid = ce.cc_yearid
    and {{ union_dataset_join_clause(left_alias="cg", right_alias="ce") }}
left join
    reporting_terms as rt
    on cg.storecode = rt.name
    and cg.schoolid = rt.school_id
    and ce.region = rt.region
    and cg.yearid = rt.powerschool_year_id
