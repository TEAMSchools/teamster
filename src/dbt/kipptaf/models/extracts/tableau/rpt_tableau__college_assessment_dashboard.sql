with
    roster as (
        select
            e.student_number,
            e.lastfirst,
            e.enroll_status,
            e.cohort,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation,
            e.grade_level,
            e.entrydate,
            e.exitdate,
            e.advisor_lastfirst,
            e.spedlep,
            e.is_504,

            c.id as kippadb_contact_id,
            c.kipp_hs_class,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("stg_kippadb__contact") }} as c
            on e.student_number = c.school_specific_id
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and not s.is_dropped_section
            and s.rn_course_number_year = 1
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.rn_year = 1
            and e.school_level = 'HS'
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
    e.courses_course_name as ccr_course,
    e.teacher_lastfirst as ccr_teacher,
    e.sections_external_expression as ccr_period,
    e.is_504 as c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    'Official' test_type,
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

    avg(if(o.score_type in ('act_composite', 'sat_total_score'), o.score, null)) over (
        partition by e.student_number, o.test_type, o.date
    ) as overall_composite_score,
from roster as e
left join
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
    e.courses_course_name as ccr_course,
    e.teacher_lastfirst as ccr_teacher,
    e.sections_external_expression as ccr_period,
    e.is_504 as c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    p.test_type,
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
    on e.student_number = p.pwe
    and e.academic_year = p.academic_year
