{% set pivot_query %}
    select distinct
        test_admin_for_roster,
        lower(replace(replace(test_admin_for_roster,'PSAT 8/9','PSAT89'),' ','_')) as test_admin_for_roster_field_name
    from {{ ref("rpt_tableau__college_assessment_dashboard_v3") }}
    where rn_undergrad = 1 and ktc_cohort >= 2025
{% endset %}

{% set results = run_query(pivot_query) %}
{% set tests = [] %}
{% for row in results %}
    {% set label = row[0] %}
    {% set prefix = row[1] %}
    {% do tests.append({"label": label, "prefix": prefix}) %}
{% endfor %}

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
    ),

    max_scale_score_dedup as (
        select
            student_number,
            avg(psat89_ebrw_max_score) as psat89_ebrw_max_score,
            avg(psat89_math_section_max_score) as psat89_math_section_max_score,
            avg(psat10_ebrw_max_score) as psat10_ebrw_max_score,
            avg(psat10_math_section_max_score) as psat10_math_section_max_score,
            avg(psatnmsqt_ebrw_max_score) as psatnmsqt_ebrw_max_score,
            avg(psatnmsqt_math_section_max_score) as psatnmsqt_math_section_max_score,
            avg(sat_ebrw_max_score) as sat_ebrw_max_score,
            avg(sat_math_max_score) as sat_math_max_score,
            avg(act_math_max_score) as act_math_max_score,
            avg(act_reading_max_score) as act_reading_max_score,
            avg(act_english_max_score) as act_english_max_score,
            avg(act_science_max_score) as act_science_max_score,
        from max_scale_score_pivot
        group by student_number
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
            case
                when
                    b.test_admin_for_roster
                    = '{{ test.label | replace("' ", " '' ") }}' then b.scale_score
            end
        ) as {{ test.prefix }}_scale_score,
        avg(
            case
                when b.test_admin_for_roster = '{{ test.label | replace(" '", "''") }}'
                then b.previous_total_score_change
            end
        ) as {{ test.prefix }}_previous_total_score_change
        {% if not loop.last %},{% endif %}
    {% endfor %}

from {{ ref("rpt_tableau__college_assessment_dashboard_v3") }} as b
left join superscore_pivot as s on b.student_number = s.student_number
left join max_scale_score_dedup as m on b.student_number = m.student_number
-- only the "current" graduating class is tracked here
where b.rn_undergrad = 1 and b.ktc_cohort >= 2025
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
