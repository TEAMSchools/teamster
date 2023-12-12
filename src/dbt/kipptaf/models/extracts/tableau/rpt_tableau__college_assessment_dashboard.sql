with
    roster as (
        select
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation,
            e.student_number,
            e.lastfirst,
            e.grade_level,
            e.enroll_status,
            e.cohort,
            e.entrydate,
            e.exitdate,

            if(e.spedlep in ('No IEP', null), 0, 1) as sped,
            e.is_504 as c_504_status,
            e.lep_status,
            e.advisor_lastfirst,

            adb.contact_id,
            adb.ktc_cohort,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

            t.test_type as expected_test_type,
            t.scope as expected_scope,
            t.subject_area as expected_subject_area,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        left join
            `teamster-332318.grangel.carat_expected_tests` as t
            on e.academic_year = t.academic_year
            and e.grade_level = t.grade
        where
            e.academic_year = 2023
            and e.rn_year = 1
            and e.school_level = 'HS'
            and e.schoolid <> 999999
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
    ),
