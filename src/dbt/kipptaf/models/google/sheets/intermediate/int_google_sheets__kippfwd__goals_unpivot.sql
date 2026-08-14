with
    scaffold_unpivot as (
        select
            academic_year,
            expected_test_type,
            expected_grade_level,
            expected_grouping,
            expected_scope,
            expected_aligned_scope,
            expected_subject_area,
            expected_score_type,
            expected_min_score,

            expected_aligned_subject_area as expected_aligned_subject,

            if(
                expected_subject_area in ('Combined', 'Composite'),
                'Total',
                expected_subject_area
            ) as expected_aligned_subject_area,

            case
                expected_min_score_type
                when 'a1_attempt_min_score'
                then 'pct_1_attempt'
                when 'a2_plus_attempts_min_score'
                then 'pct_2_plus_attempts'
                when 'hs_ready_min_score'
                then 'pct_hs_ready'
                when 'college_ready_min_score'
                then 'pct_college_ready'
            end as expected_metric_type,

            case
                expected_min_score_type
                when 'a1_attempt_min_score'
                then '1 Attempt'
                when 'a2_plus_attempts_min_score'
                then '2+ Attempts'
                when 'hs_ready_min_score'
                then 'HS-Ready'
                when 'college_ready_min_score'
                then 'College-Ready'
            end as expected_goal_subtype,

            case
                when
                    expected_min_score_type
                    in ('a1_attempt_min_score', 'a2_plus_attempts_min_score')
                then 'Attempts'
                else 'Benchmark'
            end as expected_goal_type,

            case
                expected_scope
                when 'SAT'
                then 'sat'
                when 'ACT'
                then 'act'
                when 'PSAT 8/9'
                then 'psat89'
                when 'PSAT10'
                then 'psat10'
                when 'PSAT NMSQT'
                then 'psatnmsqt'
            end as scope_stem,

        from
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} unpivot (
                expected_min_score for expected_min_score_type in (
                    a1_attempt_min_score,
                    a2_plus_attempts_min_score,
                    hs_ready_min_score,
                    college_ready_min_score
                )
            )
    ),

    scaffold_by_grade as (
        select
            * except (expected_grade_level),

            trim(expected_grade_level_item) as expected_grade_level,

        from scaffold_unpivot
        cross join unnest(split(expected_grade_level, ',')) as expected_grade_level_item
    ),

    goals_all_grades as (
        select
            academic_year,
            test_type,
            score_type,
            expected_metric_type,

            /* The over time goal where the sheet states one, else the per-grade
               goal, which is unambiguous for the score types stated at a single
               grade. test_kippfwd_goals_over_time_collapse guards the fallback. */
            coalesce(
                min(if(is_over_time_goal, expected_metric_goal, null)),
                min(expected_metric_goal)
            ) as expected_metric_goal,

        from {{ ref("stg_google_sheets__kippfwd__goals") }}
        group by academic_year, test_type, score_type, expected_metric_type
    ),

    goals_by_grade as (
        select
            g.academic_year,
            g.test_type,
            g.grade_level,
            g.cohort,
            g.score_type,
            g.expected_metric_type,
            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_goal,

            s.expected_scope,
            s.expected_aligned_scope,
            s.expected_subject_area,
            s.expected_aligned_subject_area,
            s.expected_aligned_subject,
            s.expected_min_score,
            s.scope_stem,

            [
                'rpt_tableau__college_assessment_dashboard_roster',
                'rpt_tableau__college_assessment_dashboard_current',
                'rpt_gsheets__college_assessments_wide'
            ] as rpt_consumers,

            regexp_replace(g.expected_metric_type, r'^pct_', '') as metric_stem,

        from {{ ref("stg_google_sheets__kippfwd__goals") }} as g
        left join
            scaffold_by_grade as s
            on g.academic_year = s.academic_year
            and g.test_type = s.expected_test_type
            and g.score_type = s.expected_score_type
            and g.grade_level = s.expected_grade_level
            and g.expected_metric_type = s.expected_metric_type
        where not g.is_over_time_goal
    ),

    goals_over_time as (
        select
            s.academic_year,
            s.expected_test_type as test_type,
            s.expected_score_type as score_type,
            s.expected_metric_type,
            s.expected_goal_type,
            s.expected_goal_subtype,
            s.expected_scope,
            s.expected_aligned_scope,
            s.expected_subject_area,
            s.expected_aligned_subject_area,
            s.expected_aligned_subject,
            s.expected_min_score,
            s.scope_stem,

            g.expected_metric_goal,

            cast(null as string) as grade_level,
            cast(null as string) as cohort,

            ['rpt_tableau__college_assessment_dashboard_over_time'] as rpt_consumers,

            regexp_replace(s.expected_metric_type, r'^pct_', '') as metric_stem,

        from scaffold_unpivot as s
        left join
            goals_all_grades as g
            on s.academic_year = g.academic_year
            and s.expected_test_type = g.test_type
            and s.expected_score_type = g.score_type
            and s.expected_metric_type = g.expected_metric_type
        where
            s.expected_grouping != 'Growth'
            and (
                s.expected_goal_type = 'Benchmark'
                or s.expected_aligned_subject_area = 'Total'
            )
    ),

    all_goals as (
        select
            academic_year,
            test_type,
            grade_level,
            cohort,
            score_type,
            expected_metric_type,
            expected_goal_type,
            expected_goal_subtype,
            expected_metric_goal,
            expected_scope,
            expected_aligned_scope,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_aligned_subject,
            expected_min_score,
            rpt_consumers,
            scope_stem,
            metric_stem,

        from goals_by_grade

        union all

        select
            academic_year,
            test_type,
            grade_level,
            cohort,
            score_type,
            expected_metric_type,
            expected_goal_type,
            expected_goal_subtype,
            expected_metric_goal,
            expected_scope,
            expected_aligned_scope,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_aligned_subject,
            expected_min_score,
            rpt_consumers,
            scope_stem,
            metric_stem,

        from goals_over_time
    )

select
    * except (metric_stem, scope_stem),

    concat(scope_stem, '_', metric_stem) as expected_metric_label,

    if(
        expected_goal_type = 'Attempts',
        concat(expected_scope, ' ', expected_goal_subtype),
        expected_goal_subtype
    ) as expected_metric_name,

from all_goals
