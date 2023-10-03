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
            e.advisor_lastfirst,

            adb.contact_id,
            adb.ktc_cohort,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        where
            e.academic_year = {{ var("current_academic_year") }}
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

    act_sat_official as (  -- All types of ACT scores from ADB
        select
            contact,  -- ID from ADB for the student
            'Official' as test_type,
            test_type as scope,
            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,
            date as test_date,
            case
                -- Need to verify all of these are accurately tagged to match NJ's
                -- grad requirements
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                when 'sat_ebrw'
                then 'EWBR'
                when 'act_composite'
                then 'Composite'
                when 'act_reading'
                then 'Reading'
                when 'act_math'
                then 'Math'
                when 'act_english'
                then 'English'
                when 'act_science'
                then 'Science'
            end as subject_area,
            score as scale_score,
            rn_highest,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}  -- ADB scores data
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
    e.advisor_lastfirst,

    e.contact_id,
    e.ktc_cohort,

    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,

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
    scale_score,

    rn_highest

from roster as e
left join act_sat_official as o on e.contact_id = o.contact
-- and o.test_date between e.entrydate and e.exitdate
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
    e.advisor_lastfirst,

    e.contact_id,
    e.ktc_cohort,

    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,

    'Practice' as test_type,
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
        partition by p.powerschool_student_number, p.scope, p.subject_area
        order by p.scale_score desc
    ) as rn_highest
from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
