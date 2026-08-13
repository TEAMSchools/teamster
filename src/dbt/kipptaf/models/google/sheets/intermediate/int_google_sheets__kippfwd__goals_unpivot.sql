with
    scaffold_unpivot as (
        select
            academic_year,
            expected_test_type,
            expected_scope,
            expected_aligned_scope,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_score_type,
            expected_min_score,

            trim(expected_grade_level_item) as expected_grade_level,

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

        from
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} unpivot (
                expected_min_score for expected_min_score_type in (
                    a1_attempt_min_score,
                    a2_plus_attempts_min_score,
                    hs_ready_min_score,
                    college_ready_min_score
                )
            )
        cross join unnest(split(expected_grade_level, ',')) as expected_grade_level_item
    ),

    goals as (
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
            s.expected_min_score,

            regexp_replace(g.expected_metric_type, r'^pct_', '') as metric_stem,

            case
                s.expected_scope
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

        from {{ ref("stg_google_sheets__kippfwd__goals") }} as g
        left join
            scaffold_unpivot as s
            on g.academic_year = s.academic_year
            and g.test_type = s.expected_test_type
            and g.score_type = s.expected_score_type
            and g.grade_level = s.expected_grade_level
            and g.expected_metric_type = s.expected_metric_type
    )

select
    * except (metric_stem, scope_stem),

    concat(scope_stem, '_', metric_stem) as expected_metric_label,

from goals
