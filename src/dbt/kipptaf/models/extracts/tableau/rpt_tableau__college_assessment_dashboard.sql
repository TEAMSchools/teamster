with
    roster as (
        select
            e.student_number,
            adb.contact_id,
            e.lastfirst,
            e.enroll_status,
            e.cohort,
            adb.ktc_cohort,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation,
            e.grade_level,
            e.entrydate,
            e.exitdate,
            e.advisor_lastfirst,
<<<<<<< HEAD
<<<<<<< HEAD
            if(e.spedlep in ('No IEP', null), 0, 1) as sped,
            e.is_504 as c_504_status,

            s.courses_course_name as ccr_course,
            s.teacher_lastfirst as ccr_teacher,
            s.sections_external_expression as ccr_period,

        from {{ ref("base_powerschool__student_enrollments") }} as e
=======
            e.spedlep,
            e.is_504,

=======
            e.spedlep,
            e.is_504,

>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
            c.id as kippadb_contact_id,
            c.kipp_hs_class,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("stg_kippadb__contact") }} as c
            on e.student_number = c.school_specific_id
<<<<<<< HEAD
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and not s.is_dropped_section
<<<<<<< HEAD
<<<<<<< HEAD
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
=======
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
            and s.rn_course_number_year = 1
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
<<<<<<< HEAD
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.rn_year = 1
            and e.school_level = 'HS'
<<<<<<< HEAD
<<<<<<< HEAD
            and e.schoolid <> 999999
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

            -- Sorts the table in desc order to calculate the highest score per
            -- score_type per student
            row_number() over (
                partition by contact, score_type order by score desc
            ) as rn_highest,
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
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    )

select
    e.student_number,
    e.lastfirst,
    e.enroll_status,
    e.cohort,
    e.kipp_hs_class as ktc_cohort,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation,
    e.grade_level,
    e.advisor_lastfirst,
<<<<<<< HEAD
<<<<<<< HEAD
    e.ccr_course,
    e.ccr_teacher,
    e.ccr_period,
    e.c_504_status,
    e.sped,

    e.ktc_cohort,

    o.test_type,
=======
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    e.courses_course_name as ccr_course,
    e.teacher_lastfirst as ccr_teacher,
    e.sections_external_expression as ccr_period,
    e.is_504 as c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    'Official' test_type,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    null as assessment_id,
    null as assessment_title,
    concat(
        format_date('%b', o.date), ' ', format_date('%g', o.date)
    ) as administration_round,
    o.test_type as scope,

    null as scope_round,

    e.grade_level as assessment_grade_level,

    o.date as test_date,
    case
        {# TODO: verify these are accurately tagged to match NJ grad reqs #}
        score_type
        when 'sat_total_score'
        then 'Composite'
        when 'sat_reading_test_score'
        then 'Reading Test'
        when 'sat_math_test_score'
        then 'Math Test'
        else test_subject
    end as subject_area,

    null as total_subjects_tested_per_scope_round,
    null as overall_performance_band_for_group,
    null as reporting_group_label,
    null as points_earned_for_group_subject,
    null as points_possible_for_group_subject,
    null as earned_raw_score_for_scope_round_per_subject,
    null as possible_raw_score_for_scope_round_per_subject,

    o.score as earned_scale_score_for_scope_round_per_subject,
    o.rn_highest,

<<<<<<< HEAD
<<<<<<< HEAD
    avg(case when o.subject_area = 'Composite' then o.scale_score end) over (
        partition by o.contact, o.test_type, o.administration_round, o.test_date
    ) as overall_composite_score,
from roster as e
left join
    act_sat_official as o
    on e.contact_id = o.contact
    and o.test_date between e.entrydate and e.exitdate
=======
    avg(if(o.score_type in ('act_composite', 'sat_total_score'), o.score, null)) over (
        partition by e.student_number, o.test_type, o.date
    ) as overall_composite_score,
from roster as e
left join
=======
    avg(if(o.score_type in ('act_composite', 'sat_total_score'), o.score, null)) over (
        partition by e.student_number, o.test_type, o.date
    ) as overall_composite_score,
from roster as e
left join
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    {{ ref("int_kippadb__standardized_test_unpivot") }} as o
    on e.kippadb_contact_id = o.contact
    and o.date between e.entrydate and e.exitdate
    and o.score_type in (
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
<<<<<<< HEAD
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790

union all

select
    e.student_number,
    e.lastfirst,
    e.enroll_status,
    e.cohort,
    e.kipp_hs_class as ktc_cohort,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school_abbreviation,
    e.grade_level,
    e.advisor_lastfirst,
<<<<<<< HEAD
<<<<<<< HEAD
    e.ccr_course,
    e.ccr_teacher,
    e.ccr_period,
    e.c_504_status,
    e.sped,

    e.ktc_cohort,

   'Practice' as test_type,

=======
=======
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    e.courses_course_name as ccr_course,
    e.teacher_lastfirst as ccr_teacher,
    e.sections_external_expression as ccr_period,
    e.is_504 as c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    p.test_type,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    p.assessment_id,
    p.assessment_title,
    p.administration_round,
    p.scope,
    p.scope_round,
    p.assessment_grade_level,
    p.test_date,
    p.subject_area,
    p.total_subjects_tested_per_scope_round,
    p.overall_performance_band_for_group,
    p.reporting_group_label,
    p.points_earned_for_group_subject,
    p.points_possible_for_group_subject,
    p.earned_raw_score_for_scope_round_per_subject,
    p.possible_raw_score_for_scope_round_per_subject,
    p.earned_scale_score_for_scope_round_per_subject,

    row_number() over (
        partition by e.student_number, p.scope, p.subject_area
        order by p.earned_scale_score_for_scope_round_per_subject desc
    ) as rn_highest,

    null as overall_composite_score
from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
<<<<<<< HEAD
<<<<<<< HEAD
    on e.student_number = p.student_id
=======
    on e.student_number = p.pwe
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
=======
    on e.student_number = p.pwe
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
    and e.academic_year = p.academic_year
