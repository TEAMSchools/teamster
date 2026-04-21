with
    course_enrollments as (
        select
            _dbt_source_relation,
            cc_studentid,
            cc_academic_year,
            cc_schoolid,
            cc_dcid,
            cc_dateenrolled,
            cc_dateleft,
            sections_dcid,
            students_dcid,
            students_student_number,
            region,
        from {{ ref("base_powerschool__course_enrollments") }}
    ),

    student_enrollments as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            yearid,
            student_number,
            entrydate,
            exitdate,
        from {{ ref("base_powerschool__student_enrollments") }}
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
        where `type` = 'quarter'
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "asg.assignmentsectionid",
                "asg._dbt_source_relation",
                "ce.students_dcid",
            ]
        )
    }} as grades_assignment_key,

    {{ dbt_utils.generate_surrogate_key(["ce.cc_dcid", "ce._dbt_source_relation"]) }}
    as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "asg.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

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
    }} as term_key,

    asg.duedate as due_date_key,

    asg.academic_year,

    asg.assignment_name,
    asg.category_name,
    asg.category_code,
    asg.scoretype as score_type,

    asg.score_entered as score,
    asg.totalpointvalue as max_points,
    asg.assign_final_score_percent as score_percent,

    if(asg.is_missing = 1, true, false) as is_missing,
    if(asg.is_late = 1, true, false) as is_late,
    if(asg.is_exempt = 1, true, false) as is_exempt,
    asg.is_expected,
    if(asg.iscountedinfinalgrade = 1, true, false) as is_counted_in_final_grade,
from {{ ref("int_powerschool__gradebook_assignments_scores") }} as asg
inner join
    course_enrollments as ce
    on asg.sectionsdcid = ce.sections_dcid
    and asg.students_dcid = ce.students_dcid
    and asg.duedate >= ce.cc_dateenrolled
    and asg.duedate < ce.cc_dateleft
    and {{ union_dataset_join_clause(left_alias="asg", right_alias="ce") }}
inner join
    student_enrollments as enr
    on ce.cc_studentid = enr.studentid
    and ce.cc_schoolid = enr.schoolid
    and ce.cc_academic_year - 1990 = enr.yearid
    and asg.duedate >= enr.entrydate
    and asg.duedate < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="enr") }}
left join
    reporting_terms as rt
    on asg.duedate between rt.start_date and rt.end_date
    and ce.cc_schoolid = rt.school_id
    and ce.region = rt.region

-- TODO: overlapping CC records at same section cause join fan-out;
-- qualify picks latest cc_dateenrolled and entrydate (#3633)
qualify
    row_number() over (
        partition by asg.assignmentsectionid, asg._dbt_source_relation, ce.students_dcid
        order by ce.cc_dateenrolled desc, enr.entrydate desc
    )
    = 1
