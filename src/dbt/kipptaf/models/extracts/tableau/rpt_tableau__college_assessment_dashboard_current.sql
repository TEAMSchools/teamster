{% set metrics = [
    "sat_combined_pct_890_plus_g11",
    "sat_combined_pct_1010_plus_g11",
    "sat_combined_pct_890_plus_g12",
    "sat_combined_pct_1010_plus_g12",
    "sat_ebrw_pct_450_plus_g11",
    "sat_ebrw_pct_450_plus_g12",
    "sat_math_pct_440_plus_g11",
    "sat_math_pct_440_plus_g12",
] %}

with
    board_goals as (
        select
            grade_level,
            expected_scope,
            expected_score_type,

            {% for m in metrics %}
                max(
                    if(expected_metric_label = '{{ m }}', pct_goal, null)
                ) as {{ m }}_board_pct_goal
                {% if not loop.last %},{% endif %}
            {% endfor %},

            {% for m in metrics %}
                max(
                    if(expected_metric_label = '{{ m }}', min_score, null)
                ) as {{ m }}_board_min_score
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where expected_goal_type = 'Board' and expected_scope = 'SAT'
        group by grade_level, expected_scope, expected_score_type
    ),

    strategy as (
        -- need distinct strategy for expected tests
        select distinct
            s.test_type as expected_test_type,
            s.scope as expected_scope,
            s.subject_area as expected_subject_area,
            s.score_type as expected_score_type,
            s.aligned_subject_area as expected_aligned_subject_area,

            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.expected_metric_label,
            g.min_score as expected_metric_min_score,
            g.pct_goal as expected_metric_pct_goal,

            b.sat_combined_pct_890_plus_g11_board_min_score
            as expected_sat_combined_pct_890_plus_g11_board_min_score,
            b.sat_combined_pct_890_plus_g11_board_pct_goal
            as expected_sat_combined_pct_890_plus_g11_board_pct_goal,
            b.sat_combined_pct_890_plus_g12_board_min_score
            as expected_sat_combined_pct_890_plus_g12_board_min_score,
            b.sat_combined_pct_890_plus_g12_board_pct_goal
            as expected_sat_combined_pct_890_plus_g12_board_pct_goal,

            b.sat_combined_pct_1010_plus_g11_board_min_score
            as expected_sat_combined_pct_1010_plus_g11_board_min_score,
            b.sat_combined_pct_1010_plus_g11_board_pct_goal
            as expected_sat_combined_pct_1010_plus_g11_board_pct_goal,
            b.sat_combined_pct_1010_plus_g12_board_min_score
            as expected_sat_combined_pct_1010_plus_g12_board_min_score,
            b.sat_combined_pct_1010_plus_g12_board_pct_goal
            as expected_sat_combined_pct_1010_plus_g12_board_pct_goal,

            b.sat_ebrw_pct_450_plus_g11_board_min_score
            as expected_sat_ebrw_pct_450_plus_g11_board_min_score,
            b.sat_ebrw_pct_450_plus_g11_board_pct_goal
            as expected_sat_ebrw_pct_450_plus_g11_board_pct_goal,
            b.sat_ebrw_pct_450_plus_g12_board_min_score
            as expected_sat_ebrw_pct_450_plus_g12_board_min_score,
            b.sat_ebrw_pct_450_plus_g12_board_pct_goal
            as expected_sat_ebrw_pct_450_plus_g12_board_pct_goal,

            b.sat_math_pct_440_plus_g11_board_min_score
            as expected_sat_math_pct_440_plus_g11_board_min_score,
            b.sat_math_pct_440_plus_g11_board_pct_goal
            as expected_sat_math_pct_440_plus_g11_board_pct_goal,
            b.sat_math_pct_440_plus_g12_board_min_score
            as expected_sat_math_pct_440_plus_g12_board_min_score,
            b.sat_math_pct_440_plus_g12_board_pct_goal
            as expected_sat_math_pct_440_plus_g12_board_pct_goal,

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on s.score_type = g.expected_score_type
            and g.expected_goal_type != 'Board'
        left join board_goals as b on s.score_type = b.expected_score_type
        where s.scope != 'ACT'
    ),

    attempts as (
        select
            student_number,

            attempt_count_lifetime,

            case
                scope
                when 'sat_count_lifetime'
                then 'SAT'
                when 'psatnmsqt_count_lifetime'
                then 'PSAT NMSQT'
                when 'psat10_count_lifetime'
                then 'PSAT10'
                when 'psat89_count_lifetime'
                then 'PSAT 8/9'
            end as scope,

        from
            {{ ref("int_students__college_assessment_participation_roster") }} unpivot (
                attempt_count_lifetime for scope in (
                    psat89_count_lifetime,
                    psat10_count_lifetime,
                    psatnmsqt_count_lifetime,
                    sat_count_lifetime
                )
            )
        where rn_lifetime = 1
    ),

    roster as (
        select
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.grade_level,
            e.enroll_status,
            e.iep_status,
            e.is_504,
            e.grad_iep_exempt_status_overall,
            e.lep_status,
            e.ktc_cohort,
            e.salesforce_contact_graduation_year as graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_aligned_subject_area,
            r.expected_score_type,
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,

            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,

            min(
                case
                    concat(r.expected_aligned_subject_area, e.grade_level)
                    when 'Total11'
                    then r.expected_sat_combined_pct_890_plus_g11_board_min_score
                    when 'Total12'
                    then r.expected_sat_combined_pct_890_plus_g12_board_min_score
                end
            ) as expected_board_890_plus_min_score,

            min(
                case
                    concat(r.expected_aligned_subject_area, e.grade_level)
                    when 'Total11'
                    then r.expected_sat_combined_pct_1010_plus_g11_board_min_score
                    when 'Total12'
                    then r.expected_sat_combined_pct_1010_plus_g12_board_min_score
                end
            ) as expected_board_1010_plus_min_score,

            min(
                case
                    concat(r.expected_aligned_subject_area, e.grade_level)
                    when 'Total11'
                    then r.expected_sat_combined_pct_890_plus_g11_board_pct_goal
                    when 'Total12'
                    then r.expected_sat_combined_pct_890_plus_g12_board_pct_goal
                end
            ) as expected_board_890_plus_pct_goal,

            min(
                case
                    concat(r.expected_aligned_subject_area, e.grade_level)
                    when 'EBRW11'
                    then r.expected_sat_ebrw_pct_450_plus_g11_board_min_score
                    when 'EBRW12'
                    then r.expected_sat_ebrw_pct_450_plus_g12_board_min_score
                end
            ) as expected_board_450_plus_min_score,

            min(
                case
                    concat(r.expected_aligned_subject_area, e.grade_level)
                    when 'Math11'
                    then r.expected_sat_math_pct_440_plus_g11_board_min_score
                    when 'Math12'
                    then r.expected_sat_math_pct_440_plus_g12_board_min_score
                end
            ) as expected_board_440_plus_min_score,

            avg(
                if(
                    r.expected_goal_type = 'Benchmark',
                    s.max_scale_score,
                    p.attempt_count_lifetime
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join strategy as r
        left join
            {{ ref("int_assessments__college_assessment") }} as s
            on e.student_number = s.student_number
            and r.expected_score_type = s.score_type
        left join
            attempts as p
            on e.student_number = p.student_number
            and r.expected_scope = p.scope
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
        group by
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.grade_level,
            e.enroll_status,
            e.iep_status,
            e.is_504,
            e.grad_iep_exempt_status_overall,
            e.lep_status,
            e.ktc_cohort,
            e.salesforce_contact_graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,
            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_aligned_subject_area,
            r.expected_score_type,
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,
            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type
    )

select
    *,

    if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,

    if(
        (expected_goal_subtype = '1 Attempt' and score = expected_metric_min_score)
        or (
            expected_goal_subtype != '1 Attempt' and score >= expected_metric_min_score
        ),
        1,
        0
    ) as alt_met_min_score_int,

    if(
        expected_aligned_subject_area = 'Total'
        and score >= expected_board_890_plus_min_score,
        1,
        0
    ) as met_min_board_890_plus_score_int,

    if(
        expected_aligned_subject_area = 'Total'
        and score >= expected_board_1010_plus_min_score,
        1,
        0
    ) as met_min_board_1010_plus_score_int,

    if(
        expected_aligned_subject_area = 'EBRW'
        and score >= expected_board_450_plus_min_score,
        1,
        0
    ) as met_min_board_450_plus_min_score,

    if(
        expected_aligned_subject_area = 'Math'
        and score >= expected_board_440_plus_min_score,
        1,
        0
    ) as met_min_board_440_plus_min_score,

from roster
