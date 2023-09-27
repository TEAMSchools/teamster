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
            e.is_504 as c_504_status,

            s.courses_course_name as ccr_course,
            s.teacher_lastfirst as ccr_teacher,
            s.sections_external_expression as ccr_period,
        from student_enrollments as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.courses_course_name like 'College and Career%'
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.rn_year = 1
            and e.school_level = 'HS'
    ),

    act_sat_official as (  -- All types of ACT scores from ADB
        select
            contact,  -- ID from ADB for the student
            test_type,
            date,
            score,
            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,
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
                else test_subject
            end as subject_area,

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
    e.advisor_lastfirst,
    e.ccr_course,
    e.ccr_teacher,
    e.ccr_period,
    e.c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    s.ktc_cohort,

    'Official' test_type,
    null as assessment_id,
    null as assessment_title,

    o.administration_round,
    o.scope,

    'NA' as scope_round,

    e.grade_level as assessment_grade_level,

    o.test_date,
    o.subject_area,

    null as total_subjects_tested_per_scope_round,
    null as overall_performance_band_for_group,
    'NA' as reporting_group_label,
    null as points_earned_for_group_subject,
    null as points_possible_for_group_subject,
    null as earned_raw_score_for_scope_round_per_subject,
    null as possible_raw_score_for_scope_round_per_subject,

    o.scale_score as earned_scale_score_for_scope_round_per_subject,
    o.rn_highest,

    avg(case when o.subject_area = 'Composite' then o.scale_score end) over (
        partition by o.student_number, o.test_type, o.administration_round, o.test_date
    ) as overall_composite_score,
from roster as e
left join {{ ref("int_kippadb__roster") }} as s on e.student_number = s.student_number
left join
    act_sat_official as o
    on s.student_number = o.student_number
    and o.test_date between e.entrydate and e.exitdate

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
    e.advisor_lastfirst,
    e.ccr_course,
    e.ccr_teacher,
    e.ccr_period,
    e.c_504_status,
    if(e.spedlep in ('No IEP', null), 0, 1) as sped,

    s.ktc_cohort,

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
    {{ ref('int_assessments__college_assessment_practice') }} as p
    on e.student_number = p.local_student_id
    and e.academic_year = p.academic_year
-- left join ms_grad as m on e.student_number = m.student_number
left join {{ ref("int_kippadb__roster") }} as s on e.student_number = s.student_number
