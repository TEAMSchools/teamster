with
    missing_assignments as (
        select
            a._dbt_source_relation,
            a.quarter,
            a.semester,
            a.week_number_quarter,
            a.week_start_monday,
            a.week_end_sunday,
            a.assignment_category_code,
            a.category_name,
            a.assignment_category_term,
            a.assignmentid as assignment_id,
            a.assignment_name,
            a.ismissing as missing,
            a.scoretype as score_type,
            a.scorepoints as raw_score,
            a.score_converted,
            a.totalpointvalue as max_score,
            a.assign_final_score_percent,

            e.academic_year,
            e.region,
            e.school,
            e.studentid,
            e.student_number,
            e.student_name,
            e.grade_level,
        from {{ ref("int_powerschool__student_assignment_audit") }} as a
        inner join
            {{ ref("int_tableau__student_enrollments") }} as e
            on a.studentid = e.studentid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
            and e.academic_year = 2024
        where
            a.school_level != 'ES'
            and a.assign_expected_to_be_scored
            and (a.ismissing = 1 or not a.assign_scored)
    ),

    course_enrollments as (
        select
            _dbt_source_relation,
            cc_studentid as studentid,
            cc_course_number as course_number,
            cc_sectionid as sectionid,
            cc_dateenrolled as date_enrolled,
            sections_dcid,
            sections_section_number as section_number,
            sections_external_expression as external_expression,
            courses_credittype as credit_type,
            courses_course_name as course_name,
            teachernumber as teacher_number,
            teacher_lastfirst,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_course_number_year = 1
            and cc_academic_year = 2024
            and cc_sectionid > 0
            and courses_excludefromgpa = 1
            and cc_course_number not in (
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG20',
                'LOG22999XL',
                'LOG300',
                'LOG9',
                'SEM22106G1',
                'SEM22106S1',
                'SEM72005G1',
                'SEM72005G2',
                'SEM72005G3',
                'SEM72005G4',
                'SEM22101G1'
            )
    )

select
    m.academic_year,
    m.region,
    m.school,
    m.student_number,
    m.student_name,
    m.grade_level,

    c.course_number,
    c.sectionid,
    c.date_enrolled,
    c.sections_dcid,
    c.section_number,
    c.external_expression,
    c.credit_type,
    c.course_name,
    c.teacher_number,
    c.teacher_lastfirst,

    m.quarter,
    m.semester,
    m.week_number_quarter,
    m.week_start_monday,
    m.week_end_sunday,
    m.assignment_category_code,
    m.category_name,
    m.assignment_category_term,
    m.assignment_id,
    m.assignment_name,
    m.is_missing,
    m.score_type,
    m.raw_score,
    m.score_converted,
    m.max_score,
    m.assign_final_score_percent,

from missing_assignments as m
inner join
    course_enrollments as c
    on m.studentid = c.studentid
    and {{ union_dataset_join_clause(left_alias="m", right_alias="c") }}
