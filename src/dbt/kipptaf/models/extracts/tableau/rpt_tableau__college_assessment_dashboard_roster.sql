{% set tests = [
    {
        "label": "s_91 PSAT 8/9 Math Official",
        "prefix": "s_91_psat_89_math_official",
    },
    {
        "label": "s_91 PSAT 8/9 EBRW Official",
        "prefix": "s_91_psat_89_ebrw_official",
    },
    {
        "label": "s_91 PSAT 8/9 Combined Official",
        "prefix": "s_91_psat_89_combined_official",
    },
    {"label": "s_123 SAT Math Official", "prefix": "s_123_sat_math_official"},
    {"label": "s_123 SAT EBRW Official", "prefix": "s_123_sat_ebrw_official"},
    {
        "label": "s_123 SAT Combined Official",
        "prefix": "s_123_sat_combined_official",
    },
    {
        "label": "s_123 ACT Science Official",
        "prefix": "s_123_act_science_official",
    },
    {
        "label": "s_123 ACT Reading Official",
        "prefix": "s_123_act_reading_official",
    },
    {"label": "s_123 ACT Math Official", "prefix": "s_123_act_math_official"},
    {
        "label": "s_123 ACT English Official",
        "prefix": "s_123_act_english_official",
    },
    {
        "label": "s_123 ACT Composite Official",
        "prefix": "s_123_act_composite_official",
    },
    {"label": "s_122 SAT Math Official", "prefix": "s_122_sat_math_official"},
    {"label": "s_122 SAT EBRW Official", "prefix": "s_122_sat_ebrw_official"},
    {
        "label": "s_122 SAT Combined Official",
        "prefix": "s_122_sat_combined_official",
    },
    {
        "label": "s_122 ACT Science Official",
        "prefix": "s_122_act_science_official",
    },
    {
        "label": "s_122 ACT Reading Official",
        "prefix": "s_122_act_reading_official",
    },
    {"label": "s_122 ACT Math Official", "prefix": "s_122_act_math_official"},
    {
        "label": "s_122 ACT English Official",
        "prefix": "s_122_act_english_official",
    },
    {
        "label": "s_122 ACT Composite Official",
        "prefix": "s_122_act_composite_official",
    },
    {"label": "s_121 SAT Math Official", "prefix": "s_121_sat_math_official"},
    {"label": "s_121 SAT EBRW Official", "prefix": "s_121_sat_ebrw_official"},
    {
        "label": "s_121 SAT Combined Official",
        "prefix": "s_121_sat_combined_official",
    },
    {
        "label": "s_121 ACT Science Official",
        "prefix": "s_121_act_science_official",
    },
    {
        "label": "s_121 ACT Reading Official",
        "prefix": "s_121_act_reading_official",
    },
    {"label": "s_121 ACT Math Official", "prefix": "s_121_act_math_official"},
    {
        "label": "s_121 ACT English Official",
        "prefix": "s_121_act_english_official",
    },
    {
        "label": "s_121 ACT Composite Official",
        "prefix": "s_121_act_composite_official",
    },
    {"label": "s_113 SAT Math Official", "prefix": "s_113_sat_math_official"},
    {"label": "s_113 SAT EBRW Official", "prefix": "s_113_sat_ebrw_official"},
    {
        "label": "s_113 SAT Combined Official",
        "prefix": "s_113_sat_combined_official",
    },
    {
        "label": "s_113 ACT Science Official",
        "prefix": "s_113_act_science_official",
    },
    {
        "label": "s_113 ACT Reading Official",
        "prefix": "s_113_act_reading_official",
    },
    {"label": "s_113 ACT Math Official", "prefix": "s_113_act_math_official"},
    {
        "label": "s_113 ACT English Official",
        "prefix": "s_113_act_english_official",
    },
    {
        "label": "s_113 ACT Composite Official",
        "prefix": "s_113_act_composite_official",
    },
    {"label": "s_112 SAT Math Official", "prefix": "s_112_sat_math_official"},
    {"label": "s_112 SAT EBRW Official", "prefix": "s_112_sat_ebrw_official"},
    {
        "label": "s_112 SAT Combined Official",
        "prefix": "s_112_sat_combined_official",
    },
    {
        "label": "s_112 ACT Science Official",
        "prefix": "s_112_act_science_official",
    },
    {
        "label": "s_112 ACT Reading Official",
        "prefix": "s_112_act_reading_official",
    },
    {"label": "s_112 ACT Math Official", "prefix": "s_112_act_math_official"},
    {
        "label": "s_112 ACT English Official",
        "prefix": "s_112_act_english_official",
    },
    {
        "label": "s_112 ACT Composite Official",
        "prefix": "s_112_act_composite_official",
    },
    {
        "label": "s_111 ACT Science Official",
        "prefix": "s_111_act_science_official",
    },
    {
        "label": "s_111 ACT Reading Official",
        "prefix": "s_111_act_reading_official",
    },
    {"label": "s_111 ACT Math Official", "prefix": "s_111_act_math_official"},
    {
        "label": "s_111 ACT English Official",
        "prefix": "s_111_act_english_official",
    },
    {
        "label": "s_111 ACT Composite Official",
        "prefix": "s_111_act_composite_official",
    },
    {
        "label": "s_102 PSAT10 Math Official",
        "prefix": "s_102_psat10_math_official",
    },
    {
        "label": "s_102 PSAT10 EBRW Official",
        "prefix": "s_102_psat10_ebrw_official",
    },
    {
        "label": "s_102 PSAT10 Combined Official",
        "prefix": "s_102_psat10_combined_official",
    },
    {
        "label": "s_101 PSAT NMSQT Math Official",
        "prefix": "s_101_psat_nmsqt_math_official",
    },
    {
        "label": "s_101 PSAT NMSQT EBRW Official",
        "prefix": "s_101_psat_nmsqt_ebrw_official",
    },
    {
        "label": "s_101 PSAT NMSQT Combined Official",
        "prefix": "s_101_psat_nmsqt_combined_official",
    },
] %}


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
    b.student_email,
    b.enroll_status,
    b.ktc_cohort,
    b.iep_status,
    b.cumulative_y1_gpa,
    b.cumulative_y1_gpa_projected,
    b.college_match_gpa,
    b.college_match_gpa_bands,

    s.psat89_combined_superscore,
    s.psat10_combined_superscore,
    s.psatnmsqt_combined_superscore,
    s.sat_combined_superscore,
    s.act_composite_superscore,

    m.psat89_ebrw_max_score,
    m.psat89_math_section_max_score,
    m.psat10_ebrw_max_score,
    m.psat10_math_section_max_score,
    m.psatnmsqt_ebrw_max_score,
    m.psatnmsqt_math_section_max_score,
    m.sat_ebrw_max_score,
    m.sat_math_max_score,
    m.act_math_max_score,
    m.act_reading_max_score,
    m.act_english_max_score,
    m.act_science_max_score,

    {% for test in tests %}
        avg(
            case when b.test_for_roster = '{{ test.label }}' then b.scale_score end
        ) as {{ test.prefix }}_scale_score,
        avg(
            case
                when b.test_for_roster = '{{ test.label }}'
                then b.running_max_scale_score
            end
        ) as {{ test.prefix }}_running_max_scale_score,
        avg(
            case
                when b.test_for_roster = '{{ test.label }}' then b.running_superscore
            end
        ) as {{ test.prefix }}_running_superscore
        {% if not loop.last %},{% endif %}
    {% endfor %}

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
    b.student_email,
    b.enroll_status,
    b.ktc_cohort,
    b.iep_status,
    b.cumulative_y1_gpa,
    b.cumulative_y1_gpa_projected,
    b.college_match_gpa,
    b.college_match_gpa_bands,
    s.psat89_combined_superscore,
    s.psat10_combined_superscore,
    s.psatnmsqt_combined_superscore,
    s.sat_combined_superscore,
    s.act_composite_superscore,
    m.psat89_ebrw_max_score,
    m.psat89_math_section_max_score,
    m.psat10_ebrw_max_score,
    m.psat10_math_section_max_score,
    m.psatnmsqt_ebrw_max_score,
    m.psatnmsqt_math_section_max_score,
    m.sat_ebrw_max_score,
    m.sat_math_max_score,
    m.act_math_max_score,
    m.act_reading_max_score,
    m.act_english_max_score,
    m.act_science_max_score
