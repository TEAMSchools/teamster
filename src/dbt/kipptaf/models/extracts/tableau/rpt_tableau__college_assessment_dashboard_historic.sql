with
    base_courses as (
        -- this CTE and the following one were added to help figure out which base
        -- course to pick for a student, since not all of them have CCR, and not all
        -- have HR, so i wrote this to try to catch everyone possible
        select
            _dbt_source_relation,
            cc_academic_year,
            students_student_number as student_number,
            courses_course_name,
            if(courses_course_name = 'HR', 2, 1) as course_rank,
            min(if(courses_course_name = 'HR', 2, 1)) over (
                partition by cc_academic_year, students_student_number
            ) as expected_course_rank,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_name in (
                'HR',
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
            and rn_course_number_year = 1
            and not is_dropped_section
    ),

    expected_course as (
        select distinct
            _dbt_source_relation,
            cc_academic_year,
            student_number,
            courses_course_name as courses_course_name_expected,
        from base_courses
        where course_rank = expected_course_rank
    ),

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
                'College and Career II',
                'HR'
            )
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        left join dlm as d on e.student_number = d.student_number
        left join
            expected_course as ec
            on s.cc_academic_year = ec.cc_academic_year
            and s.students_student_number = ec.student_number
            and s.courses_course_name = ec.courses_course_name_expected
            and {{ union_dataset_join_clause(left_alias="s", right_alias="ec") }}
        where
            e.rn_year = 1
            and e.school_level = 'HS'
            and e.schoolid != 999999
            and ec.courses_course_name_expected is not null
    ),

    psat10_unpivot as (
        select local_student_id as contact, test_date, score_type, score,
        from
            {{ ref("stg_illuminate__psat") }} unpivot (
                score for score_type in (
                    eb_read_write_section_score,
                    math_test_score,
                    reading_test_score,
                    total_score
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
                when 'total_score'
                then 'Composite'
                when 'reading_test_score'
                then 'Reading'
                when 'math_test_score'
                then 'Math'
                when 'eb_read_write_section_score'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when score_type in ('eb_read_write_section_score', 'reading_test_score')
                then 'ENG'
                when score_type = 'math_test_score'
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

from roster as e
left join
    college_assessments_official as o
    on e.contact_id = o.contact
    and o.test_type != 'PSAT10'
where o.test_type = 'Official'

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

from roster as e
left join
    college_assessments_official as o
    on cast(e.student_number as string) = o.contact
    and o.test_type = 'PSAT10'
where o.test_type = 'Official'

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

from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
where p.test_type = 'Practice'
