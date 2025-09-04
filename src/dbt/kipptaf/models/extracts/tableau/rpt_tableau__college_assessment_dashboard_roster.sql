{% set tests = [
    {
        "label": "s_112 ACT Composite Official",
        "prefix": "s_112_act_composite_official",
    },
    {"label": "s_112 ACT Math Official", "prefix": "s_112_act_math_official"},
    {"label": "s_112 SAT EBRW Official", "prefix": "s_112_sat_ebrw_official"},
    {
        "label": "s_121 SAT Combined Official",
        "prefix": "s_121_sat_combined_official",
    },
    {"label": "s_123 SAT EBRW Official", "prefix": "s_123_sat_ebrw_official"},
    {
        "label": "s_123 SAT Reading Test Official",
        "prefix": "s_123_sat_reading_test_official",
    },
    {
        "label": "s_122 ACT English Official",
        "prefix": "s_122_act_english_official",
    },
    {
        "label": "s_112 SAT Combined Official",
        "prefix": "s_112_sat_combined_official",
    },
    {
        "label": "s_113 SAT Reading Test Official",
        "prefix": "s_113_sat_reading_test_official",
    },
    {"label": "s_112 SAT Math Official", "prefix": "s_112_sat_math_official"},
    {"label": "s_123 SAT Math Official", "prefix": "s_123_sat_math_official"},
    {
        "label": "s_121 SAT Reading Test Official",
        "prefix": "s_121_sat_reading_test_official",
    },
    {
        "label": "s_101 PSAT NMSQT Math Official",
        "prefix": "s_101_psat_nmsqt_math_official",
    },
    {
        "label": "s_113 SAT Combined Official",
        "prefix": "s_113_sat_combined_official",
    },
    {
        "label": "s_122 SAT Reading Test Official",
        "prefix": "s_122_sat_reading_test_official",
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
        "label": "s_113 ACT English Official",
        "prefix": "s_113_act_english_official",
    },
    {
        "label": "s_122 SAT Combined Official",
        "prefix": "s_122_sat_combined_official",
    },
    {
        "label": "s_123 ACT English Official",
        "prefix": "s_123_act_english_official",
    },
    {
        "label": "s_121 ACT English Official",
        "prefix": "s_121_act_english_official",
    },
    {"label": "s_122 SAT EBRW Official", "prefix": "s_122_sat_ebrw_official"},
    {"label": "s_122 SAT Math Official", "prefix": "s_122_sat_math_official"},
    {
        "label": "s_101 PSAT NMSQT EBRW Official",
        "prefix": "s_101_psat_nmsqt_ebrw_official",
    },
    {
        "label": "s_123 ACT Composite Official",
        "prefix": "s_123_act_composite_official",
    },
    {"label": "s_121 ACT Math Official", "prefix": "s_121_act_math_official"},
    {
        "label": "s_111 ACT Composite Official",
        "prefix": "s_111_act_composite_official",
    },
    {"label": "s_111 ACT Math Official", "prefix": "s_111_act_math_official"},
    {
        "label": "s_101 PSAT NMSQT Combined Official",
        "prefix": "s_101_psat_nmsqt_combined_official",
    },
    {
        "label": "s_121 ACT Composite Official",
        "prefix": "s_121_act_composite_official",
    },
    {"label": "s_123 ACT Math Official", "prefix": "s_123_act_math_official"},
    {"label": "s_113 SAT Math Official", "prefix": "s_113_sat_math_official"},
    {
        "label": "s_91 PSAT 8/9 Combined Official",
        "prefix": "s_91_psat_89_combined_official",
    },
    {
        "label": "s_91 PSAT 8/9 Math Official",
        "prefix": "s_91_psat_89_math_official",
    },
    {
        "label": "s_112 ACT English Official",
        "prefix": "s_112_act_english_official",
    },
    {
        "label": "s_123 SAT Combined Official",
        "prefix": "s_123_sat_combined_official",
    },
    {"label": "s_113 SAT EBRW Official", "prefix": "s_113_sat_ebrw_official"},
    {
        "label": "s_113 ACT Composite Official",
        "prefix": "s_113_act_composite_official",
    },
    {"label": "s_113 ACT Math Official", "prefix": "s_113_act_math_official"},
    {
        "label": "s_122 ACT Composite Official",
        "prefix": "s_122_act_composite_official",
    },
    {"label": "s_122 ACT Math Official", "prefix": "s_122_act_math_official"},
    {
        "label": "s_112 SAT Reading Test Official",
        "prefix": "s_112_sat_reading_test_official",
    },
    {
        "label": "s_111 ACT English Official",
        "prefix": "s_111_act_english_official",
    },
    {"label": "s_121 SAT EBRW Official", "prefix": "s_121_sat_ebrw_official"},
    {"label": "s_121 SAT Math Official", "prefix": "s_121_sat_math_official"},
    {
        "label": "s_102 PSAT10 Combined Official",
        "prefix": "s_102_psat10_combined_official",
    },
    {
        "label": "s_91 PSAT 8/9 EBRW Official",
        "prefix": "s_91_psat_89_ebrw_official",
    },
] %}


select
    region,
    schoolid,
    school,
    student_number,
    salesforce_id,
    student_name,
    student_first_name,
    student_last_name,
    student_email,
    enroll_status,
    ktc_cohort,
    iep_status,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,

    {% for test in tests %}
        avg(
            case when test_for_roster = '{{ test.label }}' then scale_score end
        ) as {{ test.prefix }}_scale_score,
        avg(
            case when test_for_roster = '{{ test.label }}' then max_scale_score end
        ) as {{ test.prefix }}_max_scale_score,
        avg(
            case when test_for_roster = '{{ test.label }}' then superscore end
        ) as {{ test.prefix }}_overall_superscore,
        avg(
            case
                when test_for_roster = '{{ test.label }}' then running_max_scale_score
            end
        ) as {{ test.prefix }}_running_max_scale_score,
        avg(
            case when test_for_roster = '{{ test.label }}' then running_superscore end
        ) as {{ test.prefix }}_running_superscore
        {% if not loop.last %},{% endif %}
    {% endfor %}

from {{ ref("rpt_tableau__college_assessment_dashboard_v3") }}
where rn_undergrad = 1
group by
    region,
    schoolid,
    school,
    student_number,
    salesforce_id,
    student_name,
    student_first_name,
    student_last_name,
    student_email,
    enroll_status,
    ktc_cohort,
    iep_status,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected
