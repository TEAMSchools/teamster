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
        from {{ ref("int_powerschool__student_enrollment_union") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    course_enrollments_joined as (
        select
            cc._dbt_source_relation,
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.is_dropped_section,
            cc.is_dropped_course,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.name as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,
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
    ),

    -- TODO: overlapping enrollment records at same school cause join
    -- fan-out; deduplicate picks latest entrydate (#3633)
    course_enrollments_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="course_enrollments_joined",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="enr_entrydate desc",
            )
        }}
    )

select
    cc_academic_year as academic_year,
    cc_dateenrolled as entry_date,
    cc_dateleft as exit_date,
    is_dropped_section,
    is_dropped_course,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
    as student_section_enrollment_key,

    -- FK source_relation must match dim_course_sections, which is built from
    -- base_powerschool__sections. Rewrite cc's source relation to the parent's.
    -- TODO: replace() is a no-op if a future district uses a different base
    -- model name. Long-term fix: hash region prefix only, consistent across
    -- producer and consumer (#3820). student_section_enrollment_key has been
    -- migrated to _dbt_source_project (this wave); course_section_key and the
    -- remaining surrogate keys still await full #3820.
    {{
        dbt_utils.generate_surrogate_key(
            [
                "sections_dcid",
                (
                    "replace(_dbt_source_relation,"
                    " 'base_powerschool__course_enrollments',"
                    " 'base_powerschool__sections')"
                ),
            ]
        )
    }} as course_section_key,

    if(
        enr_student_number is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "enr_student_number",
                    "enr_source_project",
                    "enr_academic_year",
                    "enr_entrydate",
                ]
            )
        }},
        cast(null as string)
    ) as student_enrollment_key,

    if(
        rt_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt_type",
                    "rt_code",
                    "rt_name",
                    "rt_start_date",
                    "rt_region",
                    "rt_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from course_enrollments_deduped
