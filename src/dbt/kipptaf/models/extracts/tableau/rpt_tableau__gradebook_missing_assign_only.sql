with
    missing_assignments as (
        select
            a._dbt_source_relation,
            a.sectionid,
            a.category_name,
            a.assignment_name,
            a.duedate as assign_due_date,

            e.academic_year,
            e.academic_year_display,
            e.region,
            e.school,
            e.studentid,
            e.student_number,
            e.student_name,
            e.grade_level,
            e.advisory,
        from {{ ref("int_powerschool__student_assignment_audit") }} as a
        inner join
            {{ ref("int_tableau__student_enrollments") }} as e
            on a.studentid = e.studentid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
            and e.academic_year = {{ var("current_academic_year") }}
        where
            a.school_level = 'HS'
            and a.assign_expected_to_be_scored
            and (a.ismissing = 1 or not a.assign_scored)
    ),

    course_enrollments as (
        select
            _dbt_source_relation,
            cc_studentid as studentid,
            cc_course_number as course_number,
            cc_sectionid as sectionid,
            sections_external_expression as external_expression,
            courses_course_name as course_name,
            teachernumber as teacher_number,
            teacher_lastfirst,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_course_number_year = 1
            and cc_sectionid > 0
            and courses_excludefromgpa = 0
            and cc_academic_year = {{ var("current_academic_year") }}
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
    m.advisory,
    m.student_number,
    m.student_name,
    m.grade_level,

    string_agg(
        concat(
            ' • ',
            m.assignment_name,
            ' was due on ',
            m.assign_due_date,
            ' in ',
            m.course_name
        ),
        '\n'
    )
    || '\n' as assignment_info,

from missing_assignments as m
inner join
    course_enrollments as c
    on m.studentid = c.studentid
    and m.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="m", right_alias="c") }}
group by all
