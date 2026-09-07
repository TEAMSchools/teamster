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
    )

select
    m.academic_year,
    m.region,
    m.grade,
    m.test_type,
    m.discipline,
    m.subject_area,
    m.measure_standard,
    m.test_code,
    m.admin_season,
    m.month_round,
    m.illuminate_subject,
    m.iready_subject,
    m.ps_credit_type,
    m.assessment_include,
    m.pm_goal_include,
    m.pm_goal_criteria,
    m.assessment_type,
    m.matching_pm_season,
    m.expected_measure_name_code,
    m.expected_measure_name,
    m.expected_measure_standard,
    m.grade_level_text,
    m.round_number,

    t.start_date,
    t.end_date,

    min(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number
    ) as min_pm_round,

    max(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number desc
    ) as max_pm_round,

from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as m
left join
    terms as t
    on m.academic_year = t.academic_year
    and m.region = t.region
    and m.admin_season = t.name
    and m.test_code = t.code
    -- a null grade_level is a Benchmark window, which applies to every grade
    and (m.grade = t.grade_level or t.grade_level is null)
