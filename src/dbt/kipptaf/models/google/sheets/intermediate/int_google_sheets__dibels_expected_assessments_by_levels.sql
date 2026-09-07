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
        cross join unnest(split(grade_band, ',')) as band_grade
        where type = 'LIT'
    )

select
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
        partition by
            e.academic_year, e.region, e.admin_season, e.grade, e.measure_standard_level
        order by e.round_number
    ) as min_pm_round,

    max(e.round_number) over (
        partition by
            e.academic_year, e.region, e.admin_season, e.grade, e.measure_standard_level
        order by e.round_number desc
    ) as max_pm_round,

from {{ ref("stg_google_sheets__dibels_expected_assessments_by_levels") }} as e
left join
    terms as t
    on e.academic_year = t.academic_year
    and e.region = t.region
    and e.admin_season = t.name
    and e.test_code = t.code
    and e.grade = t.grade_level
