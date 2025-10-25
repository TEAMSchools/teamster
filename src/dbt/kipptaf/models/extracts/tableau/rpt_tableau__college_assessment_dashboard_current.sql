<<<<<<< HEAD
with
    strategy as (
        -- need a distinct strategy scaffold
=======
{% set metrics = [
    "sat_combined_pct_890_plus_g11",
    "sat_combined_pct_1010_plus_g11",
    "sat_combined_pct_890_plus_g12",
    "sat_combined_pct_1010_plus_g12",
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
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
        select distinct
            s.test_type as expected_test_type,
            s.scope as expected_scope,
            s.subject_area as expected_subject_area,
            s.score_type as expected_score_type,

<<<<<<< HEAD
            g.expected_metric_name,
            g.min_score as expected_metric_min_score,
            g.pct_goal as expected_metric_pct_goal,

            'foo' as bar,
=======
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
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
<<<<<<< HEAD
            on s.scope = g.expected_scope
            and s.score_type = g.expected_score_type
            and g.expected_goal_type != 'Board'
        where s.test_type = 'Official' and s.subject_area in ('Composite', 'Combined')
    ),

    max_attempts as (
        select
            student_number,

            max(psat89_count_ytd) as psat89_count_ytd,
            max(psat10_count_ytd) as psat10_count_ytd,
            max(psatnmsqt_count_ytd) as psatnmsqt_count_ytd,
            max(sat_count_ytd) as sat_count_ytd,
            max(act_count_ytd) as act_count_ytd,

        from {{ ref("int_students__college_assessment_participation_roster") }}
        group by student_number
=======
            on s.score_type = g.expected_score_type
            and g.expected_goal_type != 'Board'
        left join board_goals as b on s.score_type = b.expected_score_type
        where s.subject_area = 'Combined'
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
    ),

    attempts as (
        select
            student_number,

<<<<<<< HEAD
            attempt_count_ytd,

            case
                scope
                when 'act_count_ytd'
                then 'ACT'
                when 'sat_count_ytd'
                then 'SAT'
                when 'psatnmsqt_count_ytd'
                then 'PSAT NMSQT'
                when 'psat10_count_ytd'
                then 'PSAT10'
                when 'psat89_count_ytd'
=======
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
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
                then 'PSAT 8/9'
            end as scope,

        from
<<<<<<< HEAD
            max_attempts unpivot (
                attempt_count_ytd for scope in (
                    psat89_count_ytd,
                    psat10_count_ytd,
                    psatnmsqt_count_ytd,
                    sat_count_ytd,
                    act_count_ytd
                )
            )
=======
            {{ ref("int_students__college_assessment_participation_roster") }} unpivot (
                attempt_count_lifetime for scope in (
                    psat89_count_lifetime,
                    psat10_count_lifetime,
                    psatnmsqt_count_lifetime,
                    sat_count_lifetime
                )
            )
        where rn_lifetime = 1
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
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
            e.graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
<<<<<<< HEAD
            r.expected_metric_name,
=======
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,

            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,

<<<<<<< HEAD
=======
            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_sat_combined_pct_890_plus_g11_board_min_score
                    when 12
                    then r.expected_sat_combined_pct_890_plus_g12_board_min_score
                end
            ) as expected_board_890_plus_min_score,

            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_sat_combined_pct_1010_plus_g11_board_min_score
                    when 12
                    then r.expected_sat_combined_pct_1010_plus_g12_board_min_score
                end
            ) as expected_board_1010_plus_min_score,

            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_sat_combined_pct_890_plus_g11_board_pct_goal
                    when 12
                    then r.expected_sat_combined_pct_890_plus_g12_board_pct_goal
                end
            ) as expected_board_890_plus_pct_goal,

            min(
                case
                    e.grade_level
                    when 11
                    then r.expected_sat_combined_pct_1010_plus_g11_board_pct_goal
                    when 12
                    then r.expected_sat_combined_pct_1010_plus_g12_board_pct_goal
                end
            ) as expected_board_1010_plus_pct_goal,

>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
            avg(
                if(
                    r.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    s.max_scale_score,
<<<<<<< HEAD
                    p.attempt_count_ytd
=======
                    p.attempt_count_lifetime
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
<<<<<<< HEAD
        inner join strategy as r on 'foo' = r.bar
=======
        cross join strategy as r
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
        left join
            {{ ref("int_assessments__college_assessment") }} as s
            on e.student_number = s.student_number
            and r.expected_scope = s.scope
<<<<<<< HEAD
            and s.test_type = 'Official'
            and s.subject_area in ('Composite', 'Combined')
=======
            and s.subject_area = 'Combined'
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
        left join
            attempts as p
            on e.student_number = p.student_number
            and r.expected_scope = p.scope
<<<<<<< HEAD
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
=======
        where e.academic_year = 2025 and e.school_level = 'HS' and e.rn_year = 1
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
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
            e.graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,
            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
<<<<<<< HEAD
            r.expected_metric_name,
=======
            r.expected_goal_type,
            r.expected_goal_subtype,
            r.expected_metric_name,
            r.expected_metric_label,
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f
            r.expected_metric_min_score,
            r.expected_metric_pct_goal,
            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type
    )

<<<<<<< HEAD
select *, if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,
=======
select
    *,

    if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,

    if(
        score >= expected_board_890_plus_min_score, 1, 0
    ) as met_min_board_890_plus_score_int,
    if(
        score >= expected_board_1010_plus_min_score, 1, 0
    ) as met_min_board_1010_plus_score_int,
>>>>>>> 57fb86f66a23a507ac0a8e05615cb5535363961f

from roster
