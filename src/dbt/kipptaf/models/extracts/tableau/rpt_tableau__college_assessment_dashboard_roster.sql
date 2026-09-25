with
    /* One row per student holding all three SAT highlights, replacing three
       separate left joins to the same model that differed only by subject area.
       rn_highest = 1 already yields one row per student per subject area, so the
       aggregate picks rather than collapses. */
    sat_highlights as (
        select
            student_number,

            max(
                if(aligned_subject_area = 'Total', superscore, null)
            ) as sat_total_superscore,
            max(
                if(aligned_subject_area = 'EBRW', max_scale_score, null)
            ) as sat_ebrw_highest,
            max(
                if(aligned_subject_area = 'Math', max_scale_score, null)
            ) as sat_math_highest,

        from {{ ref("int_assessments__college_assessment") }}
        where
            scope = 'SAT'
            and rn_highest = 1
            and aligned_subject_area in ('Total', 'EBRW', 'Math')
        group by student_number
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

    sh.sat_total_superscore,
    sh.sat_ebrw_highest,
    sh.sat_math_highest,

    concat(
        ea.expected_field_name, ' ', ea.expected_score_category
    ) as expected_field_name_score_category,

    coalesce(p.psat89_count_lifetime, 0) as psat89_count_lifetime,
    coalesce(p.psat10_count_lifetime, 0) as psat10_count_lifetime,
    coalesce(p.psatnmsqt_count_lifetime, 0) as psatnmsqt_count_lifetime,
    coalesce(p.sat_count_lifetime, 0) as sat_count_lifetime,
    coalesce(p.act_count_lifetime, 0) as act_count_lifetime,

    coalesce(sch.ccr_course, 'No Data') as ccr_course,
    coalesce(sch.ccr_teacher_name, 'No Data') as ccr_teacher_name,
    coalesce(sch.ccr_section, 'No Data') as ccr_section,
    coalesce(sch.ccr_course_source, 'No Data') as ccr_course_source,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as ea
    on e.region = ea.expected_region
    and ea.rn = 1
left join
    {{ ref("int_tableau__college_assessment_roster_scores") }} as a
    on e.student_number = a.student_number
    and ea.expected_unique_test_admin_id = a.unique_test_admin_id
    and ea.expected_score_category = a.score_category
left join sat_highlights as sh on e.student_number = sh.student_number
left join
    {{ ref("int_students__ccr_schedule") }} as sch
    on e.student_number = sch.student_number
    and e.academic_year = sch.academic_year
left join
    {{ ref("int_students__college_assessment_participation_roster") }} as p
    on e.student_number = p.student_number
    and p.test_type = 'Official'
    and p.rn_lifetime = 1
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
    and not e.is_out_of_district
