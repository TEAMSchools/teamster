{% set comparison_benchmarks = [
    {"label": "College-Ready", "prefix": "college_ready"},
    {"label": "HS-Ready", "prefix": "hs_ready"},
] %}

{% set comparison_board_goals = [
    {"label": "% 16+", "prefix": "pct_16_plus"},
    {"label": "% 880+", "prefix": "pct_880_plus"},
    {"label": "% 17+", "prefix": "pct_17_plus"},
    {"label": "% 890+", "prefix": "pct_890_plus"},
    {"label": "% 21+", "prefix": "pct_21_plus"},
    {"label": "% 1010+", "prefix": "pct_1010_plus"},
] %}

with
    benchmark_goals as (
        select
            expected_test_type,
            expected_scope,
            expected_subject_area,

            {% for benchmark in comparison_benchmarks %}
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then score end
                ) as {{ benchmark.prefix }}_score,
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then goal end
                ) as {{ benchmark.prefix }}_goal
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where
            expected_test_type = 'Official'
            and goal_type = 'Benchmark'
            and expected_subject_area in ('Composite', 'Combined')
        group by expected_test_type, expected_scope, expected_subject_area
    ),

    board_goals as (
        select
            expected_test_type,
            expected_scope,
            expected_subject_area,
            grade_level,

            {% for board_goal in comparison_board_goals %}
                avg(
                    case when goal_category = '{{ board_goal.label }}' then score end
                ) as {{ board_goal.prefix }}_score,
                avg(
                    case when goal_category = '{{ board_goal.label }}' then goal end
                ) as {{ board_goal.prefix }}_goal
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where
            expected_test_type = 'Official'
            and goal_type = 'Board'
            and expected_subject_area in ('Composite', 'Combined')
        group by expected_test_type, expected_scope, expected_subject_area, grade_level
    ),

    scores as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,
            e.studentid,
            e.students_dcid,
            e.salesforce_id,
            e.grade_level,

            a.administration_round,
            a.test_type,
            a.test_date,
            a.test_month,
            a.scope,
            a.subject_area,
            a.course_discipline,
            a.score_type,
            a.scale_score,
            a.previous_total_score_change,
            a.rn_highest,
            a.max_scale_score,
            a.superscore,

            bg.hs_ready_score as hs_ready_min_score,
            bg.college_ready_score as college_ready_min_score,
            bg.hs_ready_goal,
            bg.college_ready_goal,

            case
                a.scope
                when 'ACT'
                then bd.pct_16_plus_score
                when 'SAT'
                then bd.pct_880_plus_score
            end as pct_16_880_min_score,

            case
                a.scope
                when 'ACT'
                then bd.pct_17_plus_score
                when 'SAT'
                then bd.pct_890_plus_score
            end as pct_17_890_min_score,

            case
                a.scope
                when 'ACT'
                then bd.pct_21_plus_score
                when 'SAT'
                then bd.pct_1010_plus_score
            end as pct_21_1010_min_score,

            case
                a.scope
                when 'ACT'
                then bd.pct_16_plus_goal
                when 'SAT'
                then bd.pct_880_plus_goal
            end as pct_16_880_goal,

            case
                a.scope
                when 'ACT'
                then bd.pct_17_plus_goal
                when 'SAT'
                then bd.pct_890_plus_goal
            end as pct_17_890_goal,

            case
                a.scope
                when 'ACT'
                then bd.pct_21_plus_goal
                when 'SAT'
                then bd.pct_1010_plus_goal
            end as pct_21_1010_goal,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_assessments__college_assessment") }} as a
            on e.academic_year = a.academic_year
            and e.student_number = a.student_number
            and a.score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
        left join
            benchmark_goals as bg
            on a.test_type = bg.expected_test_type
            and a.scope = bg.expected_scope
            and a.subject_area = bg.expected_subject_area
        left join
            board_goals as bd
            on a.test_type = bd.expected_test_type
            and a.scope = bd.expected_scope
            and a.subject_area = bd.expected_subject_area
            and e.grade_level = bd.grade_level
        where e.school_level = 'HS' and e.rn_year = 1
    ),

    running_max_score as (
        select
            student_number,
            academic_year,
            scope,
            score_type,
            test_date,

            max(scale_score) over (
                partition by student_number, score_type order by test_date
            ) as running_max_scale_score,

        from scores
        where test_date is not null
    ),

    dedup_running_max_score as (
        {{
            dbt_utils.deduplicate(
                relation="running_max_score",
                partition_by="student_number,score_type,test_date",
                order_by="student_number",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03)
    running_superscore as (
        select
            student_number,
            scope,
            test_date,

            round(
                if(
                    scope = 'ACT',
                    avg(running_max_scale_score) over (
                        partition by student_number, test_date
                    ),
                    sum(running_max_scale_score) over (
                        partition by student_number, test_date
                    )
                ),
                0
            ) as runnning_superscore,

        from running_max_score
        where
            score_type not in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psat10_total',
                'psatnmsqt_total'
            )
    ),

    dedup_runnning_superscore as (
        {{
            dbt_utils.deduplicate(
                relation="running_superscore",
                partition_by="student_number,scope,test_date",
                order_by="student_number",
            )
        }}
    )

select
    s.*,

    dm.running_max_scale_score,

    coalesce(dr.runnning_superscore, s.superscore) as running_superscore,

from scores as s
left join
    dedup_running_max_score as dm
    on s.student_number = dm.student_number
    and s.test_date = dm.test_date
    and s.score_type = dm.score_type
left join
    dedup_runnning_superscore as dr
    on s.student_number = dr.student_number
    and s.scope = dr.scope
    and s.test_date = dr.test_date
