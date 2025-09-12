{% set comparison_completion = [
    {"label": "ACT Group 1", "prefix": "act_group_1"},
    {"label": "ACT Group 2+", "prefix": "act_group_2_plus"},
    {"label": "SAT Group 1", "prefix": "sat_group_1"},
    {"label": "SAT Group 2+", "prefix": "sat_group_2_plus"},
    {"label": "PSAT 8/9 Group 1", "prefix": "psat89_group_1"},
    {"label": "PSAT 8/9 Group 2+", "prefix": "psat89_group_2_plus"},
    {"label": "PSAT10 Group 1", "prefix": "psat10_group_1"},
    {"label": "PSAT10 Group 2+", "prefix": "psat10_group_2_plus"},
    {"label": "PSAT NMSQT Group 1", "prefix": "psatnmsqt_group_1"},
    {"label": "PSAT NMSQT Group 2+", "prefix": "psatnmsqt_group_2_plus"},
] %}

with
    completion_goals as (
        select
            expected_test_type,
            'join' as fake_key,

            {% for completion in comparison_completion %}
                avg(
                    case
                        when
                            concat(expected_scope, ' ', goal_category)
                            = '{{ completion.label }}'
                        then score
                    end
                ) as {{ completion.prefix }}_score,
                avg(
                    case
                        when
                            concat(expected_scope, ' ', goal_category)
                            = '{{ completion.label }}'
                        then goal
                    end
                ) as {{ completion.prefix }}_goal
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where
            expected_test_type = 'Official'
            and goal_type = 'Attempts'
            and expected_subject_area in ('Composite', 'Combined')
        group by expected_test_type
    ),

    base_rows as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level,
            test_type,
            scope,
            score_type,

        from {{ ref("int_students__college_assessment_roster") }}
        where
            score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psatnmsqt_total',
                'psat10_total'
            )
    ),

    yearly_tests as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level,

            psat89_count,
            psat10_count,
            psatnmsqt_count,
            sat_count,
            act_count,

        from
            base_rows pivot (
                count(score_type) for scope in (
                    'PSAT 8/9' as psat89_count,
                    'PSAT10' as psat10_count,
                    'PSAT NMSQT' as psatnmsqt_count,
                    'SAT' as sat_count,
                    'ACT' as act_count
                )
            )
    ),

    yearly_test_counts as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level,
            'join' as fake_key,

            sum(psat89_count) as psat89_count,
            sum(psat10_count) as psat10_count,
            sum(psatnmsqt_count) as psatnmsqt_count,
            sum(sat_count) as sat_count,
            sum(act_count) as act_count,

        from yearly_tests
        group by
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level
    )

select
    y.* except (fake_key),

    c.act_group_1_score,
    c.act_group_1_goal,
    c.act_group_2_plus_score,
    c.act_group_2_plus_goal,
    c.sat_group_1_score,
    c.sat_group_1_goal,
    c.sat_group_2_plus_score,
    c.sat_group_2_plus_goal,
    c.psat89_group_1_score,
    c.psat89_group_1_goal,
    c.psat89_group_2_plus_score,
    c.psat89_group_2_plus_goal,
    c.psat10_group_1_score,
    c.psat10_group_1_goal,
    c.psat10_group_2_plus_score,
    c.psat10_group_2_plus_goal,
    c.psatnmsqt_group_1_score,
    c.psatnmsqt_group_1_goal,
    c.psatnmsqt_group_2_plus_score,
    c.psatnmsqt_group_2_plus_goal,

    sum(y.psat89_count) over (
        partition by y.student_number order by y.grade_level
    ) as psat89_count_ytd,

    sum(y.psat10_count) over (
        partition by y.student_number order by y.grade_level
    ) as psat10_count_ytd,

    sum(y.psatnmsqt_count) over (
        partition by y.student_number order by y.grade_level
    ) as psatnmsqt_count_ytd,

    sum(y.sat_count) over (
        partition by y.student_number order by y.grade_level
    ) as sat_count_ytd,

    sum(y.act_count) over (
        partition by y.student_number order by y.grade_level
    ) as act_count_ytd,

from yearly_test_counts as y
left join completion_goals as c on y.fake_key = c.fake_key
