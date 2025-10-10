with
    strategy as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            a.academic_year as expected_test_academic_year,
            a.test_type as expected_test_type,
            a.test_date as expected_test_date,
            a.test_month as expected_test_month,
            a.scope as expected_scope,
            a.subject_area as expected_subject_area,
            a.score_type as expected_score_type,

<<<<<<< HEAD
            e.grade_level as expected_grade_level,

        from {{ ref("int_assessments__college_assessment") }} as a
=======
            {% for benchmark in comparison_benchmarks %}
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then min_score end
                ) as {{ benchmark.prefix }}_score,
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then pct_goal end
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
                    case
                        when goal_category = '{{ board_goal.label }}' then min_score
                    end
                ) as {{ board_goal.prefix }}_score,
                avg(
                    case when goal_category = '{{ board_goal.label }}' then pct_goal end
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
>>>>>>> 72ea9304abd0b3f263b80b4f49c76b580b7064dc
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            a.score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    crosswalk as (
        select
            expected_test_academic_year,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            expected_grade_level,
            expected_test_date,
            expected_test_month,

            concat(
                'G', expected_grade_level, ' ', left(expected_test_month, 3)
            ) as expected_test_admin_for_over_time,

            concat(
                'G',
                expected_grade_level,
                ' ',
                expected_test_month,
                ' ',
                expected_scope,
                ' ',
                expected_test_type,
                ' ',
                expected_subject_area
            ) as expected_field_name,

            case
                expected_scope
                when 'ACT'
                then 1
                when 'SAT'
                then 2
                when 'PSAT NMSQT'
                then 3
                when 'PSAT10'
                then 4
                when 'PSAT 8/9'
                then 5
            end as expected_scope_order,

            case
                when expected_subject_area in ('Combined', 'Composite')
                then 1
                when expected_score_type = 'act_reading'
                then 2
                when expected_score_type = 'act_math'
                then 3
                when expected_score_type = 'act_english'
                then 4
                when expected_score_type = 'act_science'
                then 5
                when expected_subject_area = 'EBRW'
                then 2
                when expected_subject_area = 'Math'
                then 3
            end as expected_subject_area_order,

            if(
                extract(month from expected_test_date) >= 8,
                extract(month from expected_test_date) - 7,
                extract(month from expected_test_date) + 5
            ) as expected_month_order,

        from strategy
    ),

    additional_fields as (
        select
            *,

            concat(
                expected_scope_order,
                '_',
                expected_subject_area_order,
                '_',
                expected_month_order
            ) as expected_admin_order,

            lower(
                concat(
                    'G',
                    expected_grade_level,
                    '_',
                    expected_month_order,
                    '_',
                    expected_test_type,
                    '_',
                    expected_scope_order,
                    '_',
                    expected_subject_area_order
                )
            ) as expected_filter_group_month,

        from crosswalk
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.state,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.students_dcid,
    e.studentid,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.iep_status,
    e.rn_undergrad,
    e.is_504,
    e.lep_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.gifted_and_talented,
    e.advisory,
    e.grad_iep_exempt_status_overall,
    e.contact_owner_name,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    a.expected_test_academic_year,
    a.expected_test_type,
    a.expected_scope,
    a.expected_score_type,
    a.expected_subject_area,
    a.expected_grade_level,
    a.expected_test_date,
    a.expected_test_month,
    a.expected_test_admin_for_over_time,
    a.expected_field_name,
    a.expected_scope_order,
    a.expected_subject_area_order,
    a.expected_month_order,
    a.expected_admin_order,
    a.expected_filter_group_month,

    s.test_type,
    s.test_date,
    s.test_month,
    s.scope,
    s.subject_area,
    s.course_discipline,
    s.score_type,
    s.scale_score,
    s.previous_total_score_change,
    s.rn_highest,
    s.max_scale_score,
    s.superscore,
    s.running_max_scale_score,
    s.running_superscore,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "a.expected_grade_level",
                "a.expected_test_type",
                "a.expected_score_type",
                "a.expected_test_date",
            ]
        )
    }} as surrogate_key,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    additional_fields as a
    on e.academic_year = a.expected_test_academic_year
    and e.grade_level = a.expected_grade_level
left join
    {{ ref("int_assessments__college_assessment") }} as s
    on a.expected_test_academic_year = s.academic_year
    and a.expected_score_type = s.score_type
    and a.expected_test_date = s.test_date
    and e.student_number = s.student_number
where e.school_level = 'HS' and e.rn_year = 1
