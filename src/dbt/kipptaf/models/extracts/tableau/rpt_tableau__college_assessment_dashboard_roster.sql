with
    scores as (
        select
            student_number,
            unique_test_admin_id,
            scale_score as score,

            'Scale Score' as score_category,

        from {{ ref("int_tableau__college_assessment_roster_scores") }}

        union all

        select
            student_number,
            unique_test_admin_id,
            total_growth_score_change as score,

            'Score Change' as score_category,

        from {{ ref("int_tableau__college_assessment_roster_scores") }}
    )

select
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.iep_status,
    e.grad_iep_exempt_status_overall,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    ea.expected_test_type,
    ea.expected_scope,
    ea.expected_score_type,
    ea.expected_grouping,
    ea.expected_grade_level,
    ea.expected_admin_season,
    ea.expected_months_included,
    ea.expected_field_name,
    ea.expected_score_category,
    ea.expected_admin_season_order,

    a.score,

    ss.superscore as sat_total_superscore,

    he.max_scale_score as sat_ebrw_highest,

    hm.max_scale_score as sat_math_highest,

    concat(
        ea.expected_field_name, ' ', ea.expected_score_category
    ) as expected_field_name_score_category,

    coalesce(p.psat89_count_lifetime, 0) as psat89_count_lifetime,
    coalesce(p.psat10_count_lifetime, 0) as psat10_count_lifetime,
    coalesce(p.psatnmsqt_count_lifetime, 0) as psatnmsqt_count_lifetime,
    coalesce(p.sat_count_lifetime, 0) as sat_count_lifetime,
    coalesce(p.act_count_lifetime, 0) as act_count_lifetime,

    coalesce(c.courses_course_name, 'No Data') as ccr_course,
    coalesce(c.teacher_lastfirst, 'No Data') as ccr_teacher_name,
    coalesce(c.sections_external_expression, 'No Data') as ccr_section,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("stg_google_sheets__kippfwd_expected_assessments") }} as ea
    on e.region = ea.expected_region
    and ea.rn = 1
left join
    scores as a
    on e.student_number = a.student_number
    and ea.expected_unique_test_admin_id = a.unique_test_admin_id
    and ea.expected_score_category = a.score_category
left join
    {{ ref("int_assessments__college_assessment") }} as ss
    on e.student_number = ss.student_number
    and ss.scope = 'SAT'
    and ss.aligned_subject_area = 'Total'
    and ss.rn_highest = 1
left join
    {{ ref("int_assessments__college_assessment") }} as he
    on e.student_number = he.student_number
    and he.scope = 'SAT'
    and he.aligned_subject_area = 'EBRW'
    and he.rn_highest = 1
left join
    {{ ref("int_assessments__college_assessment") }} as hm
    on e.student_number = hm.student_number
    and hm.scope = 'SAT'
    and hm.aligned_subject_area = 'Math'
    and hm.rn_highest = 1
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on e.student_number = c.students_student_number
    and e.academic_year = c.cc_academic_year
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.courses_course_name in (
        'College and Career IV',
        'College and Career I',
        'College and Career III',
        'College and Career II'
    )
left join
    {{ ref("int_students__college_assessment_participation_roster") }} as p
    on e.student_number = p.student_number
    and p.rn_lifetime = 1
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
