{% set tests = [
    {
        "label": "EOY ACT Science Official",
        "prefix": "eoy_act_science_official",
    },
    {
        "label": "MOY ACT Reading Official",
        "prefix": "moy_act_reading_official",
    },
    {
        "label": "BOY ACT English Official",
        "prefix": "boy_act_english_official",
    },
    {
        "label": "EOY SAT Math Test Official",
        "prefix": "eoy_sat_math_test_official",
    },
    {"label": "MOY SAT EBRW Official", "prefix": "moy_sat_ebrw_official"},
    {
        "label": "BOY PSAT 8/9 Combined Official",
        "prefix": "boy_psat_89_combined_official",
    },
    {"label": "EOY ACT Math Official", "prefix": "eoy_act_math_official"},
    {"label": "BOY ACT Math Official", "prefix": "boy_act_math_official"},
    {
        "label": "BOY ACT Science Official",
        "prefix": "boy_act_science_official",
    },
    {"label": "BOY SAT EBRW Official", "prefix": "boy_sat_ebrw_official"},
    {"label": "BOY SAT Math Official", "prefix": "boy_sat_math_official"},
    {
        "label": "BOY PSAT NMSQT Combined Official",
        "prefix": "boy_psat_nmsqt_combined_official",
    },
    {
        "label": "MOY SAT Reading Test Official",
        "prefix": "moy_sat_reading_test_official",
    },
    {
        "label": "BOY SAT Combined Official",
        "prefix": "boy_sat_combined_official",
    },
    {
        "label": "MOY PSAT10 Math Official",
        "prefix": "moy_psat10_math_official",
    },
    {
        "label": "BOY PSAT NMSQT EBRW Official",
        "prefix": "boy_psat_nmsqt_ebrw_official",
    },
    {
        "label": "BOY PSAT 8/9 Math Official",
        "prefix": "boy_psat_89_math_official",
    },
    {
        "label": "EOY SAT Combined Official",
        "prefix": "eoy_sat_combined_official",
    },
    {
        "label": "EOY ACT Composite Official",
        "prefix": "eoy_act_composite_official",
    },
    {
        "label": "EOY ACT English Official",
        "prefix": "eoy_act_english_official",
    },
    {
        "label": "MOY ACT Composite Official",
        "prefix": "moy_act_composite_official",
    },
    {
        "label": "MOY ACT English Official",
        "prefix": "moy_act_english_official",
    },
    {"label": "MOY ACT Math Official", "prefix": "moy_act_math_official"},
    {
        "label": "MOY SAT Math Test Official",
        "prefix": "moy_sat_math_test_official",
    },
    {
        "label": "BOY SAT Reading Test Official",
        "prefix": "boy_sat_reading_test_official",
    },
    {
        "label": "EOY ACT Reading Official",
        "prefix": "eoy_act_reading_official",
    },
    {
        "label": "BOY ACT Composite Official",
        "prefix": "boy_act_composite_official",
    },
    {"label": "MOY SAT Math Official", "prefix": "moy_sat_math_official"},
    {
        "label": "MOY PSAT10 Math Test Official",
        "prefix": "moy_psat10_math_test_official",
    },
    {
        "label": "BOY PSAT 8/9 EBRW Official",
        "prefix": "boy_psat_89_ebrw_official",
    },
    {
        "label": "MOY SAT Combined Official",
        "prefix": "moy_sat_combined_official",
    },
    {
        "label": "MOY ACT Science Official",
        "prefix": "moy_act_science_official",
    },
    {"label": "EOY SAT Math Official", "prefix": "eoy_sat_math_official"},
    {
        "label": "BOY PSAT NMSQT Math Official",
        "prefix": "boy_psat_nmsqt_math_official",
    },
    {"label": "EOY SAT EBRW Official", "prefix": "eoy_sat_ebrw_official"},
    {
        "label": "MOY PSAT10 Combined Official",
        "prefix": "moy_psat10_combined_official",
    },
    {
        "label": "MOY PSAT10 Reading Official",
        "prefix": "moy_psat10_reading_official",
    },
    {
        "label": "BOY ACT Reading Official",
        "prefix": "boy_act_reading_official",
    },
    {
        "label": "EOY SAT Reading Test Official",
        "prefix": "eoy_sat_reading_test_official",
    },
    {
        "label": "BOY SAT Math Test Official",
        "prefix": "boy_sat_math_test_official",
    },
    {
        "label": "MOY PSAT10 EBRW Official",
        "prefix": "moy_psat10_ebrw_official",
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
    ktc_cohort,
    iep_status,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,
    superscore as overall_superscore,

    {% for test in tests %}
        avg(
            case when test_for_roster = '{{ test.label }}' then scale_score end
        ) as {{ test.prefix }}_scale_score,
        avg(
            case when test_for_roster = '{{ test.label }}' then max_scale_score end
        ) as {{ test.prefix }}_max_scale_score,
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
where test_month is not null and rn_undergrad = 1
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
    ktc_cohort,
    iep_status,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,
    superscore
