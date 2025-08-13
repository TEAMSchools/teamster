with
    modified as (
        select
            *,

            if(
                admin_season in ('BOY', 'MOY', 'EOY'), 'Benchmark', 'PM'
            ) as assessment_type,

            case
                admin_season when 'BOY' then 'BOY->MOY' when 'MOY' then 'MOY->EOY'
            end as matching_pm_season,

            regexp_extract(measure_standard, r'^[^_]*') as expected_measure_name_code,

            regexp_substr(measure_standard, r'_(.*?)_') as expected_measure_name,

            regexp_substr(measure_standard, r'[^_]+$') as expected_measure_standard,

            if(grade = 0, 'K', safe_cast(grade as string)) as grade_level_text,

            safe_cast(right(test_code, 1) as int64) as round_number,

        from
            {{
                source(
                    "google_sheets", "src_google_sheets__dibels_expected_assessments"
                )
            }}
    )

select
    m.*,

    min(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number
    ) as min_pm_round,

    max(m.round_number) over (
        partition by m.academic_year, m.region, m.admin_season, m.grade
        order by m.round_number desc
    ) as max_pm_round,

    t.start_date,
    t.end_date,

from modified as m
left join
    {{ ref("stg_reporting__terms") }} as t
    on m.academic_year = t.academic_year
    and m.region = t.region
    and m.admin_season = t.name
    and m.test_code = t.code
    and t.type = 'LIT'
