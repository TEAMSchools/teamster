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

            if(e.spedlep in ('No IEP', null), 0, 1) as sped,

        from
            `teamster-332318`.`kipptaf_powerschool`.`base_powerschool__student_enrollments`
            as e
        left join
            `teamster-332318`.`kipptaf_powerschool`.`base_powerschool__course_enrollments`
            as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and regexp_extract(e._dbt_source_relation, r'(kipp\w+)_')
            = regexp_extract(s._dbt_source_relation, r'(kipp\w+)_')
        left join
            `teamster-332318`.`kipptaf_kippadb`.`int_kippadb__roster` as adb
            on e.student_number = adb.student_number
        left join
            `teamster-332318`.`kipptaf_assessments`.`stg_assessments__college_readiness_expected_tests`
            as t
            on e.academic_year = t.academic_year
            and e.grade_level = t.grade
        where
            e.academic_year = 2023
            and e.rn_year = 1
            and e.school_level = 'HS'
            and e.schoolid != 999999
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
    ),

    college_assessments_official as (
        select
            contact,
            'Official' as test_type,
            test_type as scope,
            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,
            date as test_date,
            case
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                when 'ap'
                then 'AP'
                else test_subject
            end as subject_area,
            score as scale_score,
            rn_highest,
        from
            `teamster-332318`.`kipptaf_kippadb`.`int_kippadb__standardized_test_unpivot`
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'act_english',
                'act_science',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw',
                'ap'
            )
    )

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
    e.sped,
    e.c_504_status,
    e.lep_status,
    e.advisor_lastfirst,
    e.contact_id,
    e.ktc_cohort,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,

    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
    o.subject_area,
    o.test_date,

    'NA' as response_type,
    'NA' as response_type_description,

    null as points,
    null as percent_correct,
    null as total_subjects_tested,
    null as raw_score,

    o.scale_score,
    o.rn_highest,
from roster as e
left join
    college_assessments_official as o
    on e.contact_id = o.contact
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
where e.expected_test_type = 'Official' and o.subject_area != 'AP'
union all
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
    e.sped,
    e.c_504_status,
    e.lep_status,
    e.advisor_lastfirst,
    e.contact_id,
    e.ktc_cohort,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,

    p.test_type,
    p.scope,
    p.scope_round,
    p.assessment_id,
    p.assessment_title,
    p.administration_round,
    p.subject_area,
    p.test_date,
    p.response_type,
    p.response_type_description,
    p.points,
    p.percent_correct,
    p.total_subjects_tested,
    p.raw_score,
    p.scale_score,
    row_number() over (
        partition by e.student_number, p.scope, p.subject_area
        order by p.scale_score desc
    ) as rn_highest,
from roster as e
left join
    `teamster-332318`.`kipptaf_assessments`.`int_assessments__college_assessment_practice`
    as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
    and e.expected_test_type = p.test_type
    and e.expected_scope = p.scope
    and e.expected_subject_area = p.subject_area
where e.expected_test_type = 'Practice'
union all
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
    e.sped,
    e.c_504_status,
    e.lep_status,
    e.advisor_lastfirst,
    e.contact_id,
    e.ktc_cohort,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    'Official' as expected_test_type,
    'AP' as expected_scope,
    case
        e.courses_course_name
        when 'AP English Language and Composition'
        then 'English Language and Composition'
        when 'AP World History: Modern'
        then 'World History: Modern'
        when 'AP US History'
        then 'US History'
        when 'AP Psychology'
        then 'Psychology'
        when 'AP African American Studies'
        then 'African American Studies'
        when 'AP Calculus AB'
        then 'Calculus AB'
        when 'AP Chemistry'
        then 'Chemistry'
        when 'AP Computer Science Principles'
        then 'Computer Science Principles'
        when 'AP Physics'
        then ''
        when 'AP Pre-calculus'
        then ''
        when 'AP Seminar'
        then 'Seminar'
        when 'AP Statistics'
        then 'Statistics'
        when 'AP Computer Science A'
        then 'Computer Science A'
        else 'AP Expected Test Undefined'
    end as expected_subject_area,

    a.test_type,
    a.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    a.administration_round,
    a.subject_area,
    a.test_date,

    'NA' as response_type,
    'NA' as response_type_description,

    null as points,
    null as percent_correct,
    null as total_subjects_tested,
    null as raw_score,

    a.scale_score,
    a.rn_highest,
from roster as e
left join
    college_assessments_official as a
    on e.contact_id = a.contact
    and e.expected_test_type = a.test_type
    and e.expected_scope = a.scope
    and e.expected_subject_area = a.subject_area
where a.subject_area = 'AP' and e.courses_course_name like '%AP %'
