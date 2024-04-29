with
    dlm as (
        select distinct student_number,
        from {{ ref("int_students__graduation_path_codes") }}
        where code = 'M'
    ),

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
            adb.contact_owner_name,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

            t.test_type as expected_test_type,
            t.scope as expected_scope,
            t.subject_area as expected_subject_area,

            if(e.spedlep in ('No IEP', null), 0, 1) as sped,

            if(d.student_number is null, false, true) as dlm,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        left join
            {{ ref("stg_assessments__college_readiness_expected_tests") }} as t
            on e.academic_year = t.academic_year
            and e.grade_level = t.grade
        left join dlm as d on e.student_number = d.student_number
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.rn_year = 1
            and e.school_level = 'HS'
            and e.schoolid != 999999
    ),

    course_subjects_roster as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
            s.courses_credittype,

            adb.contact_id,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.courses_credittype in ('ENG', 'MATH')
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        where e.rn_year = 1 and e.school_level = 'HS' and e.schoolid != 999999
    ),

    psat10_unpivot as (
        select local_student_id as contact, test_date, score_type, score,
        from
            {{ ref("stg_illuminate__psat") }} unpivot (
                score for score_type in (
                    psat10_ebrw,
                    psat10_math_test_score,
                    psat10_reading_test_score,
                    psat10_total_score
                )
            )
    ),

    college_assessments_official as (
        select
            contact,
            test_type as scope,
            date as test_date,
            score as scale_score,
            rn_highest,

            'Official' as test_type,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            case
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                else test_subject
            end as subject_area,
            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ENG'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
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
                'sat_ebrw'
            )
        union all
        select
            contact,
            'PSAT10' as scope,
            test_date,
            score as scale_score,

            row_number() over (
                partition by contact, score_type order by score desc
            ) as rn_highest,

            'Official' as test_type,

            concat(
                format_date('%b', test_date), ' ', format_date('%g', test_date)
            ) as administration_round,

            case
                score_type
                when 'psat10_total_score'
                then 'Composite'
                when 'psat10_reading_test_score'
                then 'Reading'
                when 'psat10_math_test_score'
                then 'Math'
                when 'psat10_ebrw'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when score_type in ('psat10_ebrw', 'psat10_reading_test_score')
                then 'ENG'
                when score_type = 'psat10_math_test_score'
                then 'MATH'
                else 'NA'
            end as course_discipline,

            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="test_date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from psat10_unpivot
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
    e.contact_owner_name,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.dlm,

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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
from roster as e
left join
    college_assessments_official as o
    on e.contact_id = o.contact
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
    and o.test_type != 'PSAT10'
left join
    course_subjects_roster as c
    on o.contact = c.contact_id
    and o.test_academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.expected_test_type = 'Official'

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
    e.contact_owner_name,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.dlm,

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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
from roster as e
left join
    college_assessments_official as o
    on cast(e.student_number as string) = o.contact
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
    and o.test_type = 'PSAT10'
left join
    course_subjects_roster as c
    on o.contact = c.contact_id
    and o.test_academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.expected_test_type = 'Official'

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
    e.contact_owner_name,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.dlm,

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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
    and e.expected_test_type = p.test_type
    and e.expected_scope = p.scope
    and e.expected_subject_area = p.subject_area
left join
    course_subjects_roster as c
    on p.powerschool_student_number = c.student_number
    and p.academic_year = c.academic_year
    and p.course_discipline = c.courses_credittype
where e.expected_test_type = 'Practice'
