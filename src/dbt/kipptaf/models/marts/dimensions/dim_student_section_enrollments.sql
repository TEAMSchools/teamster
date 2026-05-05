with
    student_enrollments as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            yearid,
            student_number,
            academic_year,
            entrydate,
            exitdate,
        from {{ ref("base_powerschool__student_enrollments") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["cc.cc_dcid", "cc._dbt_source_relation"]) }}
    as student_section_enrollment_key,

    if(
        enr.student_number is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "enr.student_number",
                    "enr._dbt_source_relation",
                    "enr.academic_year",
                    "enr.entrydate",
                ]
            )
        }},
        cast(null as string)
    ) as student_enrollment_key,

    -- FK source_relation must match dim_course_sections, which is built from
    -- base_powerschool__sections. Rewrite cc's source relation to the parent's.
    -- TODO: replace() is a no-op if a future district uses a different base
    -- model name. Long-term fix: hash region prefix only, consistent across
    -- producer and consumer (#3820).
    {{
        dbt_utils.generate_surrogate_key(
            [
                "cc.sections_dcid",
                (
                    "replace(cc._dbt_source_relation,"
                    " 'base_powerschool__course_enrollments',"
                    " 'base_powerschool__sections')"
                ),
            ]
        )
    }} as course_section_key,

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

    cc.cc_academic_year as academic_year,
    cc.cc_dateenrolled as entry_date,
    cc.cc_dateleft as exit_date,
    cc.is_dropped_section,
    cc.is_dropped_course,

from {{ ref("base_powerschool__course_enrollments") }} as cc
left join
    student_enrollments as enr
    on cc.cc_studentid = enr.studentid
    and cc.sections_schoolid = enr.schoolid
    and cc.cc_yearid = enr.yearid
    and cc.cc_dateenrolled >= enr.entrydate
    and cc.cc_dateenrolled < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="cc", right_alias="enr") }}
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cc.cc_abs_termid = rt.powerschool_term_id
    and cc.sections_schoolid = rt.school_id
    and cc.region = rt.region
    and rt.`type` = 'RT'

-- TODO: overlapping enrollment records at same school cause join
-- fan-out; qualify picks latest entrydate (#3633)
qualify
    row_number() over (
        partition by cc.cc_dcid, cc._dbt_source_relation order by enr.entrydate desc
    )
    = 1
