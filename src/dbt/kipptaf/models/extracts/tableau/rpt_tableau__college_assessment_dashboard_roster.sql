with
    superscore_pivot as (
        select
            student_number,
            psat89_combined_superscore,
            psat10_combined_superscore,
            psatnmsqt_combined_superscore,
            sat_combined_superscore,
            act_composite_superscore,

        from
            {{ ref("rpt_tableau__college_assessment_dashboard_v3") }} pivot (
                avg(superscore) for scope in (
                    'PSAT 8/9' as psat89_combined_superscore,
                    'PSAT10' as psat10_combined_superscore,
                    'PSAT NMSQT' as psatnmsqt_combined_superscore,
                    'SAT' as sat_combined_superscore,
                    'ACT' as act_composite_superscore
                )
            )
        where subject_area in ('Combined', 'Composite')
    ),

    max_scale_score_pivot as (
        select
            student_number,
            psat89_ebrw_max_score,
            psat89_math_section_max_score,
            psat10_ebrw_max_score,
            psat10_math_section_max_score,
            psatnmsqt_ebrw_max_score,
            psatnmsqt_math_section_max_score,
            sat_ebrw_max_score,
            sat_math_max_score,
            act_math_max_score,
            act_reading_max_score,
            act_english_max_score,
            act_science_max_score,

        from
            {{ ref("rpt_tableau__college_assessment_dashboard_v3") }} pivot (
                avg(max_scale_score) for score_type in (
                    'psat89_ebrw' as psat89_ebrw_max_score,
                    'psat89_math_section' as psat89_math_section_max_score,
                    'psat10_ebrw' as psat10_ebrw_max_score,
                    'psat10_math_section' as psat10_math_section_max_score,
                    'psatnmsqt_ebrw' as psatnmsqt_ebrw_max_score,
                    'psatnmsqt_math_section' as psatnmsqt_math_section_max_score,
                    'sat_ebrw' as sat_ebrw_max_score,
                    'sat_math' as sat_math_max_score,
                    'act_math' as act_math_max_score,
                    'act_reading' as act_reading_max_score,
                    'act_english' as act_english_max_score,
                    'act_science' as act_science_max_score
                )
            )
        where subject_area not in ('Combined', 'Composite')
    )

select
    b.region,
    b.schoolid,
    b.school,
    b.student_number,
    b.salesforce_id,
    b.student_name,
    b.student_first_name,
    b.student_last_name,
    b.grade_level,
    b.student_email,
    b.enroll_status,
    b.ktc_cohort,
    b.year_in_network,
    b.iep_status,
    b.grad_iep_exempt_status_overall,
    b.cumulative_y1_gpa,
    b.cumulative_y1_gpa_projected,
    b.college_match_gpa,
    b.college_match_gpa_bands,

    b.test_admin_for_roster,
    b.scope,
    b.scale_score,
    b.previous_total_score_change,
    b.running_max_scale_score,
    b.running_superscore,

    avg(s.psat89_combined_superscore) as psat89_combined_superscore,
    avg(s.psat10_combined_superscore) as psat10_combined_superscore,
    avg(s.psatnmsqt_combined_superscore) as psatnmsqt_combined_superscore,
    avg(s.sat_combined_superscore) as sat_combined_superscore,
    avg(s.act_composite_superscore) as act_composite_superscore,

    avg(m.psat89_ebrw_max_score) as psat89_ebrw_max_score,
    avg(m.psat89_math_section_max_score) as psat89_math_section_max_score,
    avg(m.psat10_ebrw_max_score) as psat10_ebrw_max_score,
    avg(m.psat10_math_section_max_score) as psat10_math_section_max_score,
    avg(m.psatnmsqt_ebrw_max_score) as psatnmsqt_ebrw_max_score,
    avg(m.psatnmsqt_math_section_max_score) as psatnmsqt_math_section_max_score,
    avg(m.sat_ebrw_max_score) as sat_ebrw_max_score,
    avg(m.sat_math_max_score) as sat_math_max_score,
    avg(m.act_math_max_score) as act_math_max_score,
    avg(m.act_reading_max_score) as act_reading_max_score,
    avg(m.act_english_max_score) as act_english_max_score,
    avg(m.act_science_max_score) as act_science_max_score,

from {{ ref("rpt_tableau__college_assessment_dashboard_v3") }} as b
left join superscore_pivot as s on b.student_number = s.student_number
left join max_scale_score_pivot as m on b.student_number = m.student_number
where b.rn_undergrad = 1
group by
    b.region,
    b.schoolid,
    b.school,
    b.student_number,
    b.salesforce_id,
    b.student_name,
    b.student_first_name,
    b.student_last_name,
    b.grade_level,
    b.student_email,
    b.enroll_status,
    b.ktc_cohort,
    b.year_in_network,
    b.iep_status,
    b.grad_iep_exempt_status_overall,
    b.cumulative_y1_gpa,
    b.cumulative_y1_gpa_projected,
    b.college_match_gpa,
    b.college_match_gpa_bands,
    b.test_admin_for_roster,
    b.scope,
    b.scale_score,
    b.previous_total_score_change,
    b.running_max_scale_score,
    b.running_superscore
