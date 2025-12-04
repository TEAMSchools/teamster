with
    calcs as (
        select
            region,
            schoolid,
            grade_level,
            cohort,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            goal_type as expected_goal_type,
            pct_goal,

            safe_cast(min_score as float64) as min_score,

            case
                when goal_type = 'Attempts'
                then concat(expected_scope, ' ', goal_category)
                when goal_type = 'Board'
                then
                    concat(
                        goal_category,
                        ' ',
                        expected_scope,
                        ' ',
                        expected_subject_area,
                        ' Grade ',
                        grade_level
                    )
                else goal_subtype
            end as expected_metric_name,

            case
                when goal_type = 'Attempts'
                then goal_category
                when goal_type = 'Board'
                then
                    concat(
                        goal_category,
                        ' ',
                        expected_scope,
                        ' ',
                        expected_subject_area,
                        ' Grade ',
                        grade_level
                    )
                else goal_subtype
            end as expected_goal_subtype,

            case
                when expected_scope in ('ACT', 'SAT')
                then 'ACT/SAT'
                when expected_scope in ('PSAT10', 'PSAT NMSQT')
                then 'PSAT10/NMSQT'
                else expected_scope
            end as expected_aligned_scope,

            if(
                expected_subject_area in ('Composite', 'Combined'),
                'Total',
                expected_subject_area
            ) as expected_aligned_subject_area,

        from {{ source("google_sheets", "src_google_sheets__kippfwd_goals") }}
    )

select
    *,

    case
        expected_metric_name
        when 'ACT 1 Attempt'
        then 'act_1_attempt'
        when 'ACT 2+ Attempts'
        then 'act_2_plus_attempts'
        when 'SAT 1 Attempt'
        then 'sat_1_attempt'
        when 'SAT 2+ Attempts'
        then 'sat_2_plus_attempts'
        when 'PSAT 8/9 1 Attempt'
        then 'psat89_1_attempt'
        when 'PSAT 8/9 2+ Attempts'
        then 'psat89_2_plus_attempts'
        when 'PSAT10 1 Attempt'
        then 'psat10_1_attempt'
        when 'PSAT10 2+ Attempts'
        then 'psat10_2_plus_attempts'
        when 'PSAT NMSQT 1 Attempt'
        then 'psatnmsqt_1_attempt'
        when 'PSAT NMSQT 2+ Attempts'
        then 'psatnmsqt_2_plus_attempts'
        when '% 890+ SAT Combined Grade 11'
        then 'sat_combined_pct_890_plus_g11'
        when '% 890+ SAT Combined Grade 12'
        then 'sat_combined_pct_890_plus_g12'
        when '% 1010+ SAT Combined Grade 11'
        then 'sat_combined_pct_1010_plus_g11'
        when '% 1010+ SAT Combined Grade 12'
        then 'sat_combined_pct_1010_plus_g12'
        when '% 450+ SAT EBRW Grade 11'
        then 'sat_ebrw_pct_450_plus_g11'
        when '% 450+ SAT EBRW Grade 12'
        then 'sat_ebrw_pct_450_plus_g12'
        when '% 440+ SAT Math Grade 11'
        then 'sat_math_pct_440_plus_g11'
        when '% 440+ SAT Math Grade 12'
        then 'sat_math_pct_440_plus_g12'
    end as expected_metric_label,

    case
        when
            expected_score_type in (
                'act_reading',
                'sat_ebrw',
                'psat10_ebrw',
                'psatnmsqt_ebrw',
                'psat89_ebrw'
            )
        then 'EBRW/Reading'
        when expected_aligned_subject_area = 'Total'
        then 'Total'
        else expected_subject_area
    end as expected_aligned_subject,

from calcs
