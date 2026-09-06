with
    terms as (
        select
            academic_year,
            region,
            code,
            name,
            start_date,
            end_date,

            safe_cast(band_grade as int64) as grade_level,

        from {{ ref("stg_google_sheets__reporting__terms") }}
        -- left, not cross: a Benchmark row's grade_band is null, and unnesting
        -- null yields no rows, which would drop the row entirely
        left join unnest(split(grade_band, ',')) as band_grade
        where type = 'LIT'
    ),

    expected as (
        select
            academic_year,
            region,
            grade,
            test_type,
            discipline,
            subject_area,
            measure_standard,
            test_code,
            admin_season,
            month_round,
            illuminate_subject,
            iready_subject,
            ps_credit_type,
            assessment_include,
            pm_goal_include,
            pm_goal_criteria,
            assessment_type,
            matching_pm_season,
            expected_measure_name_code,
            expected_measure_name,
            expected_measure_standard,
            grade_level_text,
            round_number,

            'internal' as data_model,

            -- the 16-column source predates the cohort split and tests one
            -- measure set for everyone
            cast(null as string) as measure_standard_level,

        from {{ ref("stg_google_sheets__dibels_expected_assessments") }}

        union all

        select
            academic_year,
            region,
            grade,
            test_type,
            discipline,
            subject_area,
            measure_standard,
            test_code,
            admin_season,
            month_round,
            illuminate_subject,
            iready_subject,
            ps_credit_type,
            assessment_include,
            pm_goal_include,
            pm_goal_criteria,
            assessment_type,
            matching_pm_season,
            expected_measure_name_code,
            expected_measure_name,
            expected_measure_standard,
            grade_level_text,
            round_number,

            'aimline' as data_model,

            measure_standard_level,

        from {{ ref("stg_google_sheets__dibels_expected_assessments_by_levels") }}
    )

select
    e.data_model,
    e.academic_year,
    e.region,
    e.grade,
    e.test_type,
    e.discipline,
    e.subject_area,
    e.measure_standard,
    e.measure_standard_level,
    e.test_code,
    e.admin_season,
    e.month_round,
    e.illuminate_subject,
    e.iready_subject,
    e.ps_credit_type,
    e.assessment_include,
    e.pm_goal_include,
    e.pm_goal_criteria,
    e.assessment_type,
    e.matching_pm_season,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,
    e.grade_level_text,
    e.round_number,

    t.start_date,
    t.end_date,

    min(e.round_number) over (
        partition by e.data_model, e.academic_year, e.region, e.admin_season, e.grade
        order by e.round_number
    ) as min_pm_round,

    max(e.round_number) over (
        partition by e.data_model, e.academic_year, e.region, e.admin_season, e.grade
        order by e.round_number desc
    ) as max_pm_round,

from expected as e
left join
    terms as t
    on e.academic_year = t.academic_year
    and e.region = t.region
    and e.admin_season = t.name
    and e.test_code = t.code
    -- a null grade_level is a Benchmark window, which applies to every grade
    and (e.grade = t.grade_level or t.grade_level is null)
-- the sheet's soft delete. Still projected above so the downstream predicates
-- that pre-date this filter stay valid; they are no-ops now.
where e.assessment_include is null
